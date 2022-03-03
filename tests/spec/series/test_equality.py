from ..tables import p

table_data = {
    p: """
          |  i1 |  i2
        --+-----+-----
        1 | 101 | 101
        2 | 201 | 202
        3 | 301 |
        4 |     |
        """,
}


def test_equals(spec_test):
    spec_test(
        table_data,
        p.i1 == p.i2,
        {
            1: True,
            2: False,
            3: None,
            4: None,
        },
    )


def test_not_equals(spec_test):
    spec_test(
        table_data,
        p.i1 != p.i2,
        {
            1: False,
            2: True,
            3: None,
            4: None,
        },
    )
