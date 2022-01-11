from datetime import date, datetime

import pytest

from databuilder import codelist
from databuilder.backends.tpp import TPPBackend
from databuilder.contracts.tables import (
    WIP_ClinicalEvents,
    WIP_Hospitalizations,
    WIP_PatientAddress,
    WIP_PracticeRegistrations,
    WIP_SimplePatientDemographics,
    WIP_TestResults,
)
from databuilder.query_model import Table

from ..lib.tpp_schema import (
    CTV3Events,
    Patient,
    RegistrationHistory,
    SGSSNegativeTests,
    SGSSPositiveTests,
    SnomedEvents,
    apcs,
    organisation,
    patient,
    patient_address,
    registration,
)
from ..lib.util import extract


def run_query(database, query):
    with database.engine().connect() as cursor:
        yield from cursor.execute(query)


def test_basic_events_and_registration(database):
    database.setup(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1),
        CTV3Events(Patient_ID=1, CTV3Code="Code1"),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        code = Table(WIP_ClinicalEvents).first_by("patient_id").get("code")

    assert extract(Cohort, TPPBackend, database) == [dict(patient_id=1, code="Code1")]


def test_registration_dates(database):
    database.setup(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2012-12-12"),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _registrations = Table(WIP_PracticeRegistrations).first_by("patient_id")
        arrived = _registrations.get("date_start")
        left = _registrations.get("date_end")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, arrived=datetime(2001, 1, 1), left=datetime(2012, 12, 12))
    ]


def test_covid_test_positive_result(database):
    database.setup(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"),
        SGSSPositiveTests(
            Patient_ID=1,
            Organism_Species_Name="SARS-CoV-2",
            Specimen_Date="2020-05-05",
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        date = (
            Table(WIP_TestResults).filter(positive_result=True).earliest().get("date")
        )

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, date=date(2020, 5, 5))
    ]


def test_covid_test_negative_result(database):
    database.setup(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"),
        SGSSNegativeTests(
            Patient_ID=1,
            Organism_Species_Name="SARS-CoV-2",
            Specimen_Date="2020-05-05",
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        date = (
            Table(WIP_TestResults).filter(positive_result=False).earliest().get("date")
        )

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, date=date(2020, 5, 5))
    ]


def test_patients_table(database):
    database.setup(
        Patient(Patient_ID=1, Sex="F", DateOfBirth="1950-01-01"),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _patients = Table(WIP_SimplePatientDemographics).first_by("patient_id")
        sex = _patients.get("sex")
        dob = _patients.get("date_of_birth")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, sex="F", dob=date(1950, 1, 1))
    ]


def test_hospitalization_table_returns_admission_date_and_code(database):
    database.setup(
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26"),
            apcs(admission_date="2020-12-12", codes="xyz"),
        )
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _hospitalization = Table(WIP_Hospitalizations).first_by("patient_id")
        admission = _hospitalization.get("date")
        code = _hospitalization.get("code")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, admission=date(2020, 12, 12), code="xyz")
    ]


@pytest.mark.parametrize(
    "raw, codes",
    [
        ("flim", ["flim"]),
        ("flim ,flam ,flum", ["flim", "flam", "flum"]),
        ("flim ||flam ||flum", ["flim", "flam", "flum"]),
        ("abc ,def ||ghi ,jkl", ["abc", "def", "ghi", "jkl"]),
        ("ABCX ,XYZ ,OXO", ["ABC", "XYZ", "OXO"]),
    ],
    ids=[
        "returns a single code",
        "returns multiple space comma separated codes",
        "returns multiple space double pipe separated codes",
        "copes with comma pipe combinations",
        "strips just trailing xs",
    ],
)
def test_hospitalization_table_code_conversion(database, raw, codes):
    database.setup(
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26"),
            apcs(codes=raw),
        )
    )

    query = TPPBackend.hospitalizations.get_query()

    results = list(run_query(database, query))

    # Because of the way that we split the raw codes, the order in which they are returned is not the same as the order
    # they appear in the table.
    assert len(results) == len(codes)
    for code in codes:
        assert (1, date(2012, 12, 12), code, "icd10") in results


def test_hospitalization_code_parsing_works_with_filters(database):
    database.setup(
        patient(
            1,
            "X",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26"),
            apcs(codes="abc"),
        ),
        patient(
            2,
            "X",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26"),
            apcs(codes="xyz"),
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        code = (
            Table(WIP_Hospitalizations)
            .filter("code", is_in=codelist(["xyz"], system="icd10"))
            .first_by("patient_id")
            .get("code")
        )

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, code=None),
        dict(patient_id=2, code="xyz"),
    ]


def test_events_with_numeric_value(database):
    database.setup(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1),
        CTV3Events(Patient_ID=1, CTV3Code="Code1", NumericValue=34.7),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        value = Table(WIP_ClinicalEvents).latest().get("numeric_value")

    assert extract(Cohort, TPPBackend, database) == [dict(patient_id=1, value=34.7)]


def test_organisation(database):
    database.setup(
        organisation(1, "South"),
        organisation(2, "North"),
        patient(1, "M", "1990-1-1", registration("2001-01-01", "2021-06-26", 1)),
        patient(2, "F", "1990-1-1", registration("2001-01-01", "2026-06-26", 2)),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _registrations = Table(WIP_PracticeRegistrations).last_by("patient_id")
        region = _registrations.get("nuts1_region_name")
        practice_id = _registrations.get("pseudo_id")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, region="South", practice_id=1),
        dict(patient_id=2, region="North", practice_id=2),
    ]


def test_organisation_dates(database):
    database.setup(
        organisation(1, "South"),
        organisation(2, "North"),
        organisation(3, "West"),
        organisation(4, "East"),
        # registered at 2 practices, select the one active on 25/6
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2021-06-26", 1),
            registration("2021-06-27", "2026-06-26", 2),
        ),
        # registered at 2 practices with overlapping dates, select the latest
        patient(
            2,
            "F",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26", 2),
            registration("2021-01-01", "9999-12-31", 3),
        ),
        # registration not in range, not included
        patient(3, "F", "1990-1-1", registration("2001-01-01", "2020-06-26", 2)),
    )

    class Cohort:
        _registrations = Table(WIP_PracticeRegistrations).date_in_range("2021-06-25")
        population = _registrations.exists()
        _registration_table = _registrations.latest("date_end")
        region = _registration_table.get("nuts1_region_name")
        practice_id = _registration_table.get("pseudo_id")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, region="South", practice_id=1),
        dict(patient_id=2, region="West", practice_id=3),
    ]


def test_index_of_multiple_deprivation(database):
    database.setup(
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26"),
            patient_address("2001-01-01", "2026-06-26", 1200, "E02000001"),
        )
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        imd = Table(WIP_PatientAddress).imd_rounded_as_of("2021-06-01")

    assert extract(Cohort, TPPBackend, database) == [dict(patient_id=1, imd=1200)]


@pytest.mark.parametrize(
    "patient_addresses,expected",
    [
        # two addresses recorded as current, choose the latest start date
        (
            [
                patient_address("2001-01-01", "9999-12-31", 100, "E02000002"),
                patient_address("2021-01-01", "9999-12-31", 200, "E02000003"),
            ],
            200,
        ),
        # two addresses with same start, choose the latest end date
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003"),
                patient_address("2001-01-01", "2021-01-01", 200, "E02000002"),
            ],
            300,
        ),
        # same dates, prefer the one with a postcode
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003"),
                patient_address("2001-01-01", "9999-12-31", 400, "NPC"),
            ],
            300,
        ),
        # same dates and both have postcodes, select latest patient address id as tie-breaker
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003"),
                patient_address("2001-01-01", "9999-12-31", 400, "E02000003"),
                patient_address("2001-01-01", "9999-12-31", 500, "E02000003"),
            ],
            500,
        ),
    ],
)
def test_index_of_multiple_deprivation_sorting(database, patient_addresses, expected):
    database.setup(
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26"),
            *patient_addresses,
        )
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        imd = Table(WIP_PatientAddress).imd_rounded_as_of("2021-06-01")

    assert extract(Cohort, TPPBackend, database) == [dict(patient_id=1, imd=expected)]


def test_clinical_events_table(database):
    database.setup(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"),
        CTV3Events(Patient_ID=1, CTV3Code="Code1", ConsultationDate="2021-01-01"),
        SnomedEvents(Patient_ID=1, ConceptID="Code2", ConsultationDate="2021-02-01"),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _events = Table(WIP_ClinicalEvents)
        first_event_code = _events.earliest().get("code")
        first_event_system = _events.earliest().get("system")
        last_event_code = _events.latest().get("code")
        last_event_system = _events.latest().get("system")

    assert extract(Cohort, TPPBackend, database) == [
        dict(
            patient_id=1,
            first_event_code="Code1",
            first_event_system="ctv3",
            last_event_code="Code2",
            last_event_system="snomed",
        )
    ]


def test_clinical_events_table_multiple_codes(database):
    database.setup(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"),
        CTV3Events(Patient_ID=1, CTV3Code="Code1", ConsultationDate="2021-01-01"),
        CTV3Events(Patient_ID=1, CTV3Code="Code1", ConsultationDate="2021-02-01"),
        CTV3Events(Patient_ID=1, CTV3Code="Code1", ConsultationDate="2021-03-01"),
        SnomedEvents(Patient_ID=1, ConceptID="Code2", ConsultationDate="2021-03-01"),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _events = Table(WIP_ClinicalEvents)
        _filtered_to_code = (
            Table(WIP_ClinicalEvents)
            .filter("code", is_in=codelist(["Code1"], "ctv3"))
            .filter("date", on_or_after="2021-01-01")
        )
        count = _filtered_to_code.count("code")
        date = _filtered_to_code.earliest().get("date")

    assert extract(Cohort, TPPBackend, database) == [
        dict(
            patient_id=1,
            count=3,
            date=datetime(2021, 1, 1, 0, 0),
        )
    ]


def test_patients_contract_table(database):
    database.setup(
        patient(1, "M", "1990-01-01", date_of_death="2021-01-04"),
        patient(2, "F", "1990-01-01", date_of_death="2020-02-04"),
        patient(3, "I", "1990-01-01", date_of_death="9999-12-31"),
        patient(4, None, "1990-01-01"),
        patient(5, "X", "1990-01-01"),
    )

    query = TPPBackend.patient_demographics.get_query()

    results = list(run_query(database, query))
    assert results == [
        (1, date(1990, 1, 1), date(2021, 1, 1), "male"),
        (2, date(1990, 1, 1), date(2020, 2, 1), "female"),
        (3, date(1990, 1, 1), None, "intersex"),
        (4, date(1990, 1, 1), None, "unknown"),
        (5, date(1990, 1, 1), None, "unknown"),
    ]
