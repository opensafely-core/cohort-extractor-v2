import datetime

from ehrql.codes import SNOMEDCTCode
from ehrql.query_model.column_specs import (
    ColumnSpec,
    get_categories,
    get_range,
    get_table_specs,
)
from ehrql.query_model.nodes import (
    AggregateByPatient,
    Case,
    Column,
    Constraint,
    Dataset,
    Function,
    SelectColumn,
    SelectPatientTable,
    SelectTable,
    TableSchema,
    Value,
)


def test_get_column_specs():
    patients = SelectPatientTable(
        "patients",
        schema=TableSchema(
            date_of_birth=Column(datetime.date),
            code=Column(SNOMEDCTCode),
            category=Column(
                SNOMEDCTCode,
                constraints=[
                    Constraint.Categorical(
                        [SNOMEDCTCode("123000"), SNOMEDCTCode("456000")]
                    )
                ],
            ),
        ),
    )
    dataset = Dataset(
        population=AggregateByPatient.Exists(patients),
        variables=dict(
            dob=SelectColumn(patients, "date_of_birth"),
            code=SelectColumn(patients, "code"),
            category=SelectColumn(patients, "category"),
        ),
    )
    table_specs = get_table_specs(dataset)
    assert table_specs == {
        "dataset": {
            "patient_id": ColumnSpec(type=int, nullable=False, categories=None),
            "dob": ColumnSpec(type=datetime.date, nullable=True, categories=None),
            "code": ColumnSpec(type=str, nullable=True, categories=None),
            "category": ColumnSpec(
                type=str, nullable=True, categories=("123000", "456000")
            ),
        }
    }


events = SelectTable(
    "events",
    schema=TableSchema(
        event_type=Column(str, constraints=[Constraint.Categorical(["a", "b", "c"])]),
        event_name=Column(str),
    ),
)
event_type = SelectColumn(events, "event_type")
event_name = SelectColumn(events, "event_name")


def test_get_categories_default_implementation():
    assert get_categories(AggregateByPatient.Exists(events)) is None


def test_get_categories_for_select_column():
    assert get_categories(event_type) == ("a", "b", "c")


def test_get_categories_for_min_max():
    assert get_categories(AggregateByPatient.Min(event_type)) == ("a", "b", "c")
    assert get_categories(AggregateByPatient.Max(event_type)) == ("a", "b", "c")


def test_get_categories_for_case_with_static_values():
    name_bucket = Case(
        {
            Function.LT(event_name, Value("abc")): Value("low"),
            Function.LT(event_name, Value("lmn")): Value("med"),
            Function.GE(event_name, Value("lmn")): Value("high"),
        },
        default=None,
    )
    assert get_categories(name_bucket) == ("low", "med", "high")


def test_get_categories_for_case_with_static_default():
    type_or_missing = Case(
        {Function.Not(Function.IsNull(event_type)): event_type},
        default=Value("missing"),
    )
    assert get_categories(type_or_missing) == ("a", "b", "c", "missing")


def test_get_categories_for_case_with_mixed_categorical_and_noncategorical_values():
    type_or_name = Case(
        {Function.Not(Function.IsNull(event_type)): event_type},
        default=event_name,
    )
    assert get_categories(type_or_name) is None


def test_get_range_default_implementation():
    i = SelectColumn(SelectTable("t", schema=TableSchema(i=Column(int))), "i")
    assert get_range(i) == (None, None)


def test_get_range_for_count():
    count = AggregateByPatient.Count(events)
    min_value, max_value = get_range(count)
    assert min_value == 0
    num_bits = len(f"{max_value:b}")
    assert num_bits == 16


def test_get_range_for_select_column_with_range_constraint():
    i = SelectColumn(
        SelectTable(
            "t",
            schema=TableSchema(
                i=Column(int, constraints=[Constraint.ClosedRange(0, 100, 10)])
            ),
        ),
        "i",
    )
    assert get_range(i) == (0, 100)
