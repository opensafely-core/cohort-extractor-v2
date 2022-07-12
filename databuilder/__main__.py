import os
import sys
from argparse import ArgumentParser, ArgumentTypeError
from pathlib import Path

from .main import (
    dump_dataset_sql,
    generate_dataset,
    generate_measures,
    pass_dummy_data,
    test_connection,
)


def main(args, environ=None):
    environ = environ or {}

    parser = build_parser(environ)
    options = parser.parse_args(args)

    if options.which == "generate-dataset":
        database_url = environ.get("DATABASE_URL")
        dummy_data_file = options.dummy_data_file

        if database_url:
            generate_dataset(
                definition_file=options.dataset_definition,
                dataset_file=options.output,
                db_url=database_url,
                backend_id=environ.get("OPENSAFELY_BACKEND"),
                environ=environ,
            )
        elif dummy_data_file:
            pass_dummy_data(options.dataset_definition, options.output, dummy_data_file)
        else:
            parser.error(
                "error: either --dummy-data-file or DATABASE_URL environment variable is required"
            )
    elif options.which == "dump-dataset-sql":
        dump_dataset_sql(
            options.dataset_definition,
            options.output,
            backend_id=options.backend,
            query_engine_id=options.query_engine,
            environ=environ,
        )
    elif options.which == "generate-measures":
        generate_measures(
            definition_path=options.dataset_definition,
            input_file=options.input,
            dataset_file=options.output,
        )
    elif options.which == "test-connection":
        test_connection(
            backend_id=options.backend,
            url=options.url,
            environ=environ,
        )
    elif options.which == "print-help":
        parser.print_help()
    else:
        assert False, f"Unhandled subcommand: {options.which}"


def build_parser(environ):
    parser = ArgumentParser(
        prog="databuilder", description="Generate datasets in OpenSAFELY"
    )
    parser.set_defaults(which="print-help")

    subparsers = parser.add_subparsers(help="sub-command help")
    add_generate_dataset(subparsers, environ)
    add_dump_dataset_sql(subparsers, environ)
    add_generate_measures(subparsers, environ)
    add_test_connection(subparsers, environ)

    return parser


def add_generate_dataset(subparsers, environ):
    parser = subparsers.add_parser("generate-dataset", help="Generate a dataset")
    parser.set_defaults(which="generate-dataset")
    parser.add_argument(
        "--dataset-definition",
        help="The path of the file where the dataset is defined",
        type=existing_python_file,
    )
    parser.add_argument(
        "--output",
        help="Path and filename (or pattern) of the file(s) where the dataset will be written",
        type=Path,
    )
    parser.add_argument(
        "--dummy-data-file",
        help="Provide dummy data from a file to be validated and used as the dataset",
        type=Path,
    )


def add_dump_dataset_sql(subparsers, environ):
    parser = subparsers.add_parser(
        "dump-dataset-sql",
        help=(
            "Output the SQL that would be executed to fetch the results of the "
            "dataset definition"
        ),
    )
    parser.set_defaults(which="dump-dataset-sql")
    parser.add_argument(
        "--query-engine",
        type=str,
    )
    parser.add_argument(
        "--backend",
        type=str,
    )
    parser.add_argument(
        "--output",
        help="SQL output file (outputs to console by default)",
        type=Path,
    )
    parser.add_argument(
        "dataset_definition",
        help="Path of Python file where dataset is defined",
        type=existing_python_file,
    )


def add_generate_measures(subparsers, environ):
    parser = subparsers.add_parser(
        "generate-measures", help="Generate measures from a dataset"
    )
    parser.set_defaults(which="generate-measures")
    parser.add_argument(
        "--input",
        help="Path and filename (or pattern) of the input file(s)",
        type=Path,
    )
    parser.add_argument(
        "--output",
        help="Path and filename (or pattern) of the file(s) where the dataset will be written",
        type=Path,
    )
    parser.add_argument(
        "--dataset-definition",
        help="The path of the file where the dataset is defined",
        type=existing_python_file,
    )


def add_test_connection(subparsers, environ):
    parser = subparsers.add_parser(
        "test-connection", help="test the database connection configuration"
    )
    parser.set_defaults(which="test-connection")
    parser.add_argument(
        "--backend",
        "-b",
        help="backend type to test",
        default=environ.get("BACKEND", environ.get("OPENSAFELY_BACKEND")),
    )
    parser.add_argument(
        "--url",
        "-u",
        help="db url",
        default=environ.get("DATABASE_URL"),
    )


def existing_python_file(value):
    path = Path(value)
    if not path.exists():
        raise ArgumentTypeError(f"{value} does not exist")
    if not path.suffix == ".py":
        raise ArgumentTypeError(f"{value} is not a Python file")
    return path


if __name__ == "__main__":
    main(sys.argv[1:], environ=os.environ)
