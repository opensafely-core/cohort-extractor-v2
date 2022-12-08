import importlib.util
import shutil
import sys
from contextlib import nullcontext

import structlog

from databuilder.dummy_data import DummyDataGenerator
from databuilder.file_formats import (
    validate_dataset,
    validate_file_types_match,
    write_dataset,
)
from databuilder.query_engines.csv import CSVQueryEngine
from databuilder.query_engines.sqlite import SQLiteQueryEngine
from databuilder.query_language import Dataset, compile
from databuilder.query_model.column_specs import get_column_specs
from databuilder.utils.itertools_utils import eager_iterator
from databuilder.utils.orm_utils import write_orm_models_to_csv_directory
from databuilder.utils.sqlalchemy_query_utils import (
    clause_as_str,
    get_setup_and_cleanup_queries,
)
from databuilder.utils.traceback_utils import get_trimmed_traceback

log = structlog.getLogger()


class CommandError(Exception):
    "Errors that should be shown to the user without a traceback"


def generate_dataset(
    definition_file,
    dataset_file,
    dsn=None,
    backend_class=None,
    query_engine_class=None,
    dummy_tables_path=None,
    dummy_data_file=None,
    environ=None,
):
    if dsn:
        generate_dataset_with_dsn(
            definition_file,
            dataset_file,
            dsn,
            backend_class=backend_class,
            query_engine_class=query_engine_class,
            environ=environ or {},
        )
    elif dummy_data_file:
        pass_dummy_data(definition_file, dataset_file, dummy_data_file)
    else:
        generate_dataset_with_dummy_data(
            definition_file, dataset_file, dummy_tables_path
        )


def generate_dataset_with_dsn(
    definition_file, dataset_file, dsn, backend_class, query_engine_class, environ
):
    log.info(f"Generating dataset for {str(definition_file)}")
    dataset_definition = load_dataset_definition(definition_file)
    variable_definitions = compile(dataset_definition)
    column_specs = get_column_specs(variable_definitions)

    query_engine = get_query_engine(
        dsn,
        backend_class,
        query_engine_class,
        environ,
        default_query_engine_class=CSVQueryEngine,
    )
    results = query_engine.get_results(variable_definitions)
    # Because `results` is a generator we won't actually execute any queries until we
    # start consuming it. But we want to make sure we trigger any errors (or relevant
    # log output) before we create the output file. Wrapping the generator in
    # `eager_iterator` ensures this happens by consuming the first item upfront.
    results = eager_iterator(results)
    write_dataset(dataset_file, results, column_specs)


def generate_dataset_with_dummy_data(
    definition_file, dataset_file, dummy_tables_path=None
):
    log.info(f"Generating dummy dataset for {str(definition_file)}")
    dataset_definition = load_dataset_definition(definition_file)
    variable_definitions = compile(dataset_definition)
    column_specs = get_column_specs(variable_definitions)

    if dummy_tables_path:
        log.info(f"Reading CSV data from {dummy_tables_path}")
        query_engine = CSVQueryEngine(dummy_tables_path)
        results = query_engine.get_results(variable_definitions)
    else:
        results = DummyDataGenerator(variable_definitions).get_results()

    log.info("Building dataset and writing results")
    results = eager_iterator(results)
    write_dataset(dataset_file, results, column_specs)


def create_dummy_tables(definition_file, dummy_tables_path):
    log.info(f"Creating dummy data tables for {str(definition_file)}")
    dataset_definition = load_dataset_definition(definition_file)
    variable_definitions = compile(dataset_definition)
    generator = DummyDataGenerator(variable_definitions)
    dummy_tables = generator.get_data()
    dummy_tables_path.parent.mkdir(parents=True, exist_ok=True)
    log.info(f"Writing CSV files to {dummy_tables_path}")
    write_orm_models_to_csv_directory(dummy_tables_path, dummy_tables)


def pass_dummy_data(definition_file, dataset_file, dummy_data_file):
    log.info(f"Propagating dummy data {dummy_data_file} for {str(definition_file)}")

    dataset_definition = load_dataset_definition(definition_file)
    variable_definitions = compile(dataset_definition)
    column_specs = get_column_specs(variable_definitions)

    validate_file_types_match(dummy_data_file, dataset_file)
    validate_dataset(dummy_data_file, column_specs)

    dataset_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dummy_data_file, dataset_file)


def dump_dataset_sql(
    definition_file, output_file, backend_class, query_engine_class, environ
):
    log.info(f"Generating SQL for {str(definition_file)}")

    dataset_definition = load_dataset_definition(definition_file)
    query_engine = get_query_engine(
        None,
        backend_class,
        query_engine_class,
        environ,
        default_query_engine_class=SQLiteQueryEngine,
    )

    variable_definitions = compile(dataset_definition)
    all_query_strings = get_sql_strings(query_engine, variable_definitions)
    log.info("SQL generation succeeded")

    with open_output_file(output_file) as f:
        for query_str in all_query_strings:
            f.write(f"{query_str};\n\n")


def get_sql_strings(query_engine, variable_definitions):
    results_query = query_engine.get_query(variable_definitions)
    setup_queries, cleanup_queries = get_setup_and_cleanup_queries(results_query)
    dialect = query_engine.sqlalchemy_dialect()
    sql_strings = []

    for n, query in enumerate(setup_queries, start=1):
        sql = clause_as_str(query, dialect)
        sql_strings.append(f"-- Setup query {n:03} / {len(setup_queries):03}\n{sql}")

    sql = clause_as_str(results_query, dialect)
    sql_strings.append(f"-- Results query\n{sql}")

    assert not cleanup_queries, "Support these once tests exercise them"

    return sql_strings


def open_output_file(output_file):
    # If a file path is supplied, create it and open for writing
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        return output_file.open("w")
    # Otherwise return `stdout` wrapped in a no-op context manager
    else:
        return nullcontext(sys.stdout)


def get_query_engine(
    dsn, backend_class, query_engine_class, environ, default_query_engine_class
):
    # Construct backend if supplied
    if backend_class:
        backend = backend_class()
    else:
        backend = None

    if not query_engine_class:
        # Use the query engine class specified by the backend, if we have one
        if backend:
            query_engine_class = backend.query_engine_class
        # Otherwise default to using SQLite
        else:
            query_engine_class = default_query_engine_class

    return query_engine_class(dsn=dsn, backend=backend, config=environ)


def generate_measures(
    definition_file, input_file, output_file
):  # pragma: no cover (measures not implemented)
    raise NotImplementedError


def test_connection(backend_class, url, environ):
    from sqlalchemy import select

    backend = backend_class()
    query_engine = backend.query_engine_class(url, backend, config=environ)
    with query_engine.engine.connect() as connection:
        connection.execute(select(1))
    print("SUCCESS")


def load_dataset_definition(definition_file):
    module = load_module(definition_file)
    try:
        dataset = module.dataset
    except AttributeError:
        raise CommandError(
            "Did not find a variable called 'dataset' in dataset definition file"
        )
    if not isinstance(dataset, Dataset):
        raise CommandError(
            "'dataset' must be an instance of databuilder.ehrql.Dataset()"
        )
    return dataset


def load_module(module_path):
    # Taken from the official recipe for importing a module from a file path:
    # https://docs.python.org/3.9/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    module = importlib.util.module_from_spec(spec)
    # Temporarily add the directory containing the definition to the start of `sys.path`
    # (just as `python path/to/script.py` would) so that the definition can import
    # library modules from that directory
    original_sys_path = sys.path.copy()
    sys.path.insert(0, str(module_path.parent.absolute()))
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        traceback = get_trimmed_traceback(exc, str(module_path))
        raise CommandError(f"Failed to import '{module_path}':\n\n{traceback}")
    finally:
        sys.path = original_sys_path
