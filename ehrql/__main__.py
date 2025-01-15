import importlib
import logging
import os
import sys
import traceback
import warnings
from argparse import ArgumentParser, ArgumentTypeError, RawTextHelpFormatter
from pathlib import Path

from ehrql import __version__
from ehrql.file_formats import (
    FILE_FORMATS,
    FileValidationError,
    get_file_extension,
    split_directory_and_extension,
)
from ehrql.loaders import DEFINITION_LOADERS, DefinitionError
from ehrql.renderers import DISPLAY_RENDERERS
from ehrql.utils.string_utils import strip_indent

from .main import (
    assure,
    create_dummy_tables,
    debug_dataset_definition,
    dump_dataset_sql,
    dump_example_data,
    generate_dataset,
    generate_measures,
    graph_query,
    run_isolation_report,
    serialize_definition,
    test_connection,
)


QUERY_ENGINE_ALIASES = {
    "mssql": "ehrql.query_engines.mssql.MSSQLQueryEngine",
    "sqlite": "ehrql.query_engines.sqlite.SQLiteQueryEngine",
    "localfile": "ehrql.query_engines.local_file.LocalFileQueryEngine",
    "trino": "ehrql.query_engines.trino.TrinoQueryEngine",
    # Kept as an alias for backwards compatibility
    "csv": "ehrql.query_engines.local_file.LocalFileQueryEngine",
}


BACKEND_ALIASES = {
    "emis": "ehrql.backends.emis.EMISBackend",
    "tpp": "ehrql.backends.tpp.TPPBackend",
}


# I haven't yet come up with a good way to expose these in the CLI help text, so for now
# they only appear in the HTML docs. But it makes sense to define the text here where
# the rest of the CLI help text is defined.
USER_ARGS_NAME = "PARAMETERS"
USER_ARGS_USAGE = " -- ... PARAMETERS ..."
USER_ARGS_HELP = """\
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.
"""


if sys.flags.hash_randomization:  # pragma: no cover
    # The kinds of DoS attacks hash seed randomisation is designed to protect against
    # don't apply to ehrQL, and we want consistent set iteration orders so as to keep
    # tests deterministic and generate stable SQL output.
    warnings.warn(
        "Hash randomization is enabled so output may not be consistent with what ehrQL"
        " generates elsewhere. Set the environment variable `PYTHONHASHSEED=0` before"
        " Python starts to disable randomization."
    )


def entrypoint():
    # This is covered by tests but because they're executed via Docker and `subprocess`
    # they're not recorded for coverage
    return main(sys.argv[1:], environ=os.environ)  # pragma: no cover


def main(args, environ=None):
    environ = environ or {}

    # We allow users to pass arbitrary arguments to dataset definition modules, but they
    # must be seperated from any ehrql arguments by the string `--`
    if "--" in args:
        user_args = args[args.index("--") + 1 :]
        args = args[: args.index("--")]
    else:
        user_args = []

    parser = create_parser(user_args, environ)

    kwargs = vars(parser.parse_args(args))
    function = kwargs.pop("function")

    # Set log level to INFO, if it isn't lower already
    root_logger = logging.getLogger()
    orig_log_level = root_logger.level
    root_logger.setLevel(min(orig_log_level, logging.INFO))

    # We try to catch as many errors as possible during argument parsing but there are
    # certain classes of error that will only occur at runtime
    try:
        function(**kwargs)
    except DefinitionError as exc:
        # Errors from definition files are already pre-formatted so we just write them
        # directly to stderr and exit
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except FileValidationError as exc:
        # Handle errors encountered while reading user-supplied data
        print(f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # For functions which take a `backend_class` give that class the chance to set
        # the appropriate exit status for any errors
        if backend_class := kwargs.get("backend_class"):
            if exit_status := backend_class(environ).get_exit_status_for_exception(
                exc
            ):  # pragma: no branch
                # log the traceback to stderr to aid debugging
                traceback.print_exc()
                sys.exit(exit_status)
        raise
    finally:
        root_logger.setLevel(orig_log_level)


def create_parser(user_args, environ):
    parser = ArgumentParser(
        prog="ehrql",
        description=strip_indent(
            """
            The command line interface for ehrQL, a query language for electronic health
            record (EHR) data.
            """
        ),
        formatter_class=RawTextHelpFormatter,
    )

    def show_help(**kwargs):
        parser.print_help()
        parser.exit()

    parser.set_defaults(function=show_help)
    parser.add_argument(
        "--version",
        action="version",
        version=f"ehrql {__version__}",
        help="Show the exact version of ehrQL in use and then exit.",
    )

    subparsers = parser.add_subparsers(help="Name of the sub-command to execute.")
    add_generate_dataset(subparsers, environ, user_args)
    add_generate_measures(subparsers, environ, user_args)
    add_dump_example_data(subparsers, environ, user_args)
    add_dump_dataset_sql(subparsers, environ, user_args)
    add_create_dummy_tables(subparsers, environ, user_args)
    add_assure(subparsers, environ, user_args)
    add_test_connection(subparsers, environ, user_args)
    add_serialize_definition(subparsers, environ, user_args)
    add_isolation_report(subparsers, environ, user_args)
    add_graph_query(subparsers, environ, user_args)
    add_debug_dataset_definition(subparsers, environ, user_args)

    return parser


def add_generate_dataset(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "generate-dataset",
        help=strip_indent(
            """
        Take a dataset definition file and output a dataset.

        ehrQL is designed so that exactly the same command can be used to output a dummy
        dataset when run on your own computer and then output a real dataset when run
        inside the secure environment as part of an OpenSAFELY pipeline.
        """
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=generate_dataset)
    parser.set_defaults(environ=environ)
    parser.set_defaults(user_args=user_args)
    parser.add_argument(
        "--output",
        help=strip_indent(
            f"""
            Path of the file where the dataset will be written (console by default).

            The file extension determines the file format used. Supported formats are:
            {backtick_join(FILE_FORMATS)}
            """
        ),
        type=valid_output_path,
        dest="output_file",
    )
    parser.add_argument(
        "--test-data-file",
        help=strip_indent(
            """
            Takes a test dataset definition file.
            """
        ),
        type=existing_file,
    )
    parser.add_argument(
        "--dummy-data-file",
        help=strip_indent(
            """
            Path to a dummy dataset.

            This allows you to take complete control of the dummy dataset. ehrQL
            will ensure that the column names, types and categorical values match what
            they will be in the real dataset, but does no further validation.

            Note that the dummy dataset doesn't need to be of the same type as the
            real dataset (e.g. you can use a `.csv` file here to produce a `.arrow`
            file).

            This argument is ignored when running against real tables.
            """
        ),
        type=existing_file,
    )
    add_dummy_tables_argument(parser, environ)
    add_dataset_definition_file_argument(parser, environ)
    internal_args = create_internal_argument_group(parser, environ)
    add_dsn_argument(internal_args, environ)
    add_query_engine_argument(internal_args, environ)
    add_backend_argument(internal_args, environ)


def add_dump_dataset_sql(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "dump-dataset-sql",
        help=strip_indent(
            """
            Output the SQL that would be executed to fetch the results of the dataset
            definition.

            By default, this command will output SQL suitable for the SQLite database.
            To get the SQL as it would be run against the real tables you will to supply
            the appropriate `--backend` argument, for example `--backend tpp`.

            Note that due to configuration differences this may not always exactly match
            what gets run against the real tables.
            """
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=dump_dataset_sql)
    parser.set_defaults(environ=environ)
    parser.set_defaults(user_args=user_args)
    parser.add_argument(
        "--output",
        help="SQL output file (outputs to console by default).",
        type=Path,
        dest="output_file",
    )
    add_dataset_definition_file_argument(parser, environ)
    add_query_engine_argument(parser, environ)
    add_backend_argument(parser, environ)


def add_create_dummy_tables(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "create-dummy-tables",
        help=strip_indent(
            """
            Generate dummy tables and write them out as files – one per table, CSV by
            default.

            This command generates the same dummy tables that the `generate-dataset`
            command would generate, but instead of using them to produce a dummy
            dataset, it writes them out as individual files.

            The directory containing these files can then be used as the
            [`--dummy-tables`](#generate-dataset.dummy-tables) argument to
            `generate-dataset` to produce the dummy dataset.

            The files can be edited in any way you wish, giving you full control over
            the dummy tables.
            """
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=create_dummy_tables)
    parser.set_defaults(user_args=user_args)
    parser.set_defaults(environ=environ)
    add_dataset_definition_file_argument(parser, environ)
    parser.add_argument(
        "dummy_tables_path",
        help=strip_indent(
            f"""
            Path to directory where files (one per table) will be written.

            By default these will be CSV files. To generate files in other formats add
            `:<format>` to the directory name e.g.
            {backtick_join("my_outputs" + format_directory_extension(e) for e in FILE_FORMATS)}
            """
        ),
        type=valid_output_directory_with_csv_default,
    )


def add_generate_measures(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "generate-measures",
        help="Take a measures definition file and output measures.",
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=generate_measures)
    parser.set_defaults(environ=environ)
    parser.set_defaults(user_args=user_args)
    parser.add_argument(
        "--output",
        help=strip_indent(
            f"""
            Path of the file where the measures will be written (console by default),
            supported formats: {backtick_join(FILE_FORMATS)}
            """
        ),
        type=valid_output_path,
        dest="output_file",
    )
    parser.add_argument(
        "--dummy-data-file",
        help=strip_indent(
            """
            Path to dummy measures output.

            This allows you to take complete control of the dummy measures output. ehrQL
            will ensure that the column names, types and categorical values match what
            they will be in the real measures output, but does no further validation.

            Note that the dummy measures output doesn't need to be of the same type as the
            real measures output (e.g. you can use a `.csv` file here to produce a `.arrow`
            file).

            This argument is ignored when running against real tables.
            """
        ),
        type=existing_file,
    )
    add_dummy_tables_argument(parser, environ)
    parser.add_argument(
        "definition_file",
        help="Path of the Python file where measures are defined.",
        type=existing_python_file,
    )
    internal_args = create_internal_argument_group(parser, environ)
    add_dsn_argument(internal_args, environ)
    add_query_engine_argument(internal_args, environ)
    add_backend_argument(internal_args, environ)


def add_debug_dataset_definition(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "debug",
        help=strip_indent(
            """
            Internal command for getting debugging information from a dataset
            definition; used by the [OpenSAFELY VSCode extension][opensafely-vscode].

            Note that **this in an internal command** and not intended for end users.

            [opensafely-vscode]: https://marketplace.visualstudio.com/items?itemName=bennettoxford.opensafely
            """
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=debug_dataset_definition)
    parser.set_defaults(environ=environ)
    parser.set_defaults(user_args=user_args)
    add_dataset_definition_file_argument(parser, environ)

    parser.add_argument(
        "--dummy-tables",
        help=strip_indent(
            f"""
            Path to directory of files (one per table) to use as dummy tables
            (see [`create-dummy-tables`](#create-dummy-tables)).

            Files may be in any supported format: {backtick_join(FILE_FORMATS)}
            """
        ),
        type=existing_directory,
        dest="dummy_tables_path",
    )

    add_display_renderer_argument(parser, environ)


def add_assure(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "assure",
        help=strip_indent(
            """
            Command for running assurance tests.
            """
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=assure)
    parser.set_defaults(environ=environ)
    parser.set_defaults(user_args=user_args)
    parser.add_argument(
        "test_data_file",
        help="Path of the file where the test data is defined.",
        type=existing_python_file,
    )


def add_test_connection(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "test-connection",
        help=strip_indent(
            """
            Internal command for testing the database connection configuration.

            Note that **this in an internal command** and not intended for end users.
            """
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=test_connection)
    parser.set_defaults(environ=environ)
    parser.add_argument(
        "--backend",
        "-b",
        help=(
            f"Dotted import path to Backend class, or one of: "
            f"{backtick_join(BACKEND_ALIASES)}"
        ),
        type=backend_from_id,
        default=environ.get("BACKEND", environ.get("OPENSAFELY_BACKEND")),
        dest="backend_class",
    )
    parser.add_argument(
        "--url",
        "-u",
        help="Database connection string.",
        default=environ.get("DATABASE_URL"),
    )


def add_dump_example_data(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "dump-example-data",
        help="Dump example data for the ehrQL tutorial to the current directory.",
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=dump_example_data)
    parser.set_defaults(environ=environ)


def add_serialize_definition(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "serialize-definition",
        help=strip_indent(
            """
            Internal command for serializing a definition file to a JSON representation.

            Note that **this in an internal command** and not intended for end users.
            """
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=serialize_definition)
    parser.set_defaults(environ=environ)
    parser.set_defaults(user_args=user_args)

    parser.add_argument(
        "-t",
        "--definition-type",
        type=str,
        choices=DEFINITION_LOADERS.keys(),
        default="dataset",
        help=f"Options: {backtick_join(DEFINITION_LOADERS.keys())}",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=strip_indent("Output file path (stdout by default)"),
        type=Path,
        dest="output_file",
    )
    parser.add_argument(
        "definition_file",
        help="Definition file path",
        type=existing_python_file,
        metavar="definition_file",
    )
    add_dummy_tables_argument(parser, environ)
    add_display_renderer_argument(parser, environ)


def add_isolation_report(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "isolation-report",
        help=strip_indent(
            """
            Internal command for testing code isolation support.

            Note that **this in an internal command** and not intended for end users.
            """
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.set_defaults(function=run_isolation_report)


def add_graph_query(subparsers, environ, user_args):
    parser = subparsers.add_parser(
        "graph-query",
        help="Output the dataset definition's query graph",
    )
    parser.set_defaults(function=graph_query)
    parser.set_defaults(environ=environ)
    parser.set_defaults(user_args=user_args)
    parser.add_argument(
        "--output",
        help="SVG output file.",
        type=Path,
        dest="output_file",
        required=True,
    )
    add_dataset_definition_file_argument(parser, environ)


def create_internal_argument_group(parser, environ):
    return parser.add_argument_group(
        title="Internal Arguments",
        description=strip_indent(
            """
            You should not normally need to use these arguments: they are for the
            internal operation of ehrQL and the OpenSAFELY platform.
            """
        ),
    )


def add_dataset_definition_file_argument(parser, environ):
    parser.add_argument(
        "definition_file",
        help="Path of the Python file where the dataset is defined.",
        type=existing_python_file,
        metavar="dataset_definition",
    )


def add_dsn_argument(parser, environ):
    parser.add_argument(
        "--dsn",
        help=strip_indent(
            """
            Data Source Name: URL of remote database, or path to data on disk
            (defaults to value of DATABASE_URL environment variable).
            """
        ),
        type=str,
        default=environ.get("DATABASE_URL"),
    )


def add_dummy_tables_argument(parser, environ):
    parser.add_argument(
        "--dummy-tables",
        help=strip_indent(
            f"""
            Path to directory of files (one per table) to use as dummy tables
            (see [`create-dummy-tables`](#create-dummy-tables)).

            Files may be in any supported format: {backtick_join(FILE_FORMATS)}

            This argument is ignored when running against real tables.
            """
        ),
        type=existing_directory,
        dest="dummy_tables_path",
    )


def add_query_engine_argument(parser, environ):
    parser.add_argument(
        "--query-engine",
        type=query_engine_from_id,
        help=(
            f"Dotted import path to Query Engine class, or one of: "
            f"{backtick_join(QUERY_ENGINE_ALIASES)}"
        ),
        default=environ.get("OPENSAFELY_QUERY_ENGINE"),
        dest="query_engine_class",
    )


def add_backend_argument(parser, environ):
    parser.add_argument(
        "--backend",
        type=backend_from_id,
        help=(
            f"Dotted import path to Backend class, or one of: "
            f"{backtick_join(BACKEND_ALIASES)}"
        ),
        default=environ.get("OPENSAFELY_BACKEND"),
        dest="backend_class",
    )


def add_display_renderer_argument(parser, environ):
    parser.add_argument(
        "--display-format",
        help=strip_indent(
            """
            Render format for debug command, default ascii
            """
        ),
        dest="render_format",
        default="ascii",
        type=renderer,
    )


def renderer(value):
    if value not in DISPLAY_RENDERERS:
        raise ArgumentTypeError(
            f"'{value}' is not a supported display format, "
            f"must be one of: "
            f"{backtick_join((renderer_format) for renderer_format in DISPLAY_RENDERERS)}"
        )
    return value


def existing_file(value):
    path = Path(value)
    if not path.exists():
        raise ArgumentTypeError(f"{value} does not exist")
    if not path.is_file():
        raise ArgumentTypeError(f"{value} is not a file")
    return path


def existing_directory(value):
    path = Path(value)
    if not path.exists():
        raise ArgumentTypeError(f"{value} does not exist")
    if not path.is_dir():
        raise ArgumentTypeError(f"{value} is not a directory")
    return path


def existing_python_file(value):
    path = Path(value)
    if not path.exists():
        raise ArgumentTypeError(f"{value} does not exist")
    if not path.suffix == ".py":
        raise ArgumentTypeError(f"{value} is not a Python file")
    return path


def valid_output_path(value):
    path = Path(value)
    extension = get_file_extension(path)
    if extension not in FILE_FORMATS:
        raise ArgumentTypeError(
            f"'{extension}' is not a supported format, must be one of: "
            f"{backtick_join(FILE_FORMATS)}"
        )
    return path


def valid_output_directory_with_csv_default(value):
    path = Path(value)
    extension = split_directory_and_extension(path)[1]
    if not extension:
        return Path(value + ":csv")
    elif extension not in FILE_FORMATS:
        raise ArgumentTypeError(
            f"'{format_directory_extension(extension)}' is not a supported format, "
            f"must be one of: "
            f"{backtick_join(format_directory_extension(e) for e in FILE_FORMATS)}"
        )
    else:
        return path


def format_directory_extension(extension):
    return ":" + extension.removeprefix(".")


def query_engine_from_id(str_id):
    if "." not in str_id:
        try:
            str_id = QUERY_ENGINE_ALIASES[str_id]
        except KeyError:
            raise ArgumentTypeError(
                f"must be one of: {', '.join(QUERY_ENGINE_ALIASES.keys())} "
                f"(or a full dotted path to a query engine class)"
            )
    query_engine = import_string(str_id)
    assert_duck_type(query_engine, "query engine", "get_results_tables")
    return query_engine


def backend_from_id(str_id):
    # Workaround for the fact that Job Runner insists on setting OPENSAFELY_BACKEND to
    # "expectations" when running locally, and that the test backend sets it to "test".
    # Cohort Extractor backends have a different meaning from ehrQL's, and the semantics
    # of these "expectations" and "test" backends translate to "no backend at all" in
    # ehrQL terms so that's how we treat them.
    if str_id in ("expectations", "test"):
        return None

    if "." not in str_id:
        try:
            str_id = BACKEND_ALIASES[str_id]
        except KeyError:
            raise ArgumentTypeError(
                f"(or OPENSAFELY_BACKEND) must be one of: {backtick_join(BACKEND_ALIASES.keys())} "
                f"(or a full dotted path to a backend class) but got '{str_id}'"
            )
    backend = import_string(str_id)
    assert_duck_type(backend, "backend", "get_table_expression")
    return backend


def import_string(dotted_path):
    if "." not in dotted_path:
        raise ArgumentTypeError("must be a full dotted path to a Python class")
    module_name, _, attribute_name = dotted_path.rpartition(".")
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        raise ArgumentTypeError(f"could not import module '{module_name}'")
    try:
        return getattr(module, attribute_name)
    except AttributeError:
        raise ArgumentTypeError(
            f"module '{module_name}' has no attribute '{attribute_name}'"
        )


def assert_duck_type(obj, type_name, required_method):
    if not hasattr(obj, required_method):
        raise ArgumentTypeError(
            f"{obj} is not a valid {type_name}: no '{required_method}' method"
        )


def backtick_join(items):
    return ", ".join(f"`{i}`" for i in items)


if __name__ == "__main__":
    entrypoint()
