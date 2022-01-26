import re

import pytest

from databuilder import codelist
from databuilder.definition import register
from databuilder.definition.base import cohort_registry
from databuilder.dsl import (
    BoolSeries,
    Cohort,
    DateDeltaSeries,
    DateSeries,
    IntSeries,
    PatientSeries,
)
from databuilder.query_model_old import (
    Comparator,
    DateAddition,
    DateDeltaAddition,
    DateDeltaSubtraction,
    DateDifference,
    DateSubtraction,
    RoundToFirstOfMonth,
    RoundToFirstOfYear,
    Value,
    ValueFromRow,
    table,
)
from databuilder.query_utils import get_column_definitions

from .lib.tables import events, positive_tests, registrations
from .lib.util import OldCohortWithPopulation, make_codelist


def test_minimal_cohort_definition(cohort_with_population):
    # Nothing in the registry yet
    assert not cohort_registry.cohorts

    # old DSL
    class OldCohort(OldCohortWithPopulation):
        #  Define tables of interest, filtered to relevant values
        code = table("clinical_events").first_by("date").get("code")

    # new DSL
    cohort = cohort_with_population
    cohort.code = (
        events.sort_by(events.date).first_for_patient().select_column(events.code)
    )

    register(cohort)
    assert cohort in cohort_registry.cohorts
    assert_cohorts_equivalent(cohort, OldCohort)


def test_filter(cohort_with_population):
    class OldCohort(OldCohortWithPopulation):
        # Define tables of interest, filtered to relevant values
        code = (
            table("clinical_events")
            .filter("date", greater_than="2021-01-01")
            .first_by("date")
            .get("code")
        )

    cohort = cohort_with_population
    cohort.code = (
        events.filter(events.date > "2021-01-01")
        .sort_by(events.date)
        .first_for_patient()
        .select_column(events.code)
    )

    assert_cohorts_equivalent(cohort, OldCohort)


@pytest.mark.parametrize(
    "kwarg, method",
    [
        ("equals", "__eq__"),
        ("not_equals", "__ne__"),
        ("less_than", "__lt__"),
        ("less_than_or_equals", "__le__"),
        ("greater_than", "__gt__"),
        ("greater_than_or_equals", "__ge__"),
    ],
)
def test_date_predicates(cohort_with_population, kwarg, method):
    class OldCohort(OldCohortWithPopulation):
        has_code = (
            table("clinical_events").filter("date", **{kwarg: "2021-01-01"}).exists()
        )

    cohort = cohort_with_population
    predicate = getattr(events.date, method)(
        "2021-01-01"
    )  # e.g. events.date >= "2021-01-01"
    cohort.has_code = events.filter(predicate).exists_for_patient()

    assert_cohorts_equivalent(cohort, OldCohort)


@pytest.mark.parametrize(
    "kwarg, method",
    [
        ("equals", "__eq__"),
        ("not_equals", "__ne__"),
        ("less_than", "__lt__"),
        ("less_than_or_equals", "__le__"),
        ("greater_than", "__gt__"),
        ("greater_than_or_equals", "__ge__"),
    ],
)
def test_int_predicates(cohort_with_population, kwarg, method):
    class OldCohort(OldCohortWithPopulation):
        has_code = table("clinical_events").filter("value", **{kwarg: 42}).exists()

    cohort = cohort_with_population
    predicate = getattr(events.value, method)(42)  # e.g. events.value < 42
    cohort.has_code = events.filter(predicate).exists_for_patient()

    assert_cohorts_equivalent(cohort, OldCohort)


def test_comparison_inversion_works(cohort_with_population):
    # Check that authors can write `42 > events.value` as well as `events.value > 42`.
    class OldCohort(OldCohortWithPopulation):
        fish = table("clinical_events").filter("value", less_than=42).exists()

    cohort = cohort_with_population
    cohort.fish = events.filter(42 > events.value).exists_for_patient()

    assert_cohorts_equivalent(cohort, OldCohort)


@pytest.mark.parametrize(
    "kwarg, method",
    [
        ("equals", "__eq__"),
        ("not_equals", "__ne__"),
    ],
)
def test_code_predicates(cohort_with_population, kwarg, method):
    class OldCohort(OldCohortWithPopulation):
        has_code = table("clinical_events").filter("code", **{kwarg: "abc"}).exists()

    cohort = cohort_with_population
    predicate = getattr(events.code, method)("abc")  # e.g. events.code == "abc"
    cohort.has_code = events.filter(predicate).exists_for_patient()

    assert_cohorts_equivalent(cohort, OldCohort)


@pytest.mark.parametrize(
    "kwarg, old_value, method, new_value",
    [
        ("equals", True, "__eq__", True),
        ("equals", False, "__eq__", False),
        ("equals", False, "__ne__", True),
        ("equals", True, "__ne__", False),
    ],
)
def test_bool_predicates(cohort_with_population, kwarg, old_value, method, new_value):
    # Standard Python style frowns on direct equality comparison against True/False, but we want to allow authors to
    # write it this way if they like.
    class OldCohort(OldCohortWithPopulation):
        result = table("positive_tests").filter("result", **{kwarg: old_value}).exists()

    cohort = cohort_with_population
    predicate = getattr(positive_tests.result, method)(
        new_value
    )  # e.g. events.result == True
    cohort.result = positive_tests.filter(predicate).exists_for_patient()

    assert_cohorts_equivalent(cohort, OldCohort)


def test_alternative_bool_predicates(cohort_with_population):
    # We provide these because standard Python style frowns on direct equality comparison against True/False.
    class OldCohort(OldCohortWithPopulation):
        success = table("positive_tests").filter("result", equals=True).exists()
        failure = table("positive_tests").filter("result", equals=False).exists()

    cohort = cohort_with_population
    cohort.success = positive_tests.filter(
        positive_tests.result.is_true()
    ).exists_for_patient()
    cohort.failure = positive_tests.filter(
        positive_tests.result.is_false()
    ).exists_for_patient()

    assert_cohorts_equivalent(cohort, OldCohort)


def test_filter_with_codelist(cohort_with_population):
    class OldCohort(OldCohortWithPopulation):
        code = (
            table("clinical_events")
            .filter("code", is_in=make_codelist("Code1"))
            .first_by("date")
            .get("code")
        )

    cohort = cohort_with_population
    cohort.code = (
        events.filter(events.code.is_in(codelist(["Code1"], "ctv3")))
        .sort_by(events.date)
        .first_for_patient()
        .select_column(events.code)
    )

    assert_cohorts_equivalent(cohort, OldCohort)


def test_multiple_filters(cohort_with_population):
    class OldCohort(OldCohortWithPopulation):
        # Define tables of interest, filtered to relevant values
        code = (
            table("clinical_events")
            .filter("date", greater_than="2021-01-01")
            .filter("date", less_than="2021-10-10")
            .first_by("date")
            .get("code")
        )

    cohort = cohort_with_population
    cohort.code = (
        events.filter(events.date > "2021-01-01")
        .filter(events.date < "2021-10-10")
        .sort_by(events.date)
        .first_for_patient()
        .select_column(events.code)
    )

    assert_cohorts_equivalent(cohort, OldCohort)


def test_count_aggregation(cohort_with_population):
    class OldCohort(OldCohortWithPopulation):
        # Define tables of interest, filtered to relevant values
        num_events = table("clinical_events").count()

    cohort = cohort_with_population
    cohort.num_events = events.count_for_patient()

    assert_cohorts_equivalent(cohort, OldCohort)


def test_exists_aggregation(cohort_with_population):
    class OldCohort(OldCohortWithPopulation):
        # Define tables of interest, filtered to relevant values
        has_events = table("clinical_events").filter("code", not_equals=None).exists()

    cohort = cohort_with_population
    cohort.has_events = events.filter(events.code.is_not_null()).exists_for_patient()

    assert_cohorts_equivalent(cohort, OldCohort)


def test_set_population():
    class OldCohort:
        population = table("practice_registrations").exists("patient_id")

    cohort = Cohort()
    cohort.set_population(registrations.exists_for_patient())
    assert_cohorts_equivalent(cohort, OldCohort)


def test_set_population_variable_must_be_boolean():
    cohort = Cohort()

    with pytest.raises(
        ValueError,
        match=re.escape("Population variable must return a boolean."),
    ):
        cohort.set_population(registrations.count_for_patient())


@pytest.mark.parametrize(
    "variable_def, invalid_type",
    [
        ("code", "str"),
        (events, "Events"),
        (
            events.filter(events.date > "2021-01-01"),
            "EventFrame",
        ),
    ],
)
def test_set_variable_errors(variable_def, invalid_type):
    cohort = Cohort()
    with pytest.raises(
        TypeError,
        match=re.escape(
            f"code must be a single value per patient (got '{invalid_type}')"
        ),
    ):
        cohort.code = variable_def


def test_add_variable():
    cohort1 = Cohort()
    cohort1.set_population(registrations.exists_for_patient())
    cohort1.add_variable("code", events.count_for_patient())

    cohort2 = Cohort()
    cohort2.set_population(registrations.exists_for_patient())
    cohort2.add_variable("code", events.count_for_patient())

    assert_cohorts_equivalent(cohort1, cohort2)


def test_population_required():
    data_definition = Cohort()

    with pytest.raises(ValueError, match="must define a 'population' variable"):
        get_column_definitions(data_definition)

    data_definition.set_population(registrations.exists_for_patient())
    get_column_definitions(data_definition)


def test_patient_series_repr():
    series = (
        registrations.sort_by(registrations.date_end)
        .first_for_patient()
        .select_column(registrations.date_start)
    )
    assert (
        repr(series)
        == "DateSeries(value=ValueFromRow(source=Row(source=Table(name='practice_registrations'), sort_columns=('date_end',), descending=False), column='date_start'))"
    )


def assert_cohorts_equivalent(dsl_cohort, qm_cohort):
    """Verify that a cohort defined via Query Model objects has the same columns as a
    cohort defined via the DSL.

    Since some Query Model objects override `.__eq__`, we cannot compare two objects
    with `==`.  Instead, we compare their representations, which, thanks to dataclasses,
    contain all the information we need to compare for equality.
    """

    # Cohorts are equivalent if they have the same columns...
    dsl_col_defs = get_column_definitions(dsl_cohort)
    qm_col_defs = get_column_definitions(qm_cohort)
    assert sorted(dsl_col_defs.keys()) == sorted(qm_col_defs.keys())

    # ...and if the columns are the same.
    for k in dsl_col_defs:
        assert repr(dsl_col_defs[k]) == repr(qm_col_defs[k])


def test_boolseries_and(bool_series):
    series1 = bool_series()
    series2 = bool_series()

    expected = Comparator(
        connector="and_",
        lhs=Comparator(lhs=series1.value, operator="__ne__"),
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 & series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_boolseries_or(bool_series):
    series1 = bool_series()
    series2 = bool_series()

    expected = Comparator(
        connector="or_",
        lhs=Comparator(lhs=series1.value, operator="__ne__"),
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 | series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_codeseries_and(code_series):
    series1 = code_series()
    series2 = code_series()

    expected = Comparator(
        connector="and_",
        lhs=Comparator(lhs=series1.value, operator="__ne__"),
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 & series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_codeseries_invert(code_series):
    series = code_series()

    expected = Comparator(
        negated=True,
        operator="__ne__",
        lhs=series.value,
    )

    output = ~series
    assert repr(output) == repr(BoolSeries(value=expected))


def test_dateseries_gt(date_series):
    series1 = date_series()
    series2 = date_series()

    expected = Comparator(
        operator="__gt__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 > series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_dateseries_ge(date_series):
    series1 = date_series()
    series2 = date_series()

    expected = Comparator(
        operator="__ge__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 >= series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_dateseries_lt(date_series):
    series1 = date_series()
    series2 = date_series()

    expected = Comparator(
        operator="__lt__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 < series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_dateseries_le(date_series):
    series1 = date_series()
    series2 = date_series()

    expected = Comparator(
        operator="__le__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 <= series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_dateseries_ne(date_series):
    series1 = date_series()
    series2 = date_series()

    expected = Comparator(
        operator="__ne__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 != series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_dateseries_round_to_first_month(date_series):
    series = date_series().round_to_first_of_month()

    expected = DateSeries(value=RoundToFirstOfMonth())

    assert repr(series) == repr(expected)


def test_dateseries_round_to_first_of_year(date_series):
    series = date_series().round_to_first_of_year()

    expected = DateSeries(value=RoundToFirstOfYear())

    assert repr(series) == repr(expected)


def test_dateseries_sub():
    series1 = DateSeries(ValueFromRow(source=None, column="date"))
    series2 = DateSeries(ValueFromRow(source=None, column="start_date"))
    output = series1 - series2

    assert isinstance(output, DateDeltaSeries)
    assert isinstance(output.value, DateDifference)
    start_date_for_operation, end_date_for_operation, units = output.value.arguments

    # the right hand side of the subtraction is the start date, passed in first in the DateDifference args
    assert start_date_for_operation.column == series2.value.column
    assert end_date_for_operation.column == series1.value.column
    assert units == "years"


def test_dateseries_rsub():
    series = DateSeries(ValueFromRow(source=None, column="date"))
    output = "2021-12-01" - series

    assert isinstance(output, DateDeltaSeries)
    assert isinstance(output.value, DateDifference)

    start_date_for_operation, end_date_for_operation, units = output.value.arguments
    # the right hand side of the subtraction is the start date, passed in first in the DateDifference args

    assert start_date_for_operation.column == series.value.column
    assert end_date_for_operation == "2021-12-01"
    assert units == "years"


@pytest.mark.parametrize(
    "left,right",
    [
        (DateSeries(ValueFromRow(source=None, column="date")), "2021"),
        ("2021-02-31", DateSeries(ValueFromRow(source=None, column="date"))),
        (DateSeries(ValueFromRow(source=None, column="date")), "1-2-1999"),
        (DateSeries(ValueFromRow(source=None, column="date")), "Foo"),
    ],
)
def test_dateseries_sub_with_invalid_datestrings(left, right):
    with pytest.raises(
        ValueError, match=".+ is not a valid date; date must in YYYY-MM-DD format"
    ):
        left - right


@pytest.mark.parametrize(
    "other_value,exception,error_match",
    [
        (10, TypeError, "Can't subtract DateSeries from int"),
        ("Foo", ValueError, "Foo is not a valid date"),
    ],
)
def test_dateseries_rsub_errors(other_value, exception, error_match):
    series = DateSeries(ValueFromRow(source=None, column="date"))
    with pytest.raises(exception, match=error_match):
        other_value - series


def test_intseries_gt(int_series):
    series1 = int_series()
    series2 = int_series()

    expected = Comparator(
        operator="__gt__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 > series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_intseries_ge(int_series):
    series1 = int_series()
    series2 = int_series()

    expected = Comparator(
        operator="__ge__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 >= series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_intseries_lt(int_series):
    series1 = int_series()
    series2 = int_series()

    expected = Comparator(
        operator="__lt__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 < series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_intseries_le(int_series):
    series1 = int_series()
    series2 = int_series()

    expected = Comparator(
        operator="__le__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 <= series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_intseries_ne(int_series):
    series1 = int_series()
    series2 = int_series()

    expected = Comparator(
        operator="__ne__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 != series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_patientseries_eq(patient_series):
    series1 = patient_series()
    series2 = patient_series()

    expected = Comparator(
        operator="__eq__",
        lhs=series1.value,
        rhs=Comparator(lhs=series2.value, operator="__ne__"),
    )

    output = series1 == series2
    assert repr(output) == repr(BoolSeries(value=expected))


def test_patientseries_invert():
    series = ~PatientSeries(value=Comparator())
    assert isinstance(series.value, Comparator)
    assert repr(series) == repr(PatientSeries(value=series.value))

    series = ~PatientSeries(value=Value())
    assert isinstance(series.value, Comparator)
    assert repr(series) == repr(PatientSeries(value=series.value))


def test_datedeltaseries_convert_to_years(cohort_with_population):
    series = DateSeries(ValueFromRow(source=None, column="date"))
    deltaseries = DateDeltaSeries(
        value=DateDifference(series, "2021-12-01", units="months")
    )
    assert deltaseries.value.arguments == (series, "2021-12-01", "months")

    year_deltaseries = deltaseries.convert_to_years()
    assert year_deltaseries.value.arguments == (series, "2021-12-01", "years")


def test_datedeltaseries_convert_to_months(cohort_with_population):
    series = DateSeries(ValueFromRow(source=None, column="date"))
    # years is the default
    deltaseries = DateDeltaSeries(value=DateDifference(series, "2021-12-01"))
    assert deltaseries.value.arguments == (series, "2021-12-01", "years")

    month_deltaseries = deltaseries.convert_to_months()
    assert month_deltaseries.value.arguments == (series, "2021-12-01", "months")


def test_datedeltaseries_convert_to_days(cohort_with_population):
    series = DateSeries(ValueFromRow(source=None, column="date"))
    # years is the default
    deltaseries = DateDeltaSeries(value=DateDifference(series, "2021-12-01"))
    assert deltaseries.value.arguments == (series, "2021-12-01", "years")

    days_deltaseries = deltaseries.convert_to_days()
    assert days_deltaseries.value.arguments == (series, "2021-12-01", "days")


def test_datedeltaseries_convert_to_weeks(cohort_with_population):
    series = DateSeries(ValueFromRow(source=None, column="date"))
    # years is the default
    deltaseries = DateDeltaSeries(value=DateDifference(series, "2021-12-01"))
    assert deltaseries.value.arguments == (series, "2021-12-01", "years")

    weeks_deltaseries = deltaseries.convert_to_weeks()
    assert weeks_deltaseries.value.arguments == (series, "2021-12-01", "weeks")


def test_datedeltaseries_convert_with_incorrect_type():
    with pytest.raises(
        ValueError, match="^Can only convert differences between dates$"
    ):
        DateDeltaSeries(value="test").convert_to_years()


def test_dateseries_add_datedelta():
    series = DateSeries(ValueFromRow(source=None, column="date"))
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = series + datedelta

    # Adding a DateDeltaSeries to a DateSeries returns another DateSeries
    assert isinstance(output, DateSeries)
    assert isinstance(output.value, DateAddition)
    series_arg, delta_arg = output.value.arguments

    # first arg in the addition is the date column
    # second arg is the DateDeltaSeries converted to an DateDifference in days
    assert series_arg.column == series.value.column
    assert isinstance(delta_arg, DateDifference)
    assert delta_arg.arguments == ("2021-10-01", "2021-11-01", "days")


def test_dateseries_add_integer():
    series = DateSeries(ValueFromRow(source=None, column="date"))
    output = series + 10

    # Adding an integer to a DateSeries returns another DateSeries
    assert isinstance(output, DateSeries)
    assert isinstance(output.value, DateAddition)
    series_arg, delta_arg = output.value.arguments

    assert series_arg.column == series.value.column
    assert delta_arg == 10


def test_datedelta_add_dateseries():
    series = DateSeries(ValueFromRow(source=None, column="date"))
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = datedelta + series

    # Adding a DateDeltaSeries to a DateSeries returns another DateSeries
    assert isinstance(output, DateSeries)
    assert isinstance(output.value, DateAddition)
    series_arg, delta_arg = output.value.arguments

    # first arg in the addition is the date column
    # second arg is the DateDeltaSeries converted to an DateDifference in days
    assert series_arg.column == series.value.column
    assert isinstance(delta_arg, DateDifference)
    assert delta_arg.arguments == ("2021-10-01", "2021-11-01", "days")


def test_dateseries_radd_integer():
    series = DateSeries(ValueFromRow(source=None, column="date"))
    output = 10 + series

    # Adding an integer to a DateSeries returns another DateSeries
    assert isinstance(output, DateSeries)
    assert isinstance(output.value, DateAddition)
    series_arg, delta_arg = output.value.arguments

    assert series_arg.column == series.value.column
    assert delta_arg == 10


@pytest.mark.parametrize(
    "delta_value,error",
    [
        (
            (
                DateSeries(ValueFromRow(source=None, column="date")) - "2021-10-01"
            ).convert_to_days(),
            re.escape("Can only add integer or DateDeltaSeries (got <IntSeries>)"),
        ),
        (
            IntSeries(ValueFromRow(source=None, column="numeric_value")),
            re.escape("Can only add integer or DateDeltaSeries (got <IntSeries>)"),
        ),
        ("foo", re.escape("Can only add integer or DateDeltaSeries (got <str>)")),
    ],
)
def test_dateseries_add_validation(delta_value, error):
    series = DateSeries(ValueFromRow(source=None, column="date"))
    with pytest.raises(ValueError, match=error):
        series + delta_value


@pytest.mark.parametrize(
    "delta_value,error",
    [
        (
            (
                DateSeries(ValueFromRow(source=None, column="date")) - "2021-10-01"
            ).convert_to_days(),
            re.escape("Can only subtract integer or DateDeltaSeries (got <IntSeries>)"),
        ),
        (
            IntSeries(ValueFromRow(source=None, column="numeric_value")),
            re.escape("Can only subtract integer or DateDeltaSeries (got <IntSeries>)"),
        ),
        ("foo", "foo is not a valid date; date must in YYYY-MM-DD format"),
    ],
)
def test_dateseries_subtract_validation(delta_value, error):
    series = DateSeries(ValueFromRow(source=None, column="date"))
    with pytest.raises(ValueError, match=error):
        series - delta_value


def test_dateseries_sub_datedelta():
    series = DateSeries(ValueFromRow(source=None, column="date"))
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = series - datedelta

    # Adding a DateDeltaSeries to a DateSeries returns another DateSeries
    assert isinstance(output, DateSeries)
    assert isinstance(output.value, DateSubtraction)
    series_arg, delta_arg = output.value.arguments

    # first arg in the addition is the date column
    # second arg is the DateDeltaSeries converted to a DateDifference in days
    assert series_arg.column == series.value.column
    assert isinstance(delta_arg, DateDifference)
    assert delta_arg.arguments == ("2021-10-01", "2021-11-01", "days")


def test_dateseries_sub_integer():
    series = DateSeries(ValueFromRow(source=None, column="date"))
    output = series - 10

    # Adding an integer to a DateSeries returns another DateSeries
    assert isinstance(output, DateSeries)
    assert isinstance(output.value, DateSubtraction)
    series_arg, delta_arg = output.value.arguments

    assert series_arg.column == series.value.column
    assert delta_arg == 10


def test_datedeltaseries_rsub_datestring():
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = "2021-12-10" - datedelta

    # Adding an integer to a DateSeries returns another DateSeries
    assert isinstance(output, DateSeries)
    assert isinstance(output.value, DateSubtraction)
    series_arg, delta_arg = output.value.arguments

    assert series_arg == "2021-12-10"
    assert isinstance(delta_arg, DateDifference)
    assert delta_arg.arguments == ("2021-10-01", "2021-11-01", "days")


def test_add_datedeltaseries_together():
    datedelta1 = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    datedelta2 = DateDeltaSeries(DateDifference("2021-01-01", "2021-02-01"))
    output = datedelta1 + datedelta2

    # Adding DateDeltaSeries together returns another DateDeltaSeries
    assert isinstance(output, DateDeltaSeries)
    assert isinstance(output.value, DateDeltaAddition)
    delta1_arg, delta2_arg = output.value.arguments

    assert isinstance(delta1_arg, DateDifference)
    assert isinstance(delta2_arg, DateDifference)
    assert delta1_arg.arguments == ("2021-10-01", "2021-11-01", "days")
    assert delta2_arg.arguments == ("2021-01-01", "2021-02-01", "days")


def test_add_datedeltaseries_and_integer():
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = datedelta + 20

    # Adding DateDeltaSeries and integer returns another DateDeltaSeries
    assert isinstance(output, DateDeltaSeries)
    assert isinstance(output.value, DateDeltaAddition)
    delta1_arg, delta2_arg = output.value.arguments

    assert isinstance(delta1_arg, DateDifference)
    assert delta1_arg.arguments == ("2021-10-01", "2021-11-01", "days")
    assert delta2_arg == 20


def test_add_datedeltaseries_and_dateseries():
    series = DateSeries(ValueFromRow(source=None, column="date"))
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = datedelta + series

    # Adding DateDeltaSeries and DateSeries returns a DateSeries
    assert isinstance(output, DateSeries)
    assert isinstance(output.value, DateAddition)
    series_arg, delta_arg = output.value.arguments

    assert series_arg.column == series.value.column
    assert isinstance(delta_arg, DateDifference)
    assert delta_arg.arguments == ("2021-10-01", "2021-11-01", "days")


def test_radd_datedeltaseries_and_integer():
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = 20 + datedelta

    # Adding DateDeltaSeries and integer returns another DateDeltaSeries
    assert isinstance(output, DateDeltaSeries)
    assert isinstance(output.value, DateDeltaAddition)
    delta1_arg, delta2_arg = output.value.arguments

    assert isinstance(delta1_arg, DateDifference)
    assert delta1_arg.arguments == ("2021-10-01", "2021-11-01", "days")
    assert delta2_arg == 20


def test_datedeltaseries_sub():
    datedelta1 = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    datedelta2 = DateDeltaSeries(DateDifference("2021-01-01", "2021-02-01"))
    output = datedelta1 - datedelta2

    # Subtracting one DateDeltaSeries from another returns another DateDeltaSeries
    assert isinstance(output, DateDeltaSeries)
    assert isinstance(output.value, DateDeltaSubtraction)
    delta1_arg, delta2_arg = output.value.arguments

    assert isinstance(delta1_arg, DateDifference)
    assert isinstance(delta2_arg, DateDifference)
    assert delta1_arg.arguments == ("2021-10-01", "2021-11-01", "days")
    assert delta2_arg.arguments == ("2021-01-01", "2021-02-01", "days")


def test_datedeltaseries_sub_integer():
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = datedelta - 10

    # Subtracting an integer from DateDeltaSeries returns another DateDeltaSeries
    assert isinstance(output, DateDeltaSeries)
    assert isinstance(output.value, DateDeltaSubtraction)
    delta1_arg, delta2_arg = output.value.arguments

    assert isinstance(delta1_arg, DateDifference)
    assert delta1_arg.arguments == ("2021-10-01", "2021-11-01", "days")
    assert delta2_arg == 10


def test_datedeltaseries_rsub():
    datedelta = DateDeltaSeries(DateDifference("2021-10-01", "2021-11-01"))
    output = 10 - datedelta

    # Subtracting an integer from DateDeltaSeries returns another DateDeltaSeries
    assert isinstance(output, DateDeltaSeries)
    assert isinstance(output.value, DateDeltaSubtraction)
    delta1_arg, delta2_arg = output.value.arguments

    assert isinstance(delta2_arg, DateDifference)
    assert delta1_arg == 10
    assert delta2_arg.arguments == ("2021-10-01", "2021-11-01", "days")
