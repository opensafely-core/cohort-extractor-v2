import dataclasses

from ehrql.main import get_query_engine, open_output_file


@dataclasses.dataclass
class DummyQueryEngine:
    dsn: str
    backend: object
    config: dict


@dataclasses.dataclass
class DefaultQueryEngine:
    dsn: str
    backend: object
    config: dict


@dataclasses.dataclass
class DummyBackend:
    config: dict
    query_engine_class = DummyQueryEngine


def test_get_query_engine_defaults():
    query_engine = get_query_engine(
        dsn=None,
        backend_class=None,
        query_engine_class=None,
        environ={},
        default_query_engine_class=DefaultQueryEngine,
    )
    assert isinstance(query_engine, DefaultQueryEngine)


def test_get_query_engine_with_query_engine():
    query_engine = get_query_engine(
        dsn=None,
        backend_class=None,
        query_engine_class=DummyQueryEngine,
        environ={},
        default_query_engine_class=None,
    )
    assert isinstance(query_engine, DummyQueryEngine)
    assert query_engine.backend is None
    assert query_engine.config == {}


def test_get_query_engine_with_backend():
    query_engine = get_query_engine(
        dsn=None,
        backend_class=DummyBackend,
        query_engine_class=None,
        environ={"foo": "bar"},
        default_query_engine_class=None,
    )
    assert isinstance(query_engine, DummyQueryEngine)
    assert isinstance(query_engine.backend, DummyBackend)
    assert query_engine.config == {"foo": "bar"}
    assert query_engine.backend.config == {"foo": "bar"}


def test_get_query_engine_with_backend_and_query_engine():
    query_engine = get_query_engine(
        dsn=None,
        backend_class=DummyBackend,
        query_engine_class=DefaultQueryEngine,
        environ={},
        default_query_engine_class=None,
    )
    assert isinstance(query_engine, DefaultQueryEngine)
    assert isinstance(query_engine.backend, DummyBackend)
    assert query_engine.config == {}


def test_open_output_file(tmp_path):
    test_file = tmp_path / "testdir" / "file.txt"
    with open_output_file(test_file) as f:
        f.write("hello")
    assert test_file.read_text() == "hello"


def test_open_output_file_with_stdout(capsys):
    with open_output_file(None) as f:
        f.write("hello")
    assert capsys.readouterr().out == "hello"
