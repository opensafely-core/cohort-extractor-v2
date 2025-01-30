import datetime
import importlib
import os
from enum import Enum, auto
from pathlib import Path

import hypothesis as hyp
import hypothesis.strategies as st
import pytest
from hypothesis.vendor.pretty import _singleton_pprinters, pretty

from ehrql import dummy_data, dummy_data_nextgen
from ehrql.exceptions import CannotGenerate
from ehrql.query_model.introspection import all_unique_nodes
from ehrql.query_model.nodes import (
    AggregateByPatient,
    Column,
    Dataset,
    Function,
    Parameter,
    SelectColumn,
    SelectPatientTable,
    TableSchema,
    Value,
)
from ehrql.serializer import deserialize, serialize
from tests.lib.query_model_utils import get_all_operations

from ..conftest import QUERY_ENGINE_NAMES, engine_factory
from . import data_setup, data_strategies, variable_strategies
from .conftest import BrokenDatabaseError
from .generic_strategies import usually_all_of
from .ignored_errors import IgnoredError, get_ignored_error_type


# To simplify data generation, all tables have the same schema.
schema = TableSchema(
    i1=Column(int),
    i2=Column(int),
    b1=Column(bool),
    b2=Column(bool),
    d1=Column(datetime.date),
    d2=Column(datetime.date),
    f1=Column(float),
    f2=Column(float),
    s1=Column(str),
    s2=Column(str),
)
(
    patient_classes,
    event_classes,
    all_patients_query,
    sqla_metadata,
) = data_setup.setup(schema, num_patient_tables=2, num_event_tables=2)

# This will only get run during a failing example, so shows up as uncovered when the tests pass.
_singleton_pprinters[id(schema)] = lambda obj, p, cycle: p.text(
    "schema"
)  # pragma: no cover

# Use the same strategies for values both for query generation and data generation.
value_strategies = {
    int: st.integers(min_value=0, max_value=10),
    bool: st.booleans(),
    datetime.date: st.dates(
        min_value=datetime.date(2010, 1, 1), max_value=datetime.date(2020, 12, 31)
    ),
    float: st.floats(min_value=0.0, max_value=11.0, width=16, allow_infinity=False),
    str: st.text(alphabet=["a", "b", "c"], min_size=0, max_size=3),
}

dataset_strategy = variable_strategies.dataset(
    [c.__tablename__ for c in patient_classes],
    [c.__tablename__ for c in event_classes],
    schema,
    value_strategies,
)
data_strategy = data_strategies.data(
    patient_classes,
    event_classes,
    schema,
    value_strategies,
)
settings = dict(
    max_examples=(int(os.environ.get("GENTEST_EXAMPLES", 10))),
    deadline=None,
    # On CI we want to run derandomized unless we're explicitly in the
    # long-running bug finding tests. This prevents flaky CI.
    # In development we never want to run with derandomize because it's
    # less effective at finding bugs and, more importantly, has very slow
    # replay due to turning off the test database
    derandomize=bool(os.environ.get("GENTEST_RANDOMIZE"))
    if os.environ.get("CI")
    else False,
    # The explain phase is comparatively expensive here given how
    # costly data generation is for our tests here, so we turn it
    # off by default.
    phases=(
        (set(hyp.Phase) - {hyp.Phase.explain})
        if os.environ.get("GENTEST_EXPLAIN") != "true"
        else hyp.Phase
    ),
    report_multiple_bugs=False,
)


SELECTED_QUERY_ENGINES = (
    os.environ.get("GENTEST_QUERY_ENGINES", "").split() or QUERY_ENGINE_NAMES
)


@pytest.fixture(scope="session")
def query_engines(request):
    # By contrast with the `engine` fixture which is parametrized over the types of
    # engine and so returns them one at a time, this fixture constructs and returns all
    # the engines together at once
    return {
        name: engine_factory(request, name, with_session_scope=True)
        for name in SELECTED_QUERY_ENGINES
    }


class EnabledTests(Enum):
    serializer = auto()
    dummy_data = auto()
    dummy_data_nextgen = auto()
    main_query = auto()
    all_population = auto()
    pretty_printing = auto()


if TEST_NAMES_TO_RUN := set(
    os.environ.get("GENTEST_TESTS_TO_RUN", "").lower().split()
):  # pragma: no cover
    TESTS_TO_RUN = [t for t in EnabledTests if t.name in TEST_NAMES_TO_RUN]
else:
    TESTS_TO_RUN = list(EnabledTests)


@hyp.given(
    dataset=dataset_strategy,
    data=data_strategy,
    enabled_engines=usually_all_of(SELECTED_QUERY_ENGINES),
    test_types=usually_all_of(TESTS_TO_RUN),
)
@hyp.settings(**settings)
def test_query_model(
    query_engines, dataset, data, recorder, enabled_engines, test_types
):
    query_engines = {
        name: engine
        for name, engine in query_engines.items()
        if name in enabled_engines
    }
    recorder.record_inputs(dataset, data)

    if EnabledTests.serializer in test_types:
        run_serializer_test(dataset)
    if EnabledTests.dummy_data in test_types:
        run_dummy_data_test(dataset)
    if EnabledTests.dummy_data_nextgen in test_types:
        run_dummy_data_test(dataset, next_gen=True)
    if EnabledTests.main_query in test_types:
        run_test(query_engines, data, dataset, recorder)
    if EnabledTests.pretty_printing in test_types:
        pretty(dataset)

    if EnabledTests.all_population in test_types:
        # We run the test again using a simplified population definition which includes
        # all patients: this ensures that the calculated variable values matches for all
        # patients, not just those included in the original population (which may be
        # zero, if `data` happens not to contain any matching patients)
        run_test(query_engines, data, include_all_patients(dataset), recorder)


def run_test(query_engines, data, dataset, recorder):
    instances = instantiate(data)

    all_results = {
        name: run_with(engine, instances, dataset)
        for name, engine in query_engines.items()
    }

    # Sometimes we hit test cases where one engine is known to have problems so we
    # ignore those results
    results = {
        name: engine_results
        for name, engine_results in all_results.items()
        if not isinstance(engine_results, IgnoredError)
    }

    # SQLite has an unfortunate habit of returning NULL, rather than raising an error,
    # when it hits a date overflow. This can make Hypothesis think it has found an
    # interesting results mismatch when in fact it hasn't. To avoid this, we take the
    # approach that whenever the in-memory engine hits a date overflow we ignore the
    # results from SQLite as well.
    if all_results.get("in_memory") is IgnoredError.DATE_OVERFLOW:
        results.pop("sqlite", None)

    recorder.record_results(len(all_results), len(all_results) - len(results))

    # If we hit a case which _no_ database can handle (e.g. some silly bit of date
    # arithmetic results in an out-of-bounds date) then just bail out
    if not results:
        return

    # Use the first engine's results as the baseline (this is arbitrary, equality being
    # transitive)
    first_name = list(results.keys())[0]
    first_results = results.pop(first_name)
    # We want only approximate equality for floats to account for rounding differences
    # between different databases
    first_results = [
        [pytest.approx(row, rel=1e-5) for row in table] for table in first_results
    ]

    for other_name, other_results in results.items():
        assert first_results == other_results, (
            f"Mismatch between {first_name} and {other_name}"
        )


def instantiate(data):
    instances = []
    for item in data:
        item = item.copy()
        instances.append(item.pop("type")(**item))
    return instances


def run_with(engine, instances, dataset):
    error_type = None
    try:
        engine.setup(instances, metadata=sqla_metadata)
        return engine.get_results_tables(
            dataset,
            config={
                # In order to exercise the temporary table code path we set the limit
                # here very low
                "EHRQL_MAX_MULTIVALUE_PARAM_LENGTH": 3,
            },
        )
    except Exception as e:
        if error_type := get_ignored_error_type(e):
            # MS SQL Server has an unfortunate habit of hanging completely during generative
            # testing, which presents as a connection error. There's no point in hypothesis
            # continuing to try and run tests against a dead instance.
            if error_type is IgnoredError.CONNECTION_ERROR:  # pragma: no cover
                raise BrokenDatabaseError(engine.name).with_traceback(e.__traceback__)
            return error_type
        raise
    finally:
        if error_type is not IgnoredError.CONNECTION_ERROR:  # pragma: no cover
            engine.teardown()


def run_dummy_data_test(dataset, next_gen=False):
    try:
        run_dummy_data_test_without_error_handling(dataset, next_gen)
    except Exception as e:  # pragma: no cover
        if not get_ignored_error_type(e):
            raise


def run_dummy_data_test_without_error_handling(dataset, next_gen=False):
    # We can't do much more here than check that the generator runs without error, but
    # that's enough to catch quite a few issues

    dummy = dummy_data_nextgen if next_gen else dummy_data

    dummy_data_generator = dummy.DummyDataGenerator(
        dataset,
        population_size=1,
        # We need a batch size bigger than one otherwise by chance (or, more strictly,
        # by deterministic combination of query and fixed random seed) we can end up
        # generating no examples of any tables, resulting in a not very interesting
        # failure mode.
        batch_size=5,
        timeout=-1,
    )
    try:
        assert isinstance(dummy_data_generator.get_data(), dict)
    # TODO: This isn't reliably getting hit. Figure out how to make it be so.
    # This error is logically possible here but the actual code paths are tested
    # elsewhere so it's not that important for the generative tests to be able to
    # hit it.
    except CannotGenerate:  # pragma: no cover
        pass
    # Using a simplified population definition which should always have matching patients
    # we can confirm that we generate at least some data
    dummy_data_generator = dummy.DummyDataGenerator(
        include_all_patients(dataset),
        population_size=1,
        batch_size=1,
        timeout=-1,
    )
    dummy_tables = dummy_data_generator.get_data()
    assert sum(len(v) for v in dummy_tables.values()) > 0


def run_serializer_test(dataset):
    # Test that the dataset correctly roundtrips through the serializer
    assert dataset == deserialize(serialize(dataset), root_dir=Path.cwd())


# META TESTS
#
# The below are all "meta tests" i.e. they are tests which check that our testing
# machinery is doing what we think it's doing and covering all the things we want it to
# cover


def test_query_model_example_file(query_engines, recorder):
    # This test exists so that we can run examples from arbitrary files (by setting the
    # GENTEST_EXAMPLE_FILE env var) which is useful when digging into a new gentest
    # failure. Just to make sure that the machinery keeps working we default to running
    # the test against a tiny example file.
    filename = os.environ.get(
        "GENTEST_EXAMPLE_FILE", Path(__file__).parent / "example.py"
    )
    example = load_module(Path(filename))
    test_func = test_query_model.hypothesis.inner_test
    test_func(
        query_engines,
        example.dataset,
        example.data,
        recorder,
        SELECTED_QUERY_ENGINES,
        EnabledTests,
    )


def load_module(module_path):
    # Taken from the official recipe for importing a module from a file path:
    # https://docs.python.org/3.9/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Ensure that we don't add new query model nodes without adding an appropriate strategy
# for them.
def test_dataset_strategy_is_comprehensive():
    operations_seen = set()

    # This uses a fixed seed and no example database to make it deterministic
    # The specific seed used has no particular significance. This test is just
    # a bit fragile. If it fails and you think this isn't a real failure, feel
    # free to tweak the seed a bit and see if that fixes it.
    @hyp.settings(max_examples=600, database=None, deadline=None)
    @hyp.seed(3457902459072)
    @hyp.given(dataset=dataset_strategy)
    def record_operations_seen(dataset):
        operations_seen.update(type(node) for node in all_unique_nodes(dataset))

    record_operations_seen()

    known_missing_operations = {
        # Parameters don't themselves form part of valid queries: they are placeholders
        # which must all be replaced with Values before the query can be executed.
        Parameter,
    }
    all_operations = set(get_all_operations())
    unexpected_missing = all_operations - known_missing_operations - operations_seen
    unexpected_present = known_missing_operations & operations_seen

    assert not unexpected_missing, f"unseen operations: {unexpected_missing}"
    assert not unexpected_present, f"unexpectedly seen operations: {unexpected_present}"


@pytest.mark.parametrize(
    "operation,rhs",
    [
        (Function.DateAddYears, -2000),  # year=0
        (Function.DateAddYears, -3000),  # year=-1000
        (Function.DateAddYears, 8000),  # year = 10000
        (Function.DateAddMonths, -3000 * 12),
        (Function.DateAddMonths, 8000 * 12),
        (Function.DateAddDays, -3000 * 366),
        (Function.DateAddDays, 8000 * 366),
        (
            Function.DateAddDays,
            1500000000,
        ),  # triggers python overflow error with timedelta
    ],
)
def test_run_with_handles_date_errors(query_engines, operation, rhs):
    """
    Runs a test with input that is expected to raise an error in some way which is
    expected to be handled. If an exception is raised and handled within the test
    function, the result will be an `IGNORE_RESULT` object.  If the bad input is
    handled within the query engine itself, the result will contain a None value.
    e.g. attempting to add 8000 years to 2000-01-01 results in a date that is outside
    of the valid range (max 9999-12-31).  The sqlite engine returns None for this,
    all other engines raise an Exception that we catch and ignore.
    """
    data = [
        {
            "type": data_setup.P0,
            "patient_id": 1,
            "d1": datetime.date(2000, 1, 1),
        }
    ]
    dataset = Dataset(
        population=all_patients_query,
        variables={
            "v": operation(
                lhs=SelectColumn(
                    source=SelectPatientTable(name="p0", schema=schema), name="d1"
                ),
                rhs=Value(rhs),
            )
        },
        events={},
    )
    instances = instantiate(data)
    for engine in query_engines.values():
        result = run_with(engine, instances, dataset)
        assert result in [IgnoredError.DATE_OVERFLOW, [[{"patient_id": 1, "v": None}]]]


def test_run_with_still_raises_non_ignored_errors(query_engines):
    # Make sure our ignored error code isn't inadvertently catching everything
    first_engine = list(query_engines.values())[0]
    not_valid_dataset = object()
    with pytest.raises(Exception):
        run_with(first_engine, [], not_valid_dataset)


def test_run_test_handles_errors_from_all_query_engines(query_engines, recorder):
    # Make sure we can handle a query which fails for all query engines
    data = [{"type": data_setup.P0, "patient_id": 1}]
    dataset = Dataset(
        population=AggregateByPatient.Exists(SelectPatientTable("p0", schema=schema)),
        variables={
            "v": Function.DateAddYears(
                lhs=Value(datetime.date(2000, 1, 1)),
                rhs=Value(8000),
            )
        },
        events={},
    )
    run_test(query_engines, data, dataset, recorder)


def include_all_patients(dataset):
    return Dataset(
        population=all_patients_query,
        variables=dataset.variables,
        events={},
    )
