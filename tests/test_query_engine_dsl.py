from datetime import date, timedelta

import pytest

from databuilder import codelist
from databuilder.dsl import categorise
from databuilder.dsl import categorise as dsl_categorise

from .lib.mock_backend import ctv3_event, patient
from .lib.tables import events, patients

# Mark the whole module as containing integration tests
pytestmark = pytest.mark.integration


def test_categorise_simple_comparisons(engine, cohort_with_population):
    input_data = [patient(1, height=180), patient(2, height=200.5), patient(3)]
    engine.setup(input_data)

    height = patients.select_column(patients.height)
    height_categories = {
        "tall": height > 190,
        "short": height <= 190,
    }
    height_group = categorise(height_categories, default="missing")
    cohort = cohort_with_population
    cohort.height_group = height_group

    result = engine.extract(cohort)
    assert result == [
        dict(patient_id=1, height_group="short"),
        dict(patient_id=2, height_group="tall"),
        dict(patient_id=3, height_group="missing"),
    ]


def test_comparator_order(engine, cohort_with_population):
    """Test that comparison operators work on both sides of the comparator"""
    input_data = [patient(1, height=180), patient(2, height=200.5), patient(3)]
    engine.setup(input_data)

    height = patients.select_column(patients.height)
    height_categories = {
        "tall": 190 < height,
        "short": 190 >= height,
    }
    height_group = categorise(height_categories, default="missing")
    cohort = cohort_with_population
    cohort.height_group = height_group

    result = engine.extract(cohort)
    assert result == [
        dict(patient_id=1, height_group="short"),
        dict(patient_id=2, height_group="tall"),
        dict(patient_id=3, height_group="missing"),
    ]


def test_dsl_code_comparisons(cohort_with_population, engine):
    input_data = [
        patient(1, ctv3_event("abc")),
        patient(2, ctv3_event("abc")),
        patient(3, ctv3_event("def")),
    ]
    engine.setup(input_data)

    first_code = (
        events.sort_by(events.code).first_for_patient().select_column(events.code)
    )

    date_categories = {
        "abc": first_code == "abc",
        "not_abc": first_code != "abc",
    }

    data_definition = cohort_with_population
    data_definition.code_group = dsl_categorise(date_categories, default="unknown")

    result = engine.extract(data_definition)

    assert result == [
        {"patient_id": 1, "code_group": "abc"},
        {"patient_id": 2, "code_group": "abc"},
        {"patient_id": 3, "code_group": "not_abc"},
    ]


def test_dsl_date_comparisons(cohort_with_population, engine):
    """
    Exercise comparison (and some boolean) operators in the DSL

    We want to ensure the PatientSeries comparison and boolean operators work
    as expected for date values.  We're using the DSL's categorise function
    here to let us make boolean values against which to match the PatientSeries
    values.
    """
    input_data = [
        patient(1, ctv3_event("abc", "2019-12-31")),
        patient(2, ctv3_event("abc", "2020-02-29")),
        patient(3, ctv3_event("abc", "2020-10-01")),
        patient(4, ctv3_event("abc", "2021-04-07")),
    ]
    engine.setup(input_data)

    first_code_date = (
        events.sort_by(events.date).first_for_patient().select_column(events.date)
    )

    first_half_2020 = (first_code_date >= "2020-01-01") & (
        first_code_date <= "2020-06-30"
    )
    second_half_2020 = (first_code_date >= "2020-07-01") & (
        first_code_date <= "2020-12-31"
    )
    in_2020 = first_half_2020 | second_half_2020
    date_categories = {
        "before_2020": first_code_date < "2020-01-01",
        "in_2020": in_2020,
        "after_2020": first_code_date > "2020-12-31",
    }

    data_definition = cohort_with_population
    data_definition.date_group = dsl_categorise(date_categories, default="unknown")

    result = engine.extract(data_definition)

    assert result == [
        {"patient_id": 1, "date_group": "before_2020"},
        {"patient_id": 2, "date_group": "in_2020"},
        {"patient_id": 3, "date_group": "in_2020"},
        {"patient_id": 4, "date_group": "after_2020"},
    ]


def test_dsl_int_comparisons(cohort_with_population, engine):
    """
    Exercise comparison (and some boolean) operators in the DSL

    We want to ensure the IntSeries comparison and boolean operators work
    as expected for int values.  We're using the DSL's categorise function
    here to let us make boolean values against which to match the IntSeries
    values.
    """
    input_data = [
        patient(1, height=7),
        patient(2, height=21),
        patient(3, height=28),
        patient(4, height=35),
    ]
    engine.setup(input_data)

    height = patients.select_column(patients.height)

    twenty_to_twenty_four = (height >= 20) & (height <= 24)
    twenty_five_to_twenty_nine = (height >= 25) & (height <= 29)
    in_20s = twenty_to_twenty_four | twenty_five_to_twenty_nine
    height_categories = {
        "before_20s": height < 20,
        "in_20s": in_20s,
        "after_20s": height > 29,
    }

    data_definition = cohort_with_population
    data_definition.height_group = dsl_categorise(height_categories, default="unknown")

    result = engine.extract(data_definition)

    assert result == [
        {"patient_id": 1, "height_group": "before_20s"},
        {"patient_id": 2, "height_group": "in_20s"},
        {"patient_id": 3, "height_group": "in_20s"},
        {"patient_id": 4, "height_group": "after_20s"},
    ]


def test_date_arithmetic_subtract_date_series_from_datestring(
    engine, cohort_with_population
):
    input_data = [
        patient(1, dob="1990-08-10"),
        patient(2, dob="2000-03-20"),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    index_date = "2010-06-01"
    dob = patients.select_column(patients.date_of_birth)  # DateSeries

    age = index_date - dob
    data_definition.age_in_2010 = age.convert_to_years()
    result = engine.extract(data_definition)
    assert result == [
        {"patient_id": 1, "age_in_2010": 19},
        {"patient_id": 2, "age_in_2010": 10},
    ]


def test_date_arithmetic_subtract_datestring_from_date_series(
    engine, cohort_with_population
):
    input_data = [
        patient(1, dob="1990-08-10"),
        patient(2, dob="2000-03-20"),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date = "1980-06-01"
    dob = patients.select_column(patients.date_of_birth)  # DateSeries

    # we can calculate date diffs both ways round
    time_since = dob - reference_date
    data_definition.time_since = time_since.convert_to_years()
    result = engine.extract(data_definition)
    assert result == [
        {"patient_id": 1, "time_since": 10},
        {"patient_id": 2, "time_since": 19},
    ]


def test_date_arithmetic_subtract_dateseries(engine, cohort_with_population):
    input_data = [
        patient(1, ctv3_event("abc", "2020-10-01"), ctv3_event("abc", "2010-06-01")),
        patient(2, ctv3_event("abc", "2018-02-01"), ctv3_event("abc", "2010-10-01")),
        patient(3, ctv3_event("abc", "2018-02-01")),
        patient(4, ctv3_event("def", "2018-02-01")),
    ]
    engine.setup(input_data)

    codes = codelist(["abc"], "ctv3")

    data_definition = cohort_with_population
    first_event_date = (
        events.filter(events.code.is_in(codes))
        .sort_by(events.date)
        .first_for_patient()
        .select_column(events.date)
    )
    last_event_date = (
        events.filter(events.code.is_in(codes))
        .sort_by(events.date)
        .last_for_patient()
        .select_column(events.date)
    )
    time_between_events = last_event_date - first_event_date
    data_definition.time_between_events = time_between_events.convert_to_years()

    result = engine.extract(data_definition)
    assert result == [
        {"patient_id": 1, "time_between_events": 10},
        {"patient_id": 2, "time_between_events": 7},
        {"patient_id": 3, "time_between_events": 0},
        {"patient_id": 4, "time_between_events": None},
    ]


def test_date_arithmetic_conversions(engine, cohort_with_population):
    input_data = [
        # all dobs are subtracted from 2021-09-01, rounded down
        # 21 yrs, 0 months; 252 months; end month == start, end day == start
        patient(1, dob="2000-09-02"),
        # 21 yrs, 0 months; 252 months; end month == start, end day > start
        patient(2, dob="2000-09-01"),
        # 20 yrs, 11 months; 251 months; end month == start, end day < start
        patient(3, dob="2000-09-10"),
        # 31 yrs, 1 months; 373 months; end month > start, end_day == start
        patient(4, dob="1990-08-02"),
        # 31 yrs, 1 months; 373 months; end month > start, end day > start
        patient(5, dob="1990-08-01"),
        # 31 yrs, 0 months; 372 months; end month > start, end day < start
        patient(6, dob="1990-08-10"),
        #  9 yrs, 11 months; 119 months; end month < start, end day > start
        patient(7, dob="2011-10-01"),
        #  9 yrs, 11 months; 119 months; end month < start, end day == start
        patient(8, dob="2011-10-02"),
        #  9 yrs, 10 months; 118 months; end month < start, end day < start
        patient(9, dob="2011-10-15"),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    current_date = "2021-09-02"
    dob = patients.select_column(patients.date_of_birth)  # DateSeries
    age = current_date - dob

    data_definition.age_in_years = age.convert_to_years()
    data_definition.age_in_months = age.convert_to_months()

    result = engine.extract(data_definition)

    assert result == [
        {"patient_id": 1, "age_in_years": 21, "age_in_months": 252},
        {"patient_id": 2, "age_in_years": 21, "age_in_months": 252},
        {"patient_id": 3, "age_in_years": 20, "age_in_months": 251},
        {"patient_id": 4, "age_in_years": 31, "age_in_months": 373},
        {"patient_id": 5, "age_in_years": 31, "age_in_months": 373},
        {"patient_id": 6, "age_in_years": 31, "age_in_months": 372},
        {"patient_id": 7, "age_in_years": 9, "age_in_months": 119},
        {"patient_id": 8, "age_in_years": 9, "age_in_months": 119},
        {"patient_id": 9, "age_in_years": 9, "age_in_months": 118},
    ]


@pytest.mark.parametrize(
    "current_date,age_data",
    [
        (
            "2021-09-02",
            {
                1: dict(dob="2021-09-01", age=1),  # 1 day
                2: dict(dob="2021-01-15", age=230),
                # 16 in Jan, 28 in Feb, 31 Mar/May/Jul/Aug, 30 Apr/Jun, 2 in Sep; start month <2
                3: dict(
                    dob="2019-09-02", age=731
                ),  # one leap year and one non-leap year
            },
        ),
        (
            "2020-01-10",
            {
                1: dict(dob="2020-01-01", age=9),
                2: dict(dob="2019-12-20", age=21),  # across year boundary
                3: dict(
                    dob="1999-01-10", age=7670
                ),  # 16 non leap yrs, 5 leap yrs (2000/4/8/12/16)
            },
        ),
        (
            "1922-02-01",
            {
                1: dict(dob="1921-02-01", age=365),  # 1 yr, start month == 2
                2: dict(
                    dob="1921-08-20", age=165
                ),  # 11 days Aug, 30 Sep/Nov, 31 Oct/Dec/Jan, 1 Feb
                3: dict(
                    dob="1899-01-31", age=8401
                ),  # 18 non leap, 5 leap yrs (1904/8/12/16/20) + 1 day; (1900 != leap)
            },
        ),
    ],
)
def test_date_arithmetic_convert_to_days(
    engine, cohort_with_population, current_date, age_data
):
    input_data = [
        # all dobs are subtracted from current_date, rounded down
        patient(patient_id, dob=patient_data["dob"])
        for patient_id, patient_data in age_data.items()
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    dob = patients.select_column(patients.date_of_birth)  # DateSeries
    age = current_date - dob

    data_definition.age_in_days = age.convert_to_days()

    result = engine.extract(data_definition)
    assert result == [
        {"patient_id": patient_id, "age_in_days": patient_data["age"]}
        for patient_id, patient_data in age_data.items()
    ]


def test_date_arithmetic_convert_to_weeks(engine, cohort_with_population):
    input_data = [
        # all dobs are subtracted from 2021-03-02, rounded down
        patient(1, dob="2021-02-26"),  # 5 days
        patient(2, dob="2021-02-16"),  # exactly 2 weeks
        patient(3, dob="2021-02-03"),  # 3 weeks, 6 days
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    current_date = "2021-03-02"
    dob = patients.select_column(patients.date_of_birth)  # DateSeries
    age = current_date - dob

    data_definition.age_in_weeks = age.convert_to_weeks()

    result = engine.extract(data_definition)

    assert result == [
        {"patient_id": 1, "age_in_weeks": 0},
        {"patient_id": 2, "age_in_weeks": 2},
        {"patient_id": 3, "age_in_weeks": 3},
    ]


def test_date_arithmetic_add_datedeltaseries(engine, cohort_with_population):
    patient1_dob = date(1990, 8, 10)
    patient2_dob = date(1987, 9, 10)
    reference_date_obj = date(1990, 9, 10)
    input_data = [
        patient(1, dob=str(patient1_dob)),
        patient(2, dob=str(patient2_dob)),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date = str(reference_date_obj)
    dob = patients.select_column(patients.date_of_birth)  # -> DateSeries

    age = reference_date - dob  # -> DateDeltaSeries
    data_definition.age_in_days = age.convert_to_days()
    data_definition.dob_plus_age = dob + age

    result = engine.extract(data_definition)

    def _age(dob_obj):
        return reference_date_obj - dob_obj

    assert result == [
        {
            "patient_id": patient_id,
            "age_in_days": _age(patient_dob).days,
            "dob_plus_age": patient_dob + _age(patient_dob),
        }
        for patient_id, patient_dob in [(1, patient1_dob), (2, patient2_dob)]
    ]


def test_date_arithmetic_subtract_datedelta(engine, cohort_with_population):
    patient1_dob = date(1990, 8, 10)
    patient2_dob = date(1987, 9, 10)
    reference_date_obj = date(1990, 9, 10)
    input_data = [
        patient(1, dob=str(patient1_dob)),
        patient(2, dob=str(patient2_dob)),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date = str(reference_date_obj)
    dob = patients.select_column(patients.date_of_birth)  # DateSeries

    age = reference_date - dob
    data_definition.age_in_days = age.convert_to_days()
    data_definition.dob_minus_age = dob - age
    data_definition.dob_minus_10 = dob - 10
    data_definition.ref_minus_age = reference_date - age

    result = engine.extract(data_definition)

    def _age(dob_obj):
        return reference_date_obj - dob_obj

    assert result == [
        {
            "patient_id": patient_id,
            "age_in_days": _age(patient_dob).days,
            "dob_minus_age": patient_dob - _age(patient_dob),
            "dob_minus_10": patient_dob - timedelta(days=10),
            "ref_minus_age": reference_date_obj - _age(patient_dob),
        }
        for patient_id, patient_dob in [(1, patient1_dob), (2, patient2_dob)]
    ]


def test_date_arithmetic_add_datedeltaseries_together(engine, cohort_with_population):
    patient1_dob = date(1990, 8, 10)
    patient2_dob = date(1987, 9, 10)
    reference_date_obj_1990 = date(1990, 9, 10)
    reference_date_obj_2000 = date(2000, 9, 10)
    input_data = [
        patient(1, dob=str(patient1_dob)),
        patient(2, dob=str(patient2_dob)),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date_1990 = str(reference_date_obj_1990)
    reference_date_2000 = str(reference_date_obj_2000)
    dob = patients.select_column(patients.date_of_birth)  # -> DateSeries

    age_in_1990 = reference_date_1990 - dob  # -> DateDeltaSeries
    age_in_2000 = reference_date_2000 - dob  # -> DateDeltaSeries

    data_definition.age_in_days_1990 = age_in_1990.convert_to_days()
    data_definition.age_in_days_2000 = age_in_2000.convert_to_days()

    data_definition.combined_age = age_in_1990 + age_in_2000

    result = engine.extract(data_definition)

    def _days_age_on(dob_obj, reference_date_obj):
        return (reference_date_obj - dob_obj).days

    assert result == [
        {
            "patient_id": patient_id,
            "age_in_days_1990": _days_age_on(patient_dob, reference_date_obj_1990),
            "age_in_days_2000": _days_age_on(patient_dob, reference_date_obj_2000),
            "combined_age": (
                _days_age_on(patient_dob, reference_date_obj_1990)
                + _days_age_on(patient_dob, reference_date_obj_2000)
            ),
        }
        for patient_id, patient_dob in [(1, patient1_dob), (2, patient2_dob)]
    ]


def test_date_arithmetic_add_datedeltaseries_and_integer(
    engine, cohort_with_population
):
    patient1_dob = date(1990, 8, 10)
    patient2_dob = date(1987, 9, 10)
    reference_date_obj = date(1990, 9, 10)
    input_data = [
        patient(1, dob=str(patient1_dob)),
        patient(2, dob=str(patient2_dob)),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date = str(reference_date_obj)
    dob = patients.select_column(patients.date_of_birth)  # -> DateSeries

    age = reference_date - dob  # -> DateDeltaSeries
    data_definition.age_in_days = age.convert_to_days()
    data_definition.age_plus_10 = age + 10
    # We can add a datedeltaseries to an int as well
    data_definition.ten_plus_age = 10 + age

    result = engine.extract(data_definition)

    def _days_age(dob_obj):
        return (reference_date_obj - dob_obj).days

    assert result == [
        {
            "patient_id": patient_id,
            "age_in_days": _days_age(patient_dob),
            "age_plus_10": _days_age(patient_dob) + 10,
            "ten_plus_age": 10 + _days_age(patient_dob),
        }
        for patient_id, patient_dob in [(1, patient1_dob), (2, patient2_dob)]
    ]


def test_date_arithmetic_add_multiple(engine, cohort_with_population):
    patient_dob = date(1990, 8, 10)
    reference_date_obj_1990 = date(1990, 9, 10)
    reference_date_obj_1991 = date(1991, 9, 10)
    input_data = [
        patient(1, dob=str(patient_dob)),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date_1990 = str(reference_date_obj_1990)
    reference_date_1991 = str(reference_date_obj_1991)
    dob = patients.select_column(patients.date_of_birth)  # -> DateSeries

    age_in_1990 = reference_date_1990 - dob  # -> DateDeltaSeries
    age_in_1991 = reference_date_1991 - dob  # -> DateDeltaSeries

    data_definition.age_in_days_1990 = age_in_1990.convert_to_days()
    data_definition.age_in_days_1991 = age_in_1991.convert_to_days()

    data_definition.combined_age_plus_10 = age_in_1990 + age_in_1991 + 10
    data_definition.dob_plus = dob + age_in_1990 + age_in_1991 + 10

    result = engine.extract(data_definition)

    timedelta_age_1990 = (reference_date_obj_1990 - patient_dob).days
    timedelta_age_1991 = (reference_date_obj_1991 - patient_dob).days
    assert result == [
        {
            "patient_id": 1,
            "age_in_days_1990": timedelta_age_1990,
            "age_in_days_1991": timedelta_age_1991,
            "combined_age_plus_10": timedelta_age_1990 + timedelta_age_1991 + 10,
            "dob_plus": patient_dob
            + timedelta(days=timedelta_age_1990 + timedelta_age_1991 + 10),
        }
    ]


def test_date_arithmetic_subtract_two_datedeltaseries(engine, cohort_with_population):
    patient1_dob = date(1990, 8, 10)
    patient2_dob = date(1987, 9, 10)
    reference_date_obj_1990 = date(1990, 9, 10)
    reference_date_obj_2000 = date(2000, 9, 10)
    input_data = [
        patient(1, dob=str(patient1_dob)),
        patient(2, dob=str(patient2_dob)),
    ]

    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date_1990 = str(reference_date_obj_1990)
    reference_date_2000 = str(reference_date_obj_2000)
    dob = patients.select_column(patients.date_of_birth)  # -> DateSeries

    age_in_1990 = reference_date_1990 - dob  # -> DateDeltaSeries
    age_in_2000 = reference_date_2000 - dob  # -> DateDeltaSeries

    data_definition.age_in_days_1990 = age_in_1990.convert_to_days()
    data_definition.age_in_days_2000 = age_in_2000.convert_to_days()

    data_definition.age_diff = age_in_2000 - age_in_1990

    result = engine.extract(data_definition)

    def _days_age_on(dob_obj, reference_date_obj):
        return (reference_date_obj - dob_obj).days

    assert result == [
        {
            "patient_id": patient_id,
            "age_in_days_1990": _days_age_on(patient_dob, reference_date_obj_1990),
            "age_in_days_2000": _days_age_on(patient_dob, reference_date_obj_2000),
            "age_diff": _days_age_on(patient_dob, reference_date_obj_2000)
            - _days_age_on(patient_dob, reference_date_obj_1990),
        }
        for patient_id, patient_dob in [(1, patient1_dob), (2, patient2_dob)]
    ]


def test_date_arithmetic_subtract_datedeltaseries_and_integer(
    engine, cohort_with_population
):
    patient1_dob = date(1990, 8, 10)
    patient2_dob = date(1987, 9, 10)
    reference_date_obj = date(1990, 9, 10)
    input_data = [
        patient(1, dob=str(patient1_dob)),
        patient(2, dob=str(patient2_dob)),
    ]
    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date = str(reference_date_obj)
    dob = patients.select_column(patients.date_of_birth)  # -> DateSeries

    age = reference_date - dob  # -> DateDeltaSeries
    data_definition.age_in_days = age.convert_to_days()
    data_definition.age_minus_10 = age - 10
    data_definition.two_thousand_minus_age = 2000 - age

    result = engine.extract(data_definition)

    def _days_age(dob_obj):
        return (reference_date_obj - dob_obj).days

    assert result == [
        {
            "patient_id": patient_id,
            "age_in_days": _days_age(patient_dob),
            "age_minus_10": _days_age(patient_dob) - 10,
            "two_thousand_minus_age": 2000 - _days_age(patient_dob),
        }
        for patient_id, patient_dob in [(1, patient1_dob), (2, patient2_dob)]
    ]


def test_date_arithmetic_add_and_subtract(engine, cohort_with_population):
    patient_dob = date(1990, 8, 10)
    reference_date_obj_1990 = date(1990, 9, 10)
    reference_date_obj_1991 = date(2000, 9, 10)
    input_data = [patient(1, dob=str(patient_dob))]
    engine.setup(input_data)

    data_definition = cohort_with_population
    reference_date_1990 = str(reference_date_obj_1990)
    reference_date_1991 = str(reference_date_obj_1991)
    dob = patients.select_column(patients.date_of_birth)  # -> DateSeries

    age_in_1990 = reference_date_1990 - dob  # -> DateDeltaSeries
    age_in_1991 = reference_date_1991 - dob  # -> DateDeltaSeries

    data_definition.age_in_days_1990 = age_in_1990.convert_to_days()
    data_definition.age_in_days_1991 = age_in_1991.convert_to_days()

    data_definition.age_diff_plus_10 = age_in_1991 - age_in_1990 + 10
    data_definition.dob_plus_age_diff_plus_10 = dob + age_in_1991 - age_in_1990 + 10

    result = engine.extract(data_definition)

    timedelta_age_1990 = (reference_date_obj_1990 - patient_dob).days
    timedelta_age_1991 = (reference_date_obj_1991 - patient_dob).days

    assert result == [
        {
            "patient_id": 1,
            "age_in_days_1990": timedelta_age_1990,
            "age_in_days_1991": timedelta_age_1991,
            "age_diff_plus_10": timedelta_age_1991 - timedelta_age_1990 + 10,
            "dob_plus_age_diff_plus_10": patient_dob
            + timedelta(days=timedelta_age_1991 - timedelta_age_1990 + 10),
        }
    ]
