import datetime
from collections.abc import Set
from types import SimpleNamespace
from typing import Any

import pytest

from ehrql.codes import CTV3Code, SNOMEDCTCode
from ehrql.query_model.nodes import (
    AggregateByPatient,
    Case,
    Column,
    CombinedSeriesFrame,
    Dataset,
    DomainMismatchError,
    Filter,
    Frame,
    Function,
    InlinePatientTable,
    InvalidSortError,
    PatientDomainError,
    PickOneRowPerPatient,
    Position,
    SelectColumn,
    SelectPatientTable,
    SelectTable,
    Series,
    Sort,
    TableSchema,
    TypeValidationError,
    Value,
    get_domain,
    get_series_type,
    has_one_row_per_patient,
)


EVENTS_SCHEMA = TableSchema(
    date=Column(datetime.date), code=Column(str), flag=Column(bool)
)


# TEST BASIC QUERY MODEL PROPERTIES
#


@pytest.fixture
def queries():
    q = SimpleNamespace()

    patients = SelectPatientTable("patients", TableSchema(sex=Column(str)))
    events = SelectTable("events", EVENTS_SCHEMA)
    code = SelectColumn(events, "code")
    date = SelectColumn(events, "date")
    vaccinations = Filter(events, Function.EQ(code, Value("abc123")))
    anaphylaxis_events = Filter(
        events, Function.In(code, Value(frozenset({"def456", "xyz789"})))
    )

    q.sex = SelectColumn(patients, "sex")
    q.vaccination_count = AggregateByPatient.Count(vaccinations)
    q.first_vaccination = PickOneRowPerPatient(Sort(vaccinations, date), Position.FIRST)
    q.vaccination_status = Case(
        {
            Function.LT(q.vaccination_count, Value(0)): None,
            Function.EQ(q.vaccination_count, Value(1)): Value("partial"),
            Function.EQ(q.vaccination_count, Value(2)): Value("full"),
            Function.GE(q.vaccination_count, Value(3)): Value("boosted"),
        },
        default=Value("unvaccinated"),
    )

    q.vaccination_days = SelectColumn(vaccinations, "date")
    q.vaccination_days_set = AggregateByPatient.CombineAsSet(q.vaccination_days)
    q.anaphylaxis_co_occurance = Filter(
        anaphylaxis_events, Function.In(date, q.vaccination_days_set)
    )
    q.had_anaphylaxis = AggregateByPatient.Exists(q.anaphylaxis_co_occurance)

    inline_table = InlinePatientTable(
        rows=(
            (1, 100),
            (2, 200),
        ),
        schema=TableSchema(i=Column(int)),
    )
    q.inline_value = SelectColumn(inline_table, "i")

    return q


def test_queries_have_expected_types(queries):
    assert isinstance(queries.sex, Series)
    assert isinstance(queries.vaccination_count, Series)
    assert isinstance(queries.first_vaccination, Frame)
    assert isinstance(queries.vaccination_status, Series)
    assert isinstance(queries.vaccination_days, Series)
    assert isinstance(queries.vaccination_days_set, Series)
    assert isinstance(queries.anaphylaxis_co_occurance, Frame)
    assert isinstance(queries.had_anaphylaxis, Series)
    assert isinstance(queries.inline_value, Series)


def test_queries_have_expected_dimension(queries):
    assert has_one_row_per_patient(queries.sex)
    assert has_one_row_per_patient(queries.vaccination_count)
    assert has_one_row_per_patient(queries.first_vaccination)
    assert has_one_row_per_patient(queries.vaccination_status)
    assert not has_one_row_per_patient(queries.vaccination_days)
    assert has_one_row_per_patient(queries.vaccination_days_set)
    assert not has_one_row_per_patient(queries.anaphylaxis_co_occurance)
    assert has_one_row_per_patient(queries.had_anaphylaxis)
    assert has_one_row_per_patient(queries.inline_value)


def test_series_contain_expected_types(queries):
    assert get_series_type(queries.sex) is str
    assert get_series_type(queries.vaccination_count) is int
    assert get_series_type(queries.vaccination_status) is str
    assert get_series_type(queries.vaccination_days) is datetime.date
    # Generic types need equality, not identity, checks
    assert get_series_type(queries.vaccination_days_set) == Set[datetime.date]
    assert get_series_type(queries.had_anaphylaxis) is bool
    assert get_series_type(queries.inline_value) is int


def test_queries_are_hashable(queries):
    for query in vars(queries).values():
        assert hash(query) is not None


def test_unhashable_arguments_are_rejected():
    with pytest.raises(TypeError):
        Value({1, 2, 3})


# We don't _have_ to maintain this property, but it's quite a convenient one to have and
# if we're going to break it then let's at least do so deliberately
def test_query_reprs_round_trip(queries):
    # This relies on all public query model names being imported into local scope
    for query in vars(queries).values():
        assert eval(repr(query)) == query


def test_inline_patient_table_accepts_arbitrary_iterables():
    class MyIter:
        def __iter__(self):
            raise NotImplementedError()

    assert InlinePatientTable(
        rows=MyIter(),
        schema=TableSchema(i=Column(int)),
    )


@pytest.mark.parametrize(
    "rows,error",
    [
        (
            object(),
            "must be iterable",
        ),
        (
            iter(((1, 2), (3, 4))),
            "must not be an iterator",
        ),
        (
            [(1, 2), (3, 4)],
            "must be hashable",
        ),
    ],
)
def test_inline_patient_table_rejects_invalid_types(rows, error):
    with pytest.raises(TypeError, match=error):
        InlinePatientTable(
            rows=rows,
            schema=TableSchema(i=Column(int)),
        )


# TEST DOMAIN VALIDATION
#


# The simple, happy case: combining series derived directly from the same frame
def test_combining_series_from_same_frame_is_ok():
    events = SelectTable(
        "events", TableSchema(value_1=Column(int), value_2=Column(int))
    )
    value_1 = SelectColumn(events, "value_1")
    value_2 = SelectColumn(events, "value_2")
    assert Function.GT(value_1, value_2)


# We can also combine with a one-row-per-patient series derived from a different frame
# because we know we can always join by patient_id
def test_combining_a_patient_level_series_from_a_different_frame_is_ok():
    events = SelectTable("events", EVENTS_SCHEMA)
    vaccinations = SelectTable("vaccinations", EVENTS_SCHEMA)
    event_date = SelectColumn(events, "date")
    vaccination_date = SelectColumn(vaccinations, "date")
    # This makes a one-row-per-patient series which can be combined arbitrarily with
    # other series
    first_event_date = AggregateByPatient.Min(event_date)
    assert Function.EQ(first_event_date, vaccination_date)


# But we can't combine many-rows-per-patient series derived from different frames
def test_combining_non_patient_level_series_from_different_frames_throws_error():
    events = SelectTable("events", EVENTS_SCHEMA)
    vaccinations = SelectTable("vaccinations", EVENTS_SCHEMA)
    event_date = SelectColumn(events, "date")
    vaccination_date = SelectColumn(vaccinations, "date")
    with pytest.raises(DomainMismatchError):
        Function.EQ(event_date, vaccination_date)


# And in particular, we can't filter a Frame using a predicate (boolean Series) derived
# from a different Frame
def test_filtering_one_frame_by_a_condition_derived_from_another_throws_error():
    events = SelectTable("events", EVENTS_SCHEMA)
    vaccinations = SelectTable("vaccinations", EVENTS_SCHEMA)
    vaccine_code = SelectColumn(vaccinations, "code")
    filter_condition = Function.EQ(vaccine_code, Value("abc123"))
    with pytest.raises(DomainMismatchError):
        Filter(events, filter_condition)


# And ditto for sort
def test_sorting_one_frame_by_a_series_derived_from_another_throws_an_error():
    events = SelectTable("events", EVENTS_SCHEMA)
    vaccinations = SelectTable("vaccinations", EVENTS_SCHEMA)
    vaccine_code = SelectColumn(vaccinations, "code")
    with pytest.raises(DomainMismatchError):
        Sort(events, vaccine_code)


# We also can't combine results derived from the same source table if they've been
# through divergent filter operations. Although such operations aren't *complete*
# nonsense, there's never a good reason to do this and so instances of this are almost
# certainly a result of user confusion or error and we want to reject them immediately.
def test_combining_results_of_different_filter_operations_throws_an_error():
    events = SelectTable("events", EVENTS_SCHEMA)
    foo_events = Filter(events, Function.EQ(SelectColumn(events, "code"), Value("foo")))
    bar_events = Filter(events, Function.EQ(SelectColumn(events, "code"), Value("bar")))
    with pytest.raises(DomainMismatchError):
        Function.EQ(SelectColumn(foo_events, "date"), SelectColumn(bar_events, "date"))


# And once a table has been filtered, we can no longer combine the results with the filtered table
def test_combining_filtered_results_with_the_original_table_throws_an_error():
    events = SelectTable("events", EVENTS_SCHEMA)
    foo_events = Filter(events, Function.EQ(SelectColumn(events, "code"), Value("foo")))
    with pytest.raises(DomainMismatchError):
        Function.EQ(SelectColumn(foo_events, "date"), SelectColumn(events, "date"))


# And in particular we can't filter a frame using a predicate derived from a different
# filter operation. Again, this isn't complete nonsense but it's not the best way to
# express the query and is most probably the result of confusion.
def test_filtering_frame_using_result_derived_from_another_filter_throws_error():
    events = SelectTable("events", EVENTS_SCHEMA)
    older_events = Filter(
        events,
        Function.LT(SelectColumn(events, "date"), Value(datetime.date(2022, 1, 1))),
    )
    recent_events = Filter(
        events,
        Function.GE(SelectColumn(events, "date"), Value(datetime.date(2022, 1, 1))),
    )
    is_recent_foo_event = Function.EQ(SelectColumn(recent_events, "code"), Value("foo"))
    with pytest.raises(DomainMismatchError):
        Filter(older_events, is_recent_foo_event)


# However, it's fine to filter a Frame using a predicate derived from a direct ancenstor
# of that Frame. This is important because it allows us to provide a "fluent" interface to
# the Query Model. Without this, every time you wanted to filter a Frame you'd need a
# reference to that Frame to use in the filter condition. And that would make it
# impossible to use chained constructions like:
#
#     events.filter(...).filter(events.date > ...)
#
def test_filtering_frame_using_condition_derived_from_parent_frame_is_ok():
    events = SelectTable("events", EVENTS_SCHEMA)
    foo_events = Filter(events, Function.EQ(SelectColumn(events, "code"), Value("foo")))
    recent_foo_events = Filter(
        foo_events,
        # Note that we're filtering `foo_events` using a condition derived from `events`
        Function.GE(SelectColumn(events, "date"), Value(datetime.date(2022, 1, 1))),
    )
    assert recent_foo_events


# But not the other way around...
def test_filtering_frame_using_condition_derived_from_child_frame_is_not_ok():
    events = SelectTable("events", EVENTS_SCHEMA)
    foo_events = Filter(events, Function.EQ(SelectColumn(events, "code"), Value("foo")))
    with pytest.raises(DomainMismatchError):
        Filter(
            events,
            # Here we're filtering `events` using a condition derived from `foo_events`
            Function.GE(
                SelectColumn(foo_events, "date"), Value(datetime.date(2022, 1, 1))
            ),
        )


# And similarly for sort, we can't sort on a series derived from a divergent filter
def test_sorting_frame_using_result_derived_from_another_filter_throws_error():
    events = SelectTable("events", EVENTS_SCHEMA)
    older_events = Filter(
        events,
        Function.LT(SelectColumn(events, "date"), Value(datetime.date(2022, 1, 1))),
    )
    recent_events = Filter(
        events,
        Function.GE(SelectColumn(events, "date"), Value(datetime.date(2022, 1, 1))),
    )
    recent_codes = SelectColumn(recent_events, "code")
    with pytest.raises(DomainMismatchError):
        Sort(older_events, recent_codes)


# But we can sort using a series derived from an ancestor, to allow this kind of construction:
#
#     events.filter(...).sort(events.date)
#
def test_sorting_frame_using_condition_derived_from_parent_frame_is_ok():
    events = SelectTable("events", EVENTS_SCHEMA)
    foo_events = Filter(events, Function.EQ(SelectColumn(events, "code"), Value("foo")))
    sorted_foo_events = Sort(foo_events, SelectColumn(events, "date"))
    assert sorted_foo_events


# But not the other way around...
def test_sorting_frame_using_value_derived_from_child_frame_is_not_ok():
    events = SelectTable("events", EVENTS_SCHEMA)
    foo_events = Filter(events, Function.EQ(SelectColumn(events, "code"), Value("foo")))
    with pytest.raises(DomainMismatchError):
        Sort(events, SelectColumn(foo_events, "date"))


def test_cannot_sort_frame_by_patient_domain():
    events = SelectTable("events", EVENTS_SCHEMA)
    with pytest.raises(InvalidSortError):
        Sort(events, Value(1))


def test_can_aggregate_a_many_rows_per_patient_series():
    events = SelectTable("events", EVENTS_SCHEMA)
    dates = SelectColumn(events, "date")
    assert AggregateByPatient.Max(dates)


def test_cannot_aggregate_a_one_row_per_patient_series():
    events = SelectTable("events", EVENTS_SCHEMA)
    dates = SelectColumn(events, "date")
    first_event = PickOneRowPerPatient(Sort(events, dates), Position.FIRST)
    first_date = SelectColumn(first_event, "date")
    with pytest.raises(DomainMismatchError):
        AggregateByPatient.Max(first_date)


def test_can_construct_dataset():
    events = SelectTable("events", EVENTS_SCHEMA)
    dates = SelectColumn(events, "date")
    assert Dataset(
        population=AggregateByPatient.Exists(events),
        variables={"max_date": AggregateByPatient.Max(dates)},
        events={},
    )


def test_can_construct_dataset_with_no_variables():
    events = SelectTable("events", EVENTS_SCHEMA)
    assert Dataset(
        population=AggregateByPatient.Exists(events),
        variables={},
        events={},
    )


def test_cannot_use_event_series_in_dataset_variables():
    events = SelectTable("events", EVENTS_SCHEMA)
    dates = SelectColumn(events, "date")
    with pytest.raises(DomainMismatchError):
        Dataset(
            population=AggregateByPatient.Exists(events),
            variables={"date": dates},
            events={},
        )


def test_can_use_event_series_in_dataset_events():
    events = SelectTable("events", EVENTS_SCHEMA)
    dates = SelectColumn(events, "date")
    codes = SelectColumn(events, "code")
    foo_events = Filter(events, Function.EQ(SelectColumn(events, "code"), Value("foo")))
    foo_dates = SelectColumn(foo_events, "date")
    foo_codes = SelectColumn(foo_events, "code")
    assert Dataset(
        population=AggregateByPatient.Exists(events),
        variables={},
        events={
            "events": CombinedSeriesFrame(
                {
                    "dates": dates,
                    "codes": codes,
                }
            ),
            "foo_events": CombinedSeriesFrame(
                {
                    "dates": foo_dates,
                    "codes": foo_codes,
                }
            ),
        },
    )


def test_cannot_combine_patient_series_alone():
    patients = SelectPatientTable("patients", EVENTS_SCHEMA)
    patient_dates = SelectColumn(patients, "date")
    patient_codes = SelectColumn(patients, "code")
    with pytest.raises(PatientDomainError):
        CombinedSeriesFrame(
            {
                "dates": patient_dates,
                "codes": patient_codes,
            }
        )


def test_domain_get_node():
    events = SelectTable("events", EVENTS_SCHEMA)
    # This filter operation creates a new domain
    older_events = Filter(
        events,
        Function.LT(SelectColumn(events, "date"), Value(datetime.date(2022, 1, 1))),
    )
    # But the Sort and SelectColumn doesn't
    sorted_by_date = Sort(older_events, SelectColumn(events, "date"))
    codes_by_date = SelectColumn(sorted_by_date, "code")
    domain = get_domain(codes_by_date)
    # So the node corresponding to the domain should be the Filter
    assert domain.get_node() == older_events


def test_domain_get_node_fails_for_patient_domain():
    patient_domain = get_domain(Value("abc"))
    with pytest.raises(AssertionError):
        patient_domain.get_node()


# TEST TYPE VALIDATION
#


def test_cannot_sort_by_non_comparable_type():
    events = SelectTable("events", EVENTS_SCHEMA)
    bool_column = SelectColumn(events, "flag")
    with pytest.raises(TypeValidationError):
        Sort(events, bool_column)


def test_cannot_pass_argument_without_wrapping_in_value():
    events = SelectTable("events", EVENTS_SCHEMA)
    date = SelectColumn(events, "date")
    with pytest.raises(TypeValidationError):
        Function.EQ(date, datetime.date(2020, 1, 1))  # type: ignore


def test_cannot_compare_date_and_int():
    events = SelectTable("events", EVENTS_SCHEMA)
    date = SelectColumn(events, "date")
    with pytest.raises(TypeValidationError):
        Function.EQ(date, Value(2000))


def test_comparisons_between_codes_are_ok():
    ctv3_events = SelectTable("ctv3_events", schema=TableSchema(code=Column(CTV3Code)))
    code = SelectColumn(ctv3_events, "code")
    assert Function.EQ(code, Value(CTV3Code("abc00")))


def test_attempts_to_mix_coding_systems_are_rejected():
    ctv3_events = SelectTable("ctv3_events", schema=TableSchema(code=Column(CTV3Code)))
    code = SelectColumn(ctv3_events, "code")
    with pytest.raises(TypeValidationError):
        Function.EQ(code, Value(SNOMEDCTCode("123000")))


def test_attempts_to_mix_codes_and_strings_are_rejected():
    ctv3_events = SelectTable("ctv3_events", schema=TableSchema(code=Column(CTV3Code)))
    code = SelectColumn(ctv3_events, "code")
    with pytest.raises(TypeValidationError):
        Function.EQ(code, Value("abc00"))


def test_cannot_define_operation_returning_any_type(queries):
    # This is a guard against future programmer error. It's legitimate to have
    # operations which accept Any, but it's never valid as a return type and it should
    # trigger an assertion if we ever try to define and use such an operation.
    class BadOperation(Series[Any]):
        source: Series[Any]

    with pytest.raises(AssertionError, match=r"never return Series\[Any\]"):
        get_series_type(BadOperation(queries.vaccination_count))


@pytest.mark.parametrize(
    "lhs,cmp,rhs",
    [
        (10, "==", 10),
        (10, "!=", 11),
        (10, "!=", 10.0),
        (True, "==", True),
        (True, "!=", False),
        (1, "!=", True),
        (1.0, "!=", True),
        (0, "!=", False),
        (0.0, "!=", False),
        # Test that we're strict about booleans embedded in frozensets
        (frozenset({True}), "==", frozenset({True})),
        (frozenset({True}), "!=", frozenset({False})),
        (frozenset({1}), "!=", frozenset({True})),
        (frozenset({1.0}), "!=", frozenset({True})),
        (frozenset({0}), "!=", frozenset({False})),
        (frozenset({0.0}), "!=", frozenset({False})),
        (frozenset({True, False}), "==", frozenset({False, True})),
        # Test the fast path for identical frozensets
        (example := frozenset({1, 2, 3}), "==", example),
        # Test the fast path for different sized frozensets
        (frozenset({1, 2, 3}), "!=", frozenset({1, 2})),
        # Test the normal path for frozenset equality
        (frozenset({1, 2, 3}), "==", frozenset({3, 2, 1})),
        (frozenset({1, 2, 3}), "!=", frozenset({4, 5, 6})),
    ],
)
def test_comparisons_between_value_nodes_are_strict(lhs, cmp, rhs):
    if cmp == "==":
        assert Value(lhs) == Value(rhs)
    elif cmp == "!=":
        assert Value(lhs) != Value(rhs)
    else:
        assert False


def test_value_nodes_are_not_equal_to_bare_values():
    assert Value(10) != 10


def test_value_nodes_reject_unhandled_container_types():
    with pytest.raises(
        TypeError, match="does not know how to handle containers of type"
    ):
        Value((1, 2, 3))


# TEST SORTING
#


def test_cannot_pick_row_from_unsorted_table():
    events = SelectTable("events", EVENTS_SCHEMA)
    with pytest.raises(
        TypeValidationError,
        match=(
            "PickOneRowPerPatient.source requires 'SortedFrame' "
            "but received 'UnsortedFrame'"
        ),
    ):
        PickOneRowPerPatient(events, Position.FIRST)


def test_can_pick_row_from_sorted_and_filtered_table():
    events = SelectTable("events", EVENTS_SCHEMA)
    date = SelectColumn(events, "date")
    code = SelectColumn(events, "code")
    sorted_by_date = Sort(events, date)
    filtered_by_code = Filter(sorted_by_date, Function.EQ(code, Value("abc123")))
    assert PickOneRowPerPatient(filtered_by_code, Position.FIRST)
