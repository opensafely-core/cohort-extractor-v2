import pytest

from ..tables import e

title = "Including rows"


@pytest.mark.sql_spec
def test_take_with_column(spec_test):
    table_data = {
        e: """
              |  i1 |  b1
            --+-----+-----
            1 | 101 |  T
            1 | 102 |  T
            1 | 103 |
            2 | 201 |  T
            2 | 202 |
            2 | 203 |  F
            3 | 301 |
            3 | 302 |  F
        """,
    }

    spec_test(
        table_data,
        e.take(e.b1).i1.sum_for_patient(),
        {
            1: (101 + 102),
            2: 201,
            3: None,
        },
    )


@pytest.mark.sql_spec
def test_take_with_expr(spec_test):
    table_data = {
        e: """
              |  i1 |  i2
            --+-----+-----
            1 | 101 | 111
            1 | 102 | 112
            1 | 103 | 113
            2 | 201 | 211
            2 | 202 | 212
            2 | 203 | 213
            3 | 301 |
        """,
    }

    spec_test(
        table_data,
        e.take((e.i1 + e.i2) < 413).i1.sum_for_patient(),
        {
            1: (101 + 102 + 103),
            2: 201,
            3: None,
        },
    )
