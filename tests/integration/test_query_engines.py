import csv
from datetime import date

import pytest
import sqlalchemy

from ehrql import create_dataset, minimum_of, when
from ehrql.query_model.nodes import AggregateByPatient, Dataset, Function, Value
from ehrql.tables import (
    EventFrame,
    PatientFrame,
    Series,
    table,
    table_from_file,
    table_from_rows,
)


@table
class patients(PatientFrame):
    date_of_birth = Series(date)
    sex = Series(str)
    i = Series(int)


@table
class events(EventFrame):
    date = Series(date)
    code = Series(str)
    i = Series(int)


def test_handles_degenerate_population(engine):
    # Specifying a population of "False" is obviously silly, but it's more work to
    # identify and reject just this kind of silliness than it is to handle it gracefully
    engine.setup(metadata=sqlalchemy.MetaData())
    dataset = build_dataset(
        population=Value(False),
        variables={"v": Value(1)},
    )
    assert engine.extract(dataset) == []


def test_handles_inline_patient_table(engine, tmp_path):
    # Test that a temporary inline patient table, as used by table_from_rows and
    # table_from_file decorators is created and is correctly acessible

    engine.populate(
        {
            patients: [
                dict(patient_id=1, date_of_birth=date(1980, 1, 1)),
                dict(patient_id=2, date_of_birth=date(1990, 2, 2)),
                dict(patient_id=3, date_of_birth=date(2000, 3, 3)),
                dict(patient_id=4, date_of_birth=date(2010, 4, 4)),
            ]
        }
    )

    file_rows = [
        ("patient_id", "i", "s", "d"),
        (1, 10, "a", date(2021, 1, 1)),
        (2, 20, "b", date(2022, 2, 2)),
        (3, None, "c", date(2023, 3, 3)),
        (4, 40, "d", None),
    ]

    file_path = tmp_path / "test.csv"
    with file_path.open("w") as f:
        writer = csv.writer(f)
        writer.writerows(file_rows)

    @table_from_file(file_path)
    class test_table(PatientFrame):
        i = Series(int)
        s = Series(str)
        d = Series(date)

    dataset = create_dataset()
    dataset.define_population(
        patients.exists_for_patient() & test_table.exists_for_patient()
    )

    dataset.n = test_table.i + (test_table.i * 10)
    dataset.age = (test_table.d - patients.date_of_birth).years
    dataset.s = test_table.s

    results = engine.extract(dataset)

    assert results == [
        {"patient_id": 1, "age": 41, "n": 110, "s": "a"},
        {"patient_id": 2, "age": 32, "n": 220, "s": "b"},
        {"patient_id": 3, "age": 23, "n": None, "s": "c"},
        {"patient_id": 4, "age": None, "n": 440, "s": "d"},
    ]


def test_handles_inline_patient_table_with_different_patients(engine):
    engine.populate(
        {
            patients: [
                dict(patient_id=1, sex="female"),
            ]
        }
    )

    # This inline table contains patients which are not in the patients table
    @table_from_rows(
        [
            (1, 10),
            (2, 20),
            (3, 30),
        ]
    )
    class test_table(PatientFrame):
        i = Series(int)

    dataset = create_dataset()
    dataset.define_population(test_table.exists_for_patient())
    dataset.n = test_table.i + 100
    dataset.sex = patients.sex

    results = engine.extract(dataset)

    assert results == [
        {"patient_id": 1, "n": 110, "sex": "female"},
        {"patient_id": 2, "n": 120, "sex": None},
        {"patient_id": 3, "n": 130, "sex": None},
    ]


def test_cleans_up_temporary_tables(engine):
    # Cleanup doesn't apply to the in-memory engine
    if engine.name == "in_memory":
        pytest.skip()

    engine.populate(
        {
            events: [
                dict(patient_id=1, date=date(2000, 1, 1)),
                dict(patient_id=1, date=date(2001, 1, 1)),
                dict(patient_id=2, date=date(2002, 1, 1)),
            ]
        }
    )
    original_tables = _get_tables(engine)

    @table_from_rows(
        [
            (1, 10),
            (2, 20),
        ]
    )
    class inline_table(PatientFrame):
        i = Series(int)

    dataset = create_dataset()
    dataset.define_population(events.exists_for_patient())
    dataset.n = events.count_for_patient()
    dataset.i = inline_table.i

    results = engine.extract(dataset)

    assert results == [
        {"patient_id": 1, "n": 2, "i": 10},
        {"patient_id": 2, "n": 1, "i": 20},
    ]

    # Check that the tables we're left with match those we started with
    final_tables = _get_tables(engine)
    assert final_tables == original_tables


def _get_tables(engine):
    inspector = sqlalchemy.inspect(engine.sqlalchemy_engine())
    return sorted(inspector.get_table_names())


# Supplying only a single series to the min/max functions is valid in the query model so
# Hypothesis will generate examples like this which we want to handle correctly. But we
# deliberately make these unconstructable in ehrQL so we can't write standard spec tests
# to cover them.
@pytest.mark.parametrize(
    "operation",
    [
        Function.MinimumOf,
        Function.MaximumOf,
    ],
)
def test_minimum_maximum_of_single_series(engine, operation):
    engine.populate(
        {
            patients: [
                dict(patient_id=1, date_of_birth=date(1980, 1, 1)),
                dict(patient_id=2, date_of_birth=date(1990, 2, 2)),
            ]
        }
    )

    dataset = build_dataset(
        population=as_query_model(patients.exists_for_patient()),
        variables={
            "v": operation(
                (as_query_model(patients.date_of_birth),),
            )
        },
    )
    assert engine.extract(dataset) == [
        {"patient_id": 1, "v": date(1980, 1, 1)},
        {"patient_id": 2, "v": date(1990, 2, 2)},
    ]


def test_is_in_using_temporary_table(engine):
    # Test an "is_in" query, but with the engine configured to break out even tiny lists
    # of values into temporary tables so we can exercise that code path
    engine.populate(
        {
            events: [
                # Patient 1
                dict(patient_id=1, code="123000"),
                dict(patient_id=1, code="456000"),
                # Patient 2
                dict(patient_id=2, code="123001"),
                dict(patient_id=2, code="456001"),
                dict(patient_id=2, code="123002"),
            ]
        }
    )

    dataset = create_dataset()
    dataset.define_population(events.exists_for_patient())
    matching = events.code.is_in(
        ["123000", "123001", "123002", "123004"],
    )
    dataset.n = events.where(matching).count_for_patient()

    results = engine.extract(
        dataset,
        config={"EHRQL_MAX_MULTIVALUE_PARAM_LENGTH": 1},
    )

    assert results == [
        {"patient_id": 1, "n": 1},
        {"patient_id": 2, "n": 2},
    ]


def as_query_model(query_lang_expr):
    return query_lang_expr._qm_node


def test_sqlalchemy_compilation_edge_case(engine):
    # This tests an edge case in the interaction of SQLAlchemy's `replacement_traverse`
    # function and our approach to query building. By default, `replacement_traverse`
    # clones the objects it walks over, unless they belong to the class of immutable
    # objects such as Tables. CTEs act a bit like tables, but are not immutable. This
    # means its possible to construct a sequence of queries at the end of which we have
    # duplicated clones of the same CTE. When we attempt to execute the query we get an
    # error like:
    #
    #     sqlalchemy.exc.CompileError: Multiple, unrelated CTEs found with the same name: 'cte_1'
    #
    # Naturally, this was discovered by the gentests. Below is the simplest example I
    # can construct which triggers the bug.

    dataset = create_dataset()
    # Weird as it seems, we need at least three references below to create the
    # problematic sort of object graph.
    dataset.define_population(patients.i + patients.i + patients.i == 0)
    dataset.has_event = events.exists_for_patient()

    engine.populate(
        {
            patients: [{"patient_id": 1}],
            events: [{"patient_id": 1}],
        }
    )
    assert engine.extract(dataset) == []


def test_population_is_correctly_evaluated_for_containment_queries(engine):
    dataset = create_dataset()
    # Patients which exist in the `events` table but not the `patients` table still need
    # to be considered when evaluating the population condition
    dataset.define_population(patients.count_for_patient().is_in(events.i))

    engine.populate(
        {
            patients: [{"patient_id": 1}],
            events: [{"patient_id": 2, "i": 0}],
        }
    )
    assert engine.extract(dataset) == [
        {"patient_id": 2},
    ]


def test_horizontal_aggregation_wrapping_a_series_containment_query_works(engine):
    # Horizontal aggregations in the MSSQL engine are a little odd, and the gentests
    # exposed a couple of bugs here which we don't want to reoccur
    dataset = create_dataset()
    dataset.define_population(events.exists_for_patient())
    dataset.match = minimum_of(
        when(patients.i.is_in(events.i)).then("T").otherwise("F"), "X"
    )

    engine.populate(
        {
            patients: [
                # This patient should match because i=3 occurs in their events
                {"patient_id": 1, "i": 3},
                # This patient should not match
                {"patient_id": 2, "i": 3},
            ],
            events: [
                {"patient_id": 1, "i": 3},
                {"patient_id": 2, "i": 0},
            ],
        }
    )

    assert engine.extract(dataset) == [
        {"patient_id": 1, "match": "T"},
        {"patient_id": 2, "match": "F"},
    ]


def test_population_which_uses_combine_as_set_and_no_patient_frame(engine):
    # A population definition must be patient-level and therefore, if it only references
    # event frames, it must involve an aggregation somewhere. Most aggregations result
    # in a new patient-level SQL table being created but CombineAsSet is unusual here and
    # so it's possible to use it to create a population SQL expression which references
    # just a single event-level SQL table. This falsifies a previous assumption we made
    # and so we need to test that we handle it correctly.
    dataset = build_dataset(
        population=Function.In(
            Value(1),
            AggregateByPatient.CombineAsSet(as_query_model(events.i)),
        ),
        variables={"v": Value(True)},
    )

    engine.populate(
        {
            events: [
                {"patient_id": 1, "i": 1},
                {"patient_id": 1, "i": 1},
            ],
        }
    )

    assert engine.extract(dataset) == [
        {"patient_id": 1, "v": True},
    ]


def test_picking_row_doesnt_cause_filtered_rows_to_reappear(engine):
    # Regression test for a bug we introduced in the in-memory engine
    dataset = create_dataset()
    dataset.define_population(events.exists_for_patient())

    rows = events.where(events.i < 0).sort_by(events.i).first_for_patient()
    dataset.has_row = rows.exists_for_patient()
    dataset.row_count = rows.count_for_patient()

    engine.populate(
        {
            events: [{"patient_id": 1, "i": 2}],
        }
    )

    assert engine.extract(dataset) == [
        {"patient_id": 1, "has_row": False, "row_count": 0},
    ]


def test_cast_to_int_on_minimum_of_float(engine):
    # Regression test for a bug we introduced in the CastToInt operation for the Trino
    # engine
    @table
    class p(PatientFrame):
        f = Series(float)

    engine.populate(
        {
            p: [{"patient_id": 1, "f": 1.5}],
        }
    )
    dataset = create_dataset()
    dataset.define_population(p.exists_for_patient())
    # Applying the minimum_of operation first caused the Trino engine to lose track
    # of the type and therefore not apply the correct rounding when casting to int
    dataset.i = minimum_of(p.f, p.f).as_int()

    assert engine.extract(dataset) == [
        {"patient_id": 1, "i": 1},
    ]


def test_basic_event_level_data_support(engine):
    engine.populate(
        {
            patients: [
                {"patient_id": 1, "i": 100},
                {"patient_id": 2, "i": 200},
                {"patient_id": 3, "i": 300},
                {"patient_id": 4, "i": 400},
            ],
            events: [
                {"patient_id": 1, "code": "a"},
                {"patient_id": 1, "code": "b"},
                {"patient_id": 1, "code": "c"},
                {"patient_id": 2, "code": "d"},
                {"patient_id": 3, "code": "e"},
                {"patient_id": 3, "code": "f"},
                {"patient_id": 4, "code": "g"},
                {"patient_id": 4, "code": "h"},
                {"patient_id": 5, "code": "i"},
            ],
        }
    )
    dataset = create_dataset()
    dataset.define_population(patients.i != 300)
    dataset.i = patients.i
    dataset.add_event_table("events", c=events.code)

    assert engine.get_results_tables(dataset) == [
        [
            {"patient_id": 1, "i": 100},
            {"patient_id": 2, "i": 200},
            {"patient_id": 4, "i": 400},
        ],
        [
            {"patient_id": 1, "c": "a"},
            {"patient_id": 1, "c": "b"},
            {"patient_id": 1, "c": "c"},
            {"patient_id": 2, "c": "d"},
            {"patient_id": 4, "c": "g"},
            {"patient_id": 4, "c": "h"},
        ],
    ]


# Yeah, yeah mutable defaults – but nothing mutates them
def build_dataset(*, population, variables={}, events={}):
    return Dataset(population=population, variables=variables, events=events)
