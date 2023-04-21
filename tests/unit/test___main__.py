import pytest

from ehrql.__main__ import (
    ArgumentTypeError,
    backend_from_id,
    import_string,
    main,
    query_engine_from_id,
)


# We just need any old existing file with a ".py" extension for testing purposes, its
# contents are immaterial; this one will do
DATASET_DEFINITON_PATH = __file__


def test_no_args(capsys):
    # Verify that when ehrql is called without arguments, help text is shown.
    with pytest.raises(SystemExit):
        main([])
    captured = capsys.readouterr()
    assert "usage: ehrql" in captured.out


def test_generate_dataset(mocker):
    # Verify that the generate_dataset subcommand can be invoked.
    patched = mocker.patch("ehrql.__main__.generate_dataset")
    argv = [
        "generate-dataset",
        DATASET_DEFINITON_PATH,
    ]
    main(argv)
    patched.assert_called_once()


def test_generate_dataset_rejects_unknown_extension(capsys):
    argv = [
        "generate-dataset",
        DATASET_DEFINITON_PATH,
        "--output",
        "out_file.badformat",
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert ".badformat' is not a supported format" in captured.err


def test_dump_dataset_sql(mocker):
    # Verify that the dump_dataset_sql subcommand can be invoked.
    patched = mocker.patch("ehrql.__main__.dump_dataset_sql")
    argv = [
        "dump-dataset-sql",
        "--backend",
        "ehrql.backends.tpp.TPPBackend",
        DATASET_DEFINITON_PATH,
    ]
    main(argv)
    patched.assert_called_once()


def test_create_dummy_tables(mocker):
    # Verify that the create_dummy_tables subcommand can be invoked.
    patched = mocker.patch("ehrql.__main__.create_dummy_tables")
    argv = [
        "create-dummy-tables",
        DATASET_DEFINITON_PATH,
        "dummy_data_path",
    ]
    main(argv)
    patched.assert_called_once()


def test_generate_measures(mocker):
    # Verify that the generate_measures subcommand can be invoked.
    patched = mocker.patch("ehrql.__main__.generate_measures")
    argv = [
        "generate-measures",
        DATASET_DEFINITON_PATH,
    ]
    main(argv)
    patched.assert_called_once()


def test_run_sandbox(mocker):
    # Verify that the runs_sandbox subcommand can be invoked.
    patched = mocker.patch("ehrql.sandbox.run")
    argv = [
        "sandbox",
        "dummy_data_path",
    ]
    main(argv)
    patched.assert_called_once()


def test_existing_python_file_missing_file(capsys, tmp_path):
    # Verify that a helpful message is shown when a command is invoked with a path to a
    # file that should exist but doesn't.
    dataset_definition_path = tmp_path / "dataset.py"
    argv = [
        "generate-dataset",
        str(dataset_definition_path),
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "dataset.py does not exist" in captured.err


def test_existing_python_file_unpythonic_file(capsys, tmp_path):
    # Verify that a helpful message is shown when a command is invoked with a path to a
    # file that should be a Python file but isn't.
    dataset_definition_path = tmp_path / "dataset.cpp"
    dataset_definition_path.touch()
    argv = [
        "generate-dataset",
        str(dataset_definition_path),
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "dataset.cpp is not a Python file" in captured.err


def test_import_string():
    assert import_string("ehrql.__main__.main") is main


def test_import_string_not_a_dotted_path():
    with pytest.raises(ArgumentTypeError, match="must be a full dotted path"):
        import_string("urllib")


def test_import_string_no_such_module():
    with pytest.raises(ArgumentTypeError, match="could not import module"):
        import_string("urllib.this_is_not_a_module.Foo")


def test_import_string_no_such_attribute():
    with pytest.raises(ArgumentTypeError, match="'urllib.parse' has no attribute"):
        import_string("urllib.parse.ThisIsNotAClass")


class DummyQueryEngine:
    def get_results(self):
        raise NotImplementedError()


def test_query_engine_from_id():
    engine_id = f"{DummyQueryEngine.__module__}.{DummyQueryEngine.__name__}"
    assert query_engine_from_id(engine_id) is DummyQueryEngine


def test_query_engine_from_id_missing_alias():
    with pytest.raises(ArgumentTypeError, match="must be one of"):
        query_engine_from_id("missing")


def test_query_engine_from_id_wrong_type():
    with pytest.raises(ArgumentTypeError, match="is not a valid query engine"):
        query_engine_from_id("pathlib.Path")


class DummyBackend:
    def get_table_expression(self):
        raise NotImplementedError()


def test_backend_from_id():
    engine_id = f"{DummyBackend.__module__}.{DummyBackend.__name__}"
    assert backend_from_id(engine_id) is DummyBackend


def test_backend_from_id_missing_alias():
    with pytest.raises(ArgumentTypeError, match="must be one of"):
        backend_from_id("missing")


def test_backend_from_id_wrong_type():
    with pytest.raises(ArgumentTypeError, match="is not a valid backend"):
        backend_from_id("pathlib.Path")
