from pathlib import Path
from unittest.mock import patch

import hypothesis.strategies as st
import pytest
from hypothesis import given

from ehrql import debugger, quiz, weeks
from ehrql.query_engines.sandbox import SandboxQueryEngine
from ehrql.query_language import Dataset
from ehrql.tables.core import (
    clinical_events,
    medications,
    patients,
    practice_registrations,
)


def get_engine():  # Used for hypothesis test
    path = Path(__file__).parents[1] / "fixtures" / "example-data"
    return SandboxQueryEngine(str(path))


@pytest.fixture
def engine():
    return get_engine()


@pytest.fixture
def mock_questions():
    questions = quiz.Questions()
    questions.engine = get_engine()
    questions[1] = quiz.Question("Create an Empty Dataset.")
    questions[1].expected = Dataset()
    questions[2] = quiz.Question(
        "Get the `sex` column of the `patients` table as a series."
    )
    questions[2].expected = patients.sex
    return questions


def dataset_smoketest(
    index_year: int = 2022,
    min_age: int = 18,
    max_age: int = 80,
    year_of_birth_column: bool = False,
) -> Dataset:
    year_of_birth = patients.date_of_birth.year
    age = index_year - year_of_birth

    dataset = Dataset()
    dataset.define_population((age >= min_age) & (age <= max_age))
    dataset.age = age
    if year_of_birth_column:
        dataset.year_of_birth = patients.date_of_birth.year
    return dataset


def filtered_medications(
    index_year: int = 2023,
    interval_weeks: int = 52,
    codelist: str | list[str] = ["39113611000001102"],
    filter_dates: bool = True,
):
    index_date = f"{index_year}-01-01"
    if isinstance(codelist, str):
        codelist = [codelist]
    f = medications.dmd_code.is_in(codelist)
    if filter_dates:
        f = f & medications.date.is_on_or_between(
            index_date - weeks(interval_weeks), index_date
        )
    filtered = medications.where(f)
    return filtered


# Tests for check_answer


@pytest.mark.parametrize(
    "answer, expected, message",
    [
        (1, Dataset(), "Expected Dataset, got int instead."),
        (patients, Dataset(), "Expected Dataset, got Table instead."),
        (patients.date_of_birth, Dataset(), "Expected Dataset, got Series instead."),
        (Dataset(), patients, "Expected Table, got Dataset instead."),
        (patients, patients.date_of_birth, "Expected Series, got Table instead."),
    ],
)
def test_check_answer_wrong_type_before_evaluation(answer, expected, message):
    msg = quiz.check_answer(engine=None, answer=answer, expected=expected)
    assert msg == message


def test_check_answer_event_frame_not_converted_to_patient_frame(engine):
    # Wrong type after evaluation
    msg = quiz.check_answer(
        engine=engine,
        answer=clinical_events,
        expected=clinical_events.sort_by(clinical_events.date).last_for_patient(),
    )
    assert msg == "Expected PatientTable, got EventTable instead."


@pytest.mark.parametrize(
    "answer, expected",
    [
        (Dataset(), Dataset()),  # Same syntax but different objects
        (dataset_smoketest(), dataset_smoketest()),
        (patients, patients),
        (patients.date_of_birth, patients.date_of_birth),
        (clinical_events, clinical_events),
        (medications.dmd_code, medications.dmd_code),
    ],
)
def test_check_answer_same_syntax_correct(engine, answer, expected):
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert msg == "Correct!"


def test_check_answer_empty_dataset(engine):
    msg = quiz.check_answer(
        engine=engine, answer=Dataset(), expected=dataset_smoketest()
    )
    assert msg == "The dataset is empty."


@pytest.mark.parametrize(
    "order, message",
    [
        ([0, 1], "Missing column(s): year_of_birth."),
        ([1, 0], "Found extra column(s): year_of_birth."),
    ],
)
def test_check_answer_dataset_has_missing_or_extra_column(engine, order, message):
    datasets = [dataset_smoketest(), dataset_smoketest(year_of_birth_column=True)]
    answer, expected = (datasets[i] for i in order)
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert msg == message


def test_check_answer_dataset_typo_in_column_name(engine):
    answer = dataset_smoketest(year_of_birth_column=False)
    answer.yeah_of_birth = patients.date_of_birth.year
    expected = dataset_smoketest(year_of_birth_column=True)
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert (
        msg
        == "Missing column(s): year_of_birth.\nFound extra column(s): yeah_of_birth."
    )


@pytest.mark.parametrize(
    "order, message",
    [
        ([0, 1], "Missing patient(s): 4, 5, 9."),
        ([1, 0], "Found extra patient(s): 4, 5, 9."),
    ],
)
def test_check_answer_dataset_has_missing_or_extra_patients(engine, order, message):
    datasets = [dataset_smoketest(), dataset_smoketest(min_age=0, max_age=100)]
    answer, expected = (datasets[i] for i in order)
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert msg == message


def test_check_answer_dataset_column_has_missing_patients(engine):
    msg = quiz.check_answer(
        engine=engine,
        answer=dataset_smoketest(index_year=2023),
        expected=dataset_smoketest(),
    )
    assert msg == "Incorrect `age` value for patient 1: expected 49, got 50 instead."


@pytest.mark.parametrize(
    "order, message",
    [
        ([0, 1], "Missing patient(s): 7."),
        ([1, 0], "Found extra patient(s): 7."),
    ],
)
def test_check_answer_patient_series_has_missing_or_extra_patients(
    engine, order, message
):
    series = [
        practice_registrations.for_patient_on("2013-12-01").practice_pseudo_id,
        practice_registrations.for_patient_on("2014-01-01").practice_pseudo_id,
    ]
    answer, expected = (series[i] for i in order)
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert msg == message


def test_check_answer_patient_series_has_incorrect_value(engine):
    msg = quiz.check_answer(
        engine=engine,
        answer=patients.age_on("2023-12-31"),
        expected=patients.age_on("2022-12-31"),
    )
    assert msg == "Incorrect value for patient 1: expected 49, got 50 instead."


@pytest.mark.parametrize(
    "order, message",
    [
        ([1, 0], "Missing row(s): 1, 3, 6, 9, 10, 13, 15, 17, 19, 20."),
        ([0, 1], "Found extra row(s): 1, 3, 6, 9, 10, 13, 15, 17, 19, 20."),
    ],
)
def test_check_answer_event_table_has_missing_or_extra_rows(engine, order, message):
    tables = [
        clinical_events,
        clinical_events.where(clinical_events.snomedct_code.is_in(["60621009"])),
    ]
    answer, expected = (tables[i] for i in order)
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert msg == message


@pytest.mark.parametrize(
    "order, message",
    [
        ([1, 0], "Missing row(s): 5, 9."),
        ([0, 1], "Found extra row(s): 5, 9."),
    ],
)
def test_check_answer_event_series_has_missing_or_extra_rows(engine, order, message):
    series = [
        medications.dmd_code,
        medications.where(medications.date.is_on_or_before("2020-12-01")).dmd_code,
    ]
    answer, expected = (series[i] for i in order)
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert msg == message


def test_check_answer_event_series_has_incorrect_value(engine):
    answer = medications.date
    expected = medications.dmd_code
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert (
        msg
        == "Incorrect value for patient 1, row 1: expected 39113611000001102, got 2014-01-11 instead."
    )


def test_check_answer_incorrect_event_selection_for_patient(engine):
    events = clinical_events.where(
        clinical_events.snomedct_code.is_in(["60621009"])
    ).sort_by(clinical_events.date)
    answer = events.first_for_patient()
    expected = events.last_for_patient()
    msg = quiz.check_answer(engine=engine, answer=answer, expected=expected)
    assert (
        msg
        == "Incorrect `numeric_value` value for patient 2: expected 23.1, got 18.4 instead."
    )


def test_check_answer_unidentified_error_shows_fallback_message(engine):
    with patch("ehrql.quiz.check_patient_table_values", return_value=None):
        msg = quiz.check_answer(
            engine, dataset_smoketest(index_year=2024), dataset_smoketest()
        )
        assert msg.startswith("Incorrect answer.\nExpected:")


# Hypothesis tests for error message coverage
# A generated answer should be either correct or gives an informative error
# Generate some answers and assert that the fall-back message is not produced


@given(
    dataset=st.builds(
        dataset_smoketest,
        index_year=...,
        min_age=...,
        max_age=...,
        year_of_birth_column=...,
    )
)
def test_check_answer_dataset_is_either_correct_or_has_informative_error(dataset):
    engine = get_engine()
    msg = quiz.check_answer(engine, dataset, dataset_smoketest())
    assert not msg.startswith("Incorrect answer.\nExpected:")


@given(
    answer=st.builds(
        filtered_medications,
        index_year=st.integers(min_value=1900, max_value=2100),
        interval_weeks=st.integers(min_value=0, max_value=52),
        codelist=st.from_regex(r"[1-9][0-9]{5,17}", fullmatch=True),
        filter_dates=...,
    )
)
def test_check_answer_filtered_medications_is_either_correct_or_has_informative_error(
    answer,
):
    engine = get_engine()
    msg = quiz.check_answer(
        engine,
        answer,
        filtered_medications(),
    )
    assert not msg.startswith("Incorrect answer.\nExpected:")


@pytest.mark.parametrize(
    "answer,message",
    [
        (Dataset(), "Correct!"),
        (..., "Skipped."),
    ],
)
def test_check(answer, message):
    question = quiz.Question("Create an Empty Dataset.", 0)
    question.expected = Dataset()
    assert question.check(answer) == message


def test_summarise_skipped(mock_questions, capfd):
    # This should be the default state if the user did not modify the quiz file
    mock_questions.check(1, ...)
    mock_questions.check(2, ...)
    mock_questions.summarise()
    assert capfd.readouterr().err.rstrip() == "\n".join(
        [
            "Question 1\nSkipped.\n",
            "Question 2\nSkipped.\n",
            "\n\nSummary of your results",
            "Correct: 0",
            "Incorrect: 0",
            "Unanswered: 2",
        ]
    )


def test_summarise_attempted(mock_questions, capfd):
    mock_questions.check(1, Dataset())
    mock_questions.check(2, patients.date_of_birth)
    mock_questions.summarise()

    assert capfd.readouterr().err.rstrip() == (
        "\n".join(
            [
                "Question 1\nCorrect!\n",
                "Question 2\nIncorrect value for patient 1: expected female, got 1973-07-01 instead.\n",
                "\n\nSummary of your results",
                "Correct: 1",
                "Incorrect: 1",
                "Unanswered: 0",
            ]
        )
    )


def test_summarise_blank(mock_questions, capfd):
    # This mocks the case where the user has removed the provided check statements
    mock_questions.summarise()
    assert capfd.readouterr().err.rstrip() == "\n".join(
        [
            "\n\nSummary of your results",
            "Correct: 0",
            "Incorrect: 0",
            "Unanswered: 2",
        ]
    )


def test_questions():
    questions = quiz.Questions()
    questions.set_dummy_tables_path("test_dummy_path")
    questions[1] = quiz.Question("Q1")
    questions[2] = quiz.Question("Q2")
    assert len(list(questions.get_all())) == 2
    assert questions.questions.keys() == {1, 2}
    assert questions[1].prompt == "Q1"
    assert questions[2].engine.dsn.name == "test_dummy_path"


def test_set_dummy_tables_path_in_debug_context():
    with debugger.activate_debug_context(
        dummy_tables_path="foo", render_function=lambda v: v
    ):
        questions = quiz.Questions()
        questions.set_dummy_tables_path("bar")
        assert debugger.DEBUG_QUERY_ENGINE.dsn.name == "bar"
    # This should be unset outside of the context manager
    assert debugger.DEBUG_QUERY_ENGINE is None
