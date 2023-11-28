import hashlib
from datetime import date

import pytest
import sqlalchemy

from ehrql import create_dataset
from ehrql.backends.tpp import TPPBackend
from ehrql.query_engines.mssql_dialect import SelectStarInto
from ehrql.query_language import compile, get_tables_from_namespace
from ehrql.tables.beta import tpp
from ehrql.tables.beta.raw import tpp as tpp_raw
from tests.lib.tpp_schema import (
    APCS,
    EC,
    OPA,
    APCS_Cost,
    APCS_Cost_JRC20231009_LastFilesToContainAllHistoricalCostData,
    APCS_Der,
    APCS_JRC20231009_LastFilesToContainAllHistoricalCostData,
    Appointment,
    CodedEvent,
    CodedEvent_SNOMED,
    CustomMedicationDictionary,
    EC_Cost,
    EC_Diagnosis,
    HealthCareWorker,
    Household,
    HouseholdMember,
    ISARIC_New,
    MedicationDictionary,
    MedicationIssue,
    ONS_Deaths,
    OPA_Cost,
    OPA_Diag,
    OPA_Proc,
    OpenPROMPT,
    Organisation,
    Patient,
    PatientAddress,
    PatientsWithTypeOneDissent,
    PotentialCareHomeAddress,
    RegistrationHistory,
    SGSS_AllTests_Negative,
    SGSS_AllTests_Positive,
    Vaccination,
    VaccinationReference,
    WL_ClockStops,
    WL_OpenPathways,
)


REGISTERED_TABLES = set()


# This slightly odd way of supplying the table object to the test function makes the
# tests introspectable in such a way that we can confirm that every table in the module
# is covered by a test
def register_test_for(table):
    def annotate_test_function(fn):
        REGISTERED_TABLES.add(table)
        fn._table = table
        return fn

    return annotate_test_function


@pytest.fixture
def select_all(request, mssql_database):
    try:
        ql_table = request.function._table
    except AttributeError:  # pragma: no cover
        raise RuntimeError(
            f"Function '{request.function.__name__}' needs the "
            f"`@register_test_for(table)` decorator applied"
        )

    qm_table = ql_table._qm_node
    backend = TPPBackend(config={"TEMP_DATABASE_NAME": "temp_tables"})
    sql_table = backend.get_table_expression(qm_table.name, qm_table.schema)
    columns = [
        # Using `type_coerce(..., None)` like this strips the type information from the
        # SQLAlchemy column meaning we get back the type that the column actually is in
        # database, not the type we've told SQLAlchemy it is.
        sqlalchemy.type_coerce(column, None).label(column.key)
        for column in sql_table.columns
    ]
    select_all_query = sqlalchemy.select(*columns)

    def _select_all(*input_data):
        mssql_database.setup(*input_data)
        with mssql_database.engine().connect() as connection:
            results = connection.execute(select_all_query)
            return [row._asdict() for row in results]

    return _select_all


def test_backend_columns_have_correct_types(mssql_database):
    columns_with_types = get_all_backend_columns_with_types(mssql_database)
    mismatched = [
        f"{table}.{column} expects {column_type!r} but got {column_args!r}"
        for table, column, column_type, column_args in columns_with_types
        if not types_compatible(column_type, column_args)
    ]
    nl = "\n"
    assert not mismatched, (
        f"Mismatch between columns returned by backend queries"
        f" queries and those expected:\n{nl.join(mismatched)}\n\n"
    )


def types_compatible(column_type, column_args):
    """
    Is this given SQLAlchemy type instance compatible with the supplied dictionary of
    column arguments?
    """
    # It seems we use this sometimes for the patient ID column where we don't care what
    # type it is
    if isinstance(column_type, sqlalchemy.sql.sqltypes.NullType):
        return True
    elif isinstance(column_type, sqlalchemy.Boolean):
        # MSSQL doesn't have a boolean type so we expect an int here
        return column_args["type"] == "int"
    elif isinstance(column_type, sqlalchemy.Integer):
        return column_args["type"] in ("int", "bigint")
    elif isinstance(column_type, sqlalchemy.Float):
        return column_args["type"] == "real"
    elif isinstance(column_type, sqlalchemy.Date):
        return column_args["type"] == "date"
    elif isinstance(column_type, sqlalchemy.String):
        return (
            column_args["type"] == "varchar"
            and column_args["collation"] == column_type.collation
        )
    else:
        assert False, f"Unhandled type: {column_type}"


def get_all_backend_columns_with_types(mssql_database):
    """
    For every column on every table we expose in the backend, yield the SQLAlchemy type
    instance we expect to use for that column together with the type information that
    database has for that column so we can check they're compatible
    """
    table_names = set()
    column_types = {}
    queries = []
    for table, columns in get_all_backend_columns():
        table_names.add(table)
        column_types.update({(table, c.key): c.type for c in columns})
        # Construct a query which selects every column in the table
        select_query = sqlalchemy.select(*[c.label(c.key) for c in columns])
        # Write the results of that query into a temporary table (it will be empty but
        # that's fine, we just want the types)
        temp_table = sqlalchemy.table(f"#{table}")
        queries.append(SelectStarInto(temp_table, select_query.alias()))
    # Create all the underlying tables in the database without populating them
    mssql_database.setup(metadata=Patient.metadata)
    with mssql_database.engine().connect() as connection:
        # Create our temporary tables
        for query in queries:
            connection.execute(query)
        # Get the column names, types and collations for all columns in those tables
        query = sqlalchemy.text(
            """
            SELECT
                -- MSSQL does some nasty name mangling involving underscores to make
                -- local temporary table names globally unique. We undo that here.
                SUBSTRING(t.name, 2, CHARINDEX('__________', t.name) - 2) AS [table],
                c.name AS [column],
                y.name AS [type_name],
                c.collation_name AS [collation]
            FROM
                tempdb.sys.columns c
            JOIN
                tempdb.sys.objects t ON t.object_id = c.object_id
            JOIN
                tempdb.sys.types y ON y.user_type_id = c.user_type_id
            WHERE
                t.type_desc = 'USER_TABLE'
                AND CHARINDEX('__________', t.name) > 0
            """
        )
        results = list(connection.execute(query))
    for table, column, type_name, collation in results:
        # Ignore any leftover cruft in the database
        if table not in table_names:  # pragma: no cover
            continue
        column_type = column_types[table, column]
        column_args = {"type": type_name, "collation": collation}
        yield table, column, column_type, column_args


def get_all_backend_columns():
    backend = TPPBackend(config={"TEMP_DATABASE_NAME": "temp_tables"})
    for _, table in get_all_tables():
        qm_table = table._qm_node
        table_expr = backend.get_table_expression(qm_table.name, qm_table.schema)
        yield qm_table.name, table_expr.columns


@register_test_for(tpp.addresses)
def test_addresses(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        PatientAddress(
            Patient_ID=1,
            PatientAddress_ID=2,
            StartDate="2000-01-01T10:10:00",
            EndDate="2010-01-01T10:00:00",
            AddressType=3,
            RuralUrbanClassificationCode=4,
            ImdRankRounded=1000,
            MSOACode="NPC",
        ),
        PatientAddress(
            Patient_ID=1,
            PatientAddress_ID=3,
            StartDate="2010-01-01T10:10:00",
            EndDate="2020-01-01T10:10:00",
            AddressType=3,
            RuralUrbanClassificationCode=-1,
            ImdRankRounded=-1,
            MSOACode="",
        ),
        PatientAddress(
            Patient_ID=1,
            PatientAddress_ID=4,
            StartDate="2010-01-01T10:10:00",
            EndDate="2020-01-01T10:10:00",
            AddressType=3,
            RuralUrbanClassificationCode=4,
            ImdRankRounded=2000,
            MSOACode="L001",
        ),
        PotentialCareHomeAddress(
            PatientAddress_ID=4,
            LocationRequiresNursing="Y",
            LocationDoesNotRequireNursing="N",
        ),
        PatientAddress(
            Patient_ID=1,
            PatientAddress_ID=5,
            StartDate="9999-12-31T00:00:00",
            EndDate="9999-12-31T00:00:00",
            AddressType=3,
            RuralUrbanClassificationCode=4,
            ImdRankRounded=1000,
            MSOACode="NPC",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "address_id": 2,
            "start_date": date(2000, 1, 1),
            "end_date": date(2010, 1, 1),
            "address_type": 3,
            "rural_urban_classification": 4,
            "imd_rounded": 1000,
            "msoa_code": None,
            "has_postcode": False,
            "care_home_is_potential_match": False,
            "care_home_requires_nursing": None,
            "care_home_does_not_require_nursing": None,
        },
        {
            "patient_id": 1,
            "address_id": 3,
            "start_date": date(2010, 1, 1),
            "end_date": date(2020, 1, 1),
            "address_type": 3,
            "rural_urban_classification": None,
            "imd_rounded": None,
            "msoa_code": None,
            "has_postcode": False,
            "care_home_is_potential_match": False,
            "care_home_requires_nursing": None,
            "care_home_does_not_require_nursing": None,
        },
        {
            "patient_id": 1,
            "address_id": 4,
            "start_date": date(2010, 1, 1),
            "end_date": date(2020, 1, 1),
            "address_type": 3,
            "rural_urban_classification": 4,
            "imd_rounded": 2000,
            "msoa_code": "L001",
            "has_postcode": True,
            "care_home_is_potential_match": True,
            "care_home_requires_nursing": True,
            "care_home_does_not_require_nursing": False,
        },
        {
            "patient_id": 1,
            "address_id": 5,
            "start_date": None,
            "end_date": None,
            "address_type": 3,
            "rural_urban_classification": 4,
            "imd_rounded": 1000,
            "msoa_code": None,
            "has_postcode": False,
            "care_home_is_potential_match": False,
            "care_home_requires_nursing": None,
            "care_home_does_not_require_nursing": None,
        },
    ]


@register_test_for(tpp.apcs)
def test_apcs(select_all):
    results = select_all(
        APCS(
            Patient_ID=1,
            APCS_Ident=1,
            Admission_Date=date(2023, 1, 1),
            Discharge_Date=date(2023, 2, 1),
            Spell_Core_HRG_SUS="XXX",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "apcs_ident": 1,
            "admission_date": date(2023, 1, 1),
            "discharge_date": date(2023, 2, 1),
            "spell_core_hrg_sus": "XXX",
        },
    ]


@register_test_for(tpp.apcs_cost)
def test_apcs_cost(select_all):
    results = select_all(
        APCS(
            APCS_Ident=1,
            Admission_Date=date(2023, 1, 1),
            Discharge_Date=date(2023, 2, 1),
        ),
        APCS_Cost(
            Patient_ID=1,
            APCS_Ident=1,
            Grand_Total_Payment_MFF=1.1,
            Tariff_Initial_Amount=2.2,
            Tariff_Total_Payment=3.3,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "apcs_ident": 1,
            "grand_total_payment_mff": pytest.approx(1.1, rel=1e-5),
            "tariff_initial_amount": pytest.approx(2.2, rel=1e-5),
            "tariff_total_payment": pytest.approx(3.3, rel=1e-5),
            "admission_date": date(2023, 1, 1),
            "discharge_date": date(2023, 2, 1),
        },
    ]


@register_test_for(tpp_raw.apcs_historical)
def test_apcs_historical(select_all):
    results = select_all(
        APCS_JRC20231009_LastFilesToContainAllHistoricalCostData(
            Patient_ID=1,
            APCS_Ident=1,
            Admission_Date=date(2023, 1, 1),
            Discharge_Date=date(2023, 2, 1),
            Spell_Core_HRG_SUS="XXX",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "apcs_ident": 1,
            "admission_date": date(2023, 1, 1),
            "discharge_date": date(2023, 2, 1),
            "spell_core_hrg_sus": "XXX",
        },
    ]


@register_test_for(tpp_raw.apcs_cost_historical)
def test_apcs_cost_historical(select_all):
    results = select_all(
        APCS_JRC20231009_LastFilesToContainAllHistoricalCostData(
            APCS_Ident=1,
            Admission_Date=date(2023, 1, 1),
            Discharge_Date=date(2023, 2, 1),
        ),
        APCS_Cost_JRC20231009_LastFilesToContainAllHistoricalCostData(
            Patient_ID=1,
            APCS_Ident=1,
            Grand_Total_Payment_MFF=1.1,
            Tariff_Initial_Amount=2.2,
            Tariff_Total_Payment=3.3,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "apcs_ident": 1,
            "grand_total_payment_mff": pytest.approx(1.1, rel=1e-5),
            "tariff_initial_amount": pytest.approx(2.2, rel=1e-5),
            "tariff_total_payment": pytest.approx(3.3, rel=1e-5),
            "admission_date": date(2023, 1, 1),
            "discharge_date": date(2023, 2, 1),
        },
    ]


@register_test_for(tpp.appointments)
def test_appointments(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        Appointment(
            Patient_ID=1,
            BookedDate="2021-01-01T09:00:00",
            StartDate="2021-01-01T09:00:00",
            SeenDate="9999-12-31T00:00:00",
            Status=1,
        ),
        Appointment(
            Patient_ID=1,
            BookedDate="2021-01-01T09:00:00",
            StartDate="2021-01-01T09:00:00",
            SeenDate="9999-12-31T00:00:00",
            Status=3,
        ),
        Appointment(
            Patient_ID=1,
            BookedDate="2021-01-01T09:00:00",
            StartDate="2021-01-01T09:00:00",
            SeenDate="2021-01-01T09:00:00",
            Status=4,
        ),
        Appointment(
            Patient_ID=1,
            BookedDate="2021-01-02T09:00:00",
            StartDate="2021-01-02T09:00:00",
            SeenDate="9999-12-31T00:00:00",
            Status=9,
        ),
        Appointment(
            Patient_ID=1,
            BookedDate="2021-01-03T09:00:00",
            StartDate="2021-01-03T09:00:00",
            SeenDate="2021-01-03T09:00:00",
            Status=8,
        ),
        Appointment(
            Patient_ID=1,
            BookedDate="2021-01-04T09:00:00",
            StartDate="2021-01-04T09:00:00",
            SeenDate="2021-01-04T09:00:00",
            Status=16,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "booked_date": date(2021, 1, 1),
            "start_date": date(2021, 1, 1),
            "seen_date": None,
            "status": "Arrived",
        },
        {
            "patient_id": 1,
            "booked_date": date(2021, 1, 1),
            "start_date": date(2021, 1, 1),
            "seen_date": None,
            "status": "In Progress",
        },
        {
            "patient_id": 1,
            "booked_date": date(2021, 1, 1),
            "start_date": date(2021, 1, 1),
            "seen_date": date(2021, 1, 1),
            "status": "Finished",
        },
        {
            "patient_id": 1,
            "booked_date": date(2021, 1, 2),
            "start_date": date(2021, 1, 2),
            "seen_date": None,
            "status": "Waiting",
        },
        {
            "patient_id": 1,
            "booked_date": date(2021, 1, 3),
            "start_date": date(2021, 1, 3),
            "seen_date": date(2021, 1, 3),
            "status": "Visit",
        },
        {
            "patient_id": 1,
            "booked_date": date(2021, 1, 4),
            "start_date": date(2021, 1, 4),
            "seen_date": date(2021, 1, 4),
            "status": "Patient Walked Out",
        },
    ]


@register_test_for(tpp.clinical_events)
def test_clinical_events(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        CodedEvent(
            Patient_ID=1,
            ConsultationDate="2020-10-20T14:30:05",
            CTV3Code="xyz",
            NumericValue=0.5,
        ),
        CodedEvent_SNOMED(
            Patient_ID=1,
            ConsultationDate="2020-11-21T09:30:00",
            ConceptId="ijk",
            NumericValue=1.5,
        ),
        CodedEvent_SNOMED(
            Patient_ID=1,
            ConsultationDate="9999-12-31T00:00:00",
            ConceptId="lmn",
            NumericValue=None,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "date": date(2020, 10, 20),
            "snomedct_code": None,
            "ctv3_code": "xyz",
            "numeric_value": 0.5,
        },
        {
            "patient_id": 1,
            "date": date(2020, 11, 21),
            "snomedct_code": "ijk",
            "ctv3_code": None,
            "numeric_value": 1.5,
        },
        {
            "patient_id": 1,
            "date": None,
            "snomedct_code": "lmn",
            "ctv3_code": None,
            "numeric_value": None,
        },
    ]


@register_test_for(tpp.ec)
def test_ec(select_all):
    results = select_all(
        EC(
            Patient_ID=1,
            EC_Ident=1,
            Arrival_Date=date(2023, 1, 1),
            SUS_HRG_Code="XXX",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "ec_ident": 1,
            "arrival_date": date(2023, 1, 1),
            "sus_hrg_code": "XXX",
        },
    ]


@register_test_for(tpp.ec_cost)
def test_ec_cost(select_all):
    results = select_all(
        EC(
            EC_Ident=1,
            Arrival_Date=date(2023, 1, 2),
            EC_Decision_To_Admit_Date=date(2023, 1, 3),
            EC_Injury_Date=date(2023, 1, 1),
        ),
        EC_Cost(
            Patient_ID=1,
            EC_Ident=1,
            Grand_Total_Payment_MFF=1.1,
            Tariff_Total_Payment=2.2,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "ec_ident": 1,
            "grand_total_payment_mff": pytest.approx(1.1, rel=1e-5),
            "tariff_total_payment": pytest.approx(2.2, rel=1e-5),
            "arrival_date": date(2023, 1, 2),
            "ec_decision_to_admit_date": date(2023, 1, 3),
            "ec_injury_date": date(2023, 1, 1),
        },
    ]


@register_test_for(tpp.emergency_care_attendances)
def test_emergency_care_attendances(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        EC(
            Patient_ID=1,
            EC_Ident=2,
            Arrival_Date="2021-01-01",
            Discharge_Destination_SNOMED_CT="abc",
        ),
        EC_Diagnosis(EC_Ident=2, EC_Diagnosis_01="def", EC_Diagnosis_02="xyz"),
    )
    assert results == [
        {
            "patient_id": 1,
            "id": 2,
            "arrival_date": date(2021, 1, 1),
            "discharge_destination": "abc",
            "diagnosis_01": "def",
            "diagnosis_02": "xyz",
            "diagnosis_03": None,
            **{f"diagnosis_{i:02d}": None for i in range(4, 25)},
        }
    ]


@register_test_for(tpp.ethnicity_from_sus)
def test_ethnicity_from_sus(select_all):
    results = select_all(
        # patient 1; Z is ignored; A and B (ignoring the second (optional local code)
        # characterare equally common; B is selected as it is lexically > A
        # The EC table's Ethnic Category is national group only (1 character)
        EC(Patient_ID=1, Ethnic_Category="A"),
        EC(Patient_ID=1, Ethnic_Category="Z"),
        EC(Patient_ID=1, Ethnic_Category="P"),
        APCS(Patient_ID=1, Ethnic_Group="AA"),
        APCS(Patient_ID=1, Ethnic_Group="BA"),
        APCS(Patient_ID=1, Ethnic_Group="A1"),
        OPA(Patient_ID=1, Ethnic_Category="B1"),
        OPA(Patient_ID=1, Ethnic_Category="B"),
        # patient 2; Z and 9 codes the most frequent, but are excluded
        EC(
            Patient_ID=2,
            Ethnic_Category="Z",
        ),
        EC(
            Patient_ID=2,
            Ethnic_Category="9",
        ),
        APCS(Patient_ID=2, Ethnic_Group="99"),
        APCS(Patient_ID=2, Ethnic_Group="ZA"),
        OPA(Patient_ID=2, Ethnic_Category="G5"),
        # patient 3; only first (national code) character counts; although D1 is the most frequent
        # full code, E is the most frequent first character
        EC(Patient_ID=3, Ethnic_Category="E"),
        APCS(Patient_ID=3, Ethnic_Group="D1"),
        APCS(Patient_ID=3, Ethnic_Group="D1"),
        APCS(Patient_ID=3, Ethnic_Group="E1"),
        APCS(Patient_ID=3, Ethnic_Group="E2"),
        # patient 4; no valid codes
        EC(Patient_ID=4, Ethnic_Category="Z"),
        APCS(Patient_ID=4, Ethnic_Group="99"),
        OPA(Patient_ID=4, Ethnic_Category=""),
        OPA(Patient_ID=4, Ethnic_Category=None),
    )
    assert results == [
        {"patient_id": 1, "code": "B"},
        {"patient_id": 2, "code": "G"},
        {"patient_id": 3, "code": "E"},
    ]


@register_test_for(tpp.hospital_admissions)
def test_hospital_admissions(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        APCS(
            Patient_ID=1,
            APCS_Ident=2,
            Admission_Date="2021-01-01",
            Discharge_Date="2021-01-10",
            Admission_Method="1A",
            Der_Diagnosis_All="123;456;789",
            Patient_Classification="X",
        ),
        APCS_Der(
            APCS_Ident=2,
            Spell_PbR_CC_Day="5",
            Spell_Primary_Diagnosis="A1",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "id": 2,
            "admission_date": date(2021, 1, 1),
            "discharge_date": date(2021, 1, 10),
            "admission_method": "1A",
            "all_diagnoses": "123;456;789",
            "patient_classification": "X",
            "days_in_critical_care": 5,
            "primary_diagnoses": "A1",
            "primary_diagnosis": "A1",
        }
    ]


@register_test_for(tpp.household_memberships_2020)
def test_household_memberships_2020(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        Household(
            Household_ID=123,
            HouseholdSize=5,
        ),
        HouseholdMember(
            Patient_ID=1,
            Household_ID=123,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "household_pseudo_id": 123,
            "household_size": 5,
        },
    ]


@register_test_for(tpp_raw.isaric)
def test_isaric_raw_dates(select_all):
    isaric_patient_keys = frozenset(tpp_raw.isaric._qm_node.schema.column_names)

    # Test date extraction with all valid date strings.
    patient_1 = dict.fromkeys(isaric_patient_keys, None)
    patient_1 |= {
        "Patient_ID": 1,
        "covid19_vaccined": "2021-02-01",
        "covid19_vaccine2d": "2021-04-01",
        "cestdat": "2022-01-01",
        "hostdat": "2022-01-07",
        "hostdat_transfer": "2022-01-10",
        "dsstdat": "2022-01-05",
        "dsstdtc": "2022-01-20",
    }
    patient_1_results = dict.fromkeys(isaric_patient_keys, None)
    patient_1_results |= {
        "patient_id": 1,
        "covid19_vaccined": date(2021, 2, 1),
        "covid19_vaccine2d": date(2021, 4, 1),
        "cestdat": date(2022, 1, 1),
        "hostdat": date(2022, 1, 7),
        "hostdat_transfer": date(2022, 1, 10),
        "dsstdat": date(2022, 1, 5),
        "dsstdtc": date(2022, 1, 20),
    }
    # Test date extraction with all "NA" strings as dates..
    patient_2 = dict.fromkeys(isaric_patient_keys, None)
    patient_2 |= {
        "Patient_ID": 2,
        "covid19_vaccined": "NA",
        "covid19_vaccine2d": "NA",
        "cestdat": "NA",
        "hostdat": "NA",
        "hostdat_transfer": "NA",
        "dsstdat": "NA",
        "dsstdtc": "NA",
    }
    patient_2_results = dict.fromkeys(isaric_patient_keys, None)
    patient_2_results |= {
        "patient_id": 2,
    }
    # Test date extraction with a mixture of valid and "NA" date strings.
    patient_3 = dict.fromkeys(isaric_patient_keys, None)
    patient_3 |= {
        "Patient_ID": 3,
        "covid19_vaccined": "NA",
        "covid19_vaccine2d": "2021-04-01",
        "cestdat": "NA",
        "hostdat": "2022-01-07",
        "hostdat_transfer": "NA",
        "dsstdat": "2022-01-05",
        "dsstdtc": "NA",
    }
    patient_3_results = dict.fromkeys(isaric_patient_keys, None)
    patient_3_results |= {
        "patient_id": 3,
        "covid19_vaccine2d": date(2021, 4, 1),
        "hostdat": date(2022, 1, 7),
        "dsstdat": date(2022, 1, 5),
    }
    results = select_all(
        Patient(Patient_ID=1),
        Patient(Patient_ID=2),
        Patient(Patient_ID=3),
        ISARIC_New(
            **patient_1,
        ),
        ISARIC_New(
            **patient_2,
        ),
        ISARIC_New(
            **patient_3,
        ),
    )
    assert results == [
        patient_1_results,
        patient_2_results,
        patient_3_results,
    ]


@register_test_for(tpp_raw.isaric)
def test_isaric_raw_clinical_variables(select_all):
    isaric_patient_keys = frozenset(tpp_raw.isaric._qm_node.schema.column_names)

    patient_1 = dict.fromkeys(isaric_patient_keys, None)
    patient_1 |= {
        "Patient_ID": 1,
        "chrincard": "YES",
        "hypertension_mhyn": "YES",
        "chronicpul_mhyn": "YES",
        "asthma_mhyn": "YES",
        "renal_mhyn": "YES",
        "mildliver": "YES",
        "modliv": "YES",
        "chronicneu_mhyn": "YES",
        "malignantneo_mhyn": "YES",
        "chronichaemo_mhyn": "YES",
        "aidshiv_mhyn": "YES",
        "obesity_mhyn": "YES",
        "diabetescom_mhyn": "YES",
        "diabetes_mhyn": "YES",
        "rheumatologic_mhyn": "YES",
        "dementia_mhyn": "YES",
        "malnutrition_mhyn": "YES",
    }
    patient_1_results = dict.fromkeys(isaric_patient_keys, None)
    patient_1_results |= {
        "patient_id": 1,
        "chrincard": "YES",
        "hypertension_mhyn": "YES",
        "chronicpul_mhyn": "YES",
        "asthma_mhyn": "YES",
        "renal_mhyn": "YES",
        "mildliver": "YES",
        "modliv": "YES",
        "chronicneu_mhyn": "YES",
        "malignantneo_mhyn": "YES",
        "chronichaemo_mhyn": "YES",
        "aidshiv_mhyn": "YES",
        "obesity_mhyn": "YES",
        "diabetescom_mhyn": "YES",
        "diabetes_mhyn": "YES",
        "rheumatologic_mhyn": "YES",
        "dementia_mhyn": "YES",
        "malnutrition_mhyn": "YES",
    }
    patient_2 = dict.fromkeys(isaric_patient_keys, None)
    patient_2 |= {
        "Patient_ID": 2,
        "chrincard": "NO",
        "hypertension_mhyn": "NO",
        "chronicpul_mhyn": "NO",
        "asthma_mhyn": "NO",
        "renal_mhyn": "NO",
        "mildliver": "NO",
        "modliv": "NO",
        "chronicneu_mhyn": "NO",
        "malignantneo_mhyn": "NO",
        "chronichaemo_mhyn": "NO",
        "aidshiv_mhyn": "NO",
        "obesity_mhyn": "NO",
        "diabetescom_mhyn": "NO",
        "diabetes_mhyn": "NO",
        "rheumatologic_mhyn": "NO",
        "dementia_mhyn": "NO",
        "malnutrition_mhyn": "NO",
    }
    patient_2_results = dict.fromkeys(isaric_patient_keys, None)
    patient_2_results |= {
        "patient_id": 2,
        "chrincard": "NO",
        "hypertension_mhyn": "NO",
        "chronicpul_mhyn": "NO",
        "asthma_mhyn": "NO",
        "renal_mhyn": "NO",
        "mildliver": "NO",
        "modliv": "NO",
        "chronicneu_mhyn": "NO",
        "malignantneo_mhyn": "NO",
        "chronichaemo_mhyn": "NO",
        "aidshiv_mhyn": "NO",
        "obesity_mhyn": "NO",
        "diabetescom_mhyn": "NO",
        "diabetes_mhyn": "NO",
        "rheumatologic_mhyn": "NO",
        "dementia_mhyn": "NO",
        "malnutrition_mhyn": "NO",
    }
    patient_3 = dict.fromkeys(isaric_patient_keys, None)
    patient_3 |= {
        "Patient_ID": 3,
        "chrincard": "Unknown",
        "hypertension_mhyn": "Unknown",
        "chronicpul_mhyn": "Unknown",
        "asthma_mhyn": "Unknown",
        "renal_mhyn": "Unknown",
        "mildliver": "Unknown",
        "modliv": "Unknown",
        "chronicneu_mhyn": "Unknown",
        "malignantneo_mhyn": "Unknown",
        "chronichaemo_mhyn": "Unknown",
        "aidshiv_mhyn": "Unknown",
        "obesity_mhyn": "Unknown",
        "diabetescom_mhyn": "Unknown",
        "diabetes_mhyn": "Unknown",
        "rheumatologic_mhyn": "Unknown",
        "dementia_mhyn": "Unknown",
        "malnutrition_mhyn": "Unknown",
    }
    patient_3_results = dict.fromkeys(isaric_patient_keys, None)
    patient_3_results |= {
        "patient_id": 3,
        "chrincard": "Unknown",
        "hypertension_mhyn": "Unknown",
        "chronicpul_mhyn": "Unknown",
        "asthma_mhyn": "Unknown",
        "renal_mhyn": "Unknown",
        "mildliver": "Unknown",
        "modliv": "Unknown",
        "chronicneu_mhyn": "Unknown",
        "malignantneo_mhyn": "Unknown",
        "chronichaemo_mhyn": "Unknown",
        "aidshiv_mhyn": "Unknown",
        "obesity_mhyn": "Unknown",
        "diabetescom_mhyn": "Unknown",
        "diabetes_mhyn": "Unknown",
        "rheumatologic_mhyn": "Unknown",
        "dementia_mhyn": "Unknown",
        "malnutrition_mhyn": "Unknown",
    }
    patient_4 = dict.fromkeys(isaric_patient_keys, None)
    patient_4 |= {
        "Patient_ID": 4,
        "chrincard": "NA",
        "hypertension_mhyn": "NA",
        "chronicpul_mhyn": "NA",
        "asthma_mhyn": "NA",
        "renal_mhyn": "NA",
        "mildliver": "NA",
        "modliv": "NA",
        "chronicneu_mhyn": "NA",
        "malignantneo_mhyn": "NA",
        "chronichaemo_mhyn": "NA",
        "aidshiv_mhyn": "NA",
        "obesity_mhyn": "NA",
        "diabetescom_mhyn": "NA",
        "diabetes_mhyn": "NA",
        "rheumatologic_mhyn": "NA",
        "dementia_mhyn": "NA",
        "malnutrition_mhyn": "NA",
    }
    patient_4_results = dict.fromkeys(isaric_patient_keys, None)
    patient_4_results |= {
        "patient_id": 4,
        "chrincard": "NO",
        "hypertension_mhyn": "NO",
        "chronicpul_mhyn": "NO",
        "asthma_mhyn": "NO",
        "renal_mhyn": "NO",
        "mildliver": "NO",
        "modliv": "NO",
        "chronicneu_mhyn": "NO",
        "malignantneo_mhyn": "NO",
        "chronichaemo_mhyn": "NO",
        "aidshiv_mhyn": "NO",
        "obesity_mhyn": "NO",
        "diabetescom_mhyn": "NO",
        "diabetes_mhyn": "NO",
        "rheumatologic_mhyn": "NO",
        "dementia_mhyn": "NO",
        "malnutrition_mhyn": "NO",
    }
    patient_5 = dict.fromkeys(isaric_patient_keys, None)
    patient_5 |= {
        "Patient_ID": 5,
        "chrincard": "YES",
        "hypertension_mhyn": "NO",
        "chronicpul_mhyn": "Unknown",
        "asthma_mhyn": "NA",
        "renal_mhyn": "YES",
        "mildliver": "NO",
        "modliv": "Unknown",
        "chronicneu_mhyn": "NA",
        "malignantneo_mhyn": "YES",
        "chronichaemo_mhyn": "NO",
        "aidshiv_mhyn": "Unknown",
        "obesity_mhyn": "NA",
        "diabetescom_mhyn": "YES",
        "diabetes_mhyn": "NO",
        "rheumatologic_mhyn": "Unknown",
        "dementia_mhyn": "NA",
        "malnutrition_mhyn": "YES",
    }
    patient_5_results = dict.fromkeys(isaric_patient_keys, None)
    patient_5_results |= {
        "patient_id": 5,
        "chrincard": "YES",
        "hypertension_mhyn": "NO",
        "chronicpul_mhyn": "Unknown",
        "asthma_mhyn": "NO",
        "renal_mhyn": "YES",
        "mildliver": "NO",
        "modliv": "Unknown",
        "chronicneu_mhyn": "NO",
        "malignantneo_mhyn": "YES",
        "chronichaemo_mhyn": "NO",
        "aidshiv_mhyn": "Unknown",
        "obesity_mhyn": "NO",
        "diabetescom_mhyn": "YES",
        "diabetes_mhyn": "NO",
        "rheumatologic_mhyn": "Unknown",
        "dementia_mhyn": "NO",
        "malnutrition_mhyn": "YES",
    }
    patient_6 = dict.fromkeys(isaric_patient_keys, None)
    patient_6 |= {
        "Patient_ID": 6,
        "diabetes_type_mhyn": "No",
        "smoking_mhyn": "Yes",
    }
    patient_6_results = dict.fromkeys(isaric_patient_keys, None)
    patient_6_results |= {
        "patient_id": 6,
        "diabetes_type_mhyn": "No",
        "smoking_mhyn": "Yes",
    }
    patient_7 = dict.fromkeys(isaric_patient_keys, None)
    patient_7 |= {
        "Patient_ID": 7,
        "diabetes_type_mhyn": "1",
        "smoking_mhyn": "Never Smoked",
    }
    patient_7_results = dict.fromkeys(isaric_patient_keys, None)
    patient_7_results |= {
        "patient_id": 7,
        "diabetes_type_mhyn": "1",
        "smoking_mhyn": "Never Smoked",
    }
    patient_8 = dict.fromkeys(isaric_patient_keys, None)
    patient_8 |= {
        "Patient_ID": 8,
        "diabetes_type_mhyn": "2",
        "smoking_mhyn": "Former Smoker",
    }
    patient_8_results = dict.fromkeys(isaric_patient_keys, None)
    patient_8_results |= {
        "patient_id": 8,
        "diabetes_type_mhyn": "2",
        "smoking_mhyn": "Former Smoker",
    }
    patient_8 = dict.fromkeys(isaric_patient_keys, None)
    patient_8 |= {
        "Patient_ID": 8,
        "diabetes_type_mhyn": "N/K",
        "smoking_mhyn": "N/K",
    }
    patient_8_results = dict.fromkeys(isaric_patient_keys, None)
    patient_8_results |= {
        "patient_id": 8,
        "diabetes_type_mhyn": "N/K",
        "smoking_mhyn": "N/K",
    }
    patient_9 = dict.fromkeys(isaric_patient_keys, None)
    patient_9 |= {
        "Patient_ID": 9,
        "diabetes_type_mhyn": "N/K",
        "smoking_mhyn": "N/K",
    }
    patient_9_results = dict.fromkeys(isaric_patient_keys, None)
    patient_9_results |= {
        "patient_id": 9,
        "diabetes_type_mhyn": "N/K",
        "smoking_mhyn": "N/K",
    }
    results = select_all(
        Patient(Patient_ID=1),
        Patient(Patient_ID=2),
        Patient(Patient_ID=3),
        Patient(Patient_ID=4),
        Patient(Patient_ID=5),
        Patient(Patient_ID=6),
        Patient(Patient_ID=7),
        Patient(Patient_ID=8),
        Patient(Patient_ID=9),
        ISARIC_New(
            **patient_1,
        ),
        ISARIC_New(
            **patient_2,
        ),
        ISARIC_New(
            **patient_3,
        ),
        ISARIC_New(
            **patient_4,
        ),
        ISARIC_New(
            **patient_5,
        ),
        ISARIC_New(
            **patient_6,
        ),
        ISARIC_New(
            **patient_7,
        ),
        ISARIC_New(
            **patient_8,
        ),
        ISARIC_New(
            **patient_9,
        ),
    )
    assert results == [
        patient_1_results,
        patient_2_results,
        patient_3_results,
        patient_4_results,
        patient_5_results,
        patient_6_results,
        patient_7_results,
        patient_8_results,
        patient_9_results,
    ]


@register_test_for(tpp.medications)
def test_medications(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        # MedicationIssue.MultilexDrug_ID found in MedicationDictionary only
        MedicationDictionary(MultilexDrug_ID="0;0;0", DMD_ID="100000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-15T10:10:10",
            MultilexDrug_ID="0;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in CustomMedicationDictionary only
        CustomMedicationDictionary(MultilexDrug_ID="2;0;0", DMD_ID="200000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-16T10:10:10",
            MultilexDrug_ID="2;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in both; MedicationDictionary
        # preferred
        MedicationDictionary(MultilexDrug_ID="3;0;0", DMD_ID="300000"),
        CustomMedicationDictionary(MultilexDrug_ID="3;0;0", DMD_ID="400000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-17T10:10:10",
            MultilexDrug_ID="3;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in both, but MedicationDictionary.DMD_ID
        # contains the empty string; CustomMedicationDictionary.DMD_ID preferred
        MedicationDictionary(MultilexDrug_ID="5;0;0", DMD_ID=""),
        CustomMedicationDictionary(MultilexDrug_ID="5;0;0", DMD_ID="500000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-18T10:10:10",
            MultilexDrug_ID="5;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in MedicationDictionary but DMD_ID
        # contains the empty string; dmd_code is NULL not empty string
        MedicationDictionary(MultilexDrug_ID="6;0;0", DMD_ID=""),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-19T10:10:10",
            MultilexDrug_ID="6;0;0",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "date": date(2020, 5, 15),
            "dmd_code": "100000",
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 16),
            "dmd_code": "200000",
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 17),
            "dmd_code": "300000",
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 18),
            "dmd_code": "500000",
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 19),
            "dmd_code": None,
        },
    ]


@register_test_for(tpp.occupation_on_covid_vaccine_record)
def test_occupation_on_covid_vaccine_record(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        HealthCareWorker(Patient_ID=1),
    )
    assert results == [{"patient_id": 1, "is_healthcare_worker": True}]


@register_test_for(tpp_raw.ons_deaths)
def test_ons_deaths_raw(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        ONS_Deaths(
            Patient_ID=1,
            dod="2022-01-01",
            Place_of_occurrence="Care Home",
            icd10u="xyz",
            ICD10001="abc",
            ICD10002="def",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "date": date(2022, 1, 1),
            "place": "Care Home",
            "underlying_cause_of_death": "xyz",
            "cause_of_death_01": "abc",
            "cause_of_death_02": "def",
            "cause_of_death_03": None,
            **{f"cause_of_death_{i:02d}": None for i in range(4, 16)},
        }
    ]


@register_test_for(tpp.ons_deaths)
def test_ons_deaths(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        Patient(Patient_ID=2),
        Patient(Patient_ID=3),
        ONS_Deaths(
            Patient_ID=1,
            dod="2022-01-01",
            Place_of_occurrence="Care Home",
            icd10u="xyz",
            ICD10001="abc",
            ICD10002="def",
        ),
        # Same patient, different date of death (dod) is being tested
        ONS_Deaths(
            Patient_ID=2,
            dod="2022-01-01",
            Place_of_occurrence="Care Home",
            icd10u="xyz",
            ICD10001="abc",
            ICD10002="def",
        ),
        ONS_Deaths(
            Patient_ID=2,
            dod="2022-01-02",
            Place_of_occurrence="Care Home",
            icd10u="xyz",
            ICD10001="abc",
            ICD10002="def",
        ),
        # Same patient, same date of death (dod), different underlying
        # cause of death (icd10u) is being tested
        ONS_Deaths(
            Patient_ID=3,
            dod="2022-01-01",
            Place_of_occurrence="Care Home",
            icd10u="xyz",
            ICD10001="abc",
            ICD10002="def",
        ),
        ONS_Deaths(
            Patient_ID=3,
            dod="2022-01-01",
            Place_of_occurrence="Care Home",
            icd10u="abc",
            ICD10001="abc",
            ICD10002="def",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "date": date(2022, 1, 1),
            "place": "Care Home",
            "underlying_cause_of_death": "xyz",
            "cause_of_death_01": "abc",
            "cause_of_death_02": "def",
            "cause_of_death_03": None,
            **{f"cause_of_death_{i:02d}": None for i in range(4, 16)},
        },
        {
            "patient_id": 2,
            "date": date(2022, 1, 1),
            "place": "Care Home",
            "underlying_cause_of_death": "xyz",
            "cause_of_death_01": "abc",
            "cause_of_death_02": "def",
            "cause_of_death_03": None,
            **{f"cause_of_death_{i:02d}": None for i in range(4, 16)},
        },
        {
            "patient_id": 3,
            "date": date(2022, 1, 1),
            "place": "Care Home",
            "underlying_cause_of_death": "abc",
            "cause_of_death_01": "abc",
            "cause_of_death_02": "def",
            "cause_of_death_03": None,
            **{f"cause_of_death_{i:02d}": None for i in range(4, 16)},
        },
    ]


@register_test_for(tpp.opa)
def test_opa(select_all):
    results = select_all(
        OPA(
            Patient_ID=1,
            OPA_Ident=1,
            Appointment_Date=date(2023, 2, 1),
            Attendance_Status="1",
            Consultation_Medium_Used="02",
            First_Attendance="3",
            HRG_Code="XXX",
            Treatment_Function_Code="999",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "opa_ident": 1,
            "appointment_date": date(2023, 2, 1),
            "attendance_status": "1",
            "consultation_medium_used": "02",
            "first_attendance": "3",
            "hrg_code": "XXX",
            "treatment_function_code": "999",
        },
    ]


@register_test_for(tpp.opa_cost)
def test_opa_cost(select_all):
    results = select_all(
        OPA(
            OPA_Ident=1,
            Appointment_Date=date(2023, 2, 1),
            Referral_Request_Received_Date=date(2023, 1, 1),
        ),
        OPA_Cost(
            Patient_ID=1,
            OPA_Ident=1,
            Tariff_OPP=1.1,
            Grand_Total_Payment_MFF=2.2,
            Tariff_Total_Payment=3.3,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "opa_ident": 1,
            "tariff_opp": pytest.approx(1.1, rel=1e-5),
            "grand_total_payment_mff": pytest.approx(2.2, rel=1e-5),
            "tariff_total_payment": pytest.approx(3.3, rel=1e-5),
            "appointment_date": date(2023, 2, 1),
            "referral_request_received_date": date(2023, 1, 1),
        },
    ]


@register_test_for(tpp.opa_diag)
def test_opa_diag(select_all):
    results = select_all(
        OPA(
            OPA_Ident=1,
            Appointment_Date=date(2023, 2, 1),
            Referral_Request_Received_Date=date(2023, 1, 1),
        ),
        OPA_Diag(
            Patient_ID=1,
            OPA_Ident=1,
            Primary_Diagnosis_Code="100000",
            Primary_Diagnosis_Code_Read="Y0000",
            Secondary_Diagnosis_Code_1="100000",
            Secondary_Diagnosis_Code_1_Read="Y0000",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "opa_ident": 1,
            "primary_diagnosis_code": "100000",
            "primary_diagnosis_code_read": "Y0000",
            "secondary_diagnosis_code_1": "100000",
            "secondary_diagnosis_code_1_read": "Y0000",
            "appointment_date": date(2023, 2, 1),
            "referral_request_received_date": date(2023, 1, 1),
        },
    ]


@register_test_for(tpp.opa_proc)
def test_opa_proc(select_all):
    results = select_all(
        OPA(
            OPA_Ident=1,
            Appointment_Date=date(2023, 2, 1),
            Referral_Request_Received_Date=date(2023, 1, 1),
        ),
        OPA_Proc(
            Patient_ID=1,
            OPA_Ident=1,
            Primary_Procedure_Code="100000",
            Primary_Procedure_Code_Read="Y0000",
            Procedure_Code_2="100000",
            Procedure_Code_2_Read="Y0000",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "opa_ident": 1,
            "primary_procedure_code": "100000",
            "primary_procedure_code_read": "Y0000",
            "procedure_code_2": "100000",
            "procedure_code_2_read": "Y0000",
            "appointment_date": date(2023, 2, 1),
            "referral_request_received_date": date(2023, 1, 1),
        },
    ]


@register_test_for(tpp.open_prompt)
def test_open_prompt(select_all):
    results = select_all(
        OpenPROMPT(
            Patient_ID=1,
            CTV3Code="X0000",
            CodeSystemId=0,  # SNOMED CT
            ConceptId="100000",
            CreationDate="2023-01-01",
            ConsultationDate="2023-01-01",
            Consultation_ID=1,
            NumericCode=1,
            NumericValue=1.0,
        ),
        OpenPROMPT(
            Patient_ID=2,
            CTV3Code="Y0000",
            CodeSystemId=2,  # CTV3 "Y"
            ConceptId="Y0000",
            CreationDate="2023-01-01",
            ConsultationDate="2023-01-01",
            Consultation_ID=2,
            NumericCode=0,
            NumericValue=0,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "ctv3_code": "X0000",
            "snomedct_code": "100000",
            "creation_date": date(2023, 1, 1),
            "consultation_date": date(2023, 1, 1),
            "consultation_id": 1,
            "numeric_value": 1.0,
        },
        {
            "patient_id": 2,
            "ctv3_code": "Y0000",
            "snomedct_code": None,
            "creation_date": date(2023, 1, 1),
            "consultation_date": date(2023, 1, 1),
            "consultation_id": 2,
            "numeric_value": None,
        },
    ]


@register_test_for(tpp.patients)
def test_patients(select_all):
    results = select_all(
        Patient(Patient_ID=1, DateOfBirth="2020-01-01", Sex="M"),
        Patient(Patient_ID=2, DateOfBirth="2020-01-01", Sex="F"),
        Patient(Patient_ID=3, DateOfBirth="2020-01-01", Sex="I"),
        Patient(Patient_ID=4, DateOfBirth="2020-01-01", Sex="U"),
        Patient(Patient_ID=5, DateOfBirth="2020-01-01", Sex=""),
        Patient(
            Patient_ID=6, DateOfBirth="2000-01-01", Sex="M", DateOfDeath="2020-01-01"
        ),
        Patient(
            Patient_ID=7, DateOfBirth="2000-01-01", Sex="M", DateOfDeath="9999-12-31"
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "date_of_birth": date(2020, 1, 1),
            "sex": "male",
            "date_of_death": None,
        },
        {
            "patient_id": 2,
            "date_of_birth": date(2020, 1, 1),
            "sex": "female",
            "date_of_death": None,
        },
        {
            "patient_id": 3,
            "date_of_birth": date(2020, 1, 1),
            "sex": "intersex",
            "date_of_death": None,
        },
        {
            "patient_id": 4,
            "date_of_birth": date(2020, 1, 1),
            "sex": "unknown",
            "date_of_death": None,
        },
        {
            "patient_id": 5,
            "date_of_birth": date(2020, 1, 1),
            "sex": "unknown",
            "date_of_death": None,
        },
        {
            "patient_id": 6,
            "date_of_birth": date(2000, 1, 1),
            "sex": "male",
            "date_of_death": date(2020, 1, 1),
        },
        {
            "patient_id": 7,
            "date_of_birth": date(2000, 1, 1),
            "sex": "male",
            "date_of_death": None,
        },
    ]


@register_test_for(tpp.practice_registrations)
def test_practice_registrations(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        Organisation(Organisation_ID=2, STPCode="abc", Region="def"),
        Organisation(Organisation_ID=3, STPCode="", Region=""),
        RegistrationHistory(
            Patient_ID=1,
            StartDate=date(2010, 1, 1),
            EndDate=date(2020, 1, 1),
            Organisation_ID=2,
        ),
        RegistrationHistory(
            Patient_ID=1,
            StartDate=date(2020, 1, 1),
            EndDate=date(9999, 12, 31),
            Organisation_ID=3,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "start_date": date(2010, 1, 1),
            "end_date": date(2020, 1, 1),
            "practice_pseudo_id": 2,
            "practice_stp": "abc",
            "practice_nuts1_region_name": "def",
        },
        {
            "patient_id": 1,
            "start_date": date(2020, 1, 1),
            "end_date": None,
            "practice_pseudo_id": 3,
            "practice_stp": None,
            "practice_nuts1_region_name": None,
        },
    ]


@register_test_for(tpp.sgss_covid_all_tests)
def test_sgss_covid_all_tests(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        SGSS_AllTests_Positive(
            Patient_ID=1,
            Specimen_Date="2021-10-20",
            Lab_Report_Date="2021-10-22",
            Symptomatic="N",
            SGTF="2",
            Variant="VOC-22JAN-O1",
            VariantDetectionMethod="Reflex Assay",
        ),
        SGSS_AllTests_Positive(
            Patient_ID=1,
            Specimen_Date="2021-12-20",
            Lab_Report_Date="2021-12-20",
            Symptomatic="U",
            SGTF="",
            Variant="",
            VariantDetectionMethod="",
        ),
        SGSS_AllTests_Negative(
            Patient_ID=1,
            Specimen_Date="2021-11-20",
            Lab_Report_Date="2021-11-23",
            Symptomatic="true",
        ),
        SGSS_AllTests_Negative(
            Patient_ID=1,
            Specimen_Date="2022-01-20",
            Lab_Report_Date="2022-01-20",
            Symptomatic="false",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "specimen_taken_date": date(2021, 10, 20),
            "is_positive": True,
            "lab_report_date": date(2021, 10, 22),
            "was_symptomatic": False,
            "sgtf_status": 2,
            "variant": "VOC-22JAN-O1",
            "variant_detection_method": "Reflex Assay",
        },
        {
            "patient_id": 1,
            "specimen_taken_date": date(2021, 12, 20),
            "is_positive": True,
            "lab_report_date": date(2021, 12, 20),
            "was_symptomatic": None,
            "sgtf_status": None,
            "variant": None,
            "variant_detection_method": None,
        },
        {
            "patient_id": 1,
            "specimen_taken_date": date(2021, 11, 20),
            "is_positive": False,
            "lab_report_date": date(2021, 11, 23),
            "was_symptomatic": True,
            "sgtf_status": None,
            "variant": None,
            "variant_detection_method": None,
        },
        {
            "patient_id": 1,
            "specimen_taken_date": date(2022, 1, 20),
            "is_positive": False,
            "lab_report_date": date(2022, 1, 20),
            "was_symptomatic": False,
            "sgtf_status": None,
            "variant": None,
            "variant_detection_method": None,
        },
    ]


@register_test_for(tpp.vaccinations)
def test_vaccinations(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        VaccinationReference(VaccinationName_ID=10, VaccinationContent="foo"),
        VaccinationReference(VaccinationName_ID=10, VaccinationContent="bar"),
        Vaccination(
            Patient_ID=1,
            Vaccination_ID=123,
            VaccinationDate="2020-01-01T14:00:00",
            VaccinationName="baz",
            VaccinationName_ID=10,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "vaccination_id": 123,
            "date": date(2020, 1, 1),
            "target_disease": "foo",
            "product_name": "baz",
        },
        {
            "patient_id": 1,
            "vaccination_id": 123,
            "date": date(2020, 1, 1),
            "target_disease": "bar",
            "product_name": "baz",
        },
    ]


def sha256_digest(int_):
    return hashlib.sha256(int_.to_bytes()).digest()


def to_hex(bytes_):
    return bytes_.hex().upper()


@register_test_for(tpp_raw.wl_clockstops)
def test_wl_clockstops_raw(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        WL_ClockStops(
            Patient_ID=1,
            ACTIVITY_TREATMENT_FUNCTION_CODE="110",
            PRIORITY_TYPE_CODE="1",
            PSEUDO_ORGANISATION_CODE_PATIENT_PATHWAY_IDENTIFIER_ISSUER=sha256_digest(1),
            PSEUDO_PATIENT_PATHWAY_IDENTIFIER=sha256_digest(1),
            Pseudo_Referral_Identifier=sha256_digest(1),
            Referral_Request_Received_Date="2023-02-01",
            REFERRAL_TO_TREATMENT_PERIOD_END_DATE="2025-04-03",
            REFERRAL_TO_TREATMENT_PERIOD_START_DATE="2024-03-02",
            SOURCE_OF_REFERRAL_FOR_OUTPATIENTS="",
            Waiting_List_Type="ORTT",
            Week_Ending_Date="2024-03-03",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "activity_treatment_function_code": "110",
            "priority_type_code": "1",
            "pseudo_organisation_code_patient_pathway_identifier_issuer": to_hex(
                sha256_digest(1)
            ),
            "pseudo_patient_pathway_identifier": to_hex(sha256_digest(1)),
            "pseudo_referral_identifier": to_hex(sha256_digest(1)),
            "referral_request_received_date": "2023-02-01",
            "referral_to_treatment_period_end_date": "2025-04-03",
            "referral_to_treatment_period_start_date": "2024-03-02",
            "source_of_referral_for_outpatients": "",
            "waiting_list_type": "ORTT",
            "week_ending_date": "2024-03-03",
        }
    ]


@register_test_for(tpp.wl_clockstops)
def test_wl_clockstops(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        WL_ClockStops(
            Patient_ID=1,
            ACTIVITY_TREATMENT_FUNCTION_CODE="110",
            PRIORITY_TYPE_CODE="1",
            PSEUDO_ORGANISATION_CODE_PATIENT_PATHWAY_IDENTIFIER_ISSUER=sha256_digest(1),
            PSEUDO_PATIENT_PATHWAY_IDENTIFIER=sha256_digest(1),
            Pseudo_Referral_Identifier=sha256_digest(1),
            Referral_Request_Received_Date="2023-02-01",
            REFERRAL_TO_TREATMENT_PERIOD_END_DATE="2025-04-03",
            REFERRAL_TO_TREATMENT_PERIOD_START_DATE="2024-03-02",
            SOURCE_OF_REFERRAL_FOR_OUTPATIENTS="",
            Waiting_List_Type="ORTT",
            Week_Ending_Date="2024-03-03",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "activity_treatment_function_code": "110",
            "priority_type_code": "routine",
            "pseudo_organisation_code_patient_pathway_identifier_issuer": to_hex(
                sha256_digest(1)
            ),
            "pseudo_patient_pathway_identifier": to_hex(sha256_digest(1)),
            "pseudo_referral_identifier": to_hex(sha256_digest(1)),
            "referral_request_received_date": date(2023, 2, 1),
            "referral_to_treatment_period_end_date": date(2025, 4, 3),
            "referral_to_treatment_period_start_date": date(2024, 3, 2),
            "source_of_referral_for_outpatients": "",
            "waiting_list_type": "ORTT",
            "week_ending_date": date(2024, 3, 3),
        }
    ]


@register_test_for(tpp_raw.wl_openpathways)
def test_wl_openpathways_raw(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        WL_OpenPathways(
            Patient_ID=1,
            ACTIVITY_TREATMENT_FUNCTION_CODE="110",
            Current_Pathway_Period_Start_Date="2024-03-02",
            PRIORITY_TYPE_CODE="2",
            PSEUDO_ORGANISATION_CODE_PATIENT_PATHWAY_IDENTIFIER_ISSUER=sha256_digest(1),
            PSEUDO_PATIENT_PATHWAY_IDENTIFIER=sha256_digest(1),
            Pseudo_Referral_Identifier=sha256_digest(1),
            REFERRAL_REQUEST_RECEIVED_DATE="2023-02-01",
            REFERRAL_TO_TREATMENT_PERIOD_END_DATE="9999-12-31",
            REFERRAL_TO_TREATMENT_PERIOD_START_DATE="2024-03-02",
            SOURCE_OF_REFERRAL="",
            Waiting_List_Type="IRTT",
            Week_Ending_Date="2024-03-03",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "activity_treatment_function_code": "110",
            "current_pathway_period_start_date": "2024-03-02",
            "priority_type_code": "2",
            "pseudo_organisation_code_patient_pathway_identifier_issuer": to_hex(
                sha256_digest(1)
            ),
            "pseudo_patient_pathway_identifier": to_hex(sha256_digest(1)),
            "pseudo_referral_identifier": to_hex(sha256_digest(1)),
            "referral_request_received_date": "2023-02-01",
            "referral_to_treatment_period_end_date": "9999-12-31",
            "referral_to_treatment_period_start_date": "2024-03-02",
            "source_of_referral": "",
            "waiting_list_type": "IRTT",
            "week_ending_date": "2024-03-03",
        }
    ]


@register_test_for(tpp.wl_openpathways)
def test_wl_openpathways(select_all):
    results = select_all(
        Patient(Patient_ID=1),
        WL_OpenPathways(
            Patient_ID=1,
            ACTIVITY_TREATMENT_FUNCTION_CODE="110",
            Current_Pathway_Period_Start_Date="2024-03-02",
            PRIORITY_TYPE_CODE="2",
            PSEUDO_ORGANISATION_CODE_PATIENT_PATHWAY_IDENTIFIER_ISSUER=sha256_digest(1),
            PSEUDO_PATIENT_PATHWAY_IDENTIFIER=sha256_digest(1),
            Pseudo_Referral_Identifier=sha256_digest(1),
            REFERRAL_REQUEST_RECEIVED_DATE="2023-02-01",
            REFERRAL_TO_TREATMENT_PERIOD_END_DATE="9999-12-31",
            REFERRAL_TO_TREATMENT_PERIOD_START_DATE="2024-03-02",
            SOURCE_OF_REFERRAL="",
            Waiting_List_Type="IRTT",
            Week_Ending_Date="2024-03-03",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "activity_treatment_function_code": "110",
            "current_pathway_period_start_date": date(2024, 3, 2),
            "priority_type_code": "urgent",
            "pseudo_organisation_code_patient_pathway_identifier_issuer": to_hex(
                sha256_digest(1)
            ),
            "pseudo_patient_pathway_identifier": to_hex(sha256_digest(1)),
            "pseudo_referral_identifier": to_hex(sha256_digest(1)),
            "referral_request_received_date": date(2023, 2, 1),
            "referral_to_treatment_period_end_date": None,
            "referral_to_treatment_period_start_date": date(2024, 3, 2),
            "source_of_referral": "",
            "waiting_list_type": "IRTT",
            "week_ending_date": date(2024, 3, 3),
        }
    ]


def test_registered_tests_are_exhaustive():
    missing = [
        name for name, table in get_all_tables() if table not in REGISTERED_TABLES
    ]
    assert not missing, f"No tests for tables: {', '.join(missing)}"


def get_all_tables():
    for module in [tpp, tpp_raw]:
        for name, table in get_tables_from_namespace(module):
            yield f"{module.__name__}.{name}", table


# Where queries involve joins with temporary tables on string columns we need to ensure
# the collations of the columns are consistent or MSSQL will error. Special care must be
# taken with columns which don't have the default collation so we test each of those
# individually below.
@pytest.mark.parametrize(
    "table,column,values,factory",
    [
        (
            tpp.clinical_events,
            tpp.clinical_events.ctv3_code,
            ["abc00", "abc01", "abc02", "abc03"],
            lambda patient_id, value: [
                CodedEvent(Patient_ID=patient_id, CTV3Code=value)
            ],
        ),
        (
            tpp.clinical_events,
            tpp.clinical_events.snomedct_code,
            ["123000", "123001", "123002", "123003"],
            lambda patient_id, value: [
                CodedEvent_SNOMED(Patient_ID=patient_id, ConceptId=value)
            ],
        ),
        (
            tpp.medications,
            tpp.medications.dmd_code,
            ["123000", "123001", "123002", "123003"],
            lambda patient_id, value: [
                MedicationDictionary(MultilexDrug_ID=f";{value};", DMD_ID=value),
                MedicationIssue(Patient_ID=patient_id, MultilexDrug_ID=f";{value};"),
            ],
        ),
        (
            tpp.open_prompt,
            tpp.open_prompt.ctv3_code,
            ["abc00", "abc01", "abc02", "abc03"],
            lambda patient_id, value: [
                OpenPROMPT(Patient_ID=patient_id, CTV3Code=value)
            ],
        ),
        (
            tpp.open_prompt,
            tpp.open_prompt.snomedct_code,
            ["123000", "123001", "123002", "123003"],
            lambda patient_id, value: [
                OpenPROMPT(Patient_ID=patient_id, ConceptId=value, CodeSystemId=0)
            ],
        ),
    ],
)
def test_is_in_queries_on_columns_with_nonstandard_collation(
    mssql_engine, table, column, values, factory
):
    # Assign a patient ID to each value
    patient_values = list(enumerate(values, start=1))
    # Create patient data for each of the values
    mssql_engine.setup(
        [factory(patient_id, value) for patient_id, value in patient_values]
    )
    # Choose every other value to match against (so we have a mixture of matching and
    # non-matching patients)
    matching_values = values[::2]

    dataset = create_dataset()
    dataset.define_population(table.exists_for_patient())
    dataset.matches = table.where(column.is_in(matching_values)).exists_for_patient()
    results = mssql_engine.extract(
        dataset,
        # Configure query engine to always break out lists into temporary tables so we
        # exercise that code path
        config={"EHRQL_MAX_MULTIVALUE_PARAM_LENGTH": 1},
        backend=TPPBackend(
            config={"TEMP_DATABASE_NAME": "temp_tables"},
        ),
    )

    # Check that the expected patients match
    assert results == [
        {"patient_id": patient_id, "matches": value in matching_values}
        for patient_id, value in patient_values
    ]


@pytest.mark.parametrize(
    "suffix,expected",
    [
        (
            "?opensafely_include_t1oo=false",
            [
                (1, 2001),
                (4, 2004),
            ],
        ),
        (
            "?opensafely_include_t1oo=true",
            [
                (1, 2001),
                (2, 2002),
                (3, 2003),
                (4, 2004),
            ],
        ),
    ],
)
def test_t1oo_patients_excluded_as_specified(mssql_database, suffix, expected):
    mssql_database.setup(
        Patient(Patient_ID=1, DateOfBirth=date(2001, 1, 1)),
        Patient(Patient_ID=2, DateOfBirth=date(2002, 1, 1)),
        Patient(Patient_ID=3, DateOfBirth=date(2003, 1, 1)),
        Patient(Patient_ID=4, DateOfBirth=date(2004, 1, 1)),
        PatientsWithTypeOneDissent(Patient_ID=2),
        PatientsWithTypeOneDissent(Patient_ID=3),
    )

    dataset = create_dataset()
    dataset.define_population(tpp.patients.date_of_birth.is_not_null())
    dataset.birth_year = tpp.patients.date_of_birth.year

    backend = TPPBackend()
    query_engine = backend.query_engine_class(
        mssql_database.host_url() + suffix,
        backend=backend,
    )
    results = query_engine.get_results(compile(dataset))

    assert list(results) == expected
