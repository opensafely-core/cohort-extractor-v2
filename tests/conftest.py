import os
import random
import subprocess
import threading
from pathlib import Path

import pytest
from hypothesis.internal.reflection import extract_lambda_source

import ehrql
import ehrql.__main__
from ehrql import query_language as ql
from ehrql.main import get_sql_strings
from ehrql.query_engines.in_memory import InMemoryQueryEngine
from ehrql.query_engines.mssql import MSSQLQueryEngine
from ehrql.query_engines.sqlite import SQLiteQueryEngine
from ehrql.query_engines.trino import TrinoQueryEngine
from ehrql.query_model import nodes as qm
from tests.lib.orm_utils import make_orm_models

from .lib.databases import (
    InMemoryPythonDatabase,
    InMemorySQLiteDatabase,
    make_mssql_database,
    make_trino_database,
    wait_for_database,
)
from .lib.docker import Containers


def pytest_collection_modifyitems(session, config, items):  # pragma: no cover
    """If running with pytest-xdist, add a group identifier to each test item, based on
    which database is used by the test.

    This lets us use pytest-xdist to distribute tests across three processes leading to
    a moderate speed-up, via `pytest -n3`.

    The "proper" way to distribute tests with pytest-xdist is by adding the xdist_group
    mark.  However, this is very hard to do dynamically (because of our use of
    request.getfixturevalue) so it is less invasive to add a group identifier here,
    during test collection.  Later, pytest-xdist will use the group identifier to
    distribute tests to workers.
    """

    if "PYTEST_XDIST_WORKER" not in os.environ:
        # Modifying test item identifiers makes it harder to copy and paste identifiers
        # from failing outputs, so it only makes sense to do so if we're running tests
        # with pytest-xdist.
        return

    slow_database_names = ["mssql", "trino"]

    for item in items:
        group = "other"

        if "engine" in item.fixturenames:
            database_name = item.callspec.params["engine"]
            if database_name in slow_database_names:
                group = database_name

        else:
            found_database_in_fixtures = False
            for database_name in slow_database_names:
                if any(
                    database_name in fixture_name for fixture_name in item.fixturenames
                ):
                    group = database_name
                    # Check that tests do not use multiple fixtures for slow databases.
                    assert not found_database_in_fixtures
                    found_database_in_fixtures = True

        item._nodeid = f"{item.nodeid}@{group}"


# Fail the build if we see any warnings.
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if terminalreporter.stats.get("warnings"):  # pragma: no cover
        print("ERROR: warnings detected")
        if terminalreporter._session.exitstatus == 0:
            terminalreporter._session.exitstatus = 13


def pytest_make_parametrize_id(config, val):
    # Where we use lambdas as test parameters, having the source as the parameter ID
    # makes it quicker to identify specific test cases in the output
    if callable(val) and val.__name__ == "<lambda>":
        return extract_lambda_source(val).removeprefix("lambda: ")


@pytest.fixture(scope="session")
def show_delayed_warning(request):
    """
    Some fixtures can take a long time to execute the first time they're run (e.g. they
    might need to pull down a large Docker image) but pytest's output capturing means
    that the user has no idea what's happening. This fixture allows us to "poke through"
    the output capturing and display a message to the user, but only if the task has
    already taken more than N seconds.
    """

    def show_warning(message):  # pragma: no cover
        capturemanager = request.config.pluginmanager.getplugin("capturemanager")
        # No need to display anything if output is not being captured
        if capturemanager.is_capturing():
            with capturemanager.global_and_fixture_disabled():
                print(f"\n => {message} ...")

    return lambda delay, message: ContextTimer(delay, show_warning, args=[message])


# Timer which starts/cancels itself when entering/exiting a context block
class ContextTimer(threading.Timer):
    def __enter__(self):
        self.start()

    def __exit__(self, *_):
        self.cancel()


@pytest.fixture(scope="session")
def containers():
    yield Containers()


# Database fixtures {

# These fixtures come in pairs.  For each database, there is a session-scoped fixture,
# which performs any setup, and there is a function-scoped fixture, which reuses the
# fixture returned by the session-scoped fixture.
#
# In most cases, we will want the function-scoped fixture, as this allows post-test
# teardown.  However, the generative tests require a session-scoped fixture.


@pytest.fixture(scope="session")
def in_memory_sqlite_database_with_session_scope():
    return InMemorySQLiteDatabase()


@pytest.fixture(scope="function")
def in_memory_sqlite_database(in_memory_sqlite_database_with_session_scope):
    database = in_memory_sqlite_database_with_session_scope
    yield database
    database.teardown()


@pytest.fixture(scope="session")
def mssql_database_with_session_scope(containers, show_delayed_warning):
    with show_delayed_warning(
        3, "Starting MSSQL Docker image (will download image on first run)"
    ):
        database = make_mssql_database(containers)
        wait_for_database(database)
    return database


@pytest.fixture(scope="function")
def mssql_database(mssql_database_with_session_scope):
    database = mssql_database_with_session_scope
    yield database
    database.teardown()


@pytest.fixture(scope="session")
def trino_database_with_session_scope(containers, show_delayed_warning):
    with show_delayed_warning(
        3, "Starting Trino Docker image (will download image on first run)"
    ):
        database = make_trino_database(containers)
        wait_for_database(database)
    return database


@pytest.fixture(scope="function")
def trino_database(trino_database_with_session_scope):
    database = trino_database_with_session_scope
    yield database
    database.teardown()


class QueryEngineFixture:
    def __init__(self, name, database, query_engine_class):
        self.name = name
        self.database = database
        self.query_engine_class = query_engine_class

    def setup(self, *items, metadata=None):
        return self.database.setup(*items, metadata=metadata)

    def teardown(self):
        return self.database.teardown()

    def populate(self, *args):
        return self.setup(make_orm_models(*args))

    def query_engine(self, dsn=False, **engine_kwargs):
        if dsn is False:
            dsn = self.database.host_url()
        return self.query_engine_class(dsn, **engine_kwargs)

    def get_results_tables(self, dataset, **engine_kwargs):
        if isinstance(dataset, ql.Dataset):
            dataset = dataset._compile()
        assert isinstance(dataset, qm.Dataset)
        query_engine = self.query_engine(**engine_kwargs)
        results_tables = query_engine.get_results_tables(dataset)
        # We don't explicitly order the results and not all databases naturally
        # return in the same order
        return [
            [row._asdict() for row in sort_table(table)] for table in results_tables
        ]

    def extract(self, dataset, **engine_kwargs):
        return self.get_results_tables(dataset, **engine_kwargs)[0]

    def dump_dataset_sql(self, dataset, **engine_kwargs):
        assert isinstance(dataset, ql.Dataset)
        dataset_qm = dataset._compile()
        query_engine = self.query_engine(dsn=None, **engine_kwargs)
        return get_sql_strings(query_engine, dataset_qm)

    def sqlalchemy_engine(self):
        return self.query_engine().engine


def sort_table(table):
    # Python won't naturally compare None with other values, but we need to sort tables
    # containg None values so we treat None as smaller than all other values
    return sorted(table, key=sort_key_with_nones)


def sort_key_with_nones(row):
    return [(v is not None, v) for v in row]


QUERY_ENGINE_NAMES = ("in_memory", "sqlite", "mssql", "trino")


def engine_factory(request, engine_name, with_session_scope=False):
    if engine_name == "in_memory":
        return QueryEngineFixture(
            engine_name, InMemoryPythonDatabase(), InMemoryQueryEngine
        )

    if engine_name == "sqlite":
        database_fixture_name = "in_memory_sqlite_database"
        query_engine_class = SQLiteQueryEngine
    elif engine_name == "mssql":
        database_fixture_name = "mssql_database"
        query_engine_class = MSSQLQueryEngine
    elif engine_name == "trino":
        database_fixture_name = "trino_database"
        query_engine_class = TrinoQueryEngine
    else:
        assert False

    if with_session_scope:
        database_fixture_name = f"{database_fixture_name}_with_session_scope"

    # We dynamically request fixtures rather than making them arguments in the usual way
    # so that we only start the database containers we actually need for the test run
    database = request.getfixturevalue(database_fixture_name)

    return QueryEngineFixture(engine_name, database, query_engine_class)


@pytest.fixture(params=QUERY_ENGINE_NAMES)
def engine(request):
    return engine_factory(request, request.param)


@pytest.fixture
def mssql_engine(request):
    return engine_factory(request, "mssql")


@pytest.fixture
def trino_engine(request):
    return engine_factory(request, "trino")


@pytest.fixture
def in_memory_engine(request):
    return engine_factory(request, "in_memory")


@pytest.fixture
def sqlite_engine(request):
    return engine_factory(request, "sqlite")


@pytest.fixture(scope="session")
def ehrql_image(show_delayed_warning):
    project_dir = Path(ehrql.__file__).parents[1]
    # Note different name from production image to avoid confusion
    image = "ehrql-dev"
    # We're deliberately choosing to shell out to the docker client here rather than use
    # the docker-py library to avoid possible difference in the build process (docker-py
    # doesn't seem to be particularly actively maintained)
    with show_delayed_warning(3, f"Building {image} Docker image"):
        subprocess.run(
            ["docker", "build", project_dir, "-t", image],
            check=True,
            env=dict(os.environ, DOCKER_BUILDKIT="1"),
        )
    return f"{image}:latest"


@pytest.fixture(autouse=True)
def random_should_not_be_used():
    """Asserts that every test should leave the global random number generator unchanged.

    This is because we want all of our use of randomness to be based on seeded random number
    generators, so it should not depend on the global random number generator in any way.
    If this is failing, please find all uses of the random module and replace them with a
    Random instance, ideally from a predictable seed.
    """
    prev_state = random.getstate()
    yield
    assert random.getstate() == prev_state, (
        "Global random number generator was used in test."
    )


@pytest.fixture
def call_cli(capsys):
    """
    Wrapper around the CLI entrypoint to make it easier to call from tests
    """

    def call(*args, environ=None):
        # Convert any Path instances to strings
        args = [str(arg) if isinstance(arg, Path) else arg for arg in args]
        ehrql.__main__.main(args, environ=environ)
        return capsys.readouterr()

    # Allow reading captured output even when call throws an exception
    call.readouterr = capsys.readouterr

    return call


@pytest.fixture
def call_cli_docker(containers, ehrql_image):
    """
    As above, but invoke the CLI via the Docker image
    """

    def call(*args, environ=None, workspace=None):
        args = [
            # Make any paths relative to the workspace directory so they still point to
            # the right place inside Docker. If you supply path arguments and no
            # workspace this will error, as it should. Likewise if you supply paths
            # outside of the workspace.
            str(arg.relative_to(workspace)) if isinstance(arg, Path) else str(arg)
            for arg in args
        ]
        if workspace is not None:
            # Because the files in these directories will need to be readable by
            # low-privilege, isolated processes we can't use the standard restrictive
            # permissions for temporary directories
            workspace.chmod(0o755)
            volumes = {workspace: {"bind": "/workspace", "mode": "rw"}}
        else:
            volumes = {}
        return containers.run_captured(
            ehrql_image,
            command=args,
            volumes=volumes,
            environment=environ or {},
        )

    return call
