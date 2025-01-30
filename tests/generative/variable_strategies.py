import datetime
from os import environ

import hypothesis as hyp
import hypothesis.strategies as st
from hypothesis.control import current_build_context

from ehrql.query_model.nodes import (
    AggregateByPatient,
    Case,
    CombinedSeriesFrame,
    Dataset,
    Filter,
    Function,
    InlinePatientTable,
    PickOneRowPerPatient,
    Position,
    SelectColumn,
    SelectPatientTable,
    SelectTable,
    Sort,
    Value,
)
from ehrql.query_model.population_validation import (
    ValidationError,
    validate_population_definition,
)

from .generic_strategies import usually
from .ignored_errors import get_ignored_error_type


# Max depth
#
# There are various points at which we generate deeply recursive data
# which hits Hypothesis's recursion limits, and we need to stop going deeper
# at this point and force generating a terminating node.
#
# Otherwise, the generated graph can continue forever, and will eventually hit the
# hypothesis limit (100) and will be abandoned. This results in too many invalid examples,
# which triggers the too-many-filters healthcheck.
#
# If the max limit is set high - e.g. if we always let it go to 100 and then return our
# default terminating node, generating the examples takes a really long time.  Setting it
# too low means that hypothesis takes too long to shrink examples.
#
# The default is therefore set, somewhat arbitrarily, to 15.

MAX_DEPTH = int(environ.get("GENTEST_MAX_DEPTH", 15))


def depth_exceeded():
    ctx = current_build_context()
    return ctx.data.depth > MAX_DEPTH


@st.composite
def _should_stop(draw):
    """Returns True if we need to stop and generate a terminating node."""

    # Generally speaking we want this to return False unless it needs
    # to return True. This need can either come from the fact that
    # we've exceeded the maximum depth, or because the shrinker told
    # us to.
    #
    # In the former case, we still need to draw a variable that says
    # we should, because this gives us the shrinker the opportunity to
    # set that decision to false, which makes us no longer dependent on
    # hitting the maximum depth to generate a terminating node here.

    should_continue = draw(usually)

    if depth_exceeded():
        should_continue = False

    return not should_continue


should_stop = _should_stop()


@st.composite
def depth_bounded_one_of(draw, *options):
    """Equivalent to `one_of` but if we've got too deep always uses the first option."""
    assert options

    # Similar to how `should_stop` works, we always draw the choice, but if
    # we've exceeded the current maximum depth, we pretend that we got a zero
    # even if we didn't. When the shrinker runs it will change this to zero
    # for real, and then we no longer need to hit maximum depth for this branch
    # to trigger.
    i = draw(st.integers(0, len(options) - 1))
    if depth_exceeded():
        i = 0
    return draw(options[i])


# This module defines a set of recursive Hypothesis strategies for generating query model graphs.
#
# There are a few points where we deliberate order the types that we choose from, with the
# "simplest" first (by some subjective measure). This is to enable Hypothesis to more effectively
# explore the query space and to "shrink" examples when it finds errors. These points are commented
# below.
#
# We use several Hypothesis combinators for defining our strategies. Most (`one_of`, `just`,
# `sampled_from`) are fairly self-explanatory. A couple are worth clarifying.
#     * `st.builds()` is used to construct objects, it takes the class and strategies
#       corresponding to the constructor arguments.
#     * `@st.composite` allows us to define a strategy by composing other strategies with
#       arbitrary Python code; it adds a `draw` argument which is part of the machinery that
#       enables this composition but which doesn't form part of the signature of the resulting
#       strategy function.


def dataset(patient_tables, event_tables, schema, value_strategies):
    # Every inner-function here returns a Hypothesis strategy for creating the thing it is named
    # for, not the thing itself.
    #
    # Several of these strategy functions ignore one or more of their arguments in order to make
    # them uniform with other functions that return the same sort of strategy. Such ignored
    # arguments are named with a leading underscore.

    # Series strategies
    #
    # Whenever a series is needed, we call series() passing the type of the series and frame that
    # it should be built on (these are either constrained by the context in which the series is to
    # be used or chosen arbitrarily by the caller).
    #
    # This strategy then chooses an arbitrary concrete series that respects the constraints imposed
    # by the passed type and frame.
    #
    # A note on frames and domains:
    #
    #     When we pass `frame` as an argument to a series strategy function, the intended semantics
    #     are always "construct a series that is _consistent_ with this frame". It's always
    #     permitted to return a one-row-per-patient series, because such series can always be
    #     composed a many-rows-per-patient series; so there are series strategy functions that,
    #     always or sometimes, ignore the frame argument.

    COMPARABLE_TYPES = [t for t in value_strategies.keys() if t is not bool]

    @st.composite
    def series(draw, type_, frame):
        if draw(should_stop):  # pragma: no cover
            return draw(select_column(type_, frame))

        class DomainConstraint:
            PATIENT = (True,)
            NON_PATIENT = (False,)
            ANY = (True, False)

        # Order matters: "simpler" first (see header comment)
        series_constraints = {
            select_column: (value_strategies.keys(), DomainConstraint.ANY),
            exists: ({bool}, DomainConstraint.PATIENT),
            count: ({int}, DomainConstraint.PATIENT),
            count_distinct: ({int}, DomainConstraint.PATIENT),
            min_: (COMPARABLE_TYPES, DomainConstraint.PATIENT),
            max_: (COMPARABLE_TYPES, DomainConstraint.PATIENT),
            sum_: ({int, float}, DomainConstraint.PATIENT),
            mean: ({float}, DomainConstraint.PATIENT),
            is_null: ({bool}, DomainConstraint.ANY),
            not_: ({bool}, DomainConstraint.ANY),
            year_from_date: ({int}, DomainConstraint.ANY),
            month_from_date: ({int}, DomainConstraint.ANY),
            day_from_date: ({int}, DomainConstraint.ANY),
            to_first_of_year: ({datetime.date}, DomainConstraint.ANY),
            to_first_of_month: ({datetime.date}, DomainConstraint.ANY),
            cast_to_float: ({float}, DomainConstraint.ANY),
            cast_to_int: ({int}, DomainConstraint.ANY),
            negate: ({int, float}, DomainConstraint.ANY),
            eq: ({bool}, DomainConstraint.ANY),
            ne: ({bool}, DomainConstraint.ANY),
            string_contains: ({bool}, DomainConstraint.ANY),
            in_: ({bool}, DomainConstraint.ANY),
            and_: ({bool}, DomainConstraint.ANY),
            or_: ({bool}, DomainConstraint.ANY),
            lt: ({bool}, DomainConstraint.ANY),
            gt: ({bool}, DomainConstraint.ANY),
            le: ({bool}, DomainConstraint.ANY),
            ge: ({bool}, DomainConstraint.ANY),
            add: ({int, float}, DomainConstraint.ANY),
            subtract: ({int, float}, DomainConstraint.ANY),
            multiply: ({int, float}, DomainConstraint.ANY),
            truediv: ({float}, DomainConstraint.ANY),
            floordiv: ({int}, DomainConstraint.ANY),
            date_add_years: ({datetime.date}, DomainConstraint.ANY),
            date_add_months: ({datetime.date}, DomainConstraint.ANY),
            date_add_days: ({datetime.date}, DomainConstraint.ANY),
            date_difference_in_years: ({int}, DomainConstraint.ANY),
            date_difference_in_months: ({int}, DomainConstraint.ANY),
            date_difference_in_days: ({int}, DomainConstraint.ANY),
            count_episodes: ({int}, DomainConstraint.PATIENT),
            case: ({int, float, bool, datetime.date}, DomainConstraint.ANY),
            maximum_of: (COMPARABLE_TYPES, DomainConstraint.ANY),
            minimum_of: (COMPARABLE_TYPES, DomainConstraint.ANY),
        }
        series_types = series_constraints.keys()

        def constraints_match(series_type):
            type_constraint, domain_constraint = series_constraints[series_type]
            return (
                type_ in type_constraint
                and is_one_row_per_patient_frame(frame) in domain_constraint
            )

        possible_series = [s for s in series_types if constraints_match(s)]
        assert possible_series, f"No series matches {type_}, {type(frame)}"

        series_strategy = draw(st.sampled_from(possible_series))
        return draw(series_strategy(type_, frame))

    def value(type_, _frame):
        return st.builds(Value, value_strategies[type_])

    def select_column(type_, frame):
        column_names = [n for n, t in schema.column_types if t == type_]
        return st.builds(SelectColumn, st.just(frame), st.sampled_from(column_names))

    def exists(_type, _frame):
        return st.builds(AggregateByPatient.Exists, any_frame())

    def count(_type, _frame):
        return st.builds(AggregateByPatient.Count, any_frame())

    @st.composite
    def count_distinct(draw, _type, _frame):
        type_ = draw(any_type())
        frame = draw(many_rows_per_patient_frame())
        return AggregateByPatient.CountDistinct(draw(series(type_, frame)))

    @st.composite
    def count_episodes(draw, _type, _frame):
        frame = draw(many_rows_per_patient_frame())
        date_series = draw(series(datetime.date, frame))
        maximum_gap_days = draw(st.integers(1, 5))
        return AggregateByPatient.CountEpisodes(date_series, maximum_gap_days)

    def min_(type_, _frame):
        return aggregation_operation(type_, AggregateByPatient.Min)

    def max_(type_, _frame):
        return aggregation_operation(type_, AggregateByPatient.Max)

    def sum_(type_, _frame):
        return aggregation_operation(type_, AggregateByPatient.Sum)

    def combine_as_set(type_, _frame):
        return aggregation_operation(type_, AggregateByPatient.CombineAsSet)

    @st.composite
    def mean(draw, _type, _frame):
        type_ = draw(any_numeric_type())
        frame = draw(many_rows_per_patient_frame())
        return AggregateByPatient.Mean(draw(series(type_, frame)))

    @st.composite
    def aggregation_operation(draw, type_, aggregation):
        # An aggregation operation that returns a patient series but takes a
        # series drawn from a many-rows-per-patient frame
        frame = draw(many_rows_per_patient_frame())
        return aggregation(draw(series(type_, frame)))

    @st.composite
    def is_null(draw, _type, frame):
        type_ = draw(any_type())
        return Function.IsNull(draw(series(type_, frame)))

    def not_(type_, frame):
        return st.builds(Function.Not, series(type_, frame))

    def year_from_date(_type, frame):
        return st.builds(Function.YearFromDate, series(datetime.date, frame))

    def month_from_date(_type, frame):
        return st.builds(Function.MonthFromDate, series(datetime.date, frame))

    def day_from_date(_type, frame):
        return st.builds(Function.DayFromDate, series(datetime.date, frame))

    def to_first_of_year(_type, frame):
        return st.builds(Function.ToFirstOfYear, series(datetime.date, frame))

    def to_first_of_month(_type, frame):
        return st.builds(Function.ToFirstOfMonth, series(datetime.date, frame))

    @st.composite
    def cast_to_float(draw, _type, frame):
        type_ = draw(any_numeric_type())
        return Function.CastToFloat(draw(series(type_, frame)))

    @st.composite
    def cast_to_int(draw, type_, frame):
        type_ = draw(any_numeric_type())
        return Function.CastToInt(draw(series(type_, frame)))

    def negate(type_, frame):
        return st.builds(Function.Negate, series(type_, frame))

    @st.composite
    def eq(draw, _type, frame):
        type_ = draw(any_type())
        return draw(binary_operation(type_, frame, Function.EQ))

    @st.composite
    def ne(draw, _type, frame):
        type_ = draw(any_type())
        return draw(binary_operation(type_, frame, Function.NE))

    def string_contains(_type, frame):
        return binary_operation(str, frame, Function.StringContains)

    @st.composite
    def in_(draw, _type, frame):
        type_ = draw(any_type())
        if not draw(st.booleans()):
            rhs = Value(
                frozenset(
                    draw(st.sets(value_strategies[type_], min_size=0, max_size=5))
                )
            )
        else:
            rhs = draw(combine_as_set(type_, frame))
        return Function.In(draw(series(type_, frame)), rhs)

    def and_(type_, frame):
        return binary_operation(type_, frame, Function.And, allow_value=False)

    def or_(type_, frame):
        return binary_operation(type_, frame, Function.Or, allow_value=False)

    @st.composite
    def lt(draw, _type, frame):
        type_ = draw(any_comparable_type())
        return draw(binary_operation(type_, frame, Function.LT))

    @st.composite
    def gt(draw, _type, frame):
        type_ = draw(any_comparable_type())
        return draw(binary_operation(type_, frame, Function.GT))

    @st.composite
    def le(draw, _type, frame):
        type_ = draw(any_comparable_type())
        return draw(binary_operation(type_, frame, Function.LE))

    @st.composite
    def ge(draw, _type, frame):
        type_ = draw(any_comparable_type())
        return draw(binary_operation(type_, frame, Function.GE))

    def add(type_, frame):
        return binary_operation(type_, frame, Function.Add)

    def subtract(type_, frame):
        return binary_operation(type_, frame, Function.Subtract)

    def multiply(type_, frame):
        return binary_operation(type_, frame, Function.Multiply)

    def truediv(type_, frame):
        return binary_operation(type_, frame, Function.TrueDivide)

    def floordiv(type_, frame):
        return binary_operation(type_, frame, Function.FloorDivide)

    def date_add_years(type_, frame):
        return binary_operation_with_types(type_, int, frame, Function.DateAddYears)

    def date_add_months(type_, frame):
        return binary_operation_with_types(type_, int, frame, Function.DateAddMonths)

    def date_add_days(type_, frame):
        return binary_operation_with_types(type_, int, frame, Function.DateAddDays)

    def date_difference_in_years(type_, frame):
        return binary_operation(datetime.date, frame, Function.DateDifferenceInYears)

    def date_difference_in_months(type_, frame):
        return binary_operation(datetime.date, frame, Function.DateDifferenceInMonths)

    def date_difference_in_days(type_, frame):
        return binary_operation(datetime.date, frame, Function.DateDifferenceInDays)

    @st.composite
    def case(draw, type_, frame):
        # case takes a mapping argument which is a dict where:
        #   - keys are a bool series
        #   - values are either a series or Value of `type_` or None
        # It also takes a default, which can be None or a Value or series of `type_`
        key_st = series(bool, frame)
        value_st = st.one_of(st.none(), value(type_, frame), series(type_, frame))
        mapping_st = st.dictionaries(key_st, value_st, min_size=1, max_size=3)
        default_st = st.one_of(st.none(), value(type_, frame), series(type_, frame))
        mapping = draw(mapping_st)
        default = draw(default_st)
        # A valid Case needs at least one non-NULL value or a default
        hyp.assume(not all(v is None for v in [default, *mapping.values()]))
        return Case(mapping, default)

    def binary_operation(type_, frame, operator_func, allow_value=True):
        # A strategy for operations that take lhs and rhs arguments of the
        # same type
        return binary_operation_with_types(
            type_, type_, frame, operator_func, allow_value=allow_value
        )

    @st.composite
    def binary_operation_with_types(
        draw, lhs_type, rhs_type, frame, operator_func, allow_value=True
    ):
        # A strategy for operations that take lhs and rhs arguments with specified lhs
        # and rhs types (which may be different)

        # A binary operation has 2 inputs, which are
        # 1) A series drawn from the specified frame
        # 2) one of:
        #    a) A series drawn from the specified frame
        #    b) A series drawn from any one-row-per-patient-frame
        #    c) A series that is a Value
        #       For certain operations, Value is not allowed;  Specifically, for boolean operations
        #       i.e. and/or which take two boolean series as inputs, we exclude operations that would
        #       use True/False constant Values.  These are unlikely to be seen in the wild, and cause
        #       particularly nonsensical Case statements in generative test examples.

        # first pick an "other" input series (i.e. #2 above), either a value series (if allowed)
        # or a series drawn from a frame
        series_options = [value, series] if allow_value else [series]
        other_series = draw(st.sampled_from(series_options))
        # Now pick a frame for the series to be drawn from
        # The other frame will either be a new one-row-per-patient-frame or this frame
        # (Note if the other_series is a value, the frame will be ignored)
        other_frame = draw(st.one_of(one_row_per_patient_frame(), st.just(frame)))

        # Pick the order of the lhs and rhs inputs built from the two frames and
        # associated strategies
        lhs_frame, lhs_input, rhs_frame, rhs_input = draw(
            st.sampled_from(
                [
                    (frame, series, other_frame, other_series),
                    (other_frame, other_series, frame, series),
                ]
            )
        )
        lhs = draw(lhs_input(lhs_type, lhs_frame))
        rhs = draw(rhs_input(rhs_type, rhs_frame))

        return operator_func(lhs, rhs)

    @st.composite
    def nary_operation_with_types(draw, frame, operator_func, series_type):
        # A strategy for operations that take _n_ arguments which are expected to be
        # the same type

        # Decide how many arguments we want – we're intending to test the logic of the
        # query engines, not their scaling properties so we don't need too many
        num_args = draw(st.integers(1, 4))
        # Pick out some arguments (identified by index) to be drawn from other frames
        other_frame_args = draw(
            st.lists(
                # Draw a list of argument indices
                st.integers(0, num_args - 1),
                # Always leaving at least one argument to be drawn from the original
                # frame
                max_size=num_args - 1,
                unique=True,
            )
        )
        args = []
        # Clauses below arranged in order of simplicity (as Hypothesis sees it)
        for i in range(num_args):
            if i not in other_frame_args:
                arg = draw(series(series_type, frame))
            else:
                # If it's not drawn from the supplied frame then it should be either a
                # value or a one-row-per-patient series
                if not draw(st.booleans()):
                    arg = draw(value(series_type, None))
                else:
                    arg = draw(series(series_type, draw(one_row_per_patient_frame())))
            args.append(arg)
        return operator_func(tuple(args))

    def maximum_of(type_, frame):
        return nary_operation_with_types(frame, Function.MaximumOf, type_)

    def minimum_of(type_, frame):
        return nary_operation_with_types(frame, Function.MinimumOf, type_)

    def any_type():
        return st.sampled_from(list(value_strategies.keys()))

    def any_numeric_type():
        return st.sampled_from([int, float])

    def any_comparable_type():
        return st.sampled_from(COMPARABLE_TYPES)

    # Frame strategies
    #
    # The main concern when choosing a frame is whether it has one or many rows per patient. Some
    # callers require one or the other, some don't mind; so we provide strategies for each case.
    # And sometimes callers need _either_ the frame they have in their hand _or_ an arbitrary
    # patient frame, so we provide a strategy for that too.
    #
    # At variance with the general approach here, many-rows-per-patient frames are created by
    # imperatively building stacks of filters on top of select nodes, rather than relying on
    # recursion, because it enormously simplifies the logic needed to keep filter conditions
    # consistent with the source.
    def any_frame():
        # Order matters: "simpler" first (see header comment)
        return st.one_of(
            one_row_per_patient_frame(),
            many_rows_per_patient_frame(),
        )

    def one_row_per_patient_frame():
        return depth_bounded_one_of(
            select_patient_table(),
            pick_one_row_per_patient_frame(),
            inline_patient_table(),
        )

    def many_rows_per_patient_frame():
        return depth_bounded_one_of(select_table(), filtered_table())

    @st.composite
    def filtered_table(draw):
        source = draw(select_table())
        for _ in range(draw(st.integers(min_value=1, max_value=6))):
            source = draw(filter_(source))
        return source

    @st.composite
    def sorted_frame(draw):
        # Decide how many Sorts and Filters (if any) we're going to apply
        operations = draw(
            st.lists(st.sampled_from([sort, filter_]), min_size=1, max_size=9).filter(
                lambda ls: (1 <= ls.count(sort) <= 3) and (ls.count(filter_) <= 6)
            )
        )
        # Pick a table and apply the operations
        source = draw(select_table())
        for operation in operations:
            source = draw(operation(source))
        return source

    @st.composite
    def pick_one_row_per_patient_frame(draw):
        source = draw(sorted_frame())
        sort_order = draw(st.sampled_from([Position.FIRST, Position.LAST]))
        return PickOneRowPerPatient(source, sort_order)

    def select_table():
        return st.builds(SelectTable, st.sampled_from(event_tables), st.just(schema))

    def select_patient_table():
        return st.builds(
            SelectPatientTable, st.sampled_from(patient_tables), st.just(schema)
        )

    @st.composite
    def inline_patient_table(draw):
        return InlinePatientTable(
            rows=tuple(
                draw(
                    st.lists(
                        st.tuples(
                            st.integers(1, 10),
                            *[
                                value_strategies[type_]
                                for name, type_ in schema.column_types
                            ],
                        ),
                        unique_by=lambda r: r[0],
                    ),
                )
            ),
            schema=schema,
        )

    @st.composite
    def filter_(draw, source):
        condition = draw(series(bool, draw(ancestor_of(source))))
        return Filter(source, condition)

    @st.composite
    def sort(draw, source):
        type_ = draw(any_comparable_type())
        sort_by = draw(series(type_, draw(ancestor_of(source))))
        return Sort(source, sort_by)

    @st.composite
    def ancestor_of(draw, frame):
        for _ in range(draw(st.integers(min_value=0, max_value=3))):
            if hasattr(frame, "source"):
                frame = frame.source
            else:
                break
        return frame

    # Variable strategy
    #
    # Puts everything above together to create a variable.
    @st.composite
    def valid_patient_variable(draw):
        type_ = draw(any_type())
        frame = draw(one_row_per_patient_frame())
        return draw(series(type_, frame))

    @st.composite
    def valid_event_series(draw):
        type_ = draw(any_type())
        frame = draw(many_rows_per_patient_frame())
        return draw(series(type_, frame))

    # A population definition is a boolean-typed variable that meets some additional
    # criteria enforced by the query model
    @st.composite
    def valid_population(draw):
        frame = draw(one_row_per_patient_frame())
        population = draw(series(bool, frame))
        hyp.assume(is_valid_population(population))
        return population

    return st.builds(
        make_dataset, valid_population(), valid_patient_variable(), valid_event_series()
    )


def make_dataset(population, patient_variable, event_series):
    return Dataset(
        population=population,
        variables={"v": patient_variable},
        events={
            "event_table": CombinedSeriesFrame({"e": event_series}),
        },
    )


def is_valid_population(series):
    try:
        validate_population_definition(series)
        return True
    except ValidationError:
        return False
    except Exception as e:  # pragma: no cover
        if get_ignored_error_type(e):
            return False
        raise


def is_one_row_per_patient_frame(frame):
    return isinstance(frame, SelectPatientTable | PickOneRowPerPatient)
