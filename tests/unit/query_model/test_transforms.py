import datetime

from ehrql.query_model.nodes import (
    Case,
    Column,
    Dataset,
    Filter,
    Function,
    Parameter,
    PickOneRowPerPatient,
    Position,
    SelectColumn,
    SelectTable,
    Sort,
    TableSchema,
    Value,
)
from ehrql.query_model.transforms import (
    PickOneRowPerPatientWithColumns,
    apply_transforms,
    substitute_parameters,
)


def test_pick_one_row_per_patient_transform():
    events = SelectTable(
        "events",
        schema=TableSchema(
            date=Column(datetime.date), code=Column(str), value=Column(float)
        ),
    )
    sorted_events = Sort(
        Sort(
            Sort(
                events,
                SelectColumn(events, "value"),
            ),
            SelectColumn(events, "code"),
        ),
        SelectColumn(events, "date"),
    )
    first_event = PickOneRowPerPatient(sorted_events, Position.FIRST)
    dataset = dataset_factory(
        first_code=SelectColumn(first_event, "code"),
        first_value=SelectColumn(first_event, "value"),
        # Create a new distinct column object with the same value as the first column:
        # equal but not identical objects expose bugs in the query model transformation
        first_code_again=SelectColumn(first_event, "code"),
    )

    first_event_with_columns = PickOneRowPerPatientWithColumns(
        source=sorted_events,
        position=Position.FIRST,
        selected_columns=frozenset(
            {
                SelectColumn(
                    source=sorted_events,
                    name="value",
                ),
                SelectColumn(
                    source=sorted_events,
                    name="code",
                ),
            }
        ),
    )
    expected = {
        "first_code": SelectColumn(first_event_with_columns, "code"),
        "first_value": SelectColumn(first_event_with_columns, "value"),
        "first_code_again": SelectColumn(first_event_with_columns, "code"),
    }

    transformed = apply_transforms(dataset)
    assert transformed.variables == expected


def test_adds_one_selected_column_to_sorts():
    events = SelectTable(
        "events",
        TableSchema(i1=Column(int), i2=Column(int)),
    )
    by_i1 = Sort(events, SelectColumn(events, "i1"))
    variable = SelectColumn(
        PickOneRowPerPatient(source=by_i1, position=Position.FIRST),
        "i2",
    )

    by_i2 = Sort(events, SelectColumn(events, "i2"))
    by_i2_then_i1 = Sort(by_i2, SelectColumn(events, "i1"))
    expected = SelectColumn(
        PickOneRowPerPatientWithColumns(
            by_i2_then_i1,
            Position.FIRST,
            selected_columns=frozenset(
                {
                    SelectColumn(
                        source=by_i2_then_i1,
                        name="i2",
                    ),
                }
            ),
        ),
        "i2",
    )

    assert apply_transforms(variable) == expected


def test_adds_sorts_at_lowest_priority():
    events = SelectTable(
        "events",
        TableSchema(i1=Column(int), i2=Column(int), i3=Column(int)),
    )
    by_i2 = Sort(events, SelectColumn(events, "i2"))
    by_i2_then_i1 = Sort(by_i2, SelectColumn(by_i2, "i1"))
    variable = SelectColumn(
        PickOneRowPerPatient(source=by_i2_then_i1, position=Position.FIRST),
        "i3",
    )

    by_i3 = Sort(events, SelectColumn(events, "i3"))
    by_i3_then_i2 = Sort(by_i3, SelectColumn(events, "i2"))
    by_i3_then_i2_then_i1 = Sort(by_i3_then_i2, SelectColumn(by_i3_then_i2, "i1"))
    expected = SelectColumn(
        PickOneRowPerPatientWithColumns(
            by_i3_then_i2_then_i1,
            Position.FIRST,
            selected_columns=frozenset(
                {
                    SelectColumn(
                        source=by_i3_then_i2_then_i1,
                        name="i3",
                    ),
                }
            ),
        ),
        "i3",
    )

    assert apply_transforms(variable) == expected


def test_copes_with_interleaved_sorts_and_filters():
    events = SelectTable(
        "events",
        TableSchema(i1=Column(int), i2=Column(int), i3=Column(int)),
    )
    by_i2 = Sort(events, SelectColumn(events, "i2"))
    by_i2_filtered = Filter(by_i2, Value(True))
    by_i2_then_i1 = Sort(by_i2_filtered, SelectColumn(by_i2_filtered, "i1"))
    variable = SelectColumn(
        PickOneRowPerPatient(source=by_i2_then_i1, position=Position.FIRST),
        "i3",
    )

    by_i3 = Sort(events, SelectColumn(events, "i3"))
    by_i3_then_i2 = Sort(by_i3, SelectColumn(events, "i2"))
    by_i3_then_i2_filtered = Filter(by_i3_then_i2, Value(True))
    by_i3_then_i2_then_i1 = Sort(
        by_i3_then_i2_filtered, SelectColumn(by_i3_then_i2_filtered, "i1")
    )
    expected = SelectColumn(
        PickOneRowPerPatientWithColumns(
            by_i3_then_i2_then_i1,
            Position.FIRST,
            selected_columns=frozenset(
                {
                    SelectColumn(
                        source=by_i3_then_i2_then_i1,
                        name="i3",
                    ),
                }
            ),
        ),
        "i3",
    )

    assert apply_transforms(variable) == expected


def test_doesnt_duplicate_existing_sorts():
    events = SelectTable(
        "events",
        TableSchema(i1=Column(int)),
    )
    by_i1 = Sort(events, SelectColumn(events, "i1"))
    variable = SelectColumn(
        PickOneRowPerPatient(source=by_i1, position=Position.FIRST),
        "i1",
    )

    expected = SelectColumn(
        PickOneRowPerPatientWithColumns(
            by_i1,
            Position.FIRST,
            selected_columns=frozenset(
                {
                    SelectColumn(
                        source=by_i1,
                        name="i1",
                    ),
                }
            ),
        ),
        "i1",
    )

    assert apply_transforms(variable) == expected


def test_adds_sorts_in_lexical_order_of_column_names():
    events = SelectTable(
        "events",
        TableSchema(i1=Column(int), iz=Column(int), ia=Column(int)),
    )
    by_i1 = Sort(events, SelectColumn(events, "i1"))
    first_initial = PickOneRowPerPatient(source=by_i1, position=Position.FIRST)
    dataset = dataset_factory(
        z=SelectColumn(first_initial, "iz"),
        a=SelectColumn(first_initial, "ia"),
    )

    transformed = apply_transforms(dataset)

    by_iz = Sort(events, SelectColumn(events, "iz"))
    by_iz_then_ia = Sort(by_iz, SelectColumn(events, "ia"))
    by_iz_then_ia_then_i1 = Sort(by_iz_then_ia, SelectColumn(events, "i1"))
    first_with_extra_sorts = PickOneRowPerPatientWithColumns(
        by_iz_then_ia_then_i1,
        Position.FIRST,
        selected_columns=frozenset(
            {
                SelectColumn(
                    source=by_iz_then_ia_then_i1,
                    name="iz",
                ),
                SelectColumn(
                    source=by_iz_then_ia_then_i1,
                    name="ia",
                ),
            }
        ),
    )

    expected = dict(
        z=SelectColumn(first_with_extra_sorts, "iz"),
        a=SelectColumn(first_with_extra_sorts, "ia"),
    )

    assert transformed.variables == expected


def test_maps_booleans_to_a_sortable_type():
    events = SelectTable(
        "events",
        TableSchema(i=Column(int), b=Column(bool)),
    )
    by_i = Sort(events, SelectColumn(events, "i"))
    variable = SelectColumn(
        PickOneRowPerPatient(source=by_i, position=Position.FIRST),
        "b",
    )

    b = SelectColumn(events, "b")
    by_b = Sort(
        events, Case({b: Value(2), Function.Not(b): Value(1)}, default=Value(0))
    )
    by_b_then_i = Sort(by_b, SelectColumn(events, "i"))
    expected = SelectColumn(
        PickOneRowPerPatientWithColumns(
            by_b_then_i,
            Position.FIRST,
            selected_columns=frozenset(
                {
                    SelectColumn(
                        source=by_b_then_i,
                        name="b",
                    ),
                }
            ),
        ),
        "b",
    )

    assert apply_transforms(variable) == expected


def test_sorts_by_derived_value_handled_correctly():
    events = SelectTable("events", TableSchema(i=Column(int)))

    by_negative_i = Sort(events, Function.Negate(SelectColumn(events, "i")))
    variable = SelectColumn(PickOneRowPerPatient(by_negative_i, Position.FIRST), "i")

    by_i = Sort(events, SelectColumn(events, "i"))
    by_i_then_by_negative_i = Sort(by_i, Function.Negate(SelectColumn(events, "i")))
    expected = SelectColumn(
        PickOneRowPerPatientWithColumns(
            by_i_then_by_negative_i,
            Position.FIRST,
            frozenset({SelectColumn(by_i_then_by_negative_i, "i")}),
        ),
        "i",
    )

    assert apply_transforms(variable) == expected


def test_identical_operations_are_not_transformed_differently():
    # Query model nodes are intended to be value objects: that is equality is determined
    # by value, not identity and equal objects should be intersubstitutable. Approaches
    # to query transformation which involve mutation can violate this principle and
    # treat equal but non-identical nodes differently. This tests for a specific
    # instance of this problem.
    events = SelectTable(
        "events",
        TableSchema(i1=Column(int), i2=Column(int)),
    )
    # Construct two equal but non-identical sort-and-picks
    first_by_i1_v1 = PickOneRowPerPatient(
        Sort(events, SelectColumn(events, "i1")), position=Position.FIRST
    )
    first_by_i1_v2 = PickOneRowPerPatient(
        Sort(events, SelectColumn(events, "i1")), position=Position.FIRST
    )

    # Select different columns from each one
    dataset = dataset_factory(
        i1=SelectColumn(first_by_i1_v1, "i1"),
        i2=SelectColumn(first_by_i1_v2, "i2"),
    )

    # We expect i2 to be added at the bottom of the stack of sorts
    by_i2_then_i1 = Sort(
        source=Sort(source=events, sort_by=SelectColumn(source=events, name="i2")),
        sort_by=SelectColumn(source=events, name="i1"),
    )
    # We expect the selected columns to include both i1 and i2
    pick_with_columns = PickOneRowPerPatientWithColumns(
        source=by_i2_then_i1,
        position=Position.FIRST,
        selected_columns=frozenset(
            {
                SelectColumn(by_i2_then_i1, "i1"),
                SelectColumn(by_i2_then_i1, "i2"),
            }
        ),
    )

    expected = dict(
        i1=SelectColumn(source=pick_with_columns, name="i1"),
        i2=SelectColumn(source=pick_with_columns, name="i2"),
    )

    assert apply_transforms(dataset).variables == expected


def test_substitute_parameters():
    node = Function.Negate(Function.Add(Value(10), Parameter("i", int)))
    transformed = substitute_parameters(node, i=20)
    assert transformed == Function.Negate(Function.Add(Value(10), Value(20)))


def dataset_factory(**variables):
    return Dataset(population=Value(False), variables=variables, events={})
