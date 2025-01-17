from datetime import datetime

import pytest

from ehrql.file_formats import FILE_FORMATS
from tests.lib.file_utils import read_file_as_dicts
from tests.lib.inspect_utils import function_body_as_string
from tests.lib.tpp_schema import AllowedPatientsWithTypeOneDissent, Patient


@function_body_as_string
def trivial_dataset_definition():
    from ehrql import create_dataset
    from ehrql.tables.tpp import patients

    dataset = create_dataset()
    year = patients.date_of_birth.year
    dataset.define_population(year >= 1940)
    dataset.year = year

    dataset.configure_dummy_data(
        population_size=10,
        additional_population_constraint=patients.date_of_death.is_null(),
    )


@function_body_as_string
def trivial_dataset_definition_legacy_dummy_data():
    from ehrql import create_dataset
    from ehrql.tables.tpp import patients

    dataset = create_dataset()
    year = patients.date_of_birth.year
    dataset.define_population(year >= 1940)
    dataset.year = year

    dataset.configure_dummy_data(population_size=10, legacy=True)


@function_body_as_string
def parameterised_dataset_definition():
    from argparse import ArgumentParser

    from ehrql import create_dataset
    from ehrql.tables.tpp import patients

    parser = ArgumentParser()
    parser.add_argument("--year", type=int)
    args = parser.parse_args()

    dataset = create_dataset()
    year = patients.date_of_birth.year
    dataset.define_population(year >= args.year)
    dataset.year = year


@pytest.mark.parametrize("extension", list(FILE_FORMATS.keys()))
def test_generate_dataset_with_tpp_backend(
    call_cli, tmp_path, mssql_database, extension
):
    mssql_database.setup(
        Patient(Patient_ID=1, DateOfBirth=datetime(1934, 5, 5)),
        AllowedPatientsWithTypeOneDissent(Patient_ID=1),
        Patient(Patient_ID=2, DateOfBirth=datetime(1943, 5, 5)),
        AllowedPatientsWithTypeOneDissent(Patient_ID=2),
        Patient(Patient_ID=3, DateOfBirth=datetime(1999, 5, 5)),
        AllowedPatientsWithTypeOneDissent(Patient_ID=3),
    )

    output_path = tmp_path / f"results.{extension}"
    dataset_definition_path = tmp_path / "dataset_definition.py"
    dataset_definition_path.write_text(trivial_dataset_definition)

    call_cli(
        "generate-dataset",
        dataset_definition_path,
        "--output",
        output_path,
        "--backend",
        "tpp",
        "--dsn",
        mssql_database.host_url(),
    )
    results = read_file_as_dicts(output_path)

    expected = [1943, 1999]
    if extension in (".csv", ".csv.gz"):
        expected = [str(v) for v in expected]

    assert len(results) == len(expected)
    assert {r["year"] for r in results} == set(expected)


def test_parameterised_dataset_definition(call_cli, tmp_path, mssql_database):
    mssql_database.setup(
        Patient(Patient_ID=1, DateOfBirth=datetime(1934, 5, 5)),
        AllowedPatientsWithTypeOneDissent(Patient_ID=1),
        Patient(Patient_ID=2, DateOfBirth=datetime(1943, 5, 5)),
        AllowedPatientsWithTypeOneDissent(Patient_ID=2),
        Patient(Patient_ID=3, DateOfBirth=datetime(1999, 5, 5)),
        AllowedPatientsWithTypeOneDissent(Patient_ID=3),
    )

    output_path = tmp_path / "results.csv"
    dataset_definition_path = tmp_path / "dataset_definition.py"
    dataset_definition_path.write_text(parameterised_dataset_definition)

    call_cli(
        "generate-dataset",
        dataset_definition_path,
        "--output",
        output_path,
        "--backend",
        "tpp",
        "--dsn",
        mssql_database.host_url(),
        "--",
        "--year",
        "1940",
    )
    results = read_file_as_dicts(output_path)

    expected = ["1943", "1999"]

    assert len(results) == len(expected)
    assert {r["year"] for r in results} == set(expected)


def test_parameterised_dataset_definition_with_bad_param(tmp_path, call_cli):
    dataset_definition_path = tmp_path / "dataset_definition.py"
    dataset_definition_path.write_text(parameterised_dataset_definition)

    with pytest.raises(SystemExit):
        call_cli(
            "generate-dataset",
            dataset_definition_path,
            "--",
            "--ear",
            "1940",
        )
    assert (
        "dataset_definition.py: error: unrecognized arguments: --ear 1940"
        in call_cli.readouterr().err
    )


def test_generate_dataset_with_database_error(tmp_path, call_cli, mssql_database):
    mssql_database.setup(
        Patient(Patient_ID=1, DateOfBirth=datetime(1934, 5, 5)),
        AllowedPatientsWithTypeOneDissent(Patient_ID=1),
    )

    @function_body_as_string
    def database_operational_error_dataset_definition():
        from ehrql import create_dataset, years
        from ehrql.tables.core import patients

        dataset = create_dataset()
        dataset.define_population(patients.date_of_birth.year >= 1900)
        dataset.extended_dob = patients.date_of_birth + years(9999)

        dataset.configure_dummy_data(population_size=10)

    # This dataset definition triggers an OperationalError by implementing date
    # arithmetic that results in an out of bounds date (after 9999-12-31)
    dataset_definition_path = tmp_path / "dataset_definition.py"
    dataset_definition_path.write_text(database_operational_error_dataset_definition)

    with pytest.raises(SystemExit) as err:
        call_cli(
            "generate-dataset",
            dataset_definition_path,
            "--backend",
            "tpp",
            "--dsn",
            mssql_database.host_url(),
        )
    assert err.value.code == 5


def test_validate_dummy_data_happy_path(tmp_path, call_cli):
    dummy_data_file = tmp_path / "dummy.csv"
    dummy_data = "patient_id,year\n1,1971\n2,1992"
    dummy_data_file.write_text(dummy_data)

    output_path = tmp_path / "results.csv"
    dataset_definition_path = tmp_path / "dataset_definition.py"
    dataset_definition_path.write_text(trivial_dataset_definition)

    call_cli(
        "generate-dataset",
        dataset_definition_path,
        "--output",
        output_path,
        "--dummy-data-file",
        dummy_data_file,
    )
    results = read_file_as_dicts(output_path)

    assert results == [
        {"patient_id": "1", "year": "1971"},
        {"patient_id": "2", "year": "1992"},
    ]


def test_validate_dummy_data_error_path(tmp_path, call_cli):
    dummy_data_file = tmp_path / "dummy.csv"
    dummy_data = "patient_id,year\n1,1971\n2,foo"
    dummy_data_file.write_text(dummy_data)

    dataset_definition_path = tmp_path / "dataset_definition.py"
    dataset_definition_path.write_text(trivial_dataset_definition)

    with pytest.raises(SystemExit):
        call_cli(
            "generate-dataset",
            dataset_definition_path,
            "--dummy-data-file",
            dummy_data_file,
        )
    assert "invalid literal for int" in call_cli.readouterr().err


@pytest.mark.parametrize(
    "dataset_definition_fixture",
    (
        trivial_dataset_definition,
        trivial_dataset_definition_legacy_dummy_data,
    ),
)
def test_generate_dummy_data(tmp_path, call_cli, dataset_definition_fixture):
    output_path = tmp_path / "results.csv"
    dataset_definition_path = tmp_path / "dataset_definition.py"
    dataset_definition_path.write_text(dataset_definition_fixture)

    call_cli(
        "generate-dataset",
        dataset_definition_path,
        "--output",
        output_path,
    )
    lines = output_path.read_text().splitlines()

    assert lines[0] == "patient_id,year"
    assert len(lines) == 11  # 1 header, 10 rows


def test_generate_dummy_data_with_dummy_tables(tmp_path, call_cli):
    dummy_tables_path = tmp_path / "dummy_tables"
    dummy_tables_path.mkdir()
    dummy_tables_path.joinpath("patients.csv").write_text(
        "patient_id,date_of_birth\n8,1985-10-20\n9,1995-05-10"
    )

    output_path = tmp_path / "results.csv"

    dataset_definition_path = tmp_path / "dataset_definition.py"
    dataset_definition_path.write_text(trivial_dataset_definition)

    call_cli(
        "generate-dataset",
        dataset_definition_path,
        "--output",
        output_path,
        "--dummy-tables",
        dummy_tables_path,
    )
    results = read_file_as_dicts(output_path)

    assert results == [
        {"patient_id": "8", "year": "1985"},
        {"patient_id": "9", "year": "1995"},
    ]


def test_generate_dataset_disallows_reading_file_outside_working_directory(
    tmp_path, monkeypatch, call_cli
):
    csv_file = tmp_path / "file.csv"
    csv_file.write_text("patient_id,i\n1,10\n2,20")

    @function_body_as_string
    def code():
        from ehrql import create_dataset
        from ehrql.tables import PatientFrame, Series, table_from_file

        @table_from_file("<CSV_FILE>")
        class test_table(PatientFrame):
            i = Series(int)

        dataset = create_dataset()
        dataset.define_population(test_table.exists_for_patient())
        dataset.configure_dummy_data(population_size=2)
        dataset.i = test_table.i

    code = code.replace('"<CSV_FILE>"', repr(str(csv_file)))

    dataset_file = tmp_path / "sub_dir" / "dataset_definition.py"
    dataset_file.parent.mkdir(parents=True, exist_ok=True)
    dataset_file.write_text(code)

    monkeypatch.chdir(dataset_file.parent)
    with pytest.raises(Exception) as e:
        call_cli("generate-dataset", dataset_file)
    assert "is not contained within the directory" in str(e.value)


@pytest.mark.parametrize("legacy", [True, False])
def test_generate_dataset_passes_dummy_data_config(call_cli, tmp_path, caplog, legacy):
    @function_body_as_string
    def code():
        from ehrql import create_dataset
        from ehrql.tables.core import patients

        dataset = create_dataset()
        dataset.define_population(patients.exists_for_patient())
        dataset.sex = patients.sex

        dataset.configure_dummy_data(population_size=2, timeout=3, **{})

    code = code.replace("**{}", "legacy=True" if legacy else "")
    dataset_file = tmp_path / "dataset_definition.py"
    dataset_file.write_text(code)

    call_cli(
        "generate-dataset",
        dataset_file,
        "--output",
        tmp_path / "output.csv",
    )

    logs = caplog.text
    assert "Attempting to generate 2 matching patients" in logs
    assert "timeout: 3s" in logs
    if legacy:
        assert "Using legacy dummy data generation" in logs
    else:
        assert "Using next generation dummy data generation" in logs


def test_generate_dataset_with_test_data_file(call_cli, tmp_path):
    @function_body_as_string
    def dataset_definition_with_tests():
        from ehrql import create_dataset
        from ehrql.tables.core import patients

        dataset = create_dataset()
        dataset.define_population(patients.sex == "female")

        test_data = {  # noqa: F841
            1: {
                "patients": {"sex": "male"},
                "expected_in_population": False,
            },
            2: {
                "patients": {"sex": "female"},
                "expected_in_population": True,
                "expected_columns": {},
            },
        }

    test_data_file = tmp_path / "dataset_definition.py"
    test_data_file.write_text(dataset_definition_with_tests)
    output_file = tmp_path / "output.csv"

    captured = call_cli(
        "generate-dataset",
        test_data_file,
        "--output",
        output_file,
        "--test-data-file",
        test_data_file,
    )

    # Check that the assurance tests were invoked
    assert "All OK!" in captured.out
    # Check we also generated some output
    assert len(output_file.read_text()) > 0
