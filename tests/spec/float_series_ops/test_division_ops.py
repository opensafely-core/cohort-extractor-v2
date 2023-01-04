from ..tables import p

title = "Arithmetic division operations"

table_data = {
    p: """
          |  f1   |   f2
        --+-------+--------
        1 | 101.3 |  111.5
        2 |  -1.3 |  111.5
        3 | -10.3 |    1.5
        4 | -10.3 |   -1.5
        5 |       |   -1.5
        """,
}


def test_truedivide(spec_test):
    spec_test(
        table_data,
        p.f1 / p.f2,
        {
            1: 101.3 / 111.5,
            2: -1.3 / 111.5,
            3: -10.3 / 1.5,
            4: -10.3 / -1.5,
            5: None,
        },
    )


def test_truedivide_by_constant(spec_test):
    spec_test(
        table_data,
        p.f1 / 10.0,
        {
            1: 101.3 / 10.0,
            2: -1.3 / 10.0,
            3: -10.3 / 10.0,
            4: -10.3 / 10.0,
            5: None,
        },
    )


def test_rtruedivide_by_constant(spec_test):
    spec_test(
        table_data,
        10.0 / p.f1,
        {
            1: 101.3 / 10.0,
            2: -1.3 / 10.0,
            3: -10.3 / 10.0,
            4: -10.3 / 10.0,
            5: None,
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
            5: None,
        },
    )


def test_floordivide(spec_test):
    spec_test(
        table_data,
        p.f1 // p.f2,
        {
            1: 101.3 // 111.5,
            2: -1.3 // 111.5,
            3: -10.3 // 1.5,
            4: -10.3 // -1.5,
            5: None,
        },
    )


def test_floordivide_by_constant(spec_test):
    spec_test(
        table_data,
        p.f1 // 10.0,
        {
            1: 101.3 // 10,
            2: -1.3 // 10,
            3: -10.3 // 10,
            4: -10.3 // 10,
            5: None,
        },
    )


def test_rfloordivide_by_constant(spec_test):
    spec_test(
        table_data,
        10.0 // p.f1,
        {
            1: 101.3 // 10,
            2: -1.3 // 10,
            3: -10.3 // 10,
            4: -10.3 // 10,
            5: None,
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
            5: None,
        },
    )
