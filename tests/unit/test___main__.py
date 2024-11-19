import textwrap

import pytest

from ehrql.__main__ import (
    ArgumentTypeError,
    DefinitionError,
    FileValidationError,
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


def test_generate_dataset_with_definition_error(capsys, mocker):
    # Verify that the generate_dataset subcommand can be invoked.
    patched = mocker.patch("ehrql.__main__.generate_dataset")
    patched.side_effect = DefinitionError("Not a good dataset definition")
    argv = [
        "generate-dataset",
        DATASET_DEFINITON_PATH,
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "Not a good dataset definition" in captured.err
    assert "Traceback" not in captured.err


def test_generate_dataset_with_validation_error(capsys, mocker):
    # Verify that the generate_dataset subcommand can be invoked.
    patched = mocker.patch("ehrql.__main__.generate_dataset")
    patched.side_effect = FileValidationError("Your file was bad")
    argv = [
        "generate-dataset",
        DATASET_DEFINITON_PATH,
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "Your file was bad" in captured.err
    assert "Traceback" not in captured.err


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


@pytest.mark.parametrize("output_path", ["dummy_data_path", "dummy_data_path:arrow"])
def test_create_dummy_tables(mocker, output_path):
    # Verify that the create_dummy_tables subcommand can be invoked.
    patched = mocker.patch("ehrql.__main__.create_dummy_tables")
    argv = [
        "create-dummy-tables",
        DATASET_DEFINITON_PATH,
        output_path,
    ]
    main(argv)
    patched.assert_called_once()


def test_create_dummy_tables_rejects_unsupported_format(capsys):
    argv = [
        "create-dummy-tables",
        DATASET_DEFINITON_PATH,
        "dummy_data_path:invalid",
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "':invalid' is not a supported format" in captured.err


def test_generate_measures(mocker):
    # Verify that the generate_measures subcommand can be invoked.
    patched = mocker.patch("ehrql.__main__.generate_measures")
    argv = [
        "generate-measures",
        DATASET_DEFINITON_PATH,
    ]
    main(argv)
    patched.assert_called_once()


def test_run_sandbox(mocker, tmp_path):
    # Verify that the runs_sandbox subcommand can be invoked.
    dummy_data_path = tmp_path / "dummy-data"
    dummy_data_path.mkdir()
    patched = mocker.patch("ehrql.sandbox.run")
    argv = [
        "sandbox",
        str(dummy_data_path),
    ]
    main(argv)
    patched.assert_called_once_with(dummy_data_path)


def test_run_quiz_with_file_path(mocker, tmp_path):
    patched = mocker.patch("ehrql.sandbox.run_quiz")
    file_path = tmp_path / "quiz_answers.py"
    open(file_path, "w").close()
    argv = [
        "quiz",
        str(file_path),
    ]
    main(argv)
    patched.assert_called_once_with(file_path)


def test_run_quiz_with_missing_file():
    argv = [
        "quiz",
    ]
    with pytest.raises(SystemExit):
        main(argv)


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


def test_existing_directory_missing_directory(capsys, tmp_path):
    dataset_definition_path = tmp_path / "dataset.py"
    dataset_definition_path.touch()
    argv = [
        "generate-dataset",
        str(dataset_definition_path),
        "--dummy-tables",
        "non-existent-directory",
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "non-existent-directory does not exist" in captured.err


def test_existing_directory_not_a_directory(capsys, tmp_path):
    dataset_definition_path = tmp_path / "dataset.py"
    dataset_definition_path.touch()
    file_path = tmp_path / "not-a-directory.file"
    file_path.touch()
    argv = [
        "generate-dataset",
        str(dataset_definition_path),
        "--dummy-tables",
        str(file_path),
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "not-a-directory.file is not a directory" in captured.err


def test_existing_file_missing_file(capsys, tmp_path):
    dataset_definition_path = tmp_path / "dataset.py"
    dataset_definition_path.touch()
    argv = [
        "generate-dataset",
        str(dataset_definition_path),
        "--dummy-data-file",
        "non-existent-file",
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "non-existent-file does not exist" in captured.err


def test_existing_file_not_a_file(capsys, tmp_path):
    dataset_definition_path = tmp_path / "dataset.py"
    dataset_definition_path.touch()
    directory_path = tmp_path / "not-a-file"
    directory_path.mkdir()
    argv = [
        "generate-dataset",
        str(dataset_definition_path),
        "--dummy-data-file",
        str(directory_path),
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "not-a-file is not a file" in captured.err


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


@pytest.mark.parametrize("alias", ["expectations", "test"])
def test_backend_from_id_special_case_aliases(alias):
    assert backend_from_id(alias) is None


def test_debug(capsys, tmp_path):
    # Verify that the debug subcommand can be invoked.
    definition = textwrap.dedent(
        """\
        from ehrql import create_dataset
        from ehrql.tables.core import patients

        dataset = create_dataset()
        dataset.define_population(patients.date_of_birth.year > 1900)
        """
    )

    definition_path = tmp_path / "debug.py"
    definition_path.write_text(definition)

    dummy_data_path = tmp_path / "dummy-data"
    dummy_data_path.mkdir()
    patients_table = dummy_data_path / "patients.csv"
    patients_table.write_text("patient_id,date_of_birth\n1,2020-10-01")
    argv = [
        "debug",
        str(definition_path),
        "--dummy-tables",
        str(dummy_data_path),
    ]
    main(argv)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_debug_rejects_unknown_display_format(capsys, tmp_path):
    dummy_data_path = tmp_path / "dummy-data"
    dummy_data_path.mkdir()
    argv = [
        "debug",
        DATASET_DEFINITON_PATH,
        "--dummy-tables",
        str(dummy_data_path),
        "--display-format",
        "badformat",
    ]
    with pytest.raises(SystemExit):
        main(argv)
    captured = capsys.readouterr()
    assert "badformat' is not a supported display format" in captured.err
