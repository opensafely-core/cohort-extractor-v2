from datetime import date, datetime

import pytest

from databuilder.backends.graphnet import GraphnetBackend
from databuilder.contracts.tables import (
    PatientDemographics,
    WIP_ClinicalEvents,
    WIP_HospitalizationsWithoutSystem,
    WIP_PatientAddress,
    WIP_PracticeRegistrations,
    WIP_TestResults,
)
from databuilder.query_model import Table

from ..lib.graphnet_schema import (
    ClinicalEvents,
    CovidTestResults,
    Patients,
    PracticeRegistrations,
    hospitalization,
    patient,
    patient_address,
    registration,
)
from ..lib.util import extract


def test_basic_events_and_registration(database):
    database.setup(
        Patients(Patient_ID=1),
        PracticeRegistrations(Patient_ID=1),
        ClinicalEvents(Patient_ID=1, Code="Code1", CodingSystem="CTV3"),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        code = Table(WIP_ClinicalEvents).first_by("patient_id").get("code")
        system = Table(WIP_ClinicalEvents).first_by("patient_id").get("system")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, code="Code1", system="CTV3")
    ]


def test_registration_dates(database):
    database.setup(
        Patients(Patient_ID=1),
        PracticeRegistrations(
            Patient_ID=1, StartDate="2001-01-01", EndDate="2012-12-12"
        ),
        PracticeRegistrations(Patient_ID=1, StartDate="2013-01-01"),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _registrations = Table(WIP_PracticeRegistrations).first_by("patient_id")
        arrived = _registrations.get("date_start")
        left = _registrations.get("date_end")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, arrived=datetime(2001, 1, 1), left=datetime(2012, 12, 12))
    ]


def test_registration_dates_no_end(database):
    database.setup(
        Patients(Patient_ID=1),
        PracticeRegistrations(
            Patient_ID=1, StartDate="2011-01-01", EndDate="2012-12-31"
        ),
        PracticeRegistrations(Patient_ID=1, StartDate="2013-01-01", EndDate=None),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _registrations = (
            Table(WIP_PracticeRegistrations)
            .date_in_range("2014-01-01")
            .latest("date_end")
        )
        arrived = _registrations.get("date_start")
        left = _registrations.get("date_end")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, arrived=datetime(2013, 1, 1), left=None)
    ]


def test_covid_test_positive_result(database):
    database.setup(
        Patients(Patient_ID=1),
        PracticeRegistrations(
            Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"
        ),
        CovidTestResults(
            Patient_ID=1,
            SpecimenDate="2020-05-05",
            positive_result=True,
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        date = (
            Table(WIP_TestResults).filter(positive_result=True).earliest().get("date")
        )

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, date=date(2020, 5, 5))
    ]


def test_covid_test_negative_result(database):
    database.setup(
        Patients(Patient_ID=1),
        PracticeRegistrations(
            Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"
        ),
        CovidTestResults(
            Patient_ID=1,
            SpecimenDate="2020-05-05",
            positive_result=False,
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        date = (
            Table(WIP_TestResults).filter(positive_result=False).earliest().get("date")
        )

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, date=date(2020, 5, 5))
    ]


def test_patients_table(database):
    database.setup(
        Patients(Patient_ID=1, Sex="F", DateOfBirth="1950-01-01"),
        PracticeRegistrations(
            Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _patients = Table(PatientDemographics).first_by("patient_id")
        sex = _patients.get("sex")
        dob = _patients.get("date_of_birth")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, sex="F", dob=date(1950, 1, 1))
    ]


def test_hospitalization_table_returns_admission_date_and_code(database):
    database.setup(
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26"),
            hospitalization(admit_date="2020-12-12", code="xyz"),
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _hospitalization = Table(WIP_HospitalizationsWithoutSystem).first_by(
            "patient_id"
        )
        admission = _hospitalization.get("date")
        code = _hospitalization.get("code")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, admission=date(2020, 12, 12), code="xyz")
    ]


def test_events_with_numeric_value(database):
    database.setup(
        Patients(Patient_ID=1),
        PracticeRegistrations(Patient_ID=1),
        ClinicalEvents(
            Patient_ID=1, Code="Code1", CodingSystem="CTV3", NumericValue=34.7
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        value = Table(WIP_ClinicalEvents).latest().get("numeric_value")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, value=34.7)
    ]


def test_organisation(database):
    database.setup(
        # Organisation not a separate table, so will just move detail to single registration record
        # organisation(1, "South"),
        # organisation(2, "North"),
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2021-06-26", "A83010", "North East"),
        ),
        patient(
            2,
            "F",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26", "J82031", "South West"),
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        _registrations = Table(WIP_PracticeRegistrations).last_by("patient_id")
        region = _registrations.get("nuts1_region_name")
        practice_id = _registrations.get("pseudo_id")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, region="North East", practice_id="A83010"),
        dict(patient_id=2, region="South West", practice_id="J82031"),
    ]


def test_organisation_dates(database):
    database.setup(
        # Organisation not a separate table, so will just move detail to registration record
        # organisation(1, "South"),
        # organisation(2, "North"),
        # organisation(3, "West"),
        # organisation(4, "East"),
        # registered at 2 practices, select the one active on 25/6
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2021-06-26", "A83010", "North East"),
            registration("2021-06-27", "2026-06-26", "J26003", "South West"),
        ),
        # registered at 2 practices with overlapping dates, select the latest
        patient(
            2,
            "F",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26", "S21021", "East"),
            registration("2021-01-01", "9999-12-31", "S33001", "East"),
        ),
        # registration not in range, not included
        patient(
            3,
            "F",
            "1990-1-1",
            registration("2001-01-01", "2020-06-26", "S21021", "East"),
        ),
    )

    class Cohort:
        _registrations = Table(WIP_PracticeRegistrations).date_in_range("2021-06-25")
        population = _registrations.exists()
        _registration_table = _registrations.latest("date_end")
        region = _registration_table.get("nuts1_region_name")
        practice_id = _registration_table.get("pseudo_id")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, region="North East", practice_id="A83010"),
        dict(patient_id=2, region="East", practice_id="S33001"),
    ]


def test_index_of_multiple_deprivation(database):
    database.setup(
        patient(
            1,
            "M",
            "1990-1-1",
            registration("2001-01-01", "2026-06-26"),
            patient_address("2001-01-01", "2026-06-26", 1200, "E02000001", True),
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        imd = Table(WIP_PatientAddress).imd_rounded_as_of("2021-06-01")

    assert extract(Cohort, GraphnetBackend, database) == [dict(patient_id=1, imd=1200)]


@pytest.mark.parametrize(
    "patient_addresses,expected",
    [
        # two addresses recorded as current, choose the latest start date
        (
            [
                patient_address("2001-01-01", "9999-12-31", 100, "E02000002", True),
                patient_address("2021-01-01", "9999-12-31", 200, "E02000003", True),
            ],
            200,
        ),
        # two addresses with same start, choose the latest end date
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003", True),
                patient_address("2001-01-01", "2021-01-01", 200, "E02000002", True),
            ],
            300,
        ),
        # two addresses with same start, one with null end date, choose the null end date
        (
            [
                patient_address("2001-01-01", None, 300, "E02000003", True),
                patient_address("2001-01-01", "2021-01-01", 200, "E02000002", True),
            ],
            300,
        ),
        # same dates, prefer the one with a postcode
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003", True),
                patient_address("2001-01-01", "9999-12-31", 400, "NPC", False),
            ],
            300,
        ),
        # same dates and both have postcodes, select latest patient address id as tie-breaker
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003", True),
                patient_address("2001-01-01", "9999-12-31", 400, "E02000003", True),
                patient_address("2001-01-01", "9999-12-31", 500, "E02000003", True),
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
        ),
    )

    class Cohort:
        population = Table(WIP_PracticeRegistrations).exists()
        imd = Table(WIP_PatientAddress).imd_rounded_as_of("2021-06-01")

    assert extract(Cohort, GraphnetBackend, database) == [
        dict(patient_id=1, imd=expected)
    ]
