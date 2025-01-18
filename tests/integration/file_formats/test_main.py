import contextlib
import datetime
import textwrap

import pytest

from ehrql.file_formats import (
    FILE_FORMATS,
    FileValidationError,
    read_rows,
    read_tables,
    write_rows,
    write_tables,
)
from ehrql.query_model.column_specs import ColumnSpec
from ehrql.sqlalchemy_types import TYPE_MAP
from ehrql.utils.string_utils import strip_indent


TEST_FILE_SPECS = {
    "patient_id": ColumnSpec(int),
    "b": ColumnSpec(bool),
    "i": ColumnSpec(int),
    "f": ColumnSpec(float),
    "s": ColumnSpec(str),
    "c": ColumnSpec(str, categories=("A", "B")),
    "d": ColumnSpec(datetime.date),
}

TEST_FILE_DATA = [
    (123, True, 1, 2.3, "a", "A", datetime.date(2020, 1, 1)),
    (456, False, -5, -0.4, "b", "B", datetime.date(2022, 12, 31)),
    (789, None, None, None, None, None, None),
]


def test_all_types_are_covered_in_test():
    types = [spec.type for spec in TEST_FILE_SPECS.values()]
    assert set(types) == set(TYPE_MAP)


# Generate a test file for each of the file formats we support. This is a session-scoped
# fixture so we generate each file once and then use it across multiple tests.
@pytest.fixture(params=list(FILE_FORMATS.keys()), scope="session")
def test_file(request, tmp_path_factory):
    # We have to use `tmp_path_factory` rather than the usual `tmp_path` because the latter
    # is function-scoped and we need a session-scoped fixture
    tmp_path = tmp_path_factory.mktemp("test_file_formats")
    extension = request.param
    filename = tmp_path / f"dataset{extension}"
    write_rows(filename, TEST_FILE_DATA, TEST_FILE_SPECS)
    yield filename


def test_read_and_write_rows_roundtrip(test_file):
    # Basic test that we can read what we've written
    with read_rows(test_file, TEST_FILE_SPECS) as reader:
        results = list(reader)
    assert results == TEST_FILE_DATA


def test_read_rows_with_a_subset_of_columns(test_file):
    # Read a subset of the original columns and in a different order
    column_specs = {
        "patient_id": ColumnSpec(int),
        "s": ColumnSpec(str),
        "i": ColumnSpec(int),
    }
    with read_rows(test_file, column_specs) as reader:
        results = list(reader)

    original_columns = list(TEST_FILE_SPECS.keys())
    patient_id_index = original_columns.index("patient_id")
    s_index = original_columns.index("s")
    i_index = original_columns.index("i")
    expected = [
        (row[patient_id_index], row[s_index], row[i_index]) for row in TEST_FILE_DATA
    ]

    assert results == expected


def test_read_rows_can_be_iterated_multiple_times(test_file):
    with read_rows(test_file, TEST_FILE_SPECS) as reader:
        # Each time we iterate `reader` we should get the full contents of the file
        results_1 = list(reader)
        results_2 = list(reader)
    assert results_1 == TEST_FILE_DATA
    assert results_2 == TEST_FILE_DATA


def test_read_rows_validates_on_open(test_file):
    # We should get a FileValidationError (because the columns don't match) immediately
    # on opening the file, even if we don't try to read any rows from it
    with pytest.raises(FileValidationError):
        read_rows(test_file, {"wrong_column": ColumnSpec(int)})


def test_read_rows_validates_columns(test_file):
    # Create a copy of the column specs with extra columns
    column_specs = TEST_FILE_SPECS.copy()
    column_specs["extra_column_1"] = ColumnSpec(int)
    column_specs["extra_column_2"] = ColumnSpec(int)

    with pytest.raises(
        FileValidationError,
        match=("Missing columns: extra_column_1, extra_column_2"),
    ):
        read_rows(test_file, column_specs)


def test_read_rows_validates_types(test_file):
    # Create a copy of the column specs with a modified column type
    column_specs = TEST_FILE_SPECS.copy()
    column_specs["s"] = ColumnSpec(int)

    # The errors are different here because with Arrow we can validate the schema but
    # with CSV we can only validate individual values
    errors = {
        "dataset.arrow": "expected <class 'int'>, got string",
        "dataset.csv": "invalid literal for int",
        "dataset.csv.gz": "invalid literal for int",
    }

    with pytest.raises(FileValidationError, match=errors[test_file.name]):
        read_rows(test_file, column_specs)


def test_read_rows_validates_categories(test_file):
    # Create a copy of the column specs with modified column categories
    column_specs = TEST_FILE_SPECS.copy()
    column_specs["c"] = ColumnSpec(str, categories=("X", "Y"))

    # The errors are different here because with Arrow we can validate the categories in
    # the schema but with CSV we can only validate individual values
    errors = {
        "dataset.arrow": strip_indent(
            """
            Unexpected categories in column 'c'
              Categories: A, B
              Expected: X, Y
            """
        ),
        "dataset.csv": "'A' not in valid categories: 'X', 'Y'",
        "dataset.csv.gz": "'A' not in valid categories: 'X', 'Y'",
    }

    with pytest.raises(FileValidationError, match=errors[test_file.name]):
        read_rows(test_file, column_specs)


def test_read_rows_validates_categories_on_non_categorical_column(test_file):
    # This tests that categories are validated even if an original column was not
    # written as categorical. This is relevant if a user provides their own dummy
    # dataset without making the columns categorical. It does not apply to CSV files
    # which have no types at all, let alone categorical types.
    if test_file.name.endswith((".csv", ".csv.gz")):
        pytest.skip("not relevant for CSV files")

    # Create a copy of the column specs with modified column categories
    column_specs = TEST_FILE_SPECS.copy()
    column_specs["s"] = ColumnSpec(str, categories=("X", "Y"))

    error = strip_indent(
        """
        Unexpected categories in column 's'
          Categories: a, b
          Expected: X, Y
        """
    )

    with pytest.raises(FileValidationError, match=error):
        read_rows(test_file, column_specs)


def test_read_rows_accepts_subset_of_expected_categories(test_file):
    # Create a copy of the column specs with an extra category on the categorical column
    # and the categories in a different order
    column_specs = TEST_FILE_SPECS.copy()
    column_specs["c"] = ColumnSpec(str, categories=("C", "B", "A"))

    # Check we can still read it correctly
    reader = read_rows(test_file, column_specs)
    assert list(reader) == TEST_FILE_DATA


def test_read_rows_can_allow_missing_columns(test_file):
    # Create a copy of the column specs with extra columns
    column_specs = TEST_FILE_SPECS.copy()
    column_specs["extra_column_1"] = ColumnSpec(int)

    reader = read_rows(test_file, column_specs, allow_missing_columns=True)
    # Check that there is an extra NULL column in the results
    assert list(reader) == [(*row, None) for row in TEST_FILE_DATA]


def test_rows_reader_identity(test_file):
    reader_1 = read_rows(test_file, TEST_FILE_SPECS)
    reader_2 = read_rows(test_file, TEST_FILE_SPECS)
    reader_3 = read_rows(test_file, {"i": ColumnSpec(int)})
    assert reader_1 == reader_2
    assert hash(reader_1) == hash(reader_2)
    assert reader_1 != reader_3
    # Cover the type-mismatch branch
    assert reader_1 != "foo"


def test_rows_reader_repr(test_file):
    reader = read_rows(test_file, TEST_FILE_SPECS)
    assert repr(test_file) in repr(reader)


@pytest.mark.parametrize("extension", FILE_FORMATS.keys())
def test_read_and_write_tables_roundtrip(tmp_path, extension):
    table_specs = {
        "table_1": TEST_FILE_SPECS,
        "table_2": {
            "patient_id": ColumnSpec(int),
            "s": ColumnSpec(str),
        },
    }
    tables = [
        TEST_FILE_DATA,
        [
            (1, "a"),
            (2, "b"),
            (3, "c"),
        ],
    ]

    write_tables(tmp_path / f"output:{extension[1:]}", tables, table_specs)
    results = read_tables(tmp_path / "output", table_specs)

    assert [list(rows) for rows in results] == tables


def test_read_tables_allows_single_table_format_if_only_one_table(tmp_path):
    filename = tmp_path / "file.csv"
    filename.write_text("i,s\n1,a\n2,b\n3,c\n")
    table_specs = {
        "table_1": {"i": ColumnSpec(int), "s": ColumnSpec(str)},
    }
    results = read_tables(filename, table_specs)
    assert [list(rows) for rows in results] == [
        [(1, "a"), (2, "b"), (3, "c")],
    ]


def test_write_tables_allows_single_table_format_if_only_one_table(tmp_path):
    filename = tmp_path / "file.csv"
    table_specs = {
        "table_1": {"i": ColumnSpec(int), "s": ColumnSpec(str)},
    }
    table_data = [
        [(1, "a"), (2, "b"), (3, "c")],
    ]
    write_tables(filename, table_data, table_specs)
    assert filename.read_text() == "i,s\n1,a\n2,b\n3,c\n"


def test_read_tables_rejects_single_table_format_if_multiple_tables(tmp_path):
    filename = tmp_path / "input.csv"
    filename.touch()
    table_specs = {
        "table_1": {"i": ColumnSpec(int), "s": ColumnSpec(str)},
        "table_2": {"j": ColumnSpec(int), "k": ColumnSpec(float)},
        "table_3": {"l": ColumnSpec(int), "m": ColumnSpec(float)},
    }
    expected_error = textwrap.dedent(
        """\
        Attempting to read 3 tables, but input only provides a single table
              Try moving -> input.csv
                      to -> input/table_1.csv
                  adding -> table_2.csv, table_3.csv
          and using path -> input/
        """
    )
    with contextlib.chdir(tmp_path):
        # Use relative paths to get predictable error message
        relpath = filename.relative_to(tmp_path)
        with pytest.raises(FileValidationError, match=expected_error.rstrip()):
            list(read_tables(relpath, table_specs))


def test_write_tables_rejects_single_table_format_if_multiple_tables(tmp_path):
    filename = tmp_path / "output.csv"
    table_specs = {
        "table_1": {"i": ColumnSpec(int), "s": ColumnSpec(str)},
        "table_2": {"j": ColumnSpec(int), "k": ColumnSpec(float)},
        "table_3": {"l": ColumnSpec(int), "m": ColumnSpec(float)},
    }
    table_data = [[], []]
    expected_error = textwrap.dedent(
        """\
        Attempting to write 3 tables, but output only supports a single table
          Instead of -> output.csv
                 try -> output/:csv
        """
    )
    with contextlib.chdir(tmp_path):
        # Use relative paths to get predictable error message
        relpath = filename.relative_to(tmp_path)
        with pytest.raises(FileValidationError, match=expected_error.rstrip()):
            write_tables(relpath, table_data, table_specs)
