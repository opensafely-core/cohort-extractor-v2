from collections.abc import Iterator, Sequence
from typing import Any

from ehrql.query_model import nodes as qm
from ehrql.utils.itertools_utils import iter_groups


class Marker: ...


class BaseQueryEngine:
    """
    Base class to hold methods that are agnostic to how the specific queries are built

    Inheriting classes must implement translating the query model into their particular
    flavour of tables and query language (SQL, pandas dataframes etc).
    """

    # Sentinel value used to mark the start of a new results table in a stream of results
    RESULTS_START = Marker()

    def __init__(self, dsn: str, backend: Any = None, config: dict | None = None):
        """
        `dsn` is  Data Source Name — a string (usually a URL) which provides connection
            details to a data source (usually a RDBMS)
        `backend` is an optional Backend instance
        `config` is an optional dictionary of config values
        """
        if backend is not None:
            dsn = backend.modify_dsn(dsn)
        self.dsn = dsn
        self.backend = backend
        self.config = config or {}

    def get_results_tables(
        self, dataset: qm.Dataset, measures: tuple = None
    ) -> Iterator[Iterator[Sequence]]:
        """
        Given a query model `Dataset` return an iterator of "results tables", where each
        table is an iterator of rows (usually tuples, but any sequence type will do)

        This is the primary interface to query engines and the one required method.

        Typically however, query engine subclasses will implement `get_results_stream`
        instead which yields a flat sequence of rows, with tables separated by the
        `RESULTS_START` marker value. This is converted into the appropriate structure
        by `iter_groups` which also enforces that the caller interacts with it safely.
        """
        return iter_groups(
            self.get_results_stream(dataset, measures), self.RESULTS_START
        )

    def get_results_stream(
        self, dataset: qm.Dataset, measures: tuple = None
    ) -> Iterator[Sequence | Marker]:
        """
        Given a query model `Dataset` return an iterator of rows over all the results
        tables, with each table's results separated by the `RESULTS_START` marker value

        If provided, use the `measures` tuple to aggregate a results table from `Dataset`
        by to return one or more measures results tables, which are the result of summing
        two columns (a numerator and denominator column) and grouping by one or more columns.

        Override this method to do the things necessary to generate query code and
        execute it against a particular backend.

        Emitting results in a flat sequence like this with separators between the tables
        ends up making the query code _much_ easier to reason about because everything
        happens in a clear linear sequence rather than inside nested generators. This
        makes things like transaction management and error handling much more
        straightforward.
        """
        raise NotImplementedError()

    def get_results(self, dataset: qm.Dataset) -> Iterator[Sequence]:
        """
        Temporary method to continue to support code which assumes only a single results
        table
        """
        tables = self.get_results_tables(dataset)
        yield from next(tables)
        for remaining in tables:
            assert False, "Expected only one results table"
