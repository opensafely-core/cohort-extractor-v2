from ehrql.query_model.nodes import (
    AggregateByPatient,
    Column,
    Dataset,
    Function,
    InlinePatientTable,
    SelectColumn,
    TableSchema,
)


def test_float_precision(trino_engine):
    # This tests that Trino uses 64-bit precision for float columns in inline tables.
    v1, v2 = 1, 0.001

    schema = TableSchema(f1=Column(float), f2=Column(float))
    t = InlinePatientTable(
        ((1, v1, v2),),
        schema,
    )
    f1 = SelectColumn(t, "f1")
    f2 = SelectColumn(t, "f2")

    dataset = Dataset(
        population=AggregateByPatient.Exists(t),
        variables={"v": Function.Subtract(f1, Function.Add(f1, f2))},
        events={},
    )

    results = trino_engine.extract(dataset)
    assert results[0]["v"] == v1 - (v1 + v2)
