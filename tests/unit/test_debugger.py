import json
import textwrap
from datetime import date

import pytest

from ehrql import create_dataset, show
from ehrql.debugger import (
    activate_debug_context,
    elements_are_related_series,
    related_patient_columns_to_records,
)
from ehrql.query_engines.in_memory_database import PatientColumn
from ehrql.tables import EventFrame, PatientFrame, Series, table


def date_serializer(obj):
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError("Type not serializable")  # pragma: no cover


def json_render_function(sequence, head=0, tail=0):
    """Render as JSON, useful for testing."""
    return json.dumps(sequence, indent=4, default=date_serializer)


def test_show(capsys):
    expected_output = textwrap.dedent(
        """
        Show line 3:

        """
    ).strip()

    exec(
        textwrap.dedent(
            """
            # line 2
            show("Hello")
            # line 4
            """
        )
    )

    captured = capsys.readouterr()
    assert captured.err.strip().startswith(expected_output), captured.err


def test_show_with_label(capsys):
    expected_output = textwrap.dedent(
        """
        Show line 3: Number

        """
    ).strip()

    exec(
        textwrap.dedent(
            """
            # line 2
            show(14, label="Number")
            # line 4
            """
        )
    )

    captured = capsys.readouterr()
    assert captured.err.strip().startswith(expected_output), captured.err


def test_show_fails_for_non_ehrql_object(dummy_tables_path):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ):
        with pytest.raises(TypeError):
            show("Hello")


def test_related_patient_columns_to_records_full_join():
    c1 = PatientColumn.parse(
        """
        1 | 101
        2 | 102
        4 | 104
        """
    )
    c2 = PatientColumn.parse(
        """
        1 | 201
        2 | 202
        3 | 203
        """
    )
    r = list(related_patient_columns_to_records([c1, c2]))
    r_expected = [
        {"patient_id": 1, "series_1": 101, "series_2": 201},
        {"patient_id": 2, "series_1": 102, "series_2": 202},
        {"patient_id": 3, "series_1": "", "series_2": 203},
        {"patient_id": 4, "series_1": 104, "series_2": ""},
    ]
    assert r == r_expected


@table
class patients(PatientFrame):
    date_of_birth = Series(date)
    date_of_death = Series(date)
    sex = Series(str)


@table
class events(EventFrame):
    date = Series(date)
    code = Series(str)
    test_result = Series(int)


def init_dataset(**kwargs):
    dataset = create_dataset()
    for key, value in kwargs.items():
        setattr(dataset, key, value)
    return dataset


@pytest.fixture(scope="session")
def dummy_tables_path(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("dummy_tables")
    tmp_path.joinpath("patients.csv").write_text(
        textwrap.dedent(
            """\
            patient_id,date_of_birth,date_of_death,sex
            1,1970-01-01,,male
            2,1980-01-01,2020-01-01,female
            """
        )
    )
    tmp_path.joinpath("events.csv").write_text(
        textwrap.dedent(
            """\
            patient_id,date,code,test_result
            1,2010-01-01,abc,32
            1,2020-01-01,def,
            2,2005-01-01,abc,40
            """
        )
    )
    return tmp_path


@pytest.mark.parametrize(
    "expression,contents",
    [
        (
            patients,
            [
                {
                    "patient_id": 1,
                    "date_of_birth": "1970-01-01",
                    "date_of_death": "",
                    "sex": "male",
                },
                {
                    "patient_id": 2,
                    "date_of_birth": "1980-01-01",
                    "date_of_death": "2020-01-01",
                    "sex": "female",
                },
            ],
        ),
        (
            patients.date_of_birth,
            [
                {"patient_id": 1, "value": "1970-01-01"},
                {"patient_id": 2, "value": "1980-01-01"},
            ],
        ),
        (
            init_dataset(
                dob=patients.date_of_birth,
                count=events.count_for_patient(),
                dod=patients.date_of_death,
            ),
            [
                {"patient_id": 1, "dob": "1970-01-01", "count": 2, "dod": ""},
                {
                    "patient_id": 2,
                    "dob": "1980-01-01",
                    "count": 1,
                    "dod": "2020-01-01",
                },
            ],
        ),
    ],
)
def test_activate_debug_context(dummy_tables_path, expression, contents):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ) as ctx:
        assert json.loads(ctx.render(expression)) == contents


@pytest.mark.parametrize(
    "elements,expected",
    [
        ((patients.date_of_birth, patients.sex), True),
        ((events.date, events.code), True),
        ((patients.date_of_birth, events.count_for_patient()), True),
        ((patients, patients.date_of_birth), False),
        ((patients.date_of_birth, events.date), False),
        ((patients.date_of_birth, {"some": "dict"}, patients.sex), False),
    ],
)
def test_elements_are_related_series(elements, expected):
    assert elements_are_related_series(elements) == expected


def test_render_related_patient_series(dummy_tables_path):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ) as ctx:
        rendered = ctx.render(
            patients.date_of_birth,
            patients.sex,
            events.count_for_patient(),
            patients.date_of_death,
        )
    assert json.loads(rendered) == [
        {
            "patient_id": 1,
            "series_1": "1970-01-01",
            "series_2": "male",
            "series_3": 2,
            "series_4": "",
        },
        {
            "patient_id": 2,
            "series_1": "1980-01-01",
            "series_2": "female",
            "series_3": 1,
            "series_4": "2020-01-01",
        },
    ]


def test_render_related_event_series(dummy_tables_path):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ) as ctx:
        rendered = ctx.render(events.date, events.code, events.test_result)
    assert json.loads(rendered) == [
        {
            "patient_id": 1,
            "row_id": 1,
            "series_1": "2010-01-01",
            "series_2": "abc",
            "series_3": 32,
        },
        {
            "patient_id": 1,
            "row_id": 2,
            "series_1": "2020-01-01",
            "series_2": "def",
            "series_3": "",
        },
        {
            "patient_id": 2,
            "row_id": 3,
            "series_1": "2005-01-01",
            "series_2": "abc",
            "series_3": 40,
        },
    ]


def test_render_dataset_event_tables_with_population(dummy_tables_path):
    dataset = create_dataset()
    dataset.define_population(patients.sex == "male")
    dataset.add_event_table("test", date=events.date, code=events.code)
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ) as ctx:
        rendered = ctx.render(dataset.test)
    assert json.loads(rendered) == [
        {
            "patient_id": 1,
            "row_id": 1,
            "date": "2010-01-01",
            "code": "abc",
        },
        {
            "patient_id": 1,
            "row_id": 2,
            "date": "2020-01-01",
            "code": "def",
        },
    ]


def test_render_dataset_event_tables_without_population(dummy_tables_path):
    dataset = create_dataset()
    dataset.add_event_table("test", date=events.date, code=events.code)
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ) as ctx:
        rendered = ctx.render(dataset.test)
    assert json.loads(rendered) == [
        {
            "patient_id": 1,
            "row_id": 1,
            "date": "2010-01-01",
            "code": "abc",
        },
        {
            "patient_id": 1,
            "row_id": 2,
            "date": "2020-01-01",
            "code": "def",
        },
        {
            "patient_id": 2,
            "row_id": 3,
            "date": "2005-01-01",
            "code": "abc",
        },
    ]


def test_render_date_difference(dummy_tables_path):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ) as ctx:
        rendered = ctx.render(patients.date_of_death - events.date)
    assert json.loads(rendered) == [
        {"patient_id": 1, "row_id": 1, "value": ""},
        {"patient_id": 1, "row_id": 2, "value": ""},
        {"patient_id": 2, "row_id": 3, "value": "5478 days"},
    ]


def test_render_related_date_difference_patient_series(dummy_tables_path):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ) as ctx:
        rendered = ctx.render(
            "2024-01-01" - patients.date_of_birth,
            patients.sex,
        )
    assert json.loads(rendered) == [
        {"patient_id": 1, "series_1": "19723 days", "series_2": "male"},
        {"patient_id": 2, "series_1": "16071 days", "series_2": "female"},
    ]


def test_render_related_date_difference_event_series(dummy_tables_path):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ) as ctx:
        rendered = ctx.render(
            events.date - patients.date_of_birth,
            events.code,
        )
    assert json.loads(rendered) == [
        {"patient_id": 1, "row_id": 1, "series_1": "14610 days", "series_2": "abc"},
        {"patient_id": 1, "row_id": 2, "series_1": "18262 days", "series_2": "def"},
        {"patient_id": 2, "row_id": 3, "series_1": "9132 days", "series_2": "abc"},
    ]


@pytest.mark.parametrize(
    "example_input",
    [
        ((patients, patients.date_of_birth)),
        ((patients.date_of_birth, events.date)),
        ((patients.date_of_birth, {"some": "dict"}, patients.sex)),
        ((init_dataset(), patients.date_of_birth, patients.sex)),
    ],
)
def test_show_fails_for_mismatched_inputs(example_input):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ):
        with pytest.raises(TypeError):
            assert show(*example_input)


@pytest.mark.parametrize(
    "example_input",
    [
        ((patients.date_of_birth, events.count_for_patient())),
        ((patients.date_of_birth, patients.sex)),
        ((events.date, events.code)),
        ((patients.date_of_birth, patients.sex == "male")),
        ((events.date, events.code == "123400")),
    ],
)
def test_show_does_not_raise_error_for_series_from_same_domain(
    dummy_tables_path, example_input
):
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path,
        render_function=json_render_function,
    ):
        show(example_input[0], *example_input[1:])


def test_show_not_run_outside_debug_context(capsys):
    expected_output = textwrap.dedent(
        """
        Show line 3:
         - show() ignored because we're not running in debug mode
        """
    ).strip()

    exec(
        textwrap.dedent(
            """
            # line 2
            show(patients.date_of_birth, patients.sex)
            # line 4
            """
        )
    )

    captured = capsys.readouterr()
    assert captured.err.strip() == expected_output, captured.err
