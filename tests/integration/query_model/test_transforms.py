from ehrql.query_model.nodes import (
    AggregateByPatient,
    Dataset,
    PickOneRowPerPatient,
    Position,
    SelectColumn,
    SelectTable,
    Sort,
    TableSchema,
)


events = SelectTable(
    "events",
    schema=TableSchema.from_primitives(i=int, b=bool),
)


def test_sort_booleans_null_first(engine):
    # The transforms add sorts for unsorted selected columns. Here we're checking the semantics
    # of the sort added for boolean columns (which are handled explicitly because some databases
    # don't allow sorting on booleans.
    #
    # The desired sort order is: NULL, False, True.
    #
    # Each of these patients has two records with different boolean values so we do pairwise
    # comparisons. The integer column is there only so we can specify a sort on it in the query
    # model.
    engine.populate(
        {
            events: [
                dict(patient_id=0, row_id=0, i=0, b=False),
                dict(patient_id=0, row_id=1, i=0, b=True),
                dict(patient_id=1, row_id=2, i=0, b=None),
                dict(patient_id=1, row_id=3, i=0, b=True),
                dict(patient_id=2, row_id=4, i=0, b=None),
                dict(patient_id=2, row_id=5, i=0, b=False),
            ]
        }
    )

    # Sort the events by i and pick the b from the last row.
    by_i = Sort(events, SelectColumn(events, "i"))
    variable = SelectColumn(
        PickOneRowPerPatient(source=by_i, position=Position.LAST),
        "b",
    )
    population = AggregateByPatient.Exists(events)
    dataset = Dataset(population=population, variables={"v": variable}, events={})

    assert engine.extract(dataset) == [
        dict(patient_id=0, v=True),  # True sorts after False
        dict(patient_id=1, v=True),  # True sorts after NULL
        dict(patient_id=2, v=False),  # False sorts after NULL
    ]
