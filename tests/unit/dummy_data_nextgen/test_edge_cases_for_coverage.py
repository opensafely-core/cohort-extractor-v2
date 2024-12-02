from datetime import date

from ehrql.dummy_data_nextgen.query_info import QueryInfo, is_value, specialize
from ehrql.query_language import (
    Series,
)
from ehrql.query_model.nodes import (
    Case,
    Function,
    SelectColumn,
    SelectPatientTable,
    TableSchema,
    Value,
)


def test_check_is_value():
    assert is_value(Function.GT(lhs=Value(value=0.0), rhs=Value(value=0.0)))


schema = TableSchema(
    i1=Series(int),
    b0=Series(bool),
    b1=Series(bool),
    d1=Series(date),
)
p0 = SelectPatientTable(name="p0", schema=schema)


def test_case_is_not_value_with_non_value_outcome():
    assert not is_value(
        Case(
            cases={
                Value(True): SelectColumn(p0, "i1"),
            },
            default=None,
        )
    )


def test_case_is_value_with_value_outcome():
    assert is_value(
        Case(
            cases={
                Value(True): Value(0.0),
            },
            default=None,
        )
    )


def test_minimum_of_values_is_value():
    assert is_value(Function.MinimumOf((Value(0), Value(1))))


def test_some_nonsense():
    QueryInfo.from_variable_definitions(
        {
            "population": Function.LT(
                lhs=Case(
                    cases={SelectColumn(source=p0, name="b1"): None},
                    default=Value(value=date(2010, 1, 1)),
                ),
                rhs=Value(value=date(2010, 1, 1)),
            ),
            "v": SelectColumn(
                source=p0,
                name="i1",
            ),
        }
    )


def test_rewrites_rhs_case_to_or():
    table = SelectPatientTable(name="p0", schema=schema)

    specialized = specialize(
        Function.LT(
            lhs=Value(value=date(2010, 1, 1)),
            rhs=Case(
                cases={SelectColumn(table, name="b1"): Value(value=date(2010, 1, 1))},
                default=Value(value=date(2010, 1, 1)),
            ),
        ),
        SelectColumn(table, name="i1"),
    )

    assert isinstance(specialized, Function.Or)
