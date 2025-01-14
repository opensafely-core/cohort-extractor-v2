import re
from enum import Enum
from pathlib import Path

import pytest

from ehrql import tables
from ehrql.query_language import (
    BaseSeries,
    get_tables_from_namespace,
)
from ehrql.query_model.nodes import SelectColumn
from ehrql.tables import core
from ehrql.utils.module_utils import get_submodules

from .language_server import (
    get_completion_results,
    get_element_type,
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


@pytest.mark.parametrize(
    "module, name, column_name, expected_series_type",
    [
        (
            module,
            name,
            column_name,
            type(getattr(table, column_name)).__name__,
        )
        for module in get_submodules(tables)
        for name, table in get_tables_from_namespace(module)
        for column_name in dir(table)
        if isinstance(getattr(table, column_name), BaseSeries)
        and isinstance(getattr(table, column_name)._qm_node, SelectColumn)
    ],
)
def test_types(module, name, column_name, expected_series_type):
    # For each Series on each table in each submodule of ehrql.tables we check
    # that the inferred series type on hovering matches the expected series
    content = f"import {module.__name__}; {module.__name__}.{name}.{column_name}"
    result = get_element_type(content, len(content) - 1)
    assert expected_series_type == result, (
        f"In {module.__name__}.{name}, the series `{column_name}` should be of type `{expected_series_type}` but the language server thinks it's `{result}`"
    )


def get_lines_and_expected_types_from_autocomplete_def_file():
    autocomplete_filepath = Path(__file__).with_name("autocomplete_definition.py")
    with autocomplete_filepath.open("r") as f:
        autocomplete_file = f.read()
    lines = autocomplete_file.split("\n")
    import_statements = []
    lines_with_expected_type = []
    multiline_variable_name = None
    multiline_optional_method = None
    multiline_statement_lines = []
    is_multiline_statement = False
    for idx, line in enumerate(lines):
        line_number = idx + 1
        statement_with_expected_type = re.search(
            "^(?P<statement>.+)  ## type:(?P<expected_type>.+)$", line
        )
        start_of_multiline_statement = re.search(
            "^(?P<var_name>[A-Za-z0-0_]+) = (?P<optional_method>.*)\\($", line
        )
        end_of_multiline_statement = re.search(
            "^\\)  ## type:(?P<expected_type>.+)$", line
        )
        if line.startswith("from") or line.startswith("import"):
            # capture all the import statements
            import_statements.append(line)
        elif (
            line.strip() == ""
            or line.strip().startswith("#")
            or line.strip().startswith("date_str = ")
        ):
            # empty line or comment so ignore
            # also ignore the helper var date_str
            ...
        elif end_of_multiline_statement:
            is_multiline_statement = False
            assert len(multiline_statement_lines) > 0, (
                f"I couldn't parse the multiline variable assigment for variable: {multiline_variable_name}"
            )
            statement = f"{multiline_variable_name}={multiline_optional_method}({''.join(multiline_statement_lines)});{multiline_variable_name}"
            multiline_optional_method = False
            expected_type = end_of_multiline_statement.group("expected_type").strip()
            import_statements_str = ";".join(import_statements)
            statement_with_imports = f"{import_statements_str};{statement}"
            lines_with_expected_type.append(
                (statement_with_imports, statement, line_number, expected_type)
            )
        elif is_multiline_statement:
            multiline_statement_lines.append(line.split("#")[0].strip())
        elif statement_with_expected_type:
            statement = statement_with_expected_type.group("statement").strip()
            expected_type = statement_with_expected_type.group("expected_type").strip()
            import_statements_str = ";".join(import_statements)
            statement_with_imports = (
                f"{import_statements_str};variable={statement};variable"
            )
            lines_with_expected_type.append(
                (statement_with_imports, statement, line_number, expected_type)
            )
        elif start_of_multiline_statement:
            multiline_variable_name = start_of_multiline_statement.group("var_name")
            is_multiline_statement = True
            multiline_statement_lines = []
            multiline_optional_method = start_of_multiline_statement.group(
                "optional_method"
            )
        else:
            assert 0, (
                f"The autocomplete_definition.py file contains an unexpected line: [{line}]\n\n"
                "All lines must either be:\n"
                " - An import statement\n"
                " - A comment\n"
                " - of the format: <expression_to_evaluate> ## type:<expected_type>\n"
            )
    assert not is_multiline_statement, (
        f"There is a multiline variable assignment for {multiline_variable_name}"
    )
    ", which doesn't end. Multiline variable assigments"
    return lines_with_expected_type


@pytest.mark.parametrize(
    "statement, line, line_number, expected_type",
    get_lines_and_expected_types_from_autocomplete_def_file(),
)
def test_things_in_autocomplete_definition_file(
    statement, line, line_number, expected_type
):
    actual_type = get_element_type(statement)
    assert actual_type == expected_type, (
        f"\n\nautocomplete_definition.py, line {line_number}: Expecting {expected_type} (but got {actual_type}) for the statement\n{line}\n"
    )
