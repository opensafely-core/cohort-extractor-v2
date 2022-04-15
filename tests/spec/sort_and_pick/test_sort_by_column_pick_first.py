import pytest

from ..tables import e

title = "Picking the first row for each patient"

table_data = {
    e: """
          |  i1
        --+----
        1 | 101
        1 | 102
        1 | 103
        2 | 203
        2 | 202
        2 | 201
        """,
}


@pytest.mark.sql_spec
def test_sort_by_column_pick_first(spec_test):
    spec_test(
        table_data,
        e.sort_by(e.i1).first_for_patient().i1,
        {
            1: 101,
            2: 201,
        },
    )
