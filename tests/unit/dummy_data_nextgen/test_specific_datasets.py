import operator
from collections import Counter
from datetime import date
from unittest import mock

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from hypothesis.vendor.pretty import pretty

from ehrql import case, create_dataset, maximum_of, when, years
from ehrql.dummy_data_nextgen.generator import DummyDataGenerator
from ehrql.exceptions import CannotGenerate
from ehrql.query_language import (
    EventFrame,
    PatientFrame,
    Series,
    table,
    table_from_rows,
)
from ehrql.tables.core import (
    clinical_events,
    medications,
    patients,
)


index_date = date(2022, 3, 1)

is_female_or_male = patients.sex.is_in(["female", "male"])

was_adult = (patients.age_on(index_date) >= 18) & (patients.age_on(index_date) <= 110)

was_alive = (
    patients.date_of_death.is_after(index_date) | patients.date_of_death.is_null()
)

died_more_than_10_years_ago = (patients.date_of_death + years(10)) < index_date


@table
class extra_patients(PatientFrame):
    some_integer = Series(int)


@mock.patch("ehrql.dummy_data_nextgen.generator.time")
@pytest.mark.parametrize(
    "query",
    [
        patients.sex == "male",
        patients.date_of_birth.year == 1950,
        (patients.date_of_birth.year == 1970) & (patients.sex == "intersex"),
        ((patients.date_of_birth.year == 1970) & (patients.sex == "male"))
        | ((patients.date_of_birth.year == 1963) & (patients.sex == "male")),
        is_female_or_male & was_adult & was_alive,
        died_more_than_10_years_ago,
        patients.date_of_death.is_null(),
        ~patients.date_of_death.is_null(),
        case(
            when(patients.sex == "male").then(1),
            when(patients.sex == "female").then(2),
        )
        >= 2,
        maximum_of(patients.date_of_birth, patients.date_of_birth) <= index_date,
    ],
    ids=pretty,
)
def test_queries_with_exact_one_shot_generation(patched_time, query):
    dataset = create_dataset()

    dataset.define_population(patients.exists_for_patient() & query)

    target_size = 1000

    variable_definitions = dataset._compile()
    generator = DummyDataGenerator(variable_definitions, population_size=target_size)
    generator.batch_size = target_size
    generator.timeout = 10

    # Configure `time.time()` so we timeout after one loop pass, as we
    # should be able to generate these correctly in the first pass.
    patched_time.time.side_effect = [0.0, 20.0]
    patient_ids = {row.patient_id for row in generator.get_results()}

    assert len(patient_ids) == target_size


@mock.patch("ehrql.dummy_data_nextgen.generator.time")
@pytest.mark.parametrize(
    "query",
    [
        clinical_events.exists_for_patient(),
        ~clinical_events.exists_for_patient(),
    ],
    ids=pretty,
)
def test_queries_with_exact_two_shot_generation(patched_time, query):
    """For queries which we can't guarantee correct from the start
    but we can reliably figure out enough in the first batch of results
    that the second one is complete."""
    dataset = create_dataset()

    dataset.define_population(patients.exists_for_patient() & query)

    target_size = 1000

    variable_definitions = dataset._compile()
    generator = DummyDataGenerator(variable_definitions, population_size=target_size)
    generator.batch_size = target_size
    generator.timeout = 10

    # Configure `time.time()` so we timeout after two loop passes.
    patched_time.time.side_effect = [0.0, 1.0, 20.0]
    patient_ids = {row.patient_id for row in generator.get_results()}

    assert len(patient_ids) == target_size


@st.composite
def birthday_range_query(draw):
    # We generate a single date that we require to be valid for
    # our query as a way of ensuring that the query always has
    # results.

    reasonable_dates = st.dates(min_value=date(1900, 1, 1), max_value=date(2024, 9, 1))
    valid_date = draw(reasonable_dates).replace(day=1)

    query_endpoints = draw(st.lists(reasonable_dates, min_size=1))
    query_components = []

    for endpoint in query_endpoints:
        # NB draw unconditionally for easier shrinking, but need
        # to force equality to be allowed if this is equal to the
        # target date. We invert it so that it shrinks to allowing
        # equality, as this is the slightly simpler codepath.
        allow_equal = not draw(st.booleans())
        if endpoint == valid_date:
            allow_equal = True
        if endpoint >= valid_date:
            if allow_equal:
                op = operator.le
            else:
                op = operator.lt
        else:
            if allow_equal:
                op = operator.ge
            else:
                op = operator.gt
        assert op(valid_date, endpoint)
        query_components.append(op(patients.date_of_birth, endpoint))
    while len(query_components) > 1:
        q = query_components.pop()
        i = draw(st.integers(0, len(query_components) - 1))
        query_components[i] &= q
    return query_components[0]


@example(
    query=(patients.date_of_birth >= date(2000, 1, 1))
    & (patients.date_of_birth < date(2000, 1, 2)),
    target_size=1,
)
@example(query=patients.date_of_birth < date(1900, 12, 31), target_size=1000)
@example(query=patients.date_of_birth >= date(1900, 1, 2), target_size=1000)
@example(query=patients.date_of_birth >= date(2000, 12, 1), target_size=1000)
@settings(deadline=None)
@given(query=birthday_range_query(), target_size=st.integers(1, 1000))
@mock.patch("ehrql.dummy_data_nextgen.generator.time")
def test_combined_age_range_in_one_shot(patched_time, query, target_size):
    dataset = create_dataset()

    dataset = create_dataset()

    dataset.define_population(query)

    variable_definitions = dataset._compile()
    generator = DummyDataGenerator(variable_definitions, population_size=target_size)
    generator.batch_size = target_size
    generator.timeout = 10

    # Configure `time.time()` so we timeout after one loop pass, as we
    # should be able to generate these correctly in the first pass.
    patched_time.time.side_effect = [0.0, 20.0]
    data = generator.get_data()

    # Expecting a single table
    assert len(data) == 1
    data_for_table = list(data.values())[0]
    # Within that table expecting we generated a full population
    assert len(data_for_table) == target_size


@table_from_rows([(i, i, False) for i in range(1, 1000)])
class p(PatientFrame):
    i = Series(int)
    b = Series(bool)


@table
class p0(PatientFrame):
    i1 = Series(int)
    b1 = Series(bool)
    d1 = Series(date)


@table
class e0(EventFrame):
    b0 = Series(bool)
    i1 = Series(int)


@mock.patch("ehrql.dummy_data_nextgen.generator.time")
@pytest.mark.parametrize(
    "query",
    [
        date(2010, 1, 1) < medications.date.minimum_for_patient(),
        medications.sort_by(medications.date).first_for_patient().date
        < date(2020, 1, 1),
        clinical_events.where(
            clinical_events.snomedct_code == "123456789"
        ).exists_for_patient(),
        maximum_of(patients.date_of_birth, patients.date_of_death)
        <= index_date - years(10),
        case(
            when(patients.sex == "male").then(1),
            when(patients.date_of_birth == index_date).then(2),
            otherwise=3,
        )
        >= 2,
        case(
            when(patients.date_of_birth <= index_date).then(patients.date_of_death),
            otherwise=patients.date_of_birth,
        )
        <= index_date,
        p0.i1
        < case(
            when(e0.sort_by(e0.i1).first_for_patient().b0).then(
                e0.sort_by(e0.i1).first_for_patient().i1
            ),
            otherwise=None,
        ),
        patients.date_of_birth < case(when(p0.b1).then(None), otherwise=p0.d1),
        case(when(p0.b1).then(None), otherwise=p0.d1)
        < patients.date_of_birth + years(1),
        case(when(p0.b1).then(date(2010, 1, 2)), otherwise=date(2010, 1, 1))
        > date(2010, 1, 1),
    ],
    ids=pretty,
)
def test_queries_not_yet_well_handled(patched_time, query):
    """Tests queries that we need to work, but do not currently
    expect to be handled particularly well.
    """
    dataset = create_dataset()

    dataset.define_population(patients.exists_for_patient() & query)

    target_size = 1000
    variable_definitions = dataset._compile()

    generator = DummyDataGenerator(variable_definitions, population_size=target_size)
    generator.batch_size = target_size
    generator.timeout = 10

    patched_time.time.side_effect = [0.0, 20.0]

    patient_ids = {row.patient_id for row in generator.get_results()}

    # Should be able to generate at least one patient satisfying this
    assert len(patient_ids) > 0

    # If one of these queries manages to generate fully in a single pass then
    # it deserves a more specific test. This is effectively a sort of xfail
    # assertion.
    assert len(patient_ids) < target_size


@mock.patch("ehrql.dummy_data_nextgen.generator.time")
def test_inline_table_query(patched_time):
    """Tests queries that we need to work, but do not currently
    expect to be handled particularly well.
    """
    dataset = create_dataset()

    dataset.define_population(p.i < 1000)
    dataset.i = p.i

    target_size = 1000
    variable_definitions = dataset._compile()

    generator = DummyDataGenerator(variable_definitions, population_size=target_size)
    generator.batch_size = target_size
    generator.timeout = 10

    patched_time.time.side_effect = [0.0, 20.0]

    patient_ids = {row.patient_id for row in generator.get_results()}

    # Should be able to generate at least one patient satisfying this
    assert len(patient_ids) > 0

    # If one of these queries manages to generate fully in a single pass then
    # it deserves a more specific test. This is effectively a sort of xfail
    # assertion.
    assert len(patient_ids) < target_size


@pytest.mark.parametrize(
    "query",
    [
        patients.sex == "book",
        extra_patients.some_integer + 1 < extra_patients.some_integer,
    ],
    ids=pretty,
)
@mock.patch("ehrql.dummy_data_nextgen.generator.time")
def test_will_raise_if_all_data_is_impossible(patched_time, query):
    dataset = create_dataset()

    dataset.define_population(query)
    target_size = 1000
    variable_definitions = dataset._compile()

    generator = DummyDataGenerator(variable_definitions, population_size=target_size)
    generator.timeout = 1
    patched_time.time.side_effect = [0.0, 20.0]
    with pytest.raises(CannotGenerate):
        next(generator.get_results())


def test_generates_events_starting_from_birthdate():
    dataset = create_dataset()

    age = patients.age_on("2020-03-31")

    dataset.age = age
    dataset.sex = patients.sex

    events = clinical_events.sort_by(clinical_events.date).first_for_patient()
    dataset.dob = patients.date_of_birth
    dataset.event_date = events.date
    dataset.after_dob = events.date >= patients.date_of_birth
    dataset.define_population((age > 18) & (age < 80) & ~dataset.event_date.is_null())

    target_size = 1000
    dataset.configure_dummy_data(population_size=target_size)
    variable_definitions = dataset._compile()

    generator = DummyDataGenerator(variable_definitions, population_size=target_size)

    for row in generator.get_results():
        assert row.after_dob


def test_distribution_of_booleans():
    """Ensures that the distribution of boolean properties depending on the existence
    of an event is not too badly biased."""
    dataset = create_dataset()

    dataset.has_the_thing = clinical_events.where(
        clinical_events.snomedct_code == "123456789"
    ).exists_for_patient()

    dataset.define_population(patients.exists_for_patient())

    target_size = 1000

    variable_definitions = dataset._compile()
    generator = DummyDataGenerator(variable_definitions, population_size=target_size)
    generator.batch_size = target_size

    property_counts = Counter(row.has_the_thing for row in generator.get_results())

    assert property_counts[False] + property_counts[True] == target_size
    assert 0.2 < property_counts[True] / target_size < 0.8


def test_can_generate_patients_with_one_but_not_both_conditions():
    dataset = create_dataset()

    code1 = "123456789"
    code2 = "234567891"

    dataset.condition1 = clinical_events.where(
        clinical_events.snomedct_code == code1
    ).exists_for_patient()

    dataset.condition2 = clinical_events.where(
        clinical_events.snomedct_code == code2
    ).exists_for_patient()

    dataset.define_population(
        clinical_events.where(
            clinical_events.snomedct_code.is_in([code1, code2])
        ).count_for_patient()
        >= 3
    )

    target_size = 1000
    dataset.configure_dummy_data(population_size=target_size)
    variable_definitions = dataset._compile()

    generator = DummyDataGenerator(variable_definitions, population_size=target_size)

    distinct_condition_counts = Counter()

    for row in generator.get_results():
        assert row.condition1 or row.condition2
        distinct_condition_counts[row.condition1 != row.condition2] += 1
    assert 0.2 < distinct_condition_counts[True] / target_size < 0.8


def test_additional_constraints_may_force_events_in_order():
    dataset = create_dataset()

    dataset.did_the_first_thing = (
        clinical_events.where(clinical_events.snomedct_code == "123456789")
        .sort_by(clinical_events.date)
        .first_for_patient()
        .date
    )

    dataset.did_the_second_thing = (
        clinical_events.where(clinical_events.snomedct_code == "234567891")
        .sort_by(clinical_events.date)
        .first_for_patient()
        .date
    )

    target_size = 1000
    dataset.configure_dummy_data(
        additional_population_constraint=dataset.did_the_first_thing
        < dataset.did_the_second_thing,
        population_size=target_size,
    )

    dataset.define_population(
        ~(
            dataset.did_the_first_thing.is_null()
            | dataset.did_the_second_thing.is_null()
        )
    )

    generator = DummyDataGenerator.from_dataset(dataset, batch_size=target_size)

    results = list(generator.get_results())
    assert len(results) == target_size

    for r in results:
        assert r.did_the_first_thing < r.did_the_second_thing


@mock.patch("ehrql.dummy_data_nextgen.generator.time")
def test_can_benefit_from_column_filtering_with_extra_constraints(patched_time):
    dataset = create_dataset()
    dataset.define_population(patients.exists_for_patient())
    birth_date = date(1919, 7, 1)

    dataset.sex = patients.sex
    dataset.date_of_birth = patients.date_of_birth

    target_size = 1000
    dataset.configure_dummy_data(
        additional_population_constraint=(patients.sex == "female")
        & (patients.date_of_birth == birth_date),
        population_size=target_size,
        timeout=1,
    )

    generator = DummyDataGenerator.from_dataset(dataset, batch_size=target_size)
    patched_time.time.side_effect = [0.0, 20.0]

    results = list(generator.get_results())
    assert len(results) == target_size

    for r in results:
        assert r.sex == "female"
        assert r.date_of_birth == birth_date
