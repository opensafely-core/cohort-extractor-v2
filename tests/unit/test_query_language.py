import re
import traceback
from datetime import date
from inspect import signature

import pytest

import ehrql.query_model.nodes as qm
from ehrql.codes import ICD10MultiCodeString, OPCS4MultiCodeString, SNOMEDCTCode
from ehrql.file_formats import FILE_FORMATS, write_rows
from ehrql.query_language import (
    BaseSeries,
    BoolEventSeries,
    BoolPatientSeries,
    CodePatientSeries,
    Dataset,
    DateDifference,
    DateEventSeries,
    DateFunctions,
    DatePatientSeries,
    Error,
    EventFrame,
    FloatEventSeries,
    FloatPatientSeries,
    IntEventSeries,
    IntPatientSeries,
    Parameter,
    PatientFrame,
    Series,
    StrEventSeries,
    StrPatientSeries,
    case,
    create_dataset,
    days,
    modify_exception,
    months,
    parse_date_if_str,
    table,
    table_from_file,
    table_from_rows,
    validate_patient_series_type,
    weeks,
    when,
    years,
)
from ehrql.query_model.column_specs import ColumnSpec
from ehrql.query_model.nodes import (
    Column,
    Function,
    InlinePatientTable,
    SelectColumn,
    SelectPatientTable,
    SelectTable,
    TableSchema,
    Value,
)


@table
class patients(PatientFrame):
    date_of_birth = Series(date)
    i = Series(int)
    f = Series(float)


patients_schema = TableSchema(
    date_of_birth=Column(date), i=Column(int), f=Column(float)
)


@table
class events(EventFrame):
    event_date = Series(date)
    f = Series(float)


events_schema = TableSchema(event_date=Column(date), f=Column(float))


def assert_not_chained_exception(excinfo):
    # Including chained exception details in the traceback is the default Python
    # behaviour but we often want to hide internal details from the user where these are
    # not helpful
    traceback_str = "\n".join(traceback.format_exception(excinfo.value))
    assert (
        "During handling of the above exception, another exception occurred"
        not in traceback_str
    )


def test_create_dataset():
    assert isinstance(create_dataset(), Dataset)


def test_dataset():
    year_of_birth = patients.date_of_birth.year
    dataset = Dataset()
    dataset.define_population(year_of_birth <= 2000)
    dataset.year_of_birth = year_of_birth
    dataset.configure_dummy_data(population_size=123)

    assert dataset.year_of_birth is year_of_birth
    assert dataset.dummy_data_config.population_size == 123

    assert dataset._compile() == qm.Dataset(
        population=Function.LE(
            lhs=Function.YearFromDate(
                source=SelectColumn(
                    name="date_of_birth",
                    source=SelectPatientTable("patients", patients_schema),
                )
            ),
            rhs=Value(2000),
        ),
        variables={
            "year_of_birth": Function.YearFromDate(
                source=SelectColumn(
                    name="date_of_birth",
                    source=SelectPatientTable("patients", patients_schema),
                )
            ),
        },
        events={},
    )


@pytest.mark.parametrize("legacy", [True, False])
def test_dataset_configure_dummy_data(legacy):
    year_of_birth = patients.date_of_birth.year
    dataset = Dataset()
    dataset.define_population(year_of_birth <= 2000)
    dataset.year_of_birth = year_of_birth
    dataset.configure_dummy_data(population_size=234, legacy=legacy, timeout=123)

    assert dataset.year_of_birth is year_of_birth
    assert dataset.dummy_data_config.population_size == 234
    assert dataset.dummy_data_config.legacy == legacy
    assert dataset.dummy_data_config.timeout == 123


def test_dataset_dummy_data_configured_twice():
    year_of_birth = patients.date_of_birth.year
    dataset = Dataset()
    dataset.define_population(year_of_birth <= 2000)
    dataset.year_of_birth = year_of_birth
    dataset.configure_dummy_data(population_size=200, legacy=True)
    dataset.configure_dummy_data(population_size=100)

    assert dataset.year_of_birth is year_of_birth
    assert dataset.dummy_data_config.population_size == 100
    assert not dataset.dummy_data_config.legacy


def test_dataset_preserves_variable_order():
    dataset = Dataset()
    dataset.define_population(patients.exists_for_patient())
    dataset.foo = patients.date_of_birth.year
    dataset.baz = patients.date_of_birth.year + 100
    dataset.bar = patients.date_of_birth.year - 100

    variables = list(dataset._compile().variables.keys())
    assert variables == ["foo", "baz", "bar"]


@pytest.mark.parametrize(
    "name",
    ["foo", "Foo", "f", "f_oo", "f1"],
)
def test_dataset_accepts_valid_variable_names(name):
    setattr(Dataset(), name, patients.i)


def test_add_column():
    dataset = Dataset()
    dataset.add_column("foo", patients.i)
    variables = list(dataset._variables.keys())
    assert variables == ["foo"]


@pytest.mark.parametrize(
    "variable_name,error",
    [
        ("population", "Cannot set variable 'population'; use define_population"),
        ("patient_id", "'patient_id' is not an allowed variable name"),
        (
            "dummy_data_config",
            "'dummy_data_config' is not an allowed variable name",
        ),
        ("_something", "variable names must start with a letter"),
        ("1something", "variable names must start with a letter"),
        ("something!", "contain only alphanumeric characters and underscores"),
    ],
)
def test_dataset_rejects_invalid_variable_names(variable_name, error):
    with pytest.raises(AttributeError, match=error):
        setattr(Dataset(), variable_name, patients.i)


def test_cannot_define_population_more_than_once():
    dataset = Dataset()
    dataset.define_population(patients.exists_for_patient())
    with pytest.raises(AttributeError, match="no more than once"):
        dataset.define_population(patients.exists_for_patient())


@pytest.mark.parametrize(
    "population,error",
    [
        (
            False,
            "Expecting an ehrQL series, got type 'bool'",
        ),
        (
            patients,
            "Expecting a series but got a frame (`patients`): "
            "are you missing a column name?",
        ),
        (
            patients.exists_for_patient,
            "Function referenced but not called: "
            "are you missing parentheses on `exists_for_patient()`?",
        ),
        (
            events.event_date.is_not_null(),
            "Expecting a series with only one value per patient",
        ),
        (
            patients.date_of_birth,
            "Expecting a boolean series, got series of type 'date'",
        ),
    ],
)
def test_define_population_rejects_invalid_arguments(population, error):
    with pytest.raises(TypeError, match=re.escape(error)):
        Dataset().define_population(population)


def test_define_population_rejects_invalid_population():
    with pytest.raises(
        Error,
        match="population definition must not evaluate as True for NULL inputs",
    ) as exc:
        Dataset().define_population(~events.exists_for_patient())
    assert_not_chained_exception(exc)


def test_cannot_reassign_dataset_variable():
    dataset = Dataset()
    dataset.foo = patients.date_of_birth.year
    with pytest.raises(AttributeError, match="already set"):
        dataset.foo = patients.date_of_birth.year + 100


@pytest.mark.parametrize(
    "variable,error",
    [
        (
            object(),
            "Expecting an ehrQL series, got type 'object'",
        ),
        (
            patients,
            "Expecting a series but got a frame (`patients`): "
            "are you missing a column name?",
        ),
        (
            patients.date_of_birth.is_null,
            "Function referenced but not called: "
            "are you missing parentheses on `is_null()`?",
        ),
        (
            events.event_date,
            "Expecting a series with only one value per patient",
        ),
    ],
)
def test_dataset_setattr_rejects_invalid_variables(variable, error):
    with pytest.raises(TypeError, match=re.escape(error)):
        Dataset().v = variable


def test_accessing_unassigned_variable_gives_helpful_error():
    with pytest.raises(AttributeError, match="'foo' has not been defined"):
        Dataset().foo


def test_add_event_table():
    dataset = Dataset()
    dataset.define_population(events.exists_for_patient())

    dataset.add_event_table("some_events", date=events.event_date)
    dataset.some_events.add_column("f", events.f)
    dataset.some_events.f_double = dataset.some_events.f * 2

    assert dataset._compile() == qm.Dataset(
        population=qm.AggregateByPatient.Exists(
            source=SelectTable(name="events", schema=events_schema)
        ),
        variables={},
        events={
            "some_events": qm.CombinedSeriesFrame(
                series={
                    "date": SelectColumn(
                        source=SelectTable(name="events", schema=events_schema),
                        name="event_date",
                    ),
                    "f": SelectColumn(
                        source=SelectTable(name="events", schema=events_schema),
                        name="f",
                    ),
                    "f_double": Function.Multiply(
                        lhs=SelectColumn(
                            source=SelectTable(name="events", schema=events_schema),
                            name="f",
                        ),
                        rhs=Value(value=2.0),
                    ),
                }
            )
        },
    )


def test_add_event_table_rejects_clashing_names():
    dataset = Dataset()
    dataset.dob = patients.date_of_birth
    dataset.add_event_table("f", f=events.f)

    with pytest.raises(
        AttributeError,
        match="'dob' is already set and cannot be reassigned",
    ):
        dataset.add_event_table("dob", f=events.f)

    with pytest.raises(
        AttributeError,
        match="'f' is already set and cannot be reassigned",
    ):
        dataset.f = events.f.maximum_for_patient()


def test_add_event_table_rejects_empty_tables():
    dataset = Dataset()
    with pytest.raises(
        ValueError,
        match="event tables must be defined with at least one column",
    ):
        dataset.add_event_table("test")


def test_add_event_table_rejects_patient_series():
    dataset = Dataset()
    with pytest.raises(
        TypeError,
        match="event tables must have columns with more than one value per patient",
    ):
        dataset.add_event_table("test", dob=patients.date_of_birth)


def test_add_event_table_rejects_mixed_domains():
    dataset = Dataset()
    dataset.add_event_table("events", f=events.f)
    filtered_events = events.where(events.event_date > "2000-01-01")
    with pytest.raises(
        Error,
        match="cannot combine series drawn from different tables",
    ):
        dataset.events.filtered_f = filtered_events.f


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
    assert ql_element._qm_node == qm_element


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
    "expr,expected_type",
    [
        (lambda: patients.f - 10, FloatPatientSeries),
        (lambda: patients.f + 10, FloatPatientSeries),
        (lambda: patients.f < 10, BoolPatientSeries),
        (lambda: events.f - 10, FloatEventSeries),
        (lambda: events.f < 10, BoolEventSeries),
        (lambda: events.f > 10, BoolEventSeries),
        (lambda: events.f < 10.0, BoolEventSeries),
    ],
)
def test_automatic_cast(expr, expected_type):
    assert isinstance(expr(), expected_type)


def test_is_in_rejects_unknown_types():
    with pytest.raises(TypeError, match="Not a valid ehrQL type: <object"):
        patients.i.is_in(object())


def test_is_in_rejects_scalars():
    with pytest.raises(
        TypeError,
        match=re.escape(
            "Note `is_in()` usually expects a list of values rather than a single value"
        ),
    ):
        patients.i.is_in(1)


def test_is_in_rejects_patient_series():
    with pytest.raises(TypeError, match="must be an EventSeries"):
        events.f.is_in(patients.f)


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
    assert some_table._qm_node.name == "some_table"
    assert isinstance(some_table.some_int, IntPatientSeries)
    assert isinstance(some_table.some_str, StrPatientSeries)


def test_construct_constructs_event_frame():
    @table
    class some_table(EventFrame):
        some_int = Series(int)
        some_str = Series(str)

    assert isinstance(some_table, EventFrame)
    assert some_table._qm_node.name == "some_table"
    assert isinstance(some_table.some_int, IntEventSeries)
    assert isinstance(some_table.some_str, StrEventSeries)


def test_construct_enforces_correct_base_class():
    with pytest.raises(Error, match="Schema class must subclass"):

        @table
        class some_table(Dataset):
            some_int = Series(int)


def test_construct_supports_inheritance():
    @table
    class some_table(PatientFrame):
        some_int = Series(int)

    @table
    class child_table(some_table.__class__):
        some_str = Series(str)

    assert isinstance(child_table, PatientFrame)
    assert child_table._qm_node.name == "child_table"
    assert isinstance(child_table.some_int, IntPatientSeries)
    assert isinstance(child_table.some_str, StrPatientSeries)


def test_table_from_rows():
    @table_from_rows([(1, 100), (2, 200)])
    class some_table(PatientFrame):
        some_int = Series(int)

    assert isinstance(some_table, PatientFrame)
    assert isinstance(some_table._qm_node, InlinePatientTable)


def test_table_from_rows_only_accepts_patient_frame():
    with pytest.raises(
        Error, match="`@table_from_rows` can only be used with `PatientFrame`"
    ):

        @table_from_rows([])
        class some_table(EventFrame):
            some_int = Series(int)


@pytest.mark.parametrize("file_extension", FILE_FORMATS)
def test_table_from_file(file_extension, tmp_path):
    file_data = [
        (1, 100, "a", date(2021, 1, 1)),
        (2, 200, "b", date(2022, 2, 2)),
    ]
    filename = tmp_path / f"test_file{file_extension}"

    column_specs = {
        "patient_id": ColumnSpec(int),
        "i": ColumnSpec(int),
        "s": ColumnSpec(str),
        "d": ColumnSpec(date),
    }
    write_rows(filename, file_data, column_specs)

    @table_from_file(filename)
    class some_table(PatientFrame):
        i = Series(int)
        s = Series(str)
        d = Series(date)

    assert isinstance(some_table, PatientFrame)
    assert isinstance(some_table._qm_node, InlinePatientTable)
    assert some_table._qm_node.schema.column_types == [
        ("i", int),
        ("s", str),
        ("d", date),
    ]
    assert list(some_table._qm_node.rows) == file_data


def test_table_from_file_only_accepts_patient_frame():
    with pytest.raises(
        Error,
        match="`@table_from_file` can only be used with `PatientFrame`",
    ):

        @table_from_file("")
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
    "expr",
    [
        lambda: 100 + patients.date_of_birth,
        lambda: 100 - patients.date_of_birth,
        lambda: patients.date_of_birth + 100,
        lambda: patients.date_of_birth - 100,
        lambda: 100 + days(100),
        lambda: 100 - days(100),
        lambda: days(100) + 100,
        lambda: days(100) - 100,
        lambda: date(2010, 1, 1) + patients.date_of_birth - "2000-01-01",
    ],
)
def test_unsupported_date_operations(expr):
    with pytest.raises(TypeError, match="unsupported operand type"):
        expr()


@pytest.mark.parametrize(
    "expr,expected",
    [
        # Test each type of Duration constructor
        (lambda: "2020-01-01" + days(10), date(2020, 1, 11)),
        (lambda: "2020-01-01" + weeks(1), date(2020, 1, 8)),
        (lambda: "2020-01-01" + months(10), date(2020, 11, 1)),
        (lambda: "2020-01-01" + years(10), date(2030, 1, 1)),
        # Order reversed
        (lambda: days(10) + "2020-01-01", date(2020, 1, 11)),
        # Subtraction
        (lambda: "2020-01-01" - years(10), date(2010, 1, 1)),
        # Date objects rather than ISO strings
        (lambda: date(2020, 1, 1) + years(10), date(2030, 1, 1)),
        (lambda: years(10) + date(2020, 1, 1), date(2030, 1, 1)),
        (lambda: date(2020, 1, 1) - years(10), date(2010, 1, 1)),
        # Test addition of Durations
        (lambda: days(10) + days(5), days(15)),
        (lambda: weeks(10) + weeks(5), weeks(15)),
        (lambda: months(10) + months(5), months(15)),
        (lambda: years(10) + years(5), years(15)),
        # Test subtraction of Durations
        (lambda: days(10) - days(5), days(5)),
        (lambda: weeks(10) - weeks(5), weeks(5)),
        (lambda: months(10) - months(5), months(5)),
        (lambda: years(10) - years(5), years(5)),
        # Test comparison of Durations
        (lambda: days(5) == days(5), True),
        (lambda: months(5) == years(5), False),
        (lambda: weeks(5) == weeks(4), False),
        (lambda: weeks(1) == days(7), False),
        (lambda: days(5) != days(5), False),
        (lambda: months(5) != years(5), True),
    ],
)
def test_static_date_operations(expr, expected):
    assert expr() == expected


@pytest.mark.parametrize(
    "expr,expected_type",
    [
        # Test each type of Duration constructor
        (lambda: patients.date_of_birth + days(10), DatePatientSeries),
        (lambda: patients.date_of_birth + weeks(10), DatePatientSeries),
        (lambda: patients.date_of_birth + months(10), DatePatientSeries),
        (lambda: patients.date_of_birth + years(10), DatePatientSeries),
        # Order reversed
        (lambda: days(10) + patients.date_of_birth, DatePatientSeries),
        # Subtraction
        (lambda: patients.date_of_birth - days(10), DatePatientSeries),
        # Date differences
        (lambda: patients.date_of_birth - "2020-01-01", DateDifference),
        (lambda: patients.date_of_birth - date(2020, 1, 1), DateDifference),
        # Order reversed
        (lambda: "2020-01-01" - patients.date_of_birth, DateDifference),
        (lambda: date(2020, 1, 1) - patients.date_of_birth, DateDifference),
        # DateDifference attributes
        (
            lambda: (patients.date_of_birth - "2020-01-01").days + 1,
            IntPatientSeries,
        ),
        (
            lambda: (patients.date_of_birth - "2020-01-01").weeks + 1,
            IntPatientSeries,
        ),
        (
            lambda: (patients.date_of_birth - "2020-01-01").months + 1,
            IntPatientSeries,
        ),
        (
            lambda: (patients.date_of_birth - "2020-01-01").years + 1,
            IntPatientSeries,
        ),
        # Test with a "dynamic" duration
        (lambda: patients.date_of_birth + days(patients.i), DatePatientSeries),
        (lambda: patients.date_of_birth + weeks(patients.i), DatePatientSeries),
        (lambda: patients.date_of_birth + months(patients.i), DatePatientSeries),
        (lambda: patients.date_of_birth + years(patients.i), DatePatientSeries),
        # Test with a dynamic duration and a static date
        (lambda: date(2020, 1, 1) + days(patients.i), DatePatientSeries),
        (lambda: date(2020, 1, 1) + weeks(patients.i), DatePatientSeries),
        (lambda: date(2020, 1, 1) + months(patients.i), DatePatientSeries),
        (lambda: date(2020, 1, 1) + years(patients.i), DatePatientSeries),
        # Test comparison of Durations
        (lambda: days(patients.i) == days(patients.i), BoolPatientSeries),
        (lambda: months(patients.i) == years(patients.i), bool),
        (lambda: days(patients.i) != days(patients.i), BoolPatientSeries),
        (lambda: months(patients.i) != years(patients.i), bool),
    ],
)
def test_ehrql_date_operations(expr, expected_type):
    assert isinstance(expr(), expected_type)


@pytest.mark.parametrize(
    "expr",
    [
        lambda: days(10) + months(10),
        lambda: days(10) - months(10),
        lambda: days(10) + years(10),
        lambda: days(10) - years(10),
        lambda: months(10) + years(10),
        lambda: months(10) - years(10),
    ],
)
def test_incompatible_duration_operations(expr):
    with pytest.raises(TypeError):
        expr()


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
    # Exclude methods which don't return an ehrQL series
    - {
        "__add__",
        "__sub__",
        "__radd__",
        "__rsub__",
        "_cast",
        "_repr_pretty_",
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
    if fn_name == "is_during":
        date_args = [(date_args[0], date_args[0])]
        str_args = [(str_args[0], str_args[0])]

    assert f(*date_args)._qm_node == f(*str_args)._qm_node


def test_code_series_instances_have_correct_type_attribute():
    @table
    class p(PatientFrame):
        code = Series(SNOMEDCTCode)

    # The series itself is a generic "BaseCode" series
    assert isinstance(p.code, CodePatientSeries)
    # But it knows the specfic coding system type it wraps
    assert p.code._type is SNOMEDCTCode


def test_strings_are_cast_to_codes():
    @table
    class p(PatientFrame):
        code = Series(SNOMEDCTCode)

    eq_series = p.code == "123000"
    assert eq_series._qm_node.rhs == Value(SNOMEDCTCode("123000"))

    is_in_series = p.code.is_in(["456000", "789000"])
    assert is_in_series._qm_node.rhs == Value(
        frozenset({SNOMEDCTCode("456000"), SNOMEDCTCode("789000")})
    )

    mapping = {"456000": "foo", "789000": "bar"}
    mapped_series = p.code.is_in(mapping)
    assert mapped_series._qm_node.rhs == Value(
        frozenset({SNOMEDCTCode("456000"), SNOMEDCTCode("789000")})
    )

    # Test invalid codes are rejected
    with pytest.raises(ValueError, match="Invalid SNOMEDCTCode"):
        p.code == "abc"


def test_frame_classes_are_preserved():
    @table
    class e(EventFrame):
        start_date = Series(date)

        def after_2020(self):
            return self.where(self.start_date > "2020-01-01")

    # Check that the helper method is preserved through `where`
    filtered_frame = e.where(e.start_date > "1990-01-01")
    assert isinstance(filtered_frame.after_2020(), EventFrame)

    # Check that the helper method is preserved through `sort_by`
    sorted_frame = e.sort_by(e.start_date)
    assert isinstance(sorted_frame.after_2020(), EventFrame)

    # Check that helper method is not available on patient frame
    latest_event = sorted_frame.last_for_patient()
    assert not hasattr(latest_event, "after_2020")

    # Check that column is still available. We're using `dir()` here to confirm that the
    # column is explicitly defined on the object and is available as an auto-complete
    # suggestion. Using `hasattr()` wouldn't tell us whether the attribute was only
    # available via a magic `__getattr__` method.
    assert "start_date" in dir(latest_event)


@pytest.mark.parametrize(
    "value,expected",
    [
        # Strings are parsed as dates
        ("2021-03-04", date(2021, 3, 4)),
        # Other types are passed through
        (1.23, 1.23),
        (b"abc", b"abc"),
    ],
)
def test_parse_date_if_str(value, expected):
    assert parse_date_if_str(value) == expected


@pytest.mark.parametrize(
    "value,error",
    [
        ("1st March 2020", "Dates must be in YYYY-MM-DD format: '1st March 2020'"),
        ("20201231", "Dates must be in YYYY-MM-DD format: '20201231'"),
        ("2021-02-29", "day is out of range for month in '2021-02-29'"),
        ("2020-01-01  ", "Dates must be in YYYY-MM-DD format: '2020-01-01  '"),
        ("2021-14-01", "month must be in 1..12 in '2021-14-01'"),
    ],
)
def test_parse_date_if_str_errors(value, error):
    with pytest.raises(ValueError, match=error) as exc:
        parse_date_if_str(value)
    assert_not_chained_exception(exc)


def test_parameter():
    series = Parameter("test_param", date)
    assert isinstance(series, DatePatientSeries)


# The behaviour of `date_utils.generate_intervals` is covered more fully by its own unit
# tests, we just need to test enough below to confirm that it's wired up correctly.


@pytest.mark.parametrize(
    "constructor,value,start_date,expected",
    [
        (
            weeks,
            1,
            "2020-01-01",
            [(date(2020, 1, 1), date(2020, 1, 7))],
        ),
        (
            months,
            1,
            "2020-01-01",
            [(date(2020, 1, 1), date(2020, 1, 31))],
        ),
        (
            years,
            1,
            "2020-01-01",
            [(date(2020, 1, 1), date(2020, 12, 31))],
        ),
    ],
)
def test_duration_starting_on(constructor, value, start_date, expected):
    assert constructor(value).starting_on(start_date) == expected


def test_duration_ending_on():
    assert months(3).ending_on("2020-06-30") == [
        (date(2020, 3, 31), date(2020, 4, 30)),
        (date(2020, 5, 1), date(2020, 5, 30)),
        (date(2020, 5, 31), date(2020, 6, 30)),
    ]


@pytest.mark.parametrize(
    "value,start_date,error",
    [
        (
            patients.i,
            "2020-01-01",
            r"weeks\.starting_on\(\) can only be used with a literal integer value, not an integer series",
        ),
        (
            10,
            patients.date_of_birth,
            r"weeks\.starting_on\(\) can only be used with a literal date, not a date series",
        ),
        (
            -10,
            "2020-01-01",
            r"weeks\.starting_on\(\) can only be used with positive numbers",
        ),
    ],
)
def test_duration_generate_intervals_rejects_invalid_arguments(
    value, start_date, error
):
    with pytest.raises((TypeError, ValueError), match=error):
        weeks(value).starting_on(start_date)


@pytest.mark.parametrize(
    "maximum_gap,error",
    [
        (10, r"must be supplied as `days\(\)` or `weeks\(\)`"),
        (patients.i, r"must be supplied as `days\(\)` or `weeks\(\)`"),
        (months(2), r"must be supplied as `days\(\)` or `weeks\(\)`"),
        (years(2), r"must be supplied as `days\(\)` or `weeks\(\)`"),
        (days(patients.i), "must be a single, fixed number of days"),
        (weeks(patients.i), "must be a single, fixed number of weeks"),
    ],
)
def test_count_episodes_for_patient_rejects_invalid_arguments(maximum_gap, error):
    with pytest.raises((TypeError, ValueError), match=error):
        events.event_date.count_episodes_for_patient(maximum_gap)


def test_count_episodes_for_patient_handles_weeks():
    using_days = events.event_date.count_episodes_for_patient(days(14))
    using_weeks = events.event_date.count_episodes_for_patient(weeks(2))
    assert using_days._qm_node == using_weeks._qm_node


def test_domain_mismatch_errors_are_wrapped():
    @table
    class other_events(EventFrame):
        f = Series(float)

    with pytest.raises(
        Error,
        match="Cannot combine series which are drawn from different tables",
    ) as exc:
        events.f + other_events.f
    assert "is_in" not in str(exc.value)
    assert_not_chained_exception(exc)


def test_domain_mismatch_errors_using_equality_provide_hint():
    @table
    class other_events(EventFrame):
        f = Series(float)

    with pytest.raises(
        Error,
        match="Cannot combine series which are drawn from different tables",
    ) as exc:
        events.f == other_events.f
    assert "Use `x.is_in(y)` instead of `x == y`" in str(exc.value)
    assert_not_chained_exception(exc)


def test_invalid_sort_errors_are_wrapped():
    with pytest.raises(Error, match="Cannot sort by a constant value") as exc:
        events.sort_by(1)
    assert_not_chained_exception(exc)


def test_sorting_by_string_raises_helpful_error():
    with pytest.raises(
        TypeError,
        match='use a table attribute like `events.date` rather than the string "date"',
    ) as exc:
        events.sort_by("date")
    assert_not_chained_exception(exc)


@pytest.mark.parametrize(
    "value,error",
    [
        (
            patients,
            "Expecting a series but got a frame (`patients`): "
            "are you missing a column name?",
        ),
        (
            patients.i.is_null,
            "Function referenced but not called: "
            "are you missing parentheses on `is_null()`?",
        ),
        (
            object(),
            "Not a valid ehrQL type: <object object",
        ),
    ],
)
def test_type_errors(value, error):
    with pytest.raises(TypeError, match=re.escape(error)):
        when(patients.exists_for_patient()).then(value).otherwise(None)


def test_query_model_type_errors():
    with pytest.raises(
        TypeError,
        match=re.escape("Expected type 'Series[int] | None' but got 'Series[str]'"),
    ) as exc:
        patients.i.when_null_then("empty")
    assert_not_chained_exception(exc)


@pytest.mark.parametrize(
    "code,exc_class,expected_note",
    [
        (
            lambda: patients.no_such_column,
            AttributeError,
            "",
        ),
        (
            lambda: patients.i + "foo",
            TypeError,
            "",
        ),
        (
            lambda: patients.i == 1 | patients.i == 2,
            TypeError,
            "WARNING: The `|` operator has surprising precedence rules",
        ),
        (
            lambda: patients.i == 1 & patients.i == 2,
            TypeError,
            "WARNING: The `&` operator has surprising precedence rules",
        ),
        (
            lambda: ~patients.i == 1,
            TypeError,
            "WARNING: The `~` operator has surprising precedence rules",
        ),
    ],
)
def test_modify_exception(code, exc_class, expected_note):
    with pytest.raises(exc_class) as exc:
        code()
    exception = modify_exception(exc.value)
    notes = "\n".join(getattr(exception, "__notes__", []))
    assert isinstance(exception, exc_class)
    assert expected_note in notes


@pytest.mark.parametrize(
    "type_,required_types,expected_error",
    [
        (
            bool,
            [int],
            "Expecting an integer series, got series of type 'bool'",
        ),
        (
            int,
            [bool],
            "Expecting a boolean series, got series of type 'int'",
        ),
        (
            str,
            [bool, int],
            "Expecting a boolean or integer series, got series of type 'str'",
        ),
        (
            str,
            [int, bool, float],
            "Expecting an integer, boolean or float series, got series of type 'str'",
        ),
    ],
)
def test_validate_patient_series_type(type_, required_types, expected_error):
    series = Parameter("param", type_)
    with pytest.raises(TypeError, match=re.escape(expected_error)):
        validate_patient_series_type(
            series,
            types=required_types,
            context="value",
        )


@pytest.mark.parametrize(
    "expr,expected_error",
    [
        (
            lambda: when(patients.i < 10),
            "Missing `.then(...).otherwise(...)` conditions on a `when(...)` expression",
        ),
        (
            lambda: when(patients.i < 10).then("small"),
            "Missing `.otherwise(...)` condition on a `when(...).then(...)` expression",
        ),
        (
            lambda: case(when(patients.i < 10), otherwise="none"),
            "`when(...)` clause missing a `.then(...)` value in `case()` expression",
        ),
        (
            lambda: when(patients).then("exists"),
            "Expecting a series but got a frame (`patients`): are you missing a column name?",
        ),
        (
            lambda: when(patients.i == 10).then(patients),
            "Expecting a series but got a frame (`patients`): are you missing a column name?",
        ),
        (
            lambda: when(patients.i).then("exists"),
            "Expecting a boolean series, got series of type 'int'",
        ),
        (
            lambda: case(
                when(patients.i < 10).then("small"),
                when(patients.i > 10).then("large").otherwise("none"),
            ),
            "invalid syntax for `otherwise` in `case()` expression",
        ),
        (
            lambda: case(patients.i, otherwise="none"),
            "cases must be specified in the form:",
        ),
        (
            lambda: case(),
            "`case()` expression requires at least one case",
        ),
        (
            lambda: case(when(patients.i == 0).then(None)),
            "case()` expression cannot have all `None` values",
        ),
        (
            lambda: case(
                when(patients.i == 1).then("a"),
                when(patients.i == 1).then("b"),
            ),
            "duplicated condition in `case()` expression",
        ),
    ],
)
def test_case_expression_errors(expr, expected_error):
    with pytest.raises(TypeError, match=re.escape(expected_error)):
        create_dataset().column = expr()


def test_icd10_multi_code_string_series_throws_on_invalid_comparison():
    @table
    class a(EventFrame):
        icd10_code_string = Series(ICD10MultiCodeString)

    # We don't allow ==
    with pytest.raises(TypeError):
        a.icd10_code_string == "I000"

    # We don't allow !=
    with pytest.raises(TypeError):
        a.icd10_code_string != "I000"

    # We don't allow is_in
    with pytest.raises(TypeError):
        a.icd10_code_string.is_in(["I000"])

    # We don't allow is_not_in
    with pytest.raises(TypeError):
        a.icd10_code_string.is_not_in(["I000"])

    # ICD10 string prefixes must be valid prefixes
    with pytest.raises(TypeError):
        a.icd10_code_string.contains("ZZ2")

    # Must be ICD10 code, not just any code type
    with pytest.raises(TypeError):
        a.icd10_code_string.contains(SNOMEDCTCode("11100000"))


def test_opcs4_multi_code_string_series_throws_on_invalid_comparison():
    @table
    class a(EventFrame):
        opcs4_code_string = Series(OPCS4MultiCodeString)

    # We don't allow ==
    with pytest.raises(TypeError):
        a.opcs4_code_string == "I000"

    # We don't allow !=
    with pytest.raises(TypeError):
        a.opcs4_code_string != "I000"

    # We don't allow is_in
    with pytest.raises(TypeError):
        a.opcs4_code_string.is_in(["I000"])

    # We don't allow is_not_in
    with pytest.raises(TypeError):
        a.opcs4_code_string.is_not_in(["I000"])

    # OPCS4 string prefixes must be valid prefixes
    with pytest.raises(TypeError):
        a.opcs4_code_string.contains("ZZ2")

    # Must be OPCS4 code, not just any code type
    with pytest.raises(TypeError):
        a.opcs4_code_string.contains(SNOMEDCTCode("11100000"))
