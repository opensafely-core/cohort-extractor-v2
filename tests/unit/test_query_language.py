from datetime import date
from inspect import signature

import pytest

from databuilder.query_language import (
    BaseSeries,
    BoolEventSeries,
    BoolPatientSeries,
    Dataset,
    DateDifference,
    DateEventSeries,
    DateFunctions,
    DatePatientSeries,
    EventFrame,
    FloatEventSeries,
    FloatPatientSeries,
    IntEventSeries,
    IntPatientSeries,
    PatientFrame,
    SchemaError,
    Series,
    StrEventSeries,
    StrPatientSeries,
    compile,
    days,
    months,
    table,
    table_from_rows,
    years,
)
from databuilder.query_model.nodes import (
    Column,
    Function,
    InlinePatientTable,
    SelectColumn,
    SelectPatientTable,
    SelectTable,
    TableSchema,
    TypeValidationError,
    Value,
)

patients_schema = TableSchema(
    date_of_birth=Column(date), i=Column(int), f=Column(float)
)
patients = PatientFrame(SelectPatientTable("patients", patients_schema))
events_schema = TableSchema(event_date=Column(date), f=Column(float))
events = EventFrame(SelectTable("coded_events", events_schema))


def test_dataset():
    year_of_birth = patients.date_of_birth.year
    dataset = Dataset()
    dataset.set_population(year_of_birth <= 2000)
    dataset.year_of_birth = year_of_birth

    assert dataset.year_of_birth is year_of_birth

    assert compile(dataset) == {
        "year_of_birth": Function.YearFromDate(
            source=SelectColumn(
                name="date_of_birth",
                source=SelectPatientTable("patients", patients_schema),
            )
        ),
        "population": Function.LE(
            lhs=Function.YearFromDate(
                source=SelectColumn(
                    name="date_of_birth",
                    source=SelectPatientTable("patients", patients_schema),
                )
            ),
            rhs=Value(2000),
        ),
    }


def test_dataset_preserves_variable_order():
    dataset = Dataset()
    dataset.set_population(patients.exists_for_patient())
    dataset.foo = patients.date_of_birth.year
    dataset.baz = patients.date_of_birth.year + 100
    dataset.bar = patients.date_of_birth.year - 100

    variables = list(compile(dataset).keys())
    assert variables == ["population", "foo", "baz", "bar"]


def test_assign_population_variable():
    with pytest.raises(AttributeError, match="Cannot set variable 'population'"):
        Dataset().population = patients.exists_for_patient()


def test_cannot_reassign_dataset_variable():
    dataset = Dataset()
    dataset.foo = patients.date_of_birth.year
    with pytest.raises(AttributeError, match="already set"):
        dataset.foo = patients.date_of_birth.year + 100


def test_cannot_assign_frame_to_variable():
    with pytest.raises(TypeError, match="Invalid variable 'patient'"):
        Dataset().patient = patients


def test_cannot_assign_event_series_to_variable():
    with pytest.raises(TypeError, match="Invalid variable 'event_date'"):
        Dataset().event_date = events.event_date


def test_cannot_define_variable_called_variables():
    with pytest.raises(AttributeError, match="variables"):
        Dataset().variables = patients.exists_for_patient()


def test_cannot_define_variable_names_starting_with_double_underscores():
    with pytest.raises(AttributeError, match="underscore"):
        Dataset().__something = patients.exists_for_patient()


def test_accessing_unassigned_variable_gives_helpful_error():
    with pytest.raises(AttributeError, match="'foo' has not been defined"):
        Dataset().foo


# The problem: We'd like to test that operations on query language (QL) elements return
# the correct query model (QM) elements. We like tests that emphasise what is being
# tested, and de-emphasise the scaffolding. We dislike test code that looks like
# production code.

# We'd like Series objects with specific "inner" types. How these Series objects are
# instantiated isn't important.
qm_table = SelectTable(
    name="table",
    schema=TableSchema(int_column=Column(int), date_column=Column(date)),
)
qm_int_series = SelectColumn(source=qm_table, name="int_column")
qm_date_series = SelectColumn(source=qm_table, name="date_column")


def assert_produces(ql_element, qm_element):
    assert ql_element.qm_node == qm_element


class TestIntEventSeries:
    def test_le_value(self):
        assert_produces(
            IntEventSeries(qm_int_series) <= 2000,
            Function.LE(qm_int_series, Value(2000)),
        )

    def test_le_value_reverse(self):
        assert_produces(
            2000 >= IntEventSeries(qm_int_series),
            Function.LE(qm_int_series, Value(2000)),
        )

    def test_le_intseries(self):
        assert_produces(
            IntEventSeries(qm_int_series) <= IntEventSeries(qm_int_series),
            Function.LE(qm_int_series, qm_int_series),
        )

    def test_radd(self):
        assert_produces(
            1 + IntEventSeries(qm_int_series),
            Function.Add(qm_int_series, Value(1)),
        )

    def test_rsub(self):
        assert_produces(
            1 - IntEventSeries(qm_int_series),
            Function.Add(
                Function.Negate(qm_int_series),
                Value(1),
            ),
        )


class TestDateSeries:
    def test_year(self):
        assert_produces(
            DateEventSeries(qm_date_series).year, Function.YearFromDate(qm_date_series)
        )


@pytest.mark.parametrize(
    "lhs,op,rhs,expected_type",
    [
        (patients.f, "-", 10, FloatPatientSeries),
        (patients.f, "+", 10, FloatPatientSeries),
        (patients.f, "<", 10, BoolPatientSeries),
        (events.f, "-", 10, FloatEventSeries),
        (events.f, "<", 10, BoolEventSeries),
        (events.f, ">", 10, BoolEventSeries),
        (events.f, "<", 10.0, BoolEventSeries),
    ],
)
def test_automatic_cast(lhs, op, rhs, expected_type):
    if op == "+":
        result = lhs + rhs
    elif op == "-":
        result = lhs - rhs
    elif op == ">":
        result = lhs > rhs
    elif op == "<":
        result = lhs < rhs
    else:
        assert False
    assert isinstance(result, expected_type)


def test_is_in():
    int_series = IntEventSeries(qm_int_series)
    assert_produces(
        int_series.is_in([1, 2]), Function.In(qm_int_series, Value(frozenset([1, 2])))
    )


def test_passing_a_single_value_to_is_in_raises_error():
    int_series = IntEventSeries(qm_int_series)
    with pytest.raises(TypeValidationError):
        int_series.is_in(1)


def test_series_are_not_hashable():
    # The issue here is not mutability but the fact that we overload `__eq__` for
    # syntatic sugar, which makes these types spectacularly ill-behaved as dict keys
    int_series = IntEventSeries(qm_int_series)
    with pytest.raises(TypeError):
        {int_series: True}


# TEST CLASS-BASED FRAME CONSTRUCTOR
#


def test_construct_constructs_patient_frame():
    @table
    class some_table(PatientFrame):
        some_int = Series(int)
        some_str = Series(str)

    assert isinstance(some_table, PatientFrame)
    assert some_table.qm_node.name == "some_table"
    assert isinstance(some_table.some_int, IntPatientSeries)
    assert isinstance(some_table.some_str, StrPatientSeries)


def test_construct_constructs_event_frame():
    @table
    class some_table(EventFrame):
        some_int = Series(int)
        some_str = Series(str)

    assert isinstance(some_table, EventFrame)
    assert some_table.qm_node.name == "some_table"
    assert isinstance(some_table.some_int, IntEventSeries)
    assert isinstance(some_table.some_str, StrEventSeries)


def test_construct_enforces_correct_base_class():
    with pytest.raises(SchemaError, match="Schema class must subclass"):

        @table
        class some_table(Dataset):
            some_int = Series(int)


def test_construct_enforces_exactly_one_base_class():
    with pytest.raises(SchemaError, match="Schema class must subclass"):

        @table
        class some_table(PatientFrame, Dataset):
            some_int = Series(int)


def test_must_reference_instance_not_class():
    class some_table(PatientFrame):
        some_int = Series(int)

    with pytest.raises(SchemaError, match="Missing `@table` decorator"):
        some_table.some_int


def test_table_from_rows():
    @table_from_rows([(1, 100), (2, 200)])
    class some_table(PatientFrame):
        some_int = Series(int)

    assert isinstance(some_table, PatientFrame)
    assert isinstance(some_table.qm_node, InlinePatientTable)


def test_table_from_rows_only_accepts_patient_frame():
    with pytest.raises(
        SchemaError, match="`@table_from_rows` can only be used with `PatientFrame`"
    ):

        @table_from_rows([])
        class some_table(EventFrame):
            some_int = Series(int)


def test_boolean_operators_raise_errors():
    exists = patients.exists_for_patient()
    has_dob = patients.date_of_birth.is_not_null()
    error = "The keywords 'and', 'or', and 'not' cannot be used with ehrQL"
    with pytest.raises(TypeError, match=error):
        not exists
    with pytest.raises(TypeError, match=error):
        exists and has_dob
    with pytest.raises(TypeError, match=error):
        exists or has_dob
    with pytest.raises(TypeError, match=error):
        date(2000, 1, 1) < patients.date_of_birth < date(2020, 1, 1)


@pytest.mark.parametrize(
    "lhs,op,rhs",
    [
        (100, "+", patients.date_of_birth),
        (100, "-", patients.date_of_birth),
        (patients.date_of_birth, "+", 100),
        (patients.date_of_birth, "-", 100),
        (100, "+", days(100)),
        (100, "-", days(100)),
        (days(100), "+", 100),
        (days(100), "-", 100),
        (date(2010, 1, 1), "+", patients.date_of_birth - "2000-01-01"),
    ],
)
def test_unsupported_date_operations(lhs, op, rhs):
    with pytest.raises(TypeError, match="unsupported operand type"):
        if op == "+":
            lhs + rhs
        elif op == "-":
            lhs - rhs
        else:
            assert False


@pytest.mark.parametrize(
    "lhs,op,rhs,expected",
    [
        # Test each type of Duration constructor
        ("2020-01-01", "+", days(10), date(2020, 1, 11)),
        ("2020-01-01", "+", months(10), date(2020, 11, 1)),
        ("2020-01-01", "+", years(10), date(2030, 1, 1)),
        # Order reversed
        (days(10), "+", "2020-01-01", date(2020, 1, 11)),
        # Subtraction
        ("2020-01-01", "-", years(10), date(2010, 1, 1)),
        # Date objects rather than ISO strings
        (date(2020, 1, 1), "+", years(10), date(2030, 1, 1)),
        (years(10), "+", date(2020, 1, 1), date(2030, 1, 1)),
        (date(2020, 1, 1), "-", years(10), date(2010, 1, 1)),
        # Test addition of Durations
        (days(10), "+", days(5), days(15)),
        (months(10), "+", months(5), months(15)),
        (years(10), "+", years(5), years(15)),
        # Test subtraction of Durations
        (days(10), "-", days(5), days(5)),
        (months(10), "-", months(5), months(5)),
        (years(10), "-", years(5), years(5)),
    ],
)
def test_static_date_operations(lhs, op, rhs, expected):
    if op == "+":
        result = lhs + rhs
    elif op == "-":
        result = lhs - rhs
    else:
        assert False
    assert result == expected


@pytest.mark.parametrize(
    "lhs,op,rhs,expected_type",
    [
        # Test each type of Duration constructor
        (patients.date_of_birth, "+", days(10), DatePatientSeries),
        (patients.date_of_birth, "+", months(10), DatePatientSeries),
        (patients.date_of_birth, "+", years(10), DatePatientSeries),
        # Order reversed
        (days(10), "+", patients.date_of_birth, DatePatientSeries),
        # Subtraction
        (patients.date_of_birth, "-", days(10), DatePatientSeries),
        # Date differences
        (patients.date_of_birth, "-", "2020-01-01", DateDifference),
        (patients.date_of_birth, "-", date(2020, 1, 1), DateDifference),
        # Order reversed
        ("2020-01-01", "-", patients.date_of_birth, DateDifference),
        (date(2020, 1, 1), "-", patients.date_of_birth, DateDifference),
        # DateDifference attributes
        ((patients.date_of_birth - "2020-01-01").days, "+", 1, IntPatientSeries),
        ((patients.date_of_birth - "2020-01-01").months, "+", 1, IntPatientSeries),
        ((patients.date_of_birth - "2020-01-01").years, "+", 1, IntPatientSeries),
        # Test with a "dynamic" duration
        (patients.date_of_birth, "+", days(patients.i), DatePatientSeries),
        (patients.date_of_birth, "+", months(patients.i), DatePatientSeries),
        (patients.date_of_birth, "+", years(patients.i), DatePatientSeries),
        # Test with a dynamic duration and a static date
        (date(2020, 1, 1), "+", days(patients.i), DatePatientSeries),
        (date(2020, 1, 1), "+", months(patients.i), DatePatientSeries),
        (date(2020, 1, 1), "+", years(patients.i), DatePatientSeries),
    ],
)
def test_ehrql_date_operations(lhs, op, rhs, expected_type):
    if op == "+":
        result = lhs + rhs
    elif op == "-":
        result = lhs - rhs
    else:
        assert False
    assert isinstance(result, expected_type)


@pytest.mark.parametrize(
    "lhs,op,rhs",
    [
        (days(10), "+", months(10)),
        (days(10), "-", months(10)),
        (days(10), "+", years(10)),
        (days(10), "-", years(10)),
        (months(10), "+", years(10)),
        (months(10), "-", years(10)),
    ],
)
def test_incompatible_duration_operations(lhs, op, rhs):
    with pytest.raises(TypeError):
        if op == "+":
            result = lhs + rhs
        elif op == "-":
            result = lhs - rhs
        else:
            assert False
        assert not result


fn_names = sorted(
    (
        {k for k, v in DateFunctions.__dict__.items() if callable(v)}
        | {
            k
            for k, v in BaseSeries.__dict__.items()
            # exclude dunder methods as lots inherited from dataclass
            # which don't fit the test pattern below
            if callable(v) and not k.startswith("__")
        }
    )
    # exclude date arithmetic as returned DateDifference doesn't have a qm_node
    - {
        "__add__",
        "__sub__",
        "__radd__",
        "__rsub__",
    },
)


@pytest.mark.parametrize("fn_name", fn_names)
def test_ehrql_date_string_equivalence(fn_name):
    @table
    class p(PatientFrame):
        d = Series(date)

    f = getattr(p.d, fn_name)
    n_params = len(signature(f).parameters)
    date_args = [date(2000, 1, 1) for i in range(n_params)]
    str_args = ["2000-01-01" for i in range(n_params)]

    if fn_name == "map_values":
        date_args = {d: "a" for d in date_args}
        str_args = {s: "a" for s in str_args}

    # avoid over-unpacking iterable params
    if fn_name in ["is_in", "is_not_in", "map_values"]:
        date_args = [date_args]
        str_args = [str_args]

    assert f(*date_args).qm_node == f(*str_args).qm_node
