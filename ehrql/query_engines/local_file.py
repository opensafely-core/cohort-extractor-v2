from pathlib import Path

from ehrql.file_formats import read_tables
from ehrql.query_engines.in_memory import InMemoryQueryEngine
from ehrql.query_engines.in_memory_database import InMemoryDatabase
from ehrql.query_model.column_specs import get_column_specs_from_schema
from ehrql.query_model.introspection import get_table_nodes


class LocalFileQueryEngine(InMemoryQueryEngine):
    """
    Subclass of the in-memory engine which loads its data from files
    """

    database = None

    def get_results_stream(self, dataset):
        # Given the dataset supplied determine the tables used and load the associated
        # data into the database
        self.populate_database(
            get_table_nodes(dataset),
        )
        # Run the query as normal
        return super().get_results_stream(dataset)

    def populate_database(self, table_nodes, allow_missing_columns=True):
        table_specs = {
            table.name: get_column_specs_from_schema(table.schema)
            for table in table_nodes
        }
        table_rows = read_tables(
            Path(self.dsn),
            table_specs,
            allow_missing_columns=allow_missing_columns,
        )
        table_data = dict(zip(table_nodes, table_rows))
        self.database = InMemoryDatabase(table_data)
