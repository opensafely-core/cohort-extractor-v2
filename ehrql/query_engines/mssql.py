import logging

import sqlalchemy
from sqlalchemy.schema import CreateIndex, DropTable
from sqlalchemy.sql.functions import Function as SQLFunction

from ehrql.query_engines.base_sql import BaseSQLQueryEngine, apply_patient_joins
from ehrql.query_engines.mssql_dialect import (
    MSSQLDialect,
    ScalarSelectAggregation,
    SelectStarInto,
)
from ehrql.utils.mssql_log_utils import execute_with_log
from ehrql.utils.sqlalchemy_exec_utils import (
    execute_with_retry_factory,
    fetch_table_in_batches,
)
from ehrql.utils.sqlalchemy_query_utils import (
    GeneratedTable,
    InsertMany,
    get_setup_and_cleanup_queries,
)


log = logging.getLogger()


class MSSQLQueryEngine(BaseSQLQueryEngine):
    sqlalchemy_dialect = MSSQLDialect

    # Use a CTE as the source for the aggregate query rather than a
    # subquery in order to avoid the "Cannot perform an aggregate function
    # on an expression containing an aggregate or a subquery" error
    def aggregate_series_by_patient(self, source_node, aggregation_func):
        query = self.get_select_query_for_node_domain(source_node)
        from_subquery = query.add_columns(self.get_expr(source_node))
        from_subquery = apply_patient_joins(from_subquery).subquery()
        query = sqlalchemy.select(from_subquery.columns[0])
        aggregation_expr = aggregation_func(from_subquery.columns[1]).label("value")
        return self.apply_sql_aggregation(query, aggregation_expr)

    def calculate_mean(self, sql_expr):
        # Unlike other DBMSs, MSSQL will return an integer as the mean of integers so we
        # have to explicitly cast to float
        if not isinstance(sql_expr.type, sqlalchemy.Float):
            sql_expr = sqlalchemy.cast(sql_expr, sqlalchemy.Float)
        return SQLFunction("AVG", sql_expr, type_=sqlalchemy.Float)

    def date_difference_in_days(self, end, start):
        return SQLFunction(
            "DATEDIFF",
            sqlalchemy.text("day"),
            start,
            end,
            type_=sqlalchemy.Integer,
        )

    def truedivide(self, lhs, rhs):
        rhs_null_if_zero = SQLFunction("NULLIF", rhs, 0.0, type_=sqlalchemy.Float)
        return lhs / rhs_null_if_zero

    def get_date_part(self, date, part):
        assert part in {"YEAR", "MONTH", "DAY"}
        return SQLFunction(part, date, type_=sqlalchemy.Integer)

    def date_add_days(self, date, num_days):
        return SQLFunction(
            "DATEADD",
            sqlalchemy.text("day"),
            num_days,
            date,
            type_=sqlalchemy.Date,
        )

    def date_add_months(self, date, num_months):
        new_date = SQLFunction(
            "DATEADD",
            sqlalchemy.text("month"),
            num_months,
            date,
            type_=sqlalchemy.Date,
        )
        # In cases of day-of-month overflow, MSSQL clips to the end of the month rather
        # than rolling over to the first of the next month as want it to, so we detect
        # when it's done that and correct for it here. For more detail see:
        # tests/spec/date_series/ops/test_date_series_ops.py::test_add_months
        correction = sqlalchemy.case(
            (self.get_date_part(new_date, "DAY") < self.get_date_part(date, "DAY"), 1),
            else_=0,
        )
        return self.date_add_days(new_date, correction)

    def date_add_years(self, date, num_years):
        # We can't just use `DATEADD(year, ...)` here due to MSSQL's insistence on
        # rounding 29 Feb down rather than up on non-leap years. For more detail see:
        # tests/spec/date_series/ops/test_date_series_ops.py::test_add_years
        #
        # First, do the year shifting arithmetic on the start of the month where there's
        # no leap year shenanigans to content with.
        start_of_month = SQLFunction(
            "DATEFROMPARTS",
            self.get_date_part(date, "YEAR") + num_years,
            self.get_date_part(date, "MONTH"),
            1,
            type_=sqlalchemy.Date,
        )
        # Then add on the number of days we're offset from the start of the month which
        # has the effect of rolling 29 Feb over to 1 Mar as we want
        return self.date_add_days(start_of_month, self.get_date_part(date, "DAY") - 1)

    def to_first_of_year(self, date):
        return SQLFunction(
            "DATEFROMPARTS",
            self.get_date_part(date, "YEAR"),
            1,
            1,
            type_=sqlalchemy.Date,
        )

    def to_first_of_month(self, date):
        return SQLFunction(
            "DATEFROMPARTS",
            self.get_date_part(date, "YEAR"),
            self.get_date_part(date, "MONTH"),
            1,
            type_=sqlalchemy.Date,
        )

    def reify_query(self, query):
        # The `#` prefix is an MSSQL-ism which automatically makes the tables
        # session-scoped temporary tables
        return temporary_table_from_query(
            table_name=f"#tmp_{self.get_next_id()}",
            query=query,
            index_col="patient_id",
        )

    def create_inline_table(self, columns, rows):
        table_name = f"#inline_data_{self.get_next_id()}"
        table = GeneratedTable(
            table_name,
            sqlalchemy.MetaData(),
            *columns,
        )
        table.setup_queries = [
            sqlalchemy.schema.CreateTable(table),
            InsertMany(table, rows),
            sqlalchemy.schema.CreateIndex(
                sqlalchemy.Index(None, table.c[0], mssql_clustered=True)
            ),
        ]
        return table

    def get_queries(self, dataset):
        results_queries = super().get_queries(dataset)
        # Write results to temporary tables and select them from there. This allows us
        # to use more efficient/robust mechanisms to retrieve the results.
        select_queries = []
        for n, results_query in enumerate(results_queries, start=1):
            results_table = temporary_table_from_query(
                # The double `##` prefix here makes this a global temporary table, i.e.
                # one accessible to other sessions, hence we need a globally unique
                # name. This allows us to use a separate connection to retrieve results
                # which gives us more robust retries.
                f"##results_{self.global_unique_id}_{n}",
                results_query,
                index_col="patient_id",
            )
            select_queries.append(sqlalchemy.select(results_table))
        return select_queries

    def get_measures_queries(self, dataset, measures):
        """
        Return the SQL queries to fetch the results for one or more measures, the results
        of summing a numerator column and a denominator column, and grouping by one or
        more columns.

        `measures` is a collection of two-tuples for each measure:
            (
                (numerator_column_index, denominator_column_index), (group_column_indexes),
                ...
            )
        We write each measures result table to a temporary table.
        Returns a list of select queries for each measure.
        """
        results_queries = self.get_queries(dataset)
        assert len(results_queries) == 1, (
            "Measures queries can only be applied to a single results table"
        )
        results_query = results_queries[0].subquery()
        # Write results to temporary tables and select them from there. This allows us
        # to use more efficient/robust mechanisms to retrieve the results.
        select_queries = []
        for n, (sum_over_indexes, group_by_indexes) in enumerate(measures):
            sum_overs = [
                sqlalchemy.func.sum(results_query.columns[sum_over_index]).label(
                    f"sum_{i}"
                )
                for i, sum_over_index in enumerate(sum_over_indexes)
            ]
            group_bys = [
                results_query.columns[group_by_index]
                for group_by_index in group_by_indexes
            ]
            group_query = sqlalchemy.select(*sum_overs, *group_bys).group_by(*group_bys)
            group_table = temporary_table_from_query(
                f"#group_results_{n}", group_query, index_col="sum_0"
            )
            select_queries.append(sqlalchemy.select(group_table))
        return select_queries

    def get_results_stream(self, dataset, measures=None):
        if measures is not None:
            results_queries = self.get_measures_queries(dataset, measures)
        else:
            results_queries = self.get_queries(dataset)

        # We're expecting queries in a very specific form which is "select everything
        # from one table"; so we assert that they have this form and retrieve references
        # to the tables
        results_tables = []
        for results_query in results_queries:
            results_table = results_query.get_final_froms()[0]
            assert str(results_query) == str(sqlalchemy.select(results_table))
            results_tables.append(results_table)
        setup_queries, cleanup_queries = get_setup_and_cleanup_queries(results_queries)

        with self.engine.connect() as connection:
            # All our queries are either (a) read-only queries against static data, or
            # (b) queries which modify session-scoped temporary tables. This means we
            # can use the DBAPI-level AUTOCOMMIT isolation level which causes all
            # statements to commit immediately.
            connection.execution_options(isolation_level="AUTOCOMMIT")

            for i, setup_query in enumerate(setup_queries, start=1):
                query_id = f"setup query {i:03} / {len(setup_queries):03}"
                log.info(f"Running {query_id}")
                execute_with_log(connection, setup_query, log.info, query_id=query_id)

            # We use a separate connection to retrieve the results. Our intial
            # connection keeps the temporary table "alive" and then this connection can
            # be safely reset and retried if we hit errors during the download (which we
            # often do for reasons we don't yet understand).
            with self.engine.connect() as results_connection:
                # Retry 4 times over the course of 1 minute
                execute_with_retry = execute_with_retry_factory(
                    results_connection,
                    max_retries=4,
                    retry_sleep=4.0,
                    backoff_factor=2,
                    log=log.info,
                )

                for i, results_table in enumerate(results_tables):
                    if measures:
                        # fetch_table_in_batches needs a key column to sort on in order to
                        # return a table in batches. For patient and event-level tables, this
                        # is always patient ID, but we don't have patient ID for a measures
                        # table, so we're arbitrarily giving it the first column (the numerator column).
                        # This  doesn't really make sense for sorting (a group column would make
                        # more sense, but measures don't always have groups). Given that this is an
                        # aggregated table, we wouldn't expect it to exceed the batch size, so it
                        # shouldn't have any real impact.
                        key_column = results_table.columns[0]
                    else:
                        key_column = results_table.c.patient_id
                    yield self.RESULTS_START
                    yield from fetch_table_in_batches(
                        execute_with_retry,
                        results_table,
                        key_column=key_column,
                        # TODO: We need to find a better way to identify which tables have a
                        # unique `patient_id` column because it lets the batch fetcher use a
                        # more efficient algorithm. At present, we know that the first
                        # results table does but this isn't a very comfortable approach. The
                        # other option is to just always use the non-unique algorithm on the
                        # basis that the lost efficiency probably isn't noticeable. But
                        # until we're supporting event-level data for real I'm reluctant to
                        # make things worse for the currently supported case.
                        key_is_unique=(i == 0),
                        # This value was copied from the previous cohortextractor. I suspect
                        # it has no real scientific basis.
                        batch_size=32000,
                        log=log.info,
                    )

            for i, cleanup_query in enumerate(cleanup_queries, start=1):
                query_id = f"cleanup query {i:03} / {len(cleanup_queries):03}"
                log.info(f"Running {query_id}")
                execute_with_log(connection, cleanup_query, log.info, query_id=query_id)

    def get_aggregate_subquery(self, aggregate_function, columns, return_type):
        return ScalarSelectAggregation.build(
            aggregate_function, columns, type_=return_type
        )


def temporary_table_from_query(table_name, query, index_col=0):
    # Define a table object with the same columns as the query
    table = GeneratedTable.from_query(table_name, query)
    table.setup_queries = [
        # Use the MSSQL `SELECT * INTO ...` construct to create and populate this
        # table
        SelectStarInto(table, query.alias()),
        # Create a clustered index on the specified column which defines the order in
        # which data will be stored on disk. (We use `None` as the index name to let
        # SQLAlchemy generate one for us.)
        CreateIndex(sqlalchemy.Index(None, table.c[index_col], mssql_clustered=True)),
    ]
    table.cleanup_queries = [DropTable(table, if_exists=True)]
    return table
