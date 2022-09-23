import gzip

import pytest

from databuilder.column_specs import ColumnSpec
from databuilder.file_formats import write_dataset


@pytest.mark.parametrize("basename", [None, "file.csv", "file.csv.gz"])
def test_write_dataset_csv(tmp_path, capsys, basename):
    if basename is None:
        filename = None
    else:
        filename = tmp_path / "somedir" / basename

    column_specs = {
        "patient_id": ColumnSpec(int),
        "year_of_birth": ColumnSpec(int),
        "sex": ColumnSpec(str),
    }
    results = [
        (123, 1980, "F"),
        (456, None, None),
        (789, 1999, "M"),
    ]

    write_dataset(filename, results, column_specs)

    if basename is None:
        output = capsys.readouterr().out
    elif basename.endswith(".csv.gz"):
        with gzip.open(filename, "rt") as f:
            output = f.read()
    elif basename.endswith(".csv"):
        output = filename.read_text()
    else:
        assert False

    assert output.splitlines() == [
        "patient_id,year_of_birth,sex",
        "123,1980,F",
        "456,,",
        "789,1999,M",
    ]
