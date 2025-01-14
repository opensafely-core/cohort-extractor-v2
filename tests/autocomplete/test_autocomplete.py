from enum import Enum

import pytest

from ehrql.query_language import get_tables_from_namespace
from ehrql.tables import core

from .language_server import (
    get_completion_results,
    initialize,
)


# Using the pyright language server to test ehrQL autocompletion
#


TESTED_CORE_TABLES = set()


@pytest.fixture(scope="module", autouse=True)
def launch_language_server(tmp_path_factory):
    temp_file_path = tmp_path_factory.mktemp("autoocomplete") / "autocomplete.py"
    initialize(temp_file_path)


class CompletionItemKind(Enum):
    """
    The different kinds of things the language server protocol supports.
    Currently we only have METHOD and VARIABLE but the full list is here:
    https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#completionItemKind
    """

    METHOD = 2
    VARIABLE = 6


base_frame_values = {
    "count_for_patient": CompletionItemKind.METHOD.value,
    "exists_for_patient": CompletionItemKind.METHOD.value,
}

event_frame_values = {
    **base_frame_values,
    "except_where": CompletionItemKind.METHOD.value,
    "sort_by": CompletionItemKind.METHOD.value,
    "where": CompletionItemKind.METHOD.value,
}


@pytest.mark.parametrize(
    "table, expected_values",
    [
        (
            core.patients,
            {
                **base_frame_values,
                "age_on": CompletionItemKind.METHOD.value,
                "date_of_birth": CompletionItemKind.VARIABLE.value,
                "date_of_death": CompletionItemKind.VARIABLE.value,
                "is_alive_on": CompletionItemKind.METHOD.value,
                "is_dead_on": CompletionItemKind.METHOD.value,
                "sex": CompletionItemKind.VARIABLE.value,
            },
        ),
        (
            core.clinical_events,
            {
                **event_frame_values,
                "date": CompletionItemKind.VARIABLE.value,
                "numeric_value": CompletionItemKind.VARIABLE.value,
                "snomedct_code": CompletionItemKind.VARIABLE.value,
            },
        ),
        (
            core.practice_registrations,
            {
                **event_frame_values,
                "end_date": CompletionItemKind.VARIABLE.value,
                "exists_for_patient_on": CompletionItemKind.METHOD.value,
                "for_patient_on": CompletionItemKind.METHOD.value,
                "practice_pseudo_id": CompletionItemKind.VARIABLE.value,
                "spanning": CompletionItemKind.METHOD.value,
                "start_date": CompletionItemKind.VARIABLE.value,
            },
        ),
        (
            core.ons_deaths,
            {
                **base_frame_values,
                "cause_of_death_01": CompletionItemKind.VARIABLE.value,
                "cause_of_death_02": CompletionItemKind.VARIABLE.value,
                "cause_of_death_03": CompletionItemKind.VARIABLE.value,
                "cause_of_death_04": CompletionItemKind.VARIABLE.value,
                "cause_of_death_05": CompletionItemKind.VARIABLE.value,
                "cause_of_death_06": CompletionItemKind.VARIABLE.value,
                "cause_of_death_07": CompletionItemKind.VARIABLE.value,
                "cause_of_death_08": CompletionItemKind.VARIABLE.value,
                "cause_of_death_09": CompletionItemKind.VARIABLE.value,
                "cause_of_death_10": CompletionItemKind.VARIABLE.value,
                "cause_of_death_11": CompletionItemKind.VARIABLE.value,
                "cause_of_death_12": CompletionItemKind.VARIABLE.value,
                "cause_of_death_13": CompletionItemKind.VARIABLE.value,
                "cause_of_death_14": CompletionItemKind.VARIABLE.value,
                "cause_of_death_15": CompletionItemKind.VARIABLE.value,
                "cause_of_death_is_in": CompletionItemKind.METHOD.value,
                "date": CompletionItemKind.VARIABLE.value,
                "underlying_cause_of_death": CompletionItemKind.VARIABLE.value,
            },
        ),
        (
            core.medications,
            {
                **event_frame_values,
                "date": CompletionItemKind.VARIABLE.value,
                "dmd_code": CompletionItemKind.VARIABLE.value,
            },
        ),
    ],
)
def test_core_tables(table, expected_values):
    # Check the autocompletion for each core table. I.e.
    # what you get after typing: patients.
    TESTED_CORE_TABLES.add(table)

    table_name = f"ehrql.tables.core.{table.__class__.__name__}"

    results = get_completion_results(f"import ehrql.tables.core; {table_name}.")

    actual = {}
    for x in results:
        if not x.get("label").startswith("_"):
            actual[x.get("label")] = x.get("kind")

    assert actual == expected_values


def test_core_table_tests_are_exhaustive():
    # Checking that the test_core_tables test tests all current core tables
    missing = [
        name
        for name, table in get_tables_from_namespace(core)
        if table not in TESTED_CORE_TABLES
    ]

    assert not missing, f"No tests for core tables: {', '.join(missing)}"
