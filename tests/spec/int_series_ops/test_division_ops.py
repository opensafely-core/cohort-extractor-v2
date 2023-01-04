from ..tables import p

title = "Arithmetic division operations"

table_data = {
    p: """
          |  i1 |  i2
        --+-----+------
        1 | 101 | 111
        2 |  -1 |   2
        3 |  -4 |   3
        4 |     | 201
        """,
}


def test_truedivide(spec_test):
    spec_test(
        table_data,
        p.i1 / p.i2,
        {
            1: 101 / 111,
            2: -1 / 2,
            3: -4 / 3,
            4: None,
        },
    )


def test_truedivide_by_constant(spec_test):
    spec_test(
        table_data,
        p.i1 / 10,
        {
            1: 101 / 10,
            2: -1 / 10,
            3: -4 / 10,
            4: None,
        },
    )


def test_rtruedivide_by_constant(spec_test):
    spec_test(
        table_data,
        10 / p.i1,
        {
            1: 101 / 10,
            2: -1 / 10,
            3: -4 / 10,
            4: None,
        },
    )


def test_truedivide_by_zero(spec_test):
    spec_test(
        table_data,
        p.i1 / 0,
        {
            1: None,
            2: None,
            3: None,
            4: None,
        },
    )


def test_floordivide(spec_test):
    spec_test(
        table_data,
        p.i1 // p.i2,
        {
            1: 101 // 111,
            2: -1 // 2,
            3: -4 // 3,
            4: None,
        },
    )


def test_floordivide_by_constant(spec_test):
    spec_test(
        table_data,
        p.i1 // 10,
        {
            1: 101 // 10,
            2: -1 // 10,
            3: -4 // 10,
            4: None,
        },
    )


def test_rfloordivide_by_constant(spec_test):
    spec_test(
        table_data,
        10 // p.i1,
        {
            1: 101 // 10,
            2: -1 // 10,
            3: -4 // 10,
            4: None,
        },
    )


def test_floordivide_by_zero(spec_test):
    spec_test(
        table_data,
        p.i1 // 0,
        {
            1: None,
            2: None,
            3: None,
            4: None,
        },
    )
