import hashlib
from datetime import date

import pytest
import sqlalchemy

from ehrql import create_dataset
from ehrql.backends.tpp import TPPBackend
from ehrql.query_engines.mssql_dialect import SelectStarInto
from ehrql.tables import tpp
from ehrql.tables.raw import tpp as tpp_raw
from tests.lib.tpp_schema import (
    APCS,
    APCS_ARCHIVED,
    EC,
    EC_ARCHIVED,
    OPA,
    OPA_ARCHIVED,
    UKRR,
    APCS_Cost,
    APCS_Cost_ARCHIVED,
    APCS_Cost_JRC20231009_LastFilesToContainAllHistoricalCostData,
    APCS_Der,
    APCS_Der_ARCHIVED,
    APCS_JRC20231009_LastFilesToContainAllHistoricalCostData,
    Appointment,
    CodedEvent,
    CodedEvent_SNOMED,
    CodedEventRange,
    CustomMedicationDictionary,
    DecisionSupportValue,
    DecisionSupportValueReference,
    EC_Cost,
    EC_Cost_ARCHIVED,
    EC_Diagnosis,
    EC_Diagnosis_ARCHIVED,
    HealthCareWorker,
    Household,
    HouseholdMember,
    ISARIC_New,
    MedicationDictionary,
    MedicationIssue,
    ONS_Deaths,
    OPA_Cost,
    OPA_Cost_ARCHIVED,
    OPA_Diag,
    OPA_Diag_ARCHIVED,
    OPA_Proc,
    OPA_Proc_ARCHIVED,
    OpenPROMPT,
    Organisation,
    Patient,
    PatientAddress,
    PatientsWithTypeOneDissent,
    PotentialCareHomeAddress,
    RegistrationHistory,
    Relationship,
    SGSS_AllTests_Negative,
    SGSS_AllTests_Positive,
    Therapeutics,
    Vaccination,
    VaccinationReference,
    WL_ClockStops,
    WL_OpenPathways,
)

from .helpers import (
    assert_tests_exhaustive,
    assert_types_correct,
    get_all_backend_columns,
    register_test_for,
)


def test_backend_columns_have_correct_types(mssql_database):
    columns_with_types = get_all_backend_columns_with_types(mssql_database)
    assert_types_correct(columns_with_types, mssql_database)


def get_all_backend_columns_with_types(mssql_database):
    """
    For every column on every table we expose in the backend, yield the SQLAlchemy type
    instance we expect to use for that column together with the type information that
    database has for that column so we can check they're compatible
    """
    table_names = set()
    column_types = {}
    queries = []
    backend = TPPBackend(config={"TEMP_DATABASE_NAME": "temp_tables"})
    for table, columns in get_all_backend_columns(backend):
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


@register_test_for(tpp.addresses)
def test_addresses(select_all_tpp):
    results = select_all_tpp(
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
def test_apcs(select_all_tpp):
    results = select_all_tpp(
        APCS(
            Patient_ID=1,
            APCS_Ident=1,
            Admission_Date=date(2023, 1, 1),
            Discharge_Date=date(2023, 2, 1),
            Discharge_Destination="19",
            Discharge_Method="1",
            Spell_Core_HRG_SUS="XXX",
            Der_Diagnosis_All="||E119 ,E780 ,J849 ||I801 ,I802 ,N179",
            Der_Procedure_All="||E851,T124,X403||Y532,Z921",
            Admission_Method="1A",
            Patient_Classification="X",
            Der_Activity_Month="202301",
        ),
        APCS_Der(
            APCS_Ident=1,
            Spell_PbR_CC_Day="5",
            Spell_Primary_Diagnosis="A1",
            Spell_Secondary_Diagnosis="B1",
        ),
        # Appears in both current and archived tables
        APCS(
            Patient_ID=1,
            APCS_Ident=2,
            Admission_Date=date(2022, 6, 1),
            Discharge_Date=date(2022, 7, 1),
            Der_Activity_Month="202206",
        ),
        APCS_Der(
            APCS_Ident=2,
            Spell_PbR_CC_Day="2",
        ),
        APCS_ARCHIVED(
            Patient_ID=1,
            APCS_Ident=2,
            Admission_Date=date(2022, 6, 1),
            Discharge_Date=date(2022, 7, 1),
            Der_Activity_Month="202206",
        ),
        APCS_Der_ARCHIVED(
            APCS_Ident=2,
            Spell_PbR_CC_Day="2",
        ),
        # NULL dated entry in current table (should not be included)
        APCS(
            Patient_ID=1,
            APCS_Ident=3,
            Admission_Date=date(2021, 2, 28),
            Discharge_Date=date(2021, 3, 1),
            Der_Activity_Month=None,
        ),
        APCS_Der(
            APCS_Ident=3,
            Spell_PbR_CC_Day="3",
        ),
        # Appears in archive only
        APCS_ARCHIVED(
            Patient_ID=1,
            APCS_Ident=4,
            Admission_Date=date(2021, 4, 1),
            Discharge_Date=date(2021, 5, 1),
            Der_Activity_Month="202104",
        ),
        APCS_Der_ARCHIVED(
            APCS_Ident=4,
            Spell_PbR_CC_Day="4",
        ),
        # NULL dated entry in archive table (should not be included)
        APCS_ARCHIVED(
            Patient_ID=1,
            APCS_Ident=5,
            Admission_Date=date(2022, 4, 1),
            Discharge_Date=date(2022, 5, 1),
            Der_Activity_Month=None,
        ),
        APCS_Der_ARCHIVED(
            APCS_Ident=5,
            Spell_PbR_CC_Day="5",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "apcs_ident": 1,
            "admission_date": date(2023, 1, 1),
            "discharge_date": date(2023, 2, 1),
            "discharge_destination": "19",
            "discharge_method": "1",
            "spell_core_hrg_sus": "XXX",
            "all_diagnoses": "||E119 ,E780 ,J849 ||I801 ,I802 ,N179",
            "all_procedures": "||E851,T124,X403||Y532,Z921",
            "admission_method": "1A",
            "patient_classification": "X",
            "days_in_critical_care": 5,
            "primary_diagnosis": "A1",
            "secondary_diagnosis": "B1",
        },
        {
            "patient_id": 1,
            "apcs_ident": 2,
            "admission_date": date(2022, 6, 1),
            "discharge_date": date(2022, 7, 1),
            "discharge_destination": None,
            "discharge_method": None,
            "spell_core_hrg_sus": None,
            "all_diagnoses": None,
            "all_procedures": None,
            "admission_method": None,
            "patient_classification": None,
            "days_in_critical_care": 2,
            "primary_diagnosis": None,
            "secondary_diagnosis": None,
        },
        {
            "patient_id": 1,
            "apcs_ident": 4,
            "admission_date": date(2021, 4, 1),
            "discharge_date": date(2021, 5, 1),
            "discharge_destination": None,
            "discharge_method": None,
            "spell_core_hrg_sus": None,
            "all_diagnoses": None,
            "all_procedures": None,
            "admission_method": None,
            "patient_classification": None,
            "days_in_critical_care": 4,
            "primary_diagnosis": None,
            "secondary_diagnosis": None,
        },
    ]


@register_test_for(tpp.apcs_cost)
def test_apcs_cost(select_all_tpp):
    results = select_all_tpp(
        APCS(
            APCS_Ident=1,
            Admission_Date=date(2023, 1, 1),
            Discharge_Date=date(2023, 2, 1),
            Der_Activity_Month="202301",
        ),
        APCS_Cost(
            Patient_ID=1,
            APCS_Ident=1,
            Grand_Total_Payment_MFF=1.1,
            Tariff_Initial_Amount=2.2,
            Tariff_Total_Payment=3.3,
        ),
        # Appears in both current and archived tables
        APCS(
            APCS_Ident=2,
            Admission_Date=date(2022, 6, 1),
            Discharge_Date=date(2022, 7, 1),
            Der_Activity_Month="202207",
        ),
        APCS_Cost(
            Patient_ID=1,
            APCS_Ident=2,
            Tariff_Total_Payment=3.0,
        ),
        APCS_ARCHIVED(
            APCS_Ident=2,
            Admission_Date=date(2022, 6, 1),
            Discharge_Date=date(2022, 7, 1),
            Der_Activity_Month="202207",
        ),
        APCS_Cost_ARCHIVED(
            Patient_ID=1,
            APCS_Ident=2,
            Tariff_Total_Payment=3.0,
        ),
        # Appears in archive only
        APCS_ARCHIVED(
            APCS_Ident=3,
            Admission_Date=date(2021, 4, 1),
            Discharge_Date=date(2021, 5, 1),
            Der_Activity_Month="202104",
        ),
        APCS_Cost_ARCHIVED(
            Patient_ID=1,
            APCS_Ident=3,
            Tariff_Total_Payment=4.0,
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
        {
            "patient_id": 1,
            "apcs_ident": 2,
            "grand_total_payment_mff": None,
            "tariff_initial_amount": None,
            "tariff_total_payment": 3.0,
            "admission_date": date(2022, 6, 1),
            "discharge_date": date(2022, 7, 1),
        },
        {
            "patient_id": 1,
            "apcs_ident": 3,
            "grand_total_payment_mff": None,
            "tariff_initial_amount": None,
            "tariff_total_payment": 4.0,
            "admission_date": date(2021, 4, 1),
            "discharge_date": date(2021, 5, 1),
        },
    ]


@register_test_for(tpp_raw.apcs_historical)
def test_apcs_historical(select_all_tpp):
    results = select_all_tpp(
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
def test_apcs_cost_historical(select_all_tpp):
    results = select_all_tpp(
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
def test_appointments(select_all_tpp):
    results = select_all_tpp(
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
def test_clinical_events(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        CodedEvent(
            Patient_ID=1,
            ConsultationDate="2020-10-20T14:30:05",
            CTV3Code="xyz",
            NumericValue=0.5,
            Consultation_ID=1234,
        ),
        CodedEvent_SNOMED(
            Patient_ID=1,
            ConsultationDate="2020-11-21T09:30:00",
            ConceptId="ijk",
            NumericValue=1.5,
            Consultation_ID=1234,
        ),
        CodedEvent_SNOMED(
            Patient_ID=1,
            ConsultationDate="9999-12-31T00:00:00",
            ConceptId="lmn",
            NumericValue=0,
            Consultation_ID=5678,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "date": date(2020, 10, 20),
            "snomedct_code": None,
            "ctv3_code": "xyz",
            "numeric_value": 0.5,
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2020, 11, 21),
            "snomedct_code": "ijk",
            "ctv3_code": None,
            "numeric_value": 1.5,
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": None,
            "snomedct_code": "lmn",
            "ctv3_code": None,
            "numeric_value": 0.0,
            "consultation_id": 5678,
        },
    ]


@register_test_for(tpp.clinical_events_ranges)
def test_clinical_events_ranges(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        CodedEvent(
            Patient_ID=1,
            CodedEvent_ID=1,
            ConsultationDate="2020-10-20T14:30:05",
            CTV3Code="xyz",
            NumericValue=0,
            Consultation_ID=1234,
        ),
        CodedEvent_SNOMED(
            Patient_ID=1,
            CodedEvent_ID=2,
            ConsultationDate="2020-11-21T09:30:00",
            ConceptId="ijk",
            NumericValue=1.5,
            Consultation_ID=1234,
        ),
        CodedEvent(
            Patient_ID=1,
            CodedEvent_ID=3,
            ConsultationDate="2020-12-20T14:30:05",
            CTV3Code="xyz",
            NumericValue=0,
            Consultation_ID=1234,
        ),
        CodedEvent_SNOMED(
            Patient_ID=1,
            CodedEvent_ID=4,
            ConsultationDate="2021-01-21T09:30:00",
            ConceptId="ijk",
            NumericValue=1.5,
            Consultation_ID=1234,
        ),
        CodedEvent(
            Patient_ID=1,
            CodedEvent_ID=5,
            ConsultationDate="2021-02-20T14:30:05",
            CTV3Code="xyz",
            NumericValue=0,
            Consultation_ID=1234,
        ),
        CodedEvent_SNOMED(
            Patient_ID=1,
            CodedEvent_ID=6,
            ConsultationDate="2021-03-21T09:30:00",
            ConceptId="ijk",
            NumericValue=1.5,
            Consultation_ID=1234,
        ),
        CodedEventRange(
            Patient_ID=1,
            CodedEvent_ID=1,
            Comparator=3,
            LowerBound=1,
            UpperBound=2,
        ),
        CodedEventRange(
            Patient_ID=1,
            CodedEvent_ID=2,
            Comparator=4,
            LowerBound=2,
            UpperBound=3,
        ),
        CodedEventRange(
            Patient_ID=1,
            CodedEvent_ID=3,
            Comparator=5,
            LowerBound=3,
            UpperBound=4,
        ),
        CodedEventRange(
            Patient_ID=1,
            CodedEvent_ID=4,
            Comparator=6,
            LowerBound=4,
            UpperBound=5,
        ),
        CodedEventRange(
            Patient_ID=1,
            CodedEvent_ID=5,
            Comparator=7,
            LowerBound=5,
            UpperBound=6,
        ),
        CodedEventRange(
            Patient_ID=1,
            CodedEvent_ID=6,
            Comparator=8,
            LowerBound=6,
            UpperBound=7,
        ),
    )
    expected = [
        {
            "patient_id": 1,
            "date": date(2020, 10, 20),
            "snomedct_code": None,
            "ctv3_code": "xyz",
            "numeric_value": 0.0,
            "comparator": "~",
            "lower_bound": 1.0,
            "upper_bound": 2.0,
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2020, 12, 20),
            "snomedct_code": None,
            "ctv3_code": "xyz",
            "numeric_value": 0.0,
            "comparator": ">=",
            "lower_bound": 3.0,
            "upper_bound": 4.0,
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2021, 2, 20),
            "snomedct_code": None,
            "ctv3_code": "xyz",
            "numeric_value": 0.0,
            "comparator": "<",
            "lower_bound": 5.0,
            "upper_bound": 6.0,
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2020, 11, 21),
            "snomedct_code": "ijk",
            "ctv3_code": None,
            "numeric_value": 1.5,
            "comparator": "=",
            "lower_bound": 2.0,
            "upper_bound": 3.0,
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2021, 1, 21),
            "snomedct_code": "ijk",
            "ctv3_code": None,
            "numeric_value": 1.5,
            "comparator": ">",
            "lower_bound": 4.0,
            "upper_bound": 5.0,
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2021, 3, 21),
            "snomedct_code": "ijk",
            "ctv3_code": None,
            "numeric_value": 1.5,
            "comparator": "<=",
            "lower_bound": 6.0,
            "upper_bound": 7.0,
            "consultation_id": 1234,
        },
    ]

    assert results == expected


@register_test_for(tpp.covid_therapeutics)
def test_covid_therapeutics_one_for_duplicate(select_all_tpp):
    results = select_all_tpp(
        Therapeutics(
            Patient_ID=1,
            COVID_indication="a",
            Count=3,
            CurrentStatus="b",
            Diagnosis="c",
            FormName="d",
            Intervention="e",
            CASIM05_date_of_symptom_onset="f",
            CASIM05_risk_cohort="g",
            MOL1_onset_of_symptoms="h",
            MOL1_high_risk_cohort="i",
            SOT02_onset_of_symptoms="j",
            SOT02_risk_cohorts="k",
            Received="2023-10-15T12:13:45",
            TreatmentStartDate="2023-11-16T13:45:07",
            AgeAtReceivedDate=60,
            Region="l",
            Der_LoadDate="2023-09-14 12:34:56.78000",
        ),
        Therapeutics(
            Patient_ID=1,
            COVID_indication="a",
            Count=3,
            CurrentStatus="b",
            Diagnosis="c",
            FormName="d",
            Intervention="e",
            CASIM05_date_of_symptom_onset="f",
            CASIM05_risk_cohort="g",
            MOL1_onset_of_symptoms="h",
            MOL1_high_risk_cohort="i",
            SOT02_onset_of_symptoms="j",
            SOT02_risk_cohorts="k",
            Received="2023-10-15T12:13:45",
            TreatmentStartDate="2023-11-16T13:45:07",
            AgeAtReceivedDate=60,
            Region="l",
            Der_LoadDate="2023-09-14 12:34:56.78000",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "covid_indication": "a",
            "current_status": "b",
            "intervention": "e",
            "received": date(2023, 10, 15),
            "region": "l",
            "risk_cohort": "g,i,k",
            "treatment_start_date": date(2023, 11, 16),
        },
    ]


@register_test_for(tpp.covid_therapeutics)
def test_covid_therapeutics_risk_cohort_aggregation(select_all_tpp):
    results = select_all_tpp(
        Therapeutics(
            Patient_ID=1,
            CASIM05_risk_cohort="Patients with a haematological diseases and liver disease",
        ),
        Therapeutics(
            Patient_ID=2,
            MOL1_high_risk_cohort="Solid cancer",
        ),
        Therapeutics(
            Patient_ID=3,
            SOT02_risk_cohorts="Patients with immune deficiencies and HIV or AIDS and solid organ recipients",
        ),
    )
    assert results == [
        {
            "covid_indication": None,
            "current_status": None,
            "intervention": None,
            "patient_id": 1,
            "received": None,
            "region": None,
            "risk_cohort": "haematological diseases,liver disease",
            "treatment_start_date": None,
        },
        {
            "covid_indication": None,
            "current_status": None,
            "intervention": None,
            "patient_id": 2,
            "received": None,
            "region": None,
            "risk_cohort": "Solid cancer",
            "treatment_start_date": None,
        },
        {
            "covid_indication": None,
            "current_status": None,
            "intervention": None,
            "patient_id": 3,
            "received": None,
            "region": None,
            "risk_cohort": "immune deficiencies,HIV or AIDS,solid organ recipients",
            "treatment_start_date": None,
        },
    ]


@register_test_for(tpp_raw.covid_therapeutics_raw)
def test_covid_therapeutics_raw(select_all_tpp):
    results = select_all_tpp(
        Therapeutics(
            Patient_ID=1,
            COVID_indication="a",
            Count=3,
            CurrentStatus="b",
            Diagnosis="c",
            FormName="d",
            Intervention="e",
            CASIM05_date_of_symptom_onset="f",
            CASIM05_risk_cohort="g",
            MOL1_onset_of_symptoms="h",
            MOL1_high_risk_cohort="i",
            SOT02_onset_of_symptoms="j",
            SOT02_risk_cohorts="k",
            Received="2023-10-15T12:13:45",
            TreatmentStartDate="2023-11-16T13:45:07",
            AgeAtReceivedDate=60,
            Region="l",
            Der_LoadDate="2023-09-14 12:34:56.78000",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "covid_indication": "a",
            "count": 3,
            "current_status": "b",
            "diagnosis": "c",
            "form_name": "d",
            "intervention": "e",
            "CASIM05_risk_cohort": "g",
            "MOL1_high_risk_cohort": "i",
            "SOT02_risk_cohorts": "k",
            "received": date(2023, 10, 15),
            "treatment_start_date": date(2023, 11, 16),
            "age_at_received_date": 60,
            "region": "l",
            "load_date": date(2023, 9, 14),
        },
    ]


@register_test_for(tpp.decision_support_values)
def test_decision_support_values(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        DecisionSupportValueReference(
            AlgorithmDescription="UK Electronic Frailty Index (eFI)",
            AlgorithmSourceLink="link",
            AlgorithmType=1,
            AlgorithmVersion="1.0",
        ),
        DecisionSupportValue(
            Patient_ID=1,
            AlgorithmType=1,
            CalculationDateTime="2010-01-01T10:00:00",
            NumericValue=37.5,
        ),
        DecisionSupportValue(
            Patient_ID=1,
            AlgorithmType=1,
            CalculationDateTime="2011-01-01T10:00:00",
            NumericValue=40.5,
        ),
        DecisionSupportValue(
            Patient_ID=1,
            AlgorithmType=1,
            CalculationDateTime="2012-01-01T10:00:00",
            NumericValue=45.0,
        ),
        DecisionSupportValue(
            Patient_ID=1,
            AlgorithmType=1,
            CalculationDateTime="2013-01-01T10:00:00",
            NumericValue=47.0,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "calculation_date": date(2010, 1, 1),
            "numeric_value": 37.5,
            "algorithm_description": "UK Electronic Frailty Index (eFI)",
            "algorithm_version": "1.0",
        },
        {
            "patient_id": 1,
            "calculation_date": date(2011, 1, 1),
            "numeric_value": 40.5,
            "algorithm_description": "UK Electronic Frailty Index (eFI)",
            "algorithm_version": "1.0",
        },
        {
            "patient_id": 1,
            "calculation_date": date(2012, 1, 1),
            "numeric_value": 45.0,
            "algorithm_description": "UK Electronic Frailty Index (eFI)",
            "algorithm_version": "1.0",
        },
        {
            "patient_id": 1,
            "calculation_date": date(2013, 1, 1),
            "numeric_value": 47.0,
            "algorithm_description": "UK Electronic Frailty Index (eFI)",
            "algorithm_version": "1.0",
        },
    ]


@register_test_for(tpp.ec)
def test_ec(select_all_tpp):
    results = select_all_tpp(
        EC(
            Patient_ID=1,
            EC_Ident=1,
            Arrival_Date=date(2023, 1, 1),
            SUS_HRG_Code="XXX",
            Der_Activity_Month="202301",
        ),
        # In both current and archive
        EC(
            Patient_ID=1,
            EC_Ident=2,
            Arrival_Date=date(2022, 6, 1),
            SUS_HRG_Code="XYZ",
            Der_Activity_Month="202206",
        ),
        EC_ARCHIVED(
            Patient_ID=1,
            EC_Ident=2,
            Arrival_Date=date(2022, 6, 1),
            SUS_HRG_Code="XYZ",
            Der_Activity_Month="202206",
        ),
        # Archive only
        EC_ARCHIVED(
            Patient_ID=1,
            EC_Ident=3,
            Arrival_Date=date(2021, 7, 1),
            SUS_HRG_Code="ABC",
            Der_Activity_Month="202107",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "ec_ident": 1,
            "arrival_date": date(2023, 1, 1),
            "sus_hrg_code": "XXX",
        },
        {
            "patient_id": 1,
            "ec_ident": 2,
            "arrival_date": date(2022, 6, 1),
            "sus_hrg_code": "XYZ",
        },
        {
            "patient_id": 1,
            "ec_ident": 3,
            "arrival_date": date(2021, 7, 1),
            "sus_hrg_code": "ABC",
        },
    ]


@register_test_for(tpp.ec_cost)
def test_ec_cost(select_all_tpp):
    results = select_all_tpp(
        EC(
            EC_Ident=1,
            Arrival_Date=date(2023, 1, 2),
            EC_Decision_To_Admit_Date=date(2023, 1, 3),
            EC_Injury_Date=date(2023, 1, 1),
            Der_Activity_Month="202301",
        ),
        EC_Cost(
            Patient_ID=1,
            EC_Ident=1,
            Grand_Total_Payment_MFF=1.1,
            Tariff_Total_Payment=2.2,
        ),
        # In both current and archive
        EC(
            EC_Ident=2,
            Arrival_Date=date(2022, 6, 1),
            Der_Activity_Month="202206",
        ),
        EC_Cost(
            Patient_ID=1,
            EC_Ident=2,
            Tariff_Total_Payment=2.0,
        ),
        EC_ARCHIVED(
            EC_Ident=2,
            Arrival_Date=date(2022, 6, 1),
            Der_Activity_Month="202206",
        ),
        EC_Cost_ARCHIVED(
            Patient_ID=1,
            EC_Ident=2,
            Tariff_Total_Payment=2.0,
        ),
        # Archive only
        EC_ARCHIVED(
            EC_Ident=3,
            Arrival_Date=date(2021, 5, 1),
            Der_Activity_Month="202105",
        ),
        EC_Cost_ARCHIVED(
            Patient_ID=1,
            EC_Ident=3,
            Tariff_Total_Payment=3.0,
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
        {
            "patient_id": 1,
            "ec_ident": 2,
            "grand_total_payment_mff": None,
            "tariff_total_payment": 2.0,
            "arrival_date": date(2022, 6, 1),
            "ec_decision_to_admit_date": None,
            "ec_injury_date": None,
        },
        {
            "patient_id": 1,
            "ec_ident": 3,
            "grand_total_payment_mff": None,
            "tariff_total_payment": 3.0,
            "arrival_date": date(2021, 5, 1),
            "ec_decision_to_admit_date": None,
            "ec_injury_date": None,
        },
    ]


@register_test_for(tpp.emergency_care_attendances)
def test_emergency_care_attendances(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        EC(
            Patient_ID=1,
            EC_Ident=2,
            Arrival_Date="2023-01-01",
            Discharge_Destination_SNOMED_CT="abc",
            Der_Activity_Month="202301",
        ),
        EC_Diagnosis(EC_Ident=2, EC_Diagnosis_01="def", EC_Diagnosis_02="xyz"),
        # In both current and archive
        EC(
            Patient_ID=1,
            EC_Ident=3,
            Arrival_Date="2022-04-01",
            Discharge_Destination_SNOMED_CT="ghi",
            Der_Activity_Month="202204",
        ),
        EC_Diagnosis(EC_Ident=3, EC_Diagnosis_01="jkl"),
        EC_ARCHIVED(
            Patient_ID=1,
            EC_Ident=3,
            Arrival_Date="2022-04-01",
            Discharge_Destination_SNOMED_CT="ghi",
            Der_Activity_Month="202204",
        ),
        EC_Diagnosis_ARCHIVED(EC_Ident=3, EC_Diagnosis_01="jkl"),
        # Archive only
        EC_ARCHIVED(
            Patient_ID=1,
            EC_Ident=4,
            Arrival_Date="2021-01-01",
            Discharge_Destination_SNOMED_CT="mno",
            Der_Activity_Month="202101",
        ),
        EC_Diagnosis_ARCHIVED(EC_Ident=4, EC_Diagnosis_01="pqr"),
    )
    assert results == [
        {
            "patient_id": 1,
            "id": 2,
            "arrival_date": date(2023, 1, 1),
            "discharge_destination": "abc",
            "diagnosis_01": "def",
            "diagnosis_02": "xyz",
            "diagnosis_03": None,
            **{f"diagnosis_{i:02d}": None for i in range(4, 25)},
        },
        {
            "patient_id": 1,
            "id": 3,
            "arrival_date": date(2022, 4, 1),
            "discharge_destination": "ghi",
            "diagnosis_01": "jkl",
            "diagnosis_02": None,
            **{f"diagnosis_{i:02d}": None for i in range(3, 25)},
        },
        {
            "patient_id": 1,
            "id": 4,
            "arrival_date": date(2021, 1, 1),
            "discharge_destination": "mno",
            "diagnosis_01": "pqr",
            "diagnosis_02": None,
            **{f"diagnosis_{i:02d}": None for i in range(3, 25)},
        },
    ]


@register_test_for(tpp.ethnicity_from_sus)
def test_ethnicity_from_sus(select_all_tpp):
    items = [
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
        # patient 5-7; codes in archive from before cutoff date are counted
        EC_ARCHIVED(Patient_ID=5, Ethnic_Category="A", Der_Activity_Month="202101"),
        APCS_ARCHIVED(Patient_ID=6, Ethnic_Group="B", Der_Activity_Month="202101"),
        OPA_ARCHIVED(Patient_ID=7, Ethnic_Category="C", Der_Activity_Month="202101"),
        # patient 8; codes in archive after cutoff date are not double-counted
        EC(Patient_ID=8, Ethnic_Category="A"),
        EC_ARCHIVED(Patient_ID=8, Ethnic_Category="A", Der_Activity_Month="202301"),
        EC(Patient_ID=8, Ethnic_Category="A"),
        EC_ARCHIVED(Patient_ID=8, Ethnic_Category="A", Der_Activity_Month="202301"),
        APCS(Patient_ID=8, Ethnic_Group="B"),
        APCS(Patient_ID=8, Ethnic_Group="B"),
        APCS(Patient_ID=8, Ethnic_Group="B"),
    ]
    # This column needs to be set for the current/archive table paritioning; but it's
    # irrelevant to most of the test cases
    for item in items:
        if not item.Der_Activity_Month:
            item.Der_Activity_Month = "202401"
    results = select_all_tpp(*items)
    assert results == [
        {"patient_id": 1, "code": "B"},
        {"patient_id": 2, "code": "G"},
        {"patient_id": 3, "code": "E"},
        {"patient_id": 5, "code": "A"},
        {"patient_id": 6, "code": "B"},
        {"patient_id": 7, "code": "C"},
        {"patient_id": 8, "code": "B"},
    ]


@register_test_for(tpp.household_memberships_2020)
def test_household_memberships_2020(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        Patient(Patient_ID=2),
        Household(
            Household_ID=123,
            HouseholdSize=5,
        ),
        HouseholdMember(
            Patient_ID=1,
            Household_ID=123,
        ),
        Household(
            Household_ID=0,
            HouseholdSize=0,
        ),
        HouseholdMember(
            Patient_ID=2,
            Household_ID=0,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "household_pseudo_id": 123,
            "household_size": 5,
        },
        {
            "patient_id": 2,
            "household_pseudo_id": None,
            "household_size": None,
        },
    ]


@register_test_for(tpp_raw.isaric)
def test_isaric_raw_dates(select_all_tpp):
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
    results = select_all_tpp(
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
def test_isaric_raw_clinical_variables(select_all_tpp):
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
    results = select_all_tpp(
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
def test_medications(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        # MedicationIssue.MultilexDrug_ID found in MedicationDictionary only
        MedicationDictionary(MultilexDrug_ID="0;0;0", DMD_ID="100000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-15T10:10:10",
            Consultation_ID=1234,
            MultilexDrug_ID="0;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in CustomMedicationDictionary only
        CustomMedicationDictionary(MultilexDrug_ID="2;0;0", DMD_ID="200000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-16T10:10:10",
            Consultation_ID=1234,
            MultilexDrug_ID="2;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in both; MedicationDictionary
        # preferred
        MedicationDictionary(MultilexDrug_ID="3;0;0", DMD_ID="300000"),
        CustomMedicationDictionary(MultilexDrug_ID="3;0;0", DMD_ID="400000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-17T10:10:10",
            Consultation_ID=1234,
            MultilexDrug_ID="3;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in both, but MedicationDictionary.DMD_ID
        # contains the empty string; CustomMedicationDictionary.DMD_ID preferred
        MedicationDictionary(MultilexDrug_ID="5;0;0", DMD_ID=""),
        CustomMedicationDictionary(MultilexDrug_ID="5;0;0", DMD_ID="500000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-18T10:10:10",
            Consultation_ID=1234,
            MultilexDrug_ID="5;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in MedicationDictionary but DMD_ID
        # contains the empty string; dmd_code is NULL not empty string
        MedicationDictionary(MultilexDrug_ID="6;0;0", DMD_ID=""),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-19T10:10:10",
            Consultation_ID=1234,
            MultilexDrug_ID="6;0;0",
        ),
        # MedicationIssue.MultilexDrug_ID found in both, but MedicationDictionary.DMD_ID
        # is "MULTIPLE_DMD_MAPPING"; CustomMedicationDictionary.DMD_ID preferred
        MedicationDictionary(MultilexDrug_ID="7;0;0", DMD_ID="MULTIPLE_DMD_MAPPING"),
        CustomMedicationDictionary(MultilexDrug_ID="7;0;0", DMD_ID="700000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-20T10:10:10",
            Consultation_ID=1234,
            MultilexDrug_ID="7;0;0",
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "date": date(2020, 5, 15),
            "dmd_code": "100000",
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 16),
            "dmd_code": "200000",
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 17),
            "dmd_code": "300000",
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 18),
            "dmd_code": "500000",
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 19),
            "dmd_code": None,
            "consultation_id": 1234,
        },
        {
            "patient_id": 1,
            "date": date(2020, 5, 20),
            "dmd_code": "700000",
            "consultation_id": 1234,
        },
    ]


@register_test_for(tpp_raw.medications)
def test_medications_raw(select_all_tpp):
    results = select_all_tpp(
        # MedicationIssue.MultilexDrug_ID found in MedicationDictionary only
        MedicationDictionary(MultilexDrug_ID="0;0;0", DMD_ID="100000"),
        MedicationIssue(
            Patient_ID=1,
            ConsultationDate="2020-05-15T10:10:10",
            MultilexDrug_ID="0;0;0",
            Consultation_ID=1234,
            MedicationStatus=1,
        ),
    )
    assert results == [
        {
            "patient_id": 1,
            "date": date(2020, 5, 15),
            "dmd_code": "100000",
            "consultation_id": 1234,
            "medication_status": 1,
        },
    ]


@register_test_for(tpp.occupation_on_covid_vaccine_record)
def test_occupation_on_covid_vaccine_record(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        HealthCareWorker(Patient_ID=1),
    )
    assert results == [{"patient_id": 1, "is_healthcare_worker": True}]


@register_test_for(tpp_raw.ons_deaths)
def test_ons_deaths_raw(select_all_tpp):
    results = select_all_tpp(
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
def test_ons_deaths(select_all_tpp):
    results = select_all_tpp(
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
def test_opa(select_all_tpp):
    results = select_all_tpp(
        OPA(
            Patient_ID=1,
            OPA_Ident=1,
            Appointment_Date=date(2023, 2, 1),
            Attendance_Status="1",
            Consultation_Medium_Used="02",
            First_Attendance="3",
            HRG_Code="XXX",
            Treatment_Function_Code="999",
            Der_Activity_Month="202302",
        ),
        # In both current and archive
        OPA(
            Patient_ID=1,
            OPA_Ident=2,
            Appointment_Date=date(2022, 5, 1),
            Der_Activity_Month="202205",
        ),
        OPA_ARCHIVED(
            Patient_ID=1,
            OPA_Ident=2,
            Appointment_Date=date(2022, 5, 1),
            Der_Activity_Month="202205",
        ),
        # In archive only
        OPA_ARCHIVED(
            Patient_ID=1,
            OPA_Ident=3,
            Appointment_Date=date(2021, 1, 1),
            Der_Activity_Month="202101",
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
        {
            "patient_id": 1,
            "opa_ident": 2,
            "appointment_date": date(2022, 5, 1),
            "attendance_status": None,
            "consultation_medium_used": None,
            "first_attendance": None,
            "hrg_code": None,
            "treatment_function_code": None,
        },
        {
            "patient_id": 1,
            "opa_ident": 3,
            "appointment_date": date(2021, 1, 1),
            "attendance_status": None,
            "consultation_medium_used": None,
            "first_attendance": None,
            "hrg_code": None,
            "treatment_function_code": None,
        },
    ]


@register_test_for(tpp.opa_cost)
def test_opa_cost(select_all_tpp):
    results = select_all_tpp(
        OPA(
            OPA_Ident=1,
            Appointment_Date=date(2023, 2, 1),
            Referral_Request_Received_Date=date(2023, 1, 1),
            Der_Activity_Month="202301",
        ),
        OPA_Cost(
            Patient_ID=1,
            OPA_Ident=1,
            Tariff_OPP=1.1,
            Grand_Total_Payment_MFF=2.2,
            Tariff_Total_Payment=3.3,
        ),
        # In both current and archive
        OPA(
            OPA_Ident=2,
            Appointment_Date=date(2022, 4, 1),
            Der_Activity_Month="202204",
        ),
        OPA_Cost(
            Patient_ID=1,
            OPA_Ident=2,
            Tariff_OPP=2.0,
        ),
        OPA_ARCHIVED(
            OPA_Ident=2,
            Appointment_Date=date(2022, 4, 1),
            Der_Activity_Month="202204",
        ),
        OPA_Cost_ARCHIVED(
            Patient_ID=1,
            OPA_Ident=2,
            Tariff_OPP=2.0,
        ),
        # In archive only
        OPA_ARCHIVED(
            OPA_Ident=3,
            Appointment_Date=date(2021, 4, 1),
            Der_Activity_Month="202104",
        ),
        OPA_Cost_ARCHIVED(
            Patient_ID=1,
            OPA_Ident=3,
            Tariff_OPP=3.0,
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
        {
            "patient_id": 1,
            "opa_ident": 2,
            "tariff_opp": 2.0,
            "appointment_date": date(2022, 4, 1),
            "grand_total_payment_mff": None,
            "tariff_total_payment": None,
            "referral_request_received_date": None,
        },
        {
            "patient_id": 1,
            "opa_ident": 3,
            "tariff_opp": 3.0,
            "appointment_date": date(2021, 4, 1),
            "grand_total_payment_mff": None,
            "tariff_total_payment": None,
            "referral_request_received_date": None,
        },
    ]


@register_test_for(tpp.opa_diag)
def test_opa_diag(select_all_tpp):
    results = select_all_tpp(
        OPA(
            OPA_Ident=1,
            Appointment_Date=date(2023, 2, 1),
            Referral_Request_Received_Date=date(2023, 1, 1),
            Der_Activity_Month="202301",
        ),
        OPA_Diag(
            Patient_ID=1,
            OPA_Ident=1,
            Primary_Diagnosis_Code="100000",
            Primary_Diagnosis_Code_Read="Y0000",
            Secondary_Diagnosis_Code_1="100000",
            Secondary_Diagnosis_Code_1_Read="Y0000",
        ),
        # In both current and archive
        OPA(
            OPA_Ident=2,
            Appointment_Date=date(2022, 4, 1),
            Der_Activity_Month="202204",
        ),
        OPA_Diag(
            Patient_ID=1,
            OPA_Ident=2,
            Primary_Diagnosis_Code="200000",
        ),
        OPA_ARCHIVED(
            OPA_Ident=2,
            Appointment_Date=date(2022, 4, 1),
            Der_Activity_Month="202204",
        ),
        OPA_Diag_ARCHIVED(
            Patient_ID=1,
            OPA_Ident=2,
            Primary_Diagnosis_Code="200000",
        ),
        # In archive only
        OPA_ARCHIVED(
            OPA_Ident=3,
            Appointment_Date=date(2021, 4, 1),
            Der_Activity_Month="202104",
        ),
        OPA_Diag_ARCHIVED(
            Patient_ID=1,
            OPA_Ident=3,
            Primary_Diagnosis_Code="300000",
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
        {
            "patient_id": 1,
            "opa_ident": 2,
            "appointment_date": date(2022, 4, 1),
            "primary_diagnosis_code": "200000",
            "primary_diagnosis_code_read": None,
            "secondary_diagnosis_code_1": None,
            "secondary_diagnosis_code_1_read": None,
            "referral_request_received_date": None,
        },
        {
            "patient_id": 1,
            "opa_ident": 3,
            "appointment_date": date(2021, 4, 1),
            "primary_diagnosis_code": "300000",
            "primary_diagnosis_code_read": None,
            "secondary_diagnosis_code_1": None,
            "secondary_diagnosis_code_1_read": None,
            "referral_request_received_date": None,
        },
    ]


@register_test_for(tpp.opa_proc)
def test_opa_proc(select_all_tpp):
    results = select_all_tpp(
        OPA(
            OPA_Ident=1,
            Appointment_Date=date(2023, 2, 1),
            Referral_Request_Received_Date=date(2023, 1, 1),
            Der_Activity_Month="202301",
        ),
        OPA_Proc(
            Patient_ID=1,
            OPA_Ident=1,
            Primary_Procedure_Code="100000",
            Primary_Procedure_Code_Read="Y0000",
            Procedure_Code_2="100000",
            Procedure_Code_2_Read="Y0000",
        ),
        # In both current and archive
        OPA(
            OPA_Ident=2,
            Appointment_Date=date(2022, 4, 1),
            Der_Activity_Month="202204",
        ),
        OPA_Proc(
            Patient_ID=1,
            OPA_Ident=2,
            Primary_Procedure_Code="200000",
        ),
        OPA_ARCHIVED(
            OPA_Ident=2,
            Appointment_Date=date(2022, 4, 1),
            Der_Activity_Month="202204",
        ),
        OPA_Proc_ARCHIVED(
            Patient_ID=1,
            OPA_Ident=2,
            Primary_Procedure_Code="200000",
        ),
        # In archive only
        OPA_ARCHIVED(
            OPA_Ident=3,
            Appointment_Date=date(2021, 4, 1),
            Der_Activity_Month="202104",
        ),
        OPA_Proc_ARCHIVED(
            Patient_ID=1,
            OPA_Ident=3,
            Primary_Procedure_Code="300000",
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
        {
            "patient_id": 1,
            "opa_ident": 2,
            "appointment_date": date(2022, 4, 1),
            "primary_procedure_code": "200000",
            "primary_procedure_code_read": None,
            "procedure_code_2": None,
            "procedure_code_2_read": None,
            "referral_request_received_date": None,
        },
        {
            "patient_id": 1,
            "opa_ident": 3,
            "appointment_date": date(2021, 4, 1),
            "primary_procedure_code": "300000",
            "primary_procedure_code_read": None,
            "procedure_code_2": None,
            "procedure_code_2_read": None,
            "referral_request_received_date": None,
        },
    ]


@register_test_for(tpp.open_prompt)
def test_open_prompt(select_all_tpp):
    results = select_all_tpp(
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
def test_patients(select_all_tpp):
    results = select_all_tpp(
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
def test_practice_registrations(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        Organisation(
            Organisation_ID=2,
            STPCode="abc",
            Region="def",
            GoLiveDate="2005-10-20T15:16:17",
        ),
        Organisation(
            Organisation_ID=3,
            STPCode="",
            Region="",
            GoLiveDate="2021-05-06T04:05:06",
        ),
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
            "practice_systmone_go_live_date": date(2005, 10, 20),
        },
        {
            "patient_id": 1,
            "start_date": date(2020, 1, 1),
            "end_date": None,
            "practice_pseudo_id": 3,
            "practice_stp": None,
            "practice_nuts1_region_name": None,
            "practice_systmone_go_live_date": date(2021, 5, 6),
        },
    ]


@register_test_for(tpp.sgss_covid_all_tests)
def test_sgss_covid_all_tests(select_all_tpp):
    results = select_all_tpp(
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


@register_test_for(tpp.ukrr)
def test_ukrr(select_all_tpp):
    results = select_all_tpp(
        Patient(Patient_ID=1),
        UKRR(
            Patient_ID=1,
            creat=1.0,
            dataset="2019prev",
            eGFR_ckdepi=2.0,
            mod_prev="bar",
            mod_start="foobar",
            renal_centre="The Barfoo Centre",
            rrt_start=date(2024, 10, 1),
        ),
    )
    assert results == [
        {
            "latest_creatinine": 1.0,
            "dataset": "2019_prevalence",
            "latest_egfr": 2.0,
            "treatment_modality_prevalence": "bar",
            "treatment_modality_start": "foobar",
            "patient_id": 1,
            "renal_centre": "The Barfoo Centre",
            "rrt_start_date": date(2024, 10, 1),
        },
    ]


@register_test_for(tpp.vaccinations)
def test_vaccinations(select_all_tpp):
    results = select_all_tpp(
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
def test_wl_clockstops_raw(select_all_tpp):
    results = select_all_tpp(
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
def test_wl_clockstops(select_all_tpp):
    results = select_all_tpp(
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
        # Test that unrecognised priority type codes and waiting list types are treated
        # as NULL
        WL_ClockStops(
            Patient_ID=1,
            PRIORITY_TYPE_CODE="10",
            Referral_Request_Received_Date="2024-02-01",
            Waiting_List_Type="Unrecognised",
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
        },
        {
            "patient_id": 1,
            "activity_treatment_function_code": None,
            "priority_type_code": None,
            "pseudo_organisation_code_patient_pathway_identifier_issuer": None,
            "pseudo_patient_pathway_identifier": None,
            "pseudo_referral_identifier": None,
            "referral_request_received_date": date(2024, 2, 1),
            "referral_to_treatment_period_end_date": None,
            "referral_to_treatment_period_start_date": None,
            "source_of_referral_for_outpatients": None,
            "waiting_list_type": None,
            "week_ending_date": None,
        },
    ]


@register_test_for(tpp_raw.wl_openpathways)
def test_wl_openpathways_raw(select_all_tpp):
    results = select_all_tpp(
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
def test_wl_openpathways(select_all_tpp):
    results = select_all_tpp(
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
            Waiting_List_Type="ONON",
            Week_Ending_Date="2024-03-03",
        ),
        # Test that unrecognised priority type codes and waiting list types are treated
        # as NULL
        WL_OpenPathways(
            Patient_ID=1,
            PRIORITY_TYPE_CODE="10",
            REFERRAL_REQUEST_RECEIVED_DATE="2024-02-01",
            Waiting_List_Type="Unrecognised",
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
            "waiting_list_type": "ONON",
            "week_ending_date": date(2024, 3, 3),
        },
        {
            "patient_id": 1,
            "activity_treatment_function_code": None,
            "current_pathway_period_start_date": None,
            "priority_type_code": None,
            "pseudo_organisation_code_patient_pathway_identifier_issuer": None,
            "pseudo_patient_pathway_identifier": None,
            "pseudo_referral_identifier": None,
            "referral_request_received_date": date(2024, 2, 1),
            "referral_to_treatment_period_end_date": None,
            "referral_to_treatment_period_start_date": None,
            "source_of_referral": None,
            "waiting_list_type": None,
            "week_ending_date": None,
        },
    ]


@register_test_for(tpp.parents)
def test_parents(select_all_tpp):
    fixtures, expected_results = _separate_fixtures_and_expected_results(
        ## SIMPLE HAPPY CASES: SHOULD BE RETURNED
        #
        # Mother
        Patient(Patient_ID=1, Sex="M", DateOfBirth="2020-01-01"),
        Patient(Patient_ID=2, Sex="F", DateOfBirth="1990-01-01"),
        Relationship(
            Patient_ID=1, Type_of_Relationship="Mother", Patient_ID_Relationship_With=2
        ),
        {"patient_id": 1, "mother_id": 2},
        #
        # Child
        Patient(Patient_ID=3, Sex="F", DateOfBirth="1990-01-01"),
        Patient(Patient_ID=4, Sex="F", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=3, Type_of_Relationship="Child", Patient_ID_Relationship_With=4
        ),
        {"patient_id": 4, "mother_id": 3},
        #
        # Son
        Patient(Patient_ID=5, Sex="F", DateOfBirth="1990-01-01"),
        Patient(Patient_ID=6, Sex="M", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=5, Type_of_Relationship="Son", Patient_ID_Relationship_With=6
        ),
        {"patient_id": 6, "mother_id": 5},
        #
        # Daughter
        Patient(Patient_ID=7, Sex="F", DateOfBirth="1990-01-01"),
        Patient(Patient_ID=8, Sex="F", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=7,
            Type_of_Relationship="Daughter",
            Patient_ID_Relationship_With=8,
        ),
        {"patient_id": 8, "mother_id": 7},
        #
        # Relationship recorded in both directions
        Patient(Patient_ID=9, Sex="M", DateOfBirth="2020-01-01"),
        Patient(Patient_ID=10, Sex="F", DateOfBirth="1990-01-01"),
        Relationship(
            Patient_ID=9, Type_of_Relationship="Mother", Patient_ID_Relationship_With=10
        ),
        Relationship(
            Patient_ID=10, Type_of_Relationship="Son", Patient_ID_Relationship_With=9
        ),
        {"patient_id": 9, "mother_id": 10},
        #
        ## INVALID CASES: SHOULD BE IGNORED
        #
        # Unhandled relationship type
        Patient(Patient_ID=11, Sex="F", DateOfBirth="2020-01-01"),
        Patient(Patient_ID=12, Sex="F", DateOfBirth="1990-01-01"),
        Relationship(
            Patient_ID=12,
            Type_of_Relationship="Offspring",
            Patient_ID_Relationship_With=11,
        ),
        #
        # Relationship has end date (end dates should not be present for parent/chid
        # relationships and seem to indicate a correction in the record)
        Patient(Patient_ID=13, Sex="M", DateOfBirth="2020-01-01"),
        Patient(Patient_ID=14, Sex="F", DateOfBirth="1990-01-01"),
        Relationship(
            Patient_ID=14,
            Type_of_Relationship="Son",
            Patient_ID_Relationship_With=13,
            RelationshipEndDate="2021-01-01",
        ),
        #
        # Mother's date of birth is after child's
        Patient(Patient_ID=15, Sex="F", DateOfBirth="2021-01-01"),
        Patient(Patient_ID=16, Sex="M", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=16,
            Type_of_Relationship="Mother",
            Patient_ID_Relationship_With=15,
        ),
        #
        # Parent's date of birth is after child's
        Patient(Patient_ID=17, Sex="F", DateOfBirth="2021-01-01"),
        Patient(Patient_ID=18, Sex="F", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=17, Type_of_Relationship="Child", Patient_ID_Relationship_With=18
        ),
        # Mother is recorded as male
        Patient(Patient_ID=19, Sex="M", DateOfBirth="1990-01-01"),
        Patient(Patient_ID=20, Sex="M", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=20,
            Type_of_Relationship="Mother",
            Patient_ID_Relationship_With=19,
        ),
        # Parent is recorded as male
        Patient(Patient_ID=21, Sex="M", DateOfBirth="1990-01-01"),
        Patient(Patient_ID=22, Sex="F", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=21, Type_of_Relationship="Child", Patient_ID_Relationship_With=22
        ),
        #
        # Ontologically implausible self-parentage
        Patient(Patient_ID=23, Sex="F", DateOfBirth="1990-01-01"),
        Relationship(
            Patient_ID=23,
            Type_of_Relationship="Mother",
            Patient_ID_Relationship_With=23,
        ),
        Patient(Patient_ID=24, Sex="F", DateOfBirth="1990-01-01"),
        Relationship(
            Patient_ID=24, Type_of_Relationship="Child", Patient_ID_Relationship_With=24
        ),
        #
        ## AMBIGUOUS VALID CASES: SHOULD BE IGNORED
        #
        # Multiple valid mothers
        Patient(Patient_ID=25, Sex="M", DateOfBirth="2020-01-01"),
        Patient(Patient_ID=26, Sex="F", DateOfBirth="1990-01-01"),
        Patient(Patient_ID=27, Sex="F", DateOfBirth="1991-01-01"),
        Relationship(
            Patient_ID=25,
            Type_of_Relationship="Mother",
            Patient_ID_Relationship_With=26,
        ),
        Relationship(
            Patient_ID=25,
            Type_of_Relationship="Mother",
            Patient_ID_Relationship_With=27,
        ),
        # Multiple valid parents
        Patient(Patient_ID=28, Sex="F", DateOfBirth="1990-01-01"),
        Patient(Patient_ID=29, Sex="F", DateOfBirth="1991-01-01"),
        Patient(Patient_ID=30, Sex="M", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=28, Type_of_Relationship="Child", Patient_ID_Relationship_With=30
        ),
        Relationship(
            Patient_ID=29, Type_of_Relationship="Child", Patient_ID_Relationship_With=30
        ),
        #
        # MIXED INVALID CASES WITH SINGLE VALID CASE: SHOULD BE RETURNED
        #
        # Multiple mothers but only one valid
        Patient(Patient_ID=31, Sex="M", DateOfBirth="2020-01-01"),
        Patient(Patient_ID=32, Sex="F", DateOfBirth="1990-01-01"),
        Patient(Patient_ID=33, Sex="F", DateOfBirth="1991-01-01"),
        Relationship(
            Patient_ID=31,
            Type_of_Relationship="Mother",
            Patient_ID_Relationship_With=32,
            RelationshipEndDate="2020-10-10",
        ),
        Relationship(
            Patient_ID=31,
            Type_of_Relationship="Mother",
            Patient_ID_Relationship_With=33,
        ),
        {"patient_id": 31, "mother_id": 33},
        #
        # Multiple parents but only one valid
        Patient(Patient_ID=34, Sex="F", DateOfBirth="2022-01-01"),
        Patient(Patient_ID=35, Sex="F", DateOfBirth="1991-01-01"),
        Patient(Patient_ID=36, Sex="M", DateOfBirth="2020-01-01"),
        Relationship(
            Patient_ID=34, Type_of_Relationship="Child", Patient_ID_Relationship_With=36
        ),
        Relationship(
            Patient_ID=35, Type_of_Relationship="Child", Patient_ID_Relationship_With=36
        ),
        {"patient_id": 36, "mother_id": 35},
    )
    results = select_all_tpp(fixtures)
    assert results == expected_results


def _separate_fixtures_and_expected_results(*items):
    # Allows us to interleave test fixtures and their expected results in a way that
    # makes long lists of test cases more legible
    fixtures = []
    expected_results = []
    for item in items:
        if not isinstance(item, dict):
            fixtures.append(item)
        else:
            expected_results.append(item)
    return fixtures, expected_results


def test_registered_tests_are_exhaustive():
    assert_tests_exhaustive(TPPBackend())


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
        # Disable T1OO filter for test so we don't need to worry about creating
        # registration histories
        dsn=mssql_engine.database.host_url() + "?opensafely_include_t1oo=true",
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
    results = query_engine.get_results(dataset._compile())

    assert list(results) == expected
