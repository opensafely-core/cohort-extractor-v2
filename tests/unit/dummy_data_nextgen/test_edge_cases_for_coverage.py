from datetime import date

import pytest

from ehrql.dummy_data_nextgen.generator import DummyDataGenerator
from ehrql.dummy_data_nextgen.query_info import QueryInfo, is_value, specialize
from ehrql.query_language import Series, case, create_dataset, when
from ehrql.query_model.nodes import (
    Case,
    Dataset,
    Function,
    SelectColumn,
    SelectPatientTable,
    TableSchema,
    Value,
)
from ehrql.tables.tpp import patients


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
    QueryInfo.from_dataset(
        Dataset(
            population=Function.LT(
                lhs=Case(
                    cases={SelectColumn(source=p0, name="b1"): None},
                    default=Value(value=date(2010, 1, 1)),
                ),
                rhs=Value(value=date(2010, 1, 1)),
            ),
            variables={
                "v": SelectColumn(
                    source=p0,
                    name="i1",
                ),
            },
        )
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


def test_errors_if_extra_condition_in_legacy():
    dataset = create_dataset()

    with pytest.raises(ValueError):
        dataset.configure_dummy_data(
            legacy=True, additional_population_constraint=patients.sex == "male"
        )

    with pytest.raises(ValueError):
        dataset.configure_dummy_data(
            legacy=True,
            patient_weighting=case(
                when(patients.sex == "male").then(2.0), otherwise=1.0
            ),
        )


def test_errors_if_both_configuration_and_kwargs():
    dataset = create_dataset()
    dataset.define_population(patients.exists_for_patient())

    with pytest.raises(ValueError):
        DummyDataGenerator.from_dataset(dataset, population_size=1000)


def test_invalid_constraint_raises_error():
    dataset = create_dataset()
    with pytest.raises(TypeError):
        dataset.configure_dummy_data(
            additional_population_constraint=patients.sex,
        )


def test_will_return_none_for_an_out_of_range_date_when_permitted():
    dataset = create_dataset()
    dataset.date_of_death = patients.date_of_death
    dataset.define_population(patients.exists_for_patient())

    generator = DummyDataGenerator.from_dataset(dataset)

    patient_generator = generator.patient_generator

    patient_generator.events_start = date(2050, 1, 1)

    dod_column = patient_generator.get_patient_column("date_of_death")

    with patient_generator.seed("test"):
        for _ in range(100):
            assert patient_generator.get_random_value(dod_column) is None
