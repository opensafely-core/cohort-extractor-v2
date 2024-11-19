from pathlib import Path
from typing import Any

from ehrql import create_dataset
from ehrql.query_engines.in_memory_database import (
    EventColumn,
    EventTable,
    PatientColumn,
    PatientTable,
)
from ehrql.query_engines.sandbox import EmptyDataset, SandboxQueryEngine
from ehrql.query_language import BaseFrame, BaseSeries, Dataset
from ehrql.tables.core import clinical_events, patients


def check_answer(
    engine: SandboxQueryEngine, answer: Any, expected: Dataset | BaseFrame | BaseSeries
) -> str:
    message = check_type(answer, expected)
    if message:
        return message

    ev_answer = evaluate(engine, answer)
    ev_expected = evaluate(engine, expected)

    message = check_type(ev_answer, ev_expected)
    if message:
        return message

    if ev_answer == ev_expected:
        return "Correct!"

    checks = [
        check_dataset_not_empty,
        check_dataset_columns,
        check_patient_ids,
        check_patient_table_values,
        check_patient_column_values,
        check_event_row_ids,
        check_event_table_values,
        check_event_column_values,
    ]

    for check in checks:
        message = check(ev_answer, ev_expected)
        if message is None:
            continue  # to the next check
        return message
    return "\n".join(
        [
            "Incorrect answer.",
            "Expected:",
            str(ev_expected),
            "Got:",
            str(ev_answer),
        ]
    )


def get_type_name(obj: Any) -> str:
    # Simplify the type name for better error messages
    if isinstance(obj, BaseFrame):
        return "Table"
    elif isinstance(obj, BaseSeries):
        return "Series"
    return type(obj).__name__


def check_type(answer: Any, expected: Any) -> str:
    if not isinstance(answer, type(expected)):
        answer_type_name = get_type_name(answer)
        expected_type_name = get_type_name(expected)

        if answer_type_name == "EmptyDataset":
            return None  # Return a different message for empty datasets
        if answer_type_name != expected_type_name:
            # Only return an error message if it is helpful
            return f"Expected {expected_type_name}, got {answer_type_name} instead."
    return None


def evaluate(
    engine: SandboxQueryEngine, answer: Dataset | BaseFrame | BaseSeries
) -> Any:
    if isinstance(answer, Dataset):
        return engine.evaluate_dataset(answer)
    return engine.evaluate(answer)


def check_dataset_not_empty(ev_answer: Any, ev_expected: Any) -> str | None:
    if isinstance(ev_answer, EmptyDataset):
        if isinstance(ev_expected, EmptyDataset):
            return "Correct!"  # Special case: Not an error
        return "The dataset is empty."
    return None


def check_dataset_columns(ev_answer: Any, ev_expected: Any) -> str | None:
    # Named so because we do not expect PatientTables from Frames to have varying columns
    if isinstance(ev_expected, PatientTable):
        return _check_missing_extra(
            ev_answer, ev_expected, "column", getter=lambda t: t.name_to_col.keys()
        )
    return None


def check_patient_ids(ev_answer: Any, ev_expected: Any) -> str | None:
    def check(_ev_answer, _ev_expected) -> str | None:
        return _check_missing_extra(
            _ev_answer,
            _ev_expected,
            "patient",
            getter=lambda c: c.patients(),
        )

    if isinstance(ev_expected, PatientColumn):
        return check(ev_answer, ev_expected)
    if isinstance(ev_expected, PatientTable):
        return _check_table_then_columns_one_by_one(
            ev_answer,
            ev_expected,
            check,
            column_names=list(ev_expected.name_to_col.keys() - {"patient_id"}),
        )
    return None


def check_patient_table_values(ev_answer: Any, ev_expected: Any) -> str | None:
    if isinstance(ev_expected, PatientTable):
        return _check_columns_one_by_one(
            ev_answer,
            ev_expected,
            check_patient_column_values,
            column_names=list(ev_expected.name_to_col.keys() - {"patient_id"}),
            # Patient ID handled separately
        )
    return None


def check_patient_column_values(
    ev_answer, ev_expected, column_name: str | None = None
) -> str | None:
    if isinstance(ev_expected, PatientColumn):
        column_name = f" `{column_name}` " if column_name else " "
        incorrect = sorted(
            ev_answer.patient_to_value.items() - ev_expected.patient_to_value.items()
        )
        # Last check for Patient Frames/Series; Expect incorrect to be non-empty
        # Only show the first incorrect value
        for k, v in incorrect:  # pragma: no branch
            return f"Incorrect{column_name}value for patient {k}: expected {str(ev_expected[k])}, got {str(v)} instead."
    return None


def check_event_row_ids(ev_answer: Any, ev_expected: Any) -> str | None:
    def check(_ev_answer, _ev_expected) -> str | None:
        return _check_missing_extra(
            _ev_answer,
            _ev_expected,
            "row",
            getter=lambda c: set(row["row_id"] for row in c.to_records()),
        )

    if isinstance(ev_expected, EventColumn):
        return check(ev_answer, ev_expected)
    if isinstance(ev_expected, EventTable):
        return _check_table_then_columns_one_by_one(
            ev_answer,
            ev_expected,
            check,
            column_names=list(
                ev_expected.name_to_col.keys() - {"patient_id", "row_id"}
            ),
        )
    return None


# Cannot find a wrong answer that triggers this, but a wild user answer might
# So still include this check in the list but pragma: no cover it
def check_event_table_values(
    ev_answer: Any, ev_expected: Any
) -> str | None:  # pragma: no cover
    if isinstance(ev_expected, EventTable):
        return _check_columns_one_by_one(
            ev_answer,
            ev_expected,
            check_event_column_values,
            column_names=list(
                ev_expected.name_to_col.keys() - {"patient_id", "row_id"}
            ),
            # Patient ID and Row ID handled separately
        )
    return None


def check_event_column_values(
    ev_answer, ev_expected, column_name: str | None = None
) -> str | None:
    if isinstance(ev_expected, EventColumn):
        column_name = f" `{column_name}` " if column_name else " "
        records_ans = set(tuple(rec.values()) for rec in ev_answer.to_records())
        records_exp = set(tuple(rec.values()) for rec in ev_expected.to_records())
        incorrect = sorted(records_ans - records_exp)
        # Last check for Event Frames/Series; Expect incorrect to be non-empty
        # Only show the first incorrect value
        for p, r, v in incorrect:  # pragma: no branch
            return f"Incorrect{column_name}value for patient {p}, row {r}: expected {str(ev_expected[p][r])}, got {str(v)} instead."
    return None


# Utils functions
def get_items_missing_extra(
    set_answer: set,
    set_expected: set,
    item_name: str,
) -> tuple[str | None, str | None]:
    missing = list(map(str, sorted(set_expected - set_answer)))
    missing = f"Missing {item_name}(s): {', '.join(missing)}." if missing else None
    extra = list(map(str, sorted(set_answer - set_expected)))
    extra = f"Found extra {item_name}(s): {', '.join(extra)}." if extra else None
    return missing, extra


def _check_missing_extra(
    ev_answer: Any,
    ev_expected: Any,
    item_name: str,
    getter: callable,
) -> str | None:
    missing_columns, extra_columns = get_items_missing_extra(
        getter(ev_answer), getter(ev_expected), item_name
    )
    if missing_columns or extra_columns:
        return "\n".join(filter(None, [missing_columns, extra_columns]))
    return None


def _check_columns_one_by_one(
    ev_answer: Any,
    ev_expected: Any,
    check_column: callable,
    column_names: list[str],
) -> str | None:
    for name in column_names:
        msg = check_column(ev_answer[name], ev_expected[name], name)
        if msg is None:
            continue
        return msg


def _check_table_then_columns_one_by_one(
    ev_answer: Any,
    ev_expected: Any,
    check: callable,
    column_names: list[str],
):
    def check_column(col_ans, col_exp, column_name: str | None = None) -> str | None:
        msg = check(col_ans, col_exp)
        if msg:
            return f"Column `{column_name}`:\n" + msg
        return msg

    msg_table = check(ev_answer, ev_expected)
    if msg_table:
        return msg_table
    return _check_columns_one_by_one(
        ev_answer,
        ev_expected,
        check_column,
        column_names=column_names,
    )


class Question:
    def __init__(self, prompt: str, engine: SandboxQueryEngine | None = None):
        self.prompt = prompt
        self.expected = None
        self.engine = engine

    def check(self, answer: Any = ...) -> str:
        engine = self.engine or self.get_engine()
        message = check_answer(engine, answer, self.expected)
        print(message)
        return message

    @staticmethod
    def get_engine() -> SandboxQueryEngine:
        path = Path(__file__).parent / "example-data"
        return SandboxQueryEngine(str(path))


def get_quiz_file_contents() -> str:
    def get_block_for_question(index: int, question: Question) -> str:
        return "\n".join(
            [
                f"# Question {index}: {question.prompt}",
                "answer = ...",
                f"questions[{index}].check(answer)",
            ]
        )

    questions = get_questions(create_engine=False)
    return "\n\n".join(
        [
            "# Welcome to the ehrQL Quiz! \n\n",
            "from ehrql import quiz",
            "from ehrql import create_dataset",
            "from ehrql.query_engines.sandbox import SandboxQueryEngine",
            "questions = quiz.get_questions()",
            *[get_block_for_question(i, qn) for i, qn in questions.items()],
        ]
    )


def write_quiz_file(file_path: str | Path) -> None:
    contents = get_quiz_file_contents()
    with open(file_path, "w") as f:
        f.write(contents)


def get_questions(create_engine: bool = True) -> dict[int, Question]:
    if create_engine:
        engine = Question.get_engine()
    else:
        engine = None

    questions = dict()

    add_question_1(questions, engine)
    add_question_2(questions, engine)
    return questions


# Question contents
def add_question_1(questions: dict, engine: SandboxQueryEngine):
    questions[1] = Question(
        "Add column `age` to the dataset corresponding to the patient's age on January 1, 2024.",
        engine,
    )
    questions[1].expected = create_dataset()
    questions[1].expected.age = patients.age_on("2024-01-01")


def add_question_2(questions: dict, engine: SandboxQueryEngine):
    questions[2] = Question(
        "Filter the clinical events table to only include records with SNOMED code `60621009`.",
        engine,
    )
    questions[2].expected = clinical_events.where(
        clinical_events.snomedct_code.is_in(["60621009"])
    )
