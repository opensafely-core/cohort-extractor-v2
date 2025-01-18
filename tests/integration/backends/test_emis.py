from datetime import date, datetime

import sqlalchemy

from ehrql import create_dataset
from ehrql.backends.emis import EMISBackend
from ehrql.query_engines.base_sql import get_setup_and_cleanup_queries
from ehrql.tables import PatientFrame, Series, emis, table_from_rows
from ehrql.tables.raw import emis as emis_raw
from ehrql.utils.sqlalchemy_query_utils import CreateTableAs, GeneratedTable
from tests.lib.emis_schema import (
    ImmunisationAllOrgsV2,
    MedicationAllOrgsV2,
    ObservationAllOrgsV2,
    OnsView,
    PatientAllOrgsV2,
)

from .helpers import (
    assert_tests_exhaustive,
    assert_types_correct,
    get_all_backend_columns,
    register_test_for,
)


def test_backend_columns_have_correct_types(trino_database):
    columns_with_types = get_all_backend_columns_with_types(trino_database)
    assert_types_correct(columns_with_types, trino_database)


def get_all_backend_columns_with_types(trino_database):
    """
    For every column on every table we expose in the backend, yield the SQLAlchemy type
    instance we expect to use for that column together with the type information that
    database has for that column so we can check they're compatible
    """
    table_names = set()
    column_types = {}
    queries = []
    for table, columns in get_all_backend_columns(EMISBackend()):
        table_names.add(table)
        column_types.update({(table, c.key): c.type for c in columns})
        # Construct a query which selects every column in the table
        select_query = sqlalchemy.select(*[c.label(c.key) for c in columns])
        # Write the results of that query into a temporary table (it will be empty but
        # that's fine, we just want the types)
        # Trino doesn't support actual temporary tables, so really this temp table is
        # a real table that we drop after the test
        temp_table_name = f"temp_{table}"
        temp_table = GeneratedTable.from_query(temp_table_name, select_query)
        queries.append(
            (temp_table_name, temp_table, CreateTableAs(temp_table, select_query))
        )
    # Create all the underlying tables in the database without populating them
    trino_database.setup(metadata=PatientAllOrgsV2.metadata)
    with trino_database.engine().connect() as connection:
        # Create our "temporary" tables
        for temp_table_name, temp_table, query in queries:
            connection.execute(query)
            # Get the column names, types and collations for all columns in those tables
            query = sqlalchemy.text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name=:t
                """
            )
            results = list(connection.execute(query, {"t": temp_table_name}))
            table_name = temp_table_name.replace("temp_", "")
            for column, type_name in results:
                column_type = column_types[table_name, column]
                column_args = {"type": type_name}
                yield table_name, column, column_type, column_args

            # Drop the temp table
            temp_table.drop(trino_database.engine())


@register_test_for(emis.clinical_events)
def test_clinical_events(select_all_emis):
    results = select_all_emis(
        PatientAllOrgsV2(registration_id="1"),
        PatientAllOrgsV2(registration_id="2"),
        ObservationAllOrgsV2(
            registration_id="1",
            effective_date=datetime(2020, 10, 20, 14, 30, 5),
            snomed_concept_id=123,
            value_pq_1=0.5,
        ),
        ObservationAllOrgsV2(
            registration_id="2",
            effective_date=datetime(2022, 1, 15, 12, 30, 5),
            snomed_concept_id=567,
            value_pq_1=None,
        ),
    )
    assert results == [
        {
            "patient_id": "1",
            "date": date(2020, 10, 20),
            "snomedct_code": "123",
            "numeric_value": 0.5,
        },
        {
            "patient_id": "2",
            "date": date(2022, 1, 15),
            "snomedct_code": "567",
            "numeric_value": None,
        },
    ]


@register_test_for(emis.medications)
def test_medications(select_all_emis):
    results = select_all_emis(
        PatientAllOrgsV2(registration_id="1"),
        PatientAllOrgsV2(registration_id="2"),
        MedicationAllOrgsV2(
            registration_id="1",
            effective_date=datetime(2020, 10, 20, 14, 30, 5),
            snomed_concept_id=123,
        ),
        MedicationAllOrgsV2(
            registration_id="2",
            effective_date=datetime(2022, 1, 15, 12, 30, 5),
            snomed_concept_id=567,
        ),
    )
    assert results == [
        {
            "patient_id": "1",
            "date": date(2020, 10, 20),
            "dmd_code": "123",
        },
        {
            "patient_id": "2",
            "date": date(2022, 1, 15),
            "dmd_code": "567",
        },
    ]


@register_test_for(emis.ons_deaths)
def test_ons_deaths(select_all_emis):
    results = select_all_emis(
        PatientAllOrgsV2(registration_id="1", nhs_no="nhs1"),
        PatientAllOrgsV2(registration_id="2", nhs_no="nhs2"),
        PatientAllOrgsV2(registration_id="3", nhs_no="nhs3"),
        # duplicate registration_id, patient omitted
        PatientAllOrgsV2(registration_id="4", nhs_no="nhs4"),
        PatientAllOrgsV2(registration_id="4", nhs_no="nhs4"),
        OnsView(
            pseudonhsnumber="nhs1",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
        # older upload date, ignored
        OnsView(
            pseudonhsnumber="nhs1",
            upload_date="20220101",
            reg_stat_dod="20210101",
            icd10u="wxy",
            icd10001="abc",
            icd10002="def",
        ),
        # same patient, different date of death; earliest dod is selected
        OnsView(
            pseudonhsnumber="nhs2",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
        OnsView(
            pseudonhsnumber="nhs2",
            upload_date="20230101",
            reg_stat_dod="20220102",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
        # same patient, same date of death; lexically smallest cause of death is selected
        OnsView(
            pseudonhsnumber="nhs3",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="abc",
            icd10001="abc",
            icd10002="def",
        ),
        OnsView(
            pseudonhsnumber="nhs3",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
        # duplicate in patients table, excluded
        OnsView(
            pseudonhsnumber="nhs4",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
    )
    assert results == [
        {
            "patient_id": "1",
            "date": date(2022, 1, 1),
            "underlying_cause_of_death": "xyz",
            "cause_of_death_01": "abc",
            "cause_of_death_02": "def",
            "cause_of_death_03": None,
            "cause_of_death_04": None,
            "cause_of_death_05": None,
            "cause_of_death_06": None,
            "cause_of_death_07": None,
            "cause_of_death_08": None,
            "cause_of_death_09": None,
            "cause_of_death_10": None,
            "cause_of_death_11": None,
            "cause_of_death_12": None,
            "cause_of_death_13": None,
            "cause_of_death_14": None,
            "cause_of_death_15": None,
        },
        {
            "patient_id": "2",
            "date": date(2022, 1, 1),
            "underlying_cause_of_death": "xyz",
            "cause_of_death_01": "abc",
            "cause_of_death_02": "def",
            "cause_of_death_03": None,
            "cause_of_death_04": None,
            "cause_of_death_05": None,
            "cause_of_death_06": None,
            "cause_of_death_07": None,
            "cause_of_death_08": None,
            "cause_of_death_09": None,
            "cause_of_death_10": None,
            "cause_of_death_11": None,
            "cause_of_death_12": None,
            "cause_of_death_13": None,
            "cause_of_death_14": None,
            "cause_of_death_15": None,
        },
        {
            "patient_id": "3",
            "date": date(2022, 1, 1),
            "underlying_cause_of_death": "abc",
            "cause_of_death_01": "abc",
            "cause_of_death_02": "def",
            "cause_of_death_03": None,
            "cause_of_death_04": None,
            "cause_of_death_05": None,
            "cause_of_death_06": None,
            "cause_of_death_07": None,
            "cause_of_death_08": None,
            "cause_of_death_09": None,
            "cause_of_death_10": None,
            "cause_of_death_11": None,
            "cause_of_death_12": None,
            "cause_of_death_13": None,
            "cause_of_death_14": None,
            "cause_of_death_15": None,
        },
    ]


@register_test_for(emis_raw.ons_deaths)
def test_ons_deaths_raw(select_all_emis):
    results = select_all_emis(
        PatientAllOrgsV2(registration_id="1", nhs_no="nhs1"),
        PatientAllOrgsV2(registration_id="2", nhs_no="nhs2"),
        PatientAllOrgsV2(registration_id="3", nhs_no="nhs3"),
        # duplicate registration_id, patient omitted
        PatientAllOrgsV2(registration_id="4", nhs_no="nhs4"),
        PatientAllOrgsV2(registration_id="4", nhs_no="nhs4"),
        OnsView(
            pseudonhsnumber="nhs1",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
        # older upload date, ignored
        OnsView(
            pseudonhsnumber="nhs1",
            upload_date="20220101",
            reg_stat_dod="20210101",
            icd10u="wxy",
            icd10001="abc",
            icd10002="def",
        ),
        # same patient, different date of death; earliest dod is selected
        OnsView(
            pseudonhsnumber="nhs2",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
        OnsView(
            pseudonhsnumber="nhs2",
            upload_date="20230101",
            reg_stat_dod="20220102",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
        # same patient, same date of death; lexically smallest cause of death is selected
        OnsView(
            pseudonhsnumber="nhs3",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="abc",
            icd10001="abc",
            icd10002="def",
        ),
        OnsView(
            pseudonhsnumber="nhs3",
            upload_date="20230101",
            reg_stat_dod="20220101",
            icd10u="xyz",
            icd10001="abc",
            icd10002="def",
        ),
    )

    # results include duplicates, but still omit earlier uploads and duplicate
    # registrations
    results_summary = [(result["patient_id"], result["date"]) for result in results]
    assert results_summary == [
        ("1", date(2022, 1, 1)),
        ("2", date(2022, 1, 1)),
        ("2", date(2022, 1, 2)),
        ("3", date(2022, 1, 1)),
        ("3", date(2022, 1, 1)),
    ]


@register_test_for(emis.patients)
def test_patients(select_all_emis):
    results = select_all_emis(
        PatientAllOrgsV2(
            registration_id="1",
            date_of_birth=date(2020, 1, 1),
            gender=1,
            hashed_organisation="1A2B3C",
            registered_date=date(2021, 3, 1),
            rural_urban=1,
            imd_rank=500,
        ),
        # duplicate registration ids are ignored
        PatientAllOrgsV2(
            registration_id="2",
            date_of_birth=date(2020, 1, 1),
            gender=1,
            hashed_organisation="1A2B3C",
            registered_date=date(2021, 3, 1),
        ),
        PatientAllOrgsV2(
            registration_id="2",
            date_of_birth=date(2020, 1, 1),
            gender=1,
            hashed_organisation="1A2B3C",
            registered_date=date(2021, 3, 1),
        ),
        PatientAllOrgsV2(
            registration_id="3",
            date_of_birth=date(1960, 1, 1),
            date_of_death=date(2020, 1, 1),
            gender=2,
            hashed_organisation="1A2B3C",
            registered_date=date(1960, 3, 1),
        ),
        PatientAllOrgsV2(
            registration_id="4",
            date_of_birth=date(2020, 1, 1),
            gender=0,
            hashed_organisation="1A2B3C",
            registered_date=date(2021, 3, 1),
        ),
        PatientAllOrgsV2(
            registration_id="5",
            date_of_birth=date(1978, 10, 13),
            gender=9,
            hashed_organisation="1A2B3C",
            registered_date=date(2021, 3, 1),
        ),
    )

    expected = [
        {
            "patient_id": "1",
            "date_of_birth": date(2020, 1, 1),
            "sex": "male",
            "date_of_death": None,
            "registration_start_date": date(2021, 3, 1),
            "registration_end_date": None,
            "practice_pseudo_id": "1A2B3C",
            "rural_urban_classification": 1,
            "imd_rounded": 500,
        },
        {
            "patient_id": "3",
            "date_of_birth": date(1960, 1, 1),
            "sex": "female",
            "date_of_death": date(2020, 1, 1),
            "registration_start_date": date(1960, 3, 1),
            "registration_end_date": None,
            "practice_pseudo_id": "1A2B3C",
            "rural_urban_classification": None,
            "imd_rounded": None,
        },
        {
            "patient_id": "4",
            "date_of_birth": date(2020, 1, 1),
            "sex": "unknown",
            "date_of_death": None,
            "registration_start_date": date(2021, 3, 1),
            "registration_end_date": None,
            "practice_pseudo_id": "1A2B3C",
            "rural_urban_classification": None,
            "imd_rounded": None,
        },
        {
            "patient_id": "5",
            "date_of_birth": date(1978, 10, 13),
            "sex": "unknown",
            "date_of_death": None,
            "registration_start_date": date(2021, 3, 1),
            "registration_end_date": None,
            "practice_pseudo_id": "1A2B3C",
            "rural_urban_classification": None,
            "imd_rounded": None,
        },
    ]
    assert results == expected


@register_test_for(emis.practice_registrations)
def test_practice_registrations(select_all_emis):
    results = select_all_emis(
        PatientAllOrgsV2(
            registration_id="1",
            hashed_organisation="1f",
            registered_date=date(2021, 3, 1),
            registration_end_date=date(2022, 4, 2),
        ),
        PatientAllOrgsV2(
            registration_id="1",
            hashed_organisation="10A",
            registered_date=date(2022, 4, 3),
            registration_end_date=None,
        ),
        PatientAllOrgsV2(
            registration_id="2",
            hashed_organisation="123ABC",
            registered_date=date(2000, 1, 1),
            registration_end_date=date(2020, 1, 1),
        ),
    )

    expected = [
        {
            "patient_id": "1",
            "start_date": date(2021, 3, 1),
            "end_date": date(2022, 4, 2),
            # The core `practice_registrations` table defines `practice_pseudo_id` as an
            # int, so we have to convert from hex strings to ints here
            "practice_pseudo_id": 31,
        },
        {
            "patient_id": "1",
            "start_date": date(2022, 4, 3),
            "end_date": None,
            "practice_pseudo_id": 266,
        },
        {
            "patient_id": "2",
            "start_date": date(2000, 1, 1),
            "end_date": date(2020, 1, 1),
            "practice_pseudo_id": 1194684,
        },
    ]

    # Trino doesn't return results in a stable order
    def sort(lst):
        return sorted(lst, key=lambda i: (i["patient_id"], i["practice_pseudo_id"]))

    assert sort(results) == sort(expected)


@register_test_for(emis.vaccinations)
def test_vaccinations(select_all_emis):
    results = select_all_emis(
        PatientAllOrgsV2(registration_id="1"),
        PatientAllOrgsV2(registration_id="2"),
        PatientAllOrgsV2(registration_id="3"),
        ImmunisationAllOrgsV2(
            registration_id="1",
            effective_date=datetime(2020, 10, 20, 14, 30, 5),
            snomed_concept_id=123,
        ),
        ImmunisationAllOrgsV2(
            registration_id="2",
            effective_date=datetime(2021, 3, 23, 23, 30, 5),
            snomed_concept_id=456,
        ),
        ImmunisationAllOrgsV2(
            registration_id="2",
            effective_date=datetime(2022, 1, 15, 12, 30, 5),
            snomed_concept_id=567,
        ),
    )
    assert results == [
        {
            "patient_id": "1",
            "date": date(2020, 10, 20),
            "procedure_code": "123",
        },
        {
            "patient_id": "2",
            "date": date(2021, 3, 23),
            "procedure_code": "456",
        },
        {
            "patient_id": "2",
            "date": date(2022, 1, 15),
            "procedure_code": "567",
        },
    ]


def test_registered_tests_are_exhaustive():
    assert_tests_exhaustive(EMISBackend())


def test_inline_table_includes_organisation_hash(trino_database):
    # This tests that EMIS's generated inline tables include a column
    # "hashed_organisation", where every row values is the value of the
    # EMIS_ORGANISATION_HASH environment variable
    trino_database.setup(
        PatientAllOrgsV2(registration_id="1", date_of_birth=date(2020, 1, 1)),
        PatientAllOrgsV2(registration_id="2", date_of_birth=date(2020, 1, 1)),
    )

    # Note that currently inline data tables always make patient_id an integer
    # so in this test, our patient ids from the backend DB are coerced to ints
    # In reality, this means inline tables won't be able to handle real EMIS
    # data (where patient ids are strings) but this will be dealt with
    # later
    # https://github.com/opensafely-core/ehrql/issues/743
    inline_data = [
        (1, 100),
        (2, 200),
    ]

    @table_from_rows(inline_data)
    class t(PatientFrame):
        n = Series(int)

    dataset = create_dataset()
    dataset.define_population(t.exists_for_patient())
    dataset.v = t.n

    backend = EMISBackend()
    query_engine = backend.query_engine_class(
        trino_database.host_url(),
        backend=backend,
    )

    variables = dataset._compile()

    results_queries = query_engine.get_queries(variables)
    assert len(results_queries) == 1
    inline_tables = [
        ch
        for ch in results_queries[0].get_children()
        if isinstance(ch, GeneratedTable) and "inline_data" in ch.name
    ]
    assert len(set(inline_tables)) == 1
    inline_table = inline_tables[0]
    setup_queries, cleanup_queries = get_setup_and_cleanup_queries(results_queries)

    with query_engine.engine.connect() as connection:
        for setup_query in setup_queries:
            connection.execute(setup_query)
        column_info = connection.execute(
            sqlalchemy.text(f"SHOW COLUMNS FROM {inline_table.name}")
        ).fetchall()
        assert column_info == [
            ("patient_id", "integer", "", ""),
            ("n", "integer", "", ""),
            ("hashed_organisation", "varchar", "", ""),
        ]
        all_inline_results = connection.execute(
            sqlalchemy.text(f"select * from {inline_table.name}")
        ).fetchall()
        assert sorted(all_inline_results) == [
            (1, 100, "emis_organisation_hash"),
            (2, 200, "emis_organisation_hash"),
        ]

        for cleanup_query in cleanup_queries:
            connection.execute(cleanup_query)

    results = query_engine.get_results(variables)
    assert sorted(results) == [(1, 100), (2, 200)]


def test_temp_table_includes_organisation_hash(trino_database):
    # This tests that EMIS's generated tables (created in `reify_query`)
    # include a column "hashed_organisation", where every row values is the
    # value of the EMIS_ORGANISATION_HASH environment variable
    trino_database.setup(
        PatientAllOrgsV2(registration_id="1", date_of_birth=date(2020, 1, 1)),
        PatientAllOrgsV2(registration_id="2", date_of_birth=date(2020, 1, 1)),
    )

    dataset = create_dataset()
    dataset.define_population(emis.patients.date_of_birth.is_not_null())

    backend = EMISBackend()
    query_engine = backend.query_engine_class(
        trino_database.host_url(),
        backend=backend,
    )

    variables = dataset._compile()
    results_queries = query_engine.get_queries(variables)
    assert len(results_queries) == 1
    temp_tables = [
        ch
        for ch in results_queries[0].get_children()
        if isinstance(ch, GeneratedTable) and "tmp" in ch.name
    ]
    assert len(set(temp_tables)) == 1
    temp_table = temp_tables[0]
    setup_queries, cleanup_queries = get_setup_and_cleanup_queries(results_queries)

    with query_engine.engine.connect() as connection:
        for setup_query in setup_queries:
            connection.execute(setup_query)
        column_info = connection.execute(
            sqlalchemy.text(f"SHOW COLUMNS FROM {temp_table.name}")
        ).fetchall()
        assert column_info == [
            ("patient_id", "varchar(128)", "", ""),
            ("hashed_organisation", "varchar(22)", "", ""),
        ]
        all_temp_table_results = connection.execute(
            sqlalchemy.text(f"select * from {temp_table.name}")
        ).fetchall()
        assert sorted(all_temp_table_results) == [
            ("1", "emis_organisation_hash"),
            ("2", "emis_organisation_hash"),
        ]

        for cleanup_query in cleanup_queries:
            connection.execute(cleanup_query)

    results = query_engine.get_results(variables)
    assert sorted(results) == [("1",), ("2",)]
