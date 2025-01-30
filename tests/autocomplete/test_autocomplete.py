import ast
import inspect
import re
from enum import Enum
from io import BytesIO
from pathlib import Path
from tokenize import tokenize

import pytest

from ehrql import query_language, tables
from ehrql.query_language import (
    BaseSeries,
    EventSeries,
    PatientSeries,
    days,
    get_tables_from_namespace,
    int_property,
)
from ehrql.tables import core, emis, tpp
from ehrql.utils.module_utils import get_submodules

from .language_server import LanguageServer


# Using the pyright language server to test ehrQL autocompletion
#

# Before we run the tests we first parse the autocomplete_definition.py file
# to pull out:
#   - all statements (either methods or direct attribute references)
#   - all assignments
#   - the expected type for each, parsed from the structured comments
#   - the line number and cursor position to hover to get the expected type

autocomplete_filepath = Path(__file__).with_name("autocomplete_definition.py")
autocomplete_file = autocomplete_filepath.read_text()

# We want to ensure that all lines in the autocomplete file are covered by tests
# so we keep track of those that aren't
autocomplete_uncovered_lines = set(range(0, len(autocomplete_file.split("\n")) + 1))

# Using the tokenize method we can parse all tokens, including comments, to
# find the structured comments containing the expected types. For each we
# record the line number that it occurs on, and the expected type.
expected_types = {}
for token_type, string, start, end, line in tokenize(
    BytesIO(autocomplete_file.encode("utf-8")).readline
):
    if (
        line.strip() == ""
        or line.strip().startswith("#")
        or line.strip().startswith("from")
        or line.strip().startswith("import")
    ):
        # Comments and import statements can be ignored
        autocomplete_uncovered_lines.discard(start[0])
    type_comment = re.search("^## type:(?P<expected_type>.+)$", string)
    if type_comment:
        expected_types[start[0]] = type_comment.group("expected_type").strip()


# Now we use the AST module to walk the trees in the autocomplete file. This
# allows us to:
#   - find all statements and assignments
#   - for all methods find the method name and the calling object
#   - find the line_number and cursor_position for where to hover
#   - find the line_number where we expect to see a structured comment with the
#     expected type
class MyVisitor(ast.NodeVisitor):
    """
    Traverst the AST to find all the method calls along
    with the object they were called from
    """

    def __init__(self):
        self.methods = []
        self.statements = []
        self.attributes = []

    def update_coverage(self, node):
        for line_number in range(node.lineno, node.end_lineno + 1):
            autocomplete_uncovered_lines.discard(line_number)

    def get_expected_type(self, line_number, statement):
        if line_number not in expected_types:  # pragma: no cover
            assert 0, (
                f"Line {line_number} of the autocomplete_definition.py file does not "
                "have an expected type in a structured comment. You need to provide a "
                "comment like `## type:<expected_type>` immediately after the statement.\n"
                "If this is a multi line statement, then put it on the last line. Typically "
                "this will be immediately after the closing ')'.\n"
                "The statement without an expression is:\n\n"
                f"{statement}\n"
            )
        return expected_types[line_number]

    def process_attribute(
        self, node, line_number, expected_type_line, statement, cursor_position
    ):
        attr_name = node.attr
        calling_object = ast.unparse(node.value)

        self.attributes.append((calling_object, attr_name))

        expected_type = self.get_expected_type(expected_type_line, statement)
        self.statements.append((statement, line_number, cursor_position, expected_type))

    def visit_Attribute(self, node):
        # Occurs when a statement is just an attribute call without assignment
        # e.g. patients.core.date_of_birth
        self.update_coverage(node)
        self.process_attribute(
            node,
            node.end_lineno,
            node.end_lineno,
            ast.unparse(node),
            node.end_col_offset,
        )

    def visit(self, node):
        if not isinstance(
            node,
            ast.Module  # always first node, we ignore
            | ast.ImportFrom  # ignore import statements
            | ast.alias  # ignore alias statements
            | ast.Expr  # everything is an expression, we ignore because we are only interested in the expression type
            | ast.Assign  # dealt with by visit_Assign
            | ast.Attribute  # dealt with by visit_Attribute
            | ast.Call,  # dealt with by visit_Call
        ):  # pragma: no cover
            assert 0, (
                f"Line {node.lineno} of autocomplete.definition.py contains an unexpected expression "
                "and so won't be tested. See the comments in that file for what is a valid expression. "
                "If you need to test the expression, then you will need to update this test file. The "
                f"unexpected expression was:\n\n{ast.unparse(node)}\n"
            )
        return super().visit(node)

    def process_function(self, node, statement, cursor_position):
        if not isinstance(node.func, ast.Name):
            # A function with a calling object e.g. patients.age_on()
            method = node.func.attr
            calling_object = ast.unparse(node.func.value)
        else:
            # A function imported directly from a module. So far this only
            # happens for functions defined in the top level of query_language.py
            method = node.func.id
            calling_object = "query_language"

        self.methods.append((calling_object, method))

        expected_type = self.get_expected_type(node.end_lineno, statement)
        line_number = node.func.end_lineno
        self.statements.append((statement, line_number, cursor_position, expected_type))

    def visit_Call(self, node):
        # Occurs when a statement is just a method call without assignment
        # e.g. patients.core.date_of_birth.is_after("2024-01-01")
        self.update_coverage(node)
        self.process_function(node, ast.unparse(node), node.func.end_col_offset)

    def visit_Assign(self, node):
        # Occurs when a statement is an assignment
        # e.g. var_name = patients.core.date_of_birth.is_after("2024-01-01")
        # We process the statement assigned to the variable

        if node.targets[0].id == "date_str":
            # Ignore the line that just defines a variable `date_str`
            self.update_coverage(node)
            return

        if isinstance(node.value, ast.Attribute):  # pragma: no cover
            # Currently we don't actually do this, hence the pragma, but leaving
            # it in so that potential future changes to the autocomplete_definition
            # file can be handled
            self.update_coverage(node)
            self.process_attribute(
                node.value, node.lineno, node.end_lineno, ast.unparse(node), 0
            )
        elif isinstance(node.value, ast.Call):
            self.update_coverage(node)
            self.process_function(node.value, ast.unparse(node), 0)
        else:
            # Sometimes we may want to test autocomplete for something that isn't
            # an attribute or a method call. In which case this is fine with a variable
            # assignment because the autocomplete can come from a hover at cursor
            # position 0 (the start of the variable name)
            self.update_coverage(node)
            statement = ast.unparse(node.value)
            expected_type = self.get_expected_type(node.end_lineno, statement)
            self.statements.append((statement, node.lineno, 0, expected_type))


visitor = MyVisitor()
visitor.visit(ast.parse(autocomplete_file))
autocomplete_file_statements = visitor.statements
autocomplete_file_methods = visitor.methods
autocomplete_file_attributes = visitor.attributes

assert len(autocomplete_uncovered_lines) == 0, (
    "The autocomplete_definition.py contains some lines that aren't covered by the tests:\n"
    f"{autocomplete_uncovered_lines}\n"
    "You have probably added something to it that the AST NodeVisitor isn't expecting."
)


@pytest.fixture(scope="session")
def language_server(tmp_path_factory):
    temp_file_path = tmp_path_factory.mktemp("autoocomplete") / "autocomplete.py"
    return LanguageServer(temp_file_path)


class CompletionItemKind(Enum):
    """
    The different kinds of things the language server protocol supports.
    Currently we only have METHOD, VARIABLE and PROPERTY but the full list is here:
    https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#completionItemKind
    """

    METHOD = 2
    VARIABLE = 6
    PROPERTY = 10


def get_completion_item_kind(table, attr):
    if inspect.ismethod(getattr(table, attr)):
        return CompletionItemKind.METHOD.value
    elif attr in table.__class__.__dict__ and isinstance(
        table.__class__.__dict__[attr], property
    ):
        return CompletionItemKind.PROPERTY.value
    else:
        return CompletionItemKind.VARIABLE.value


# If we create a file once, with many lines of code, which the language
# server can then load and parse, then the autocomplete is a lot quicker
# than continually telling the language server about a line changing.
# Therefore for the parameterized tests, we first populate a file with
# all statements.


all_table_attributes = [
    (module, name, attr, get_completion_item_kind(table, attr))
    for module in get_submodules(tables)
    for name, table in get_tables_from_namespace(module)
    for attr in dir(table)
    if not attr.startswith("_")
]

expected_dropdown_entries = {}
for module, name, attr, completion_item_kind in all_table_attributes:
    table = f"{module.__name__}.{name}"
    if table not in expected_dropdown_entries:
        expected_dropdown_entries[table] = {}
    expected_dropdown_entries[table][attr] = completion_item_kind

import_statements = [f"import {module.__name__}" for module in get_submodules(tables)]


@pytest.fixture(scope="session")
def language_server_preloaded_with_all_table_drop_downs(
    language_server, tmp_path_factory
):
    temp_file_path = tmp_path_factory.mktemp("autoocomplete") / "autocomplete.py"
    content = [f"{table_name}." for table_name, _ in expected_dropdown_entries.items()]
    language_server.open_doc(temp_file_path, "\n".join(import_statements + content))
    return language_server


@pytest.mark.parametrize(
    "line, table_name, expected_values",
    [
        (line, table_name, expected_values)
        for line, (table_name, expected_values) in enumerate(
            expected_dropdown_entries.items()
        )
    ],
)
def test_dropdown_completion_for_all_tables(
    language_server_preloaded_with_all_table_drop_downs,
    line,
    table_name,
    expected_values,
):
    # Check the autocompletion for each core table. I.e.
    # what you get after typing: patients.

    results = language_server_preloaded_with_all_table_drop_downs.get_completion_results_from_file(
        line + len(import_statements), len(table_name) + 1
    )

    actual = {}
    for x in results:
        if not x.get("label").startswith("_"):
            actual[x.get("label")] = x.get("kind")

    assert actual == expected_values


# If we add a new column type that is hard to support autocomplete
# we can add it here
ignored_columns = [
    # ("table_name", "column_name"),
    ("addresses", "imd_decile"),
    ("addresses", "imd_quintile"),
]

all_columns_for_all_tables = [
    (
        f"{module.__name__}.{table_name}.{column_name}",
        module,
        table_name,
        column_name,
        type(getattr(table, column_name)).__name__,
    )
    for module in get_submodules(tables)
    for table_name, table in get_tables_from_namespace(module)
    for column_name in dir(table)
    if isinstance(getattr(table, column_name), BaseSeries)
    and (table_name, column_name) not in ignored_columns
]


@pytest.fixture(scope="session")
def language_server_preloaded_with_all_types(language_server, tmp_path_factory):
    temp_file_path = tmp_path_factory.mktemp("autoocomplete") / "autocomplete.py"
    content = [thing[0] for thing in all_columns_for_all_tables]
    language_server.open_doc(temp_file_path, "\n".join(import_statements + content))
    return language_server


@pytest.mark.parametrize(
    "line, code_string, module, name, column_name, expected_series_type",
    [
        (line, code_string, module, name, column_name, expected_series_type)
        for line, (
            code_string,
            module,
            name,
            column_name,
            expected_series_type,
        ) in enumerate(all_columns_for_all_tables)
    ],
)
def test_types_of_all_series_on_all_tables(
    language_server_preloaded_with_all_types,
    line,
    code_string,
    module,
    name,
    column_name,
    expected_series_type,
):
    # For each Series on each table in each submodule of ehrql.tables we check
    # that the inferred series type on hovering matches the expected series
    result = language_server_preloaded_with_all_types.get_element_type_from_file(
        line + len(import_statements), len(code_string) - 1
    )
    assert expected_series_type == result, (
        f"In {module.__name__}.{name}, the series `{column_name}` should be of type `{expected_series_type}` but the language server thinks it's `{result}`"
    )


@pytest.fixture(scope="session")
def language_server_preloaded_with_autocomplete_defs(language_server, tmp_path_factory):
    temp_file_path = tmp_path_factory.mktemp("autoocomplete") / "autocomplete.py"
    language_server.open_doc(temp_file_path, autocomplete_file)
    return language_server


@pytest.mark.parametrize(
    "statement, line_number, cursor_position, expected_type",
    autocomplete_file_statements,
)
def test_things_in_autocomplete_definition_file(
    language_server_preloaded_with_autocomplete_defs,
    statement,
    line_number,
    cursor_position,
    expected_type,
):
    actual_type = (
        language_server_preloaded_with_autocomplete_defs.get_element_type_from_file(
            line_number - 1, cursor_position
        )
    )
    assert actual_type == expected_type, (
        f"\n\nautocomplete_definition.py, line {line_number}: Expecting {expected_type} (but got {actual_type}) for the statement\n{statement}\n"
    )


def test_all_table_methods():
    all_methods_from_tables = [
        f"{module.__name__}.{table_name}.{method}"
        for module in get_submodules(tables)
        for table_name, table in get_tables_from_namespace(module)
        for method in table.__class__.__dict__
        if callable(getattr(table, method)) and not method.startswith("_")
    ]

    # This is a list of table methods that we currently don't support for autocomplete,
    # or need to ignore
    ignored_table_methods = [
        "ehrql.tables.smoketest.patients.count_for_patient",
        "ehrql.tables.smoketest.patients.exists_for_patient",
        "ehrql.tables.emis.patients.age_on",  # requires DateDifference
        "ehrql.tables.tpp.addresses.for_patient_on",  # Needs last_for_patient
        "ehrql.tables.core.practice_registrations.for_patient_on",  # Needs last_for_patient
        "ehrql.tables.tpp.patients.age_on",  # requires DateDifference
        "ehrql.tables.core.patients.age_on",  # requires DateDifference
        "ehrql.tables.emis.ons_deaths.cause_of_death_is_in",  # need refactor of method
        "ehrql.tables.core.ons_deaths.cause_of_death_is_in",  # need refactor of method
    ]
    tested_table_methods = [
        f"ehrql.tables.{calling_object}.{method}"
        for (calling_object, method) in autocomplete_file_methods
    ]
    missing_methods = [
        method
        for method in all_methods_from_tables
        if method not in ignored_table_methods + tested_table_methods
    ]
    missing_methods_str = "\n  - ".join(missing_methods)
    assert not missing_methods, (
        "\nThe following methods do not have autocomplete tests:\n"
        f"  - {missing_methods_str}\n"
        "You must add them to the `autocomplete_definition.py` file.\n"
        "If we don't support autocomplete (yet) then add them to the "
        "`ignored_table_methods` list in this test file."
    )


@pytest.fixture(scope="session")
def query_language_methods():
    """
    Fixture to extract all methods from the query_language.py file.
    Determines for each method whether it is callable by a PatientSeries
    or an EventSeries or both.

    Currently there is one special case for the decorator @int_property.
    This appears as a method in the below, but is actually an attribute
    after the decorator has done its job. Therefore we deal with them
    separately.
    """
    class_parents = {}
    class_methods = {"object": []}
    class_int_props = {"object": []}
    series_methods = set()
    series_int_props = set()
    other_methods = {}
    ql_classes = inspect.getmembers(query_language, inspect.isclass)
    for class_name, class_obj in ql_classes:
        if class_obj.__module__ != "ehrql.query_language":
            continue
        # Get the base classes using __mro__
        base_classes = [
            base.__name__ for base in class_obj.__mro__ if base.__name__ != class_name
        ]
        class_parents[class_obj] = base_classes

        # Get the methods defined in the class
        methods = [
            method_name
            for method_name, method in vars(class_obj).items()
            if not method_name.startswith("_") and not isinstance(method, int_property)
        ]
        class_methods[class_name] = methods

        # Get the `int_property`s defined in the class
        int_props = [
            method_name
            for method_name, method in vars(class_obj).items()
            if not method_name.startswith("_") and isinstance(method, int_property)
        ]
        class_int_props[class_name] = int_props

    for cls in class_parents:
        if PatientSeries in cls.__mro__:
            for parent in class_parents[cls]:
                series_methods.update(
                    [
                        (parent, method, PatientSeries)
                        for method in class_methods[parent]
                    ]
                )
                series_int_props.update(
                    [
                        (parent, method, PatientSeries)
                        for method in class_int_props[parent]
                    ]
                )
        if EventSeries in cls.__mro__:
            for parent in class_parents[cls]:
                series_methods.update(
                    [(parent, method, EventSeries) for method in class_methods[parent]]
                )
                series_int_props.update(
                    [
                        (parent, method, EventSeries)
                        for method in class_int_props[parent]
                    ]
                )
        if class_methods[cls.__name__]:
            other_methods[cls.__name__] = class_methods[cls.__name__]

    # Currently `other_methods` contains all methods. So we remove the series methods
    # to leave the non-series methods
    for class_name, _, _ in series_methods:
        if class_name in other_methods:
            del other_methods[class_name]

    return (other_methods, series_methods, series_int_props)


def test_all_query_model_series_methods(query_language_methods):
    _, series_methods, _ = query_language_methods
    # This is a list of things we currently don't support for autocomplete.
    ignored_query_language_methods = [
        ("BaseSeries", "map_values", PatientSeries),
        ("BaseSeries", "map_values", EventSeries),
        ("CodeFunctions", "to_category", PatientSeries),
        ("CodeFunctions", "to_category", EventSeries),
        ("MultiCodeStringFunctions", "is_in", PatientSeries),  # need first_for_patient
        (
            "MultiCodeStringFunctions",
            "is_not_in",
            PatientSeries,
        ),  # need first_for_patient
        (
            "MultiCodeStringFunctions",
            "contains",
            PatientSeries,
        ),  # need first_for_patient
        (
            "MultiCodeStringFunctions",
            "contains_any_of",
            PatientSeries,
        ),  # need first_for_patient
    ]

    # To determine which methods are currently tested in the autocomplete_definition file we:
    #   - loop through each method pulled out of the AST walk earlier
    #   - for each method, evaluate the calling object - e.g. for core.patients.date_of_birth.is_after()
    #     the calling object is core.patients.date_of_birth, so we call eval() on the to get
    #     the type instance - in this case an instance of the DatePatientSeries class
    #   - we then loop through the __mro__ of the class of the instance method until we find a
    #     class with that method and assign that classes method as "tested". We stop looking at that
    #     point so that if e.g. A inherites from B, and A overrides the method c() on B, then we'd
    #     probably want to test instance_of_a.c() and instance_of_b.c() separately
    tested_methods = []
    for calling_object, method in autocomplete_file_methods:
        calling_object_instance = eval(
            calling_object,
            {
                # Things imported in the autocomplete_def file, but only present
                # in this file to be used here. We pass them as globals here. If
                # we didn't, and just imported them above, Ruff would complain.
                # This seems like a better compromise than telling Ruff to ignore
                # the unused imports
                "tpp": tpp,
                "core": core,
                "emis": emis,
                "days": days,
                "query_language": query_language,
            },
        )

        if isinstance(calling_object_instance, PatientSeries):
            series_type = PatientSeries
        elif isinstance(calling_object_instance, EventSeries):
            series_type = EventSeries
        else:
            # There are non-Series methods e.g. methods directly on tables such as patients.age_on()
            # and non-Series class methods such as Duration.days(). These are tested separately in
            # other tests
            continue

        for cls in calling_object_instance.__class__.__mro__:  # pragma: no cover
            if (
                cls.__name__,
                method,
                series_type,
            ) in series_methods:
                tested_methods.append((cls.__name__, method, series_type))
                break

    missing_methods = [
        f"{method_name} in {class_name} - called on a {series_type.__name__}"
        for class_name, method_name, series_type in series_methods
        if (class_name, method_name, series_type)
        not in tested_methods + ignored_query_language_methods
    ]
    missing_methods_str = "\n  - ".join(missing_methods)

    assert not missing_methods, (
        "\nThe following methods in query_language.py do not have autocomplete tests:\n"
        f"  - {missing_methods_str}\n"
        "You must add them to the `autocomplete_definition.py` file.\n"
        "If we don't support autocomplete (yet) then add them to the "
        "`ignored_query_language_methods` list in this test file."
    )


def test_all_query_model_non_series_methods(query_language_methods):
    other_methods, _, _ = query_language_methods
    # Whole classes that we want to ignore from autocomplete
    classes_to_ignore = [
        "Dataset",
        "DateDifference",
        "DummyDataConfig",
        "SortedEventFrameMethods",
    ]
    # Specific class methods we want to ignore
    ignored_query_language_methods = [
        ("EventFrame", "sort_by"),
        ("when", "then"),
        ("WhenThen", "otherwise"),
        # Temporarily ignore this while it's non-public
        ("EventTable", "add_column"),
    ]

    # Same logic as in previous test to find methods actually tested in the autocomplete definition file
    tested_methods = []
    for calling_object, method in autocomplete_file_methods:
        calling_object_instance = eval(
            calling_object,
            {
                # Things imported in the autocomplete_def file, but only present
                # in this file to be used here. We pass them as globals here. If
                # we didn't, and just imported them above, Ruff would complain.
                # This seems like a better compromise than telling Ruff to ignore
                # the unused imports
                "tpp": tpp,
                "core": core,
                "emis": emis,
                "days": days,
                "query_language": query_language,
            },
        )
        for cls in calling_object_instance.__class__.__mro__:
            if cls.__name__ in other_methods:
                tested_methods.append((cls.__name__, method))
                break

    missing_methods = [
        f"{method} in {class_name}"
        for class_name, methods in other_methods.items()
        for method in methods
        if (class_name, method) not in tested_methods + ignored_query_language_methods
        and class_name not in classes_to_ignore
    ]
    missing_methods_str = "\n  - ".join(missing_methods)

    assert not missing_methods, (
        "\nThe following methods in query_language.py do not have autocomplete tests:\n"
        f"  - {missing_methods_str}\n"
        "You must add them to the `autocomplete_definition.py` file.\n"
        "If we don't support autocomplete (yet) then add them to the "
        "`ignored_query_language_methods` list in this test file. Alternatively, "
        "to ignore all methods from a class, add the class to the `classes_to_ignore` list."
    )


def test_all_query_model_int_properties(query_language_methods):
    _, _, series_int_props = query_language_methods

    # Currently we test all int_props, but if in the future we don't you'd add
    # them to this list
    ignored_int_props = [
        # ("DateFunctions", "year", PatientSeries),
    ]
    tested_int_props = []
    for calling_object, attribute in autocomplete_file_attributes:
        calling_object_instance = eval(
            calling_object,
            {
                # Things imported in the autocomplete_def file, but only present
                # in this file to be used here. We pass them as globals here. If
                # we didn't, and just imported them above, Ruff would complain.
                # This seems like a better compromise than telling Ruff to ignore
                # the unused imports
                "tpp": tpp,
                "core": core,
                "emis": emis,
                "days": days,
                "query_language": query_language,
            },
        )

        if isinstance(calling_object_instance, PatientSeries):
            series_type = PatientSeries
        elif isinstance(calling_object_instance, EventSeries):
            series_type = EventSeries
        else:
            # There are non-Series attribues e.g. attribues directly on tables such as patients.sex
            # These are tested separately in other tests
            continue

        for cls in calling_object_instance.__class__.__mro__:  # pragma: no cover
            if (
                cls.__name__,
                attribute,
                series_type,
            ) in series_int_props:
                tested_int_props.append((cls.__name__, attribute, series_type))
                break

    missing_int_props = [
        f"{attribute} in {class_name} - called on a {series_type.__name__}"
        for class_name, attribute, series_type in series_int_props
        if (class_name, attribute, series_type)
        not in tested_int_props + ignored_int_props
    ]
    missing_int_props_str = "\n  - ".join(missing_int_props)

    assert not missing_int_props, (
        "\nThe following `int_property`s in query_language.py do not have autocomplete tests:\n"
        f"  - {missing_int_props_str}\n"
        "You must add them to the `autocomplete_definition.py` file.\n"
        "If we don't support autocomplete (yet) then add them to the "
        "`ignored_int_props` list in this test file."
    )
