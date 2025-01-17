from collections.abc import Iterator, Sequence
from typing import Any

from ehrql.query_model import nodes as qm


class BaseQueryEngine:
    """
    Base class to hold methods that are agnostic to how the specific queries are built

    Inheriting classes must implement translating the query model into their particular
    flavour of tables and query language (SQL, pandas dataframes etc).
    """

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

    def get_results(self, dataset: qm.Dataset) -> Iterator[Sequence]:
        """
        Given a query model `Dataset` return the results as an iterator of "rows" (which
        are usually tuples, but any sequence type will do)

        Override this method to do the things necessary to generate query code and
        execute it against a particular backend.
        """
        raise NotImplementedError()
