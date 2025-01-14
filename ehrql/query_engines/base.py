class BaseQueryEngine:
    """
    A base QueryEngine to hold methods that are agnostic to how the specific queries are built.
    Inheriting classes must implement translating the query model into their particular flavour of tables and query
    language (SQL, pandas dataframes etc).
    """

    def __init__(self, dsn, backend=None, config=None):
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

    def get_results(self, dataset):
        """
        `dataset` is a query model `Dataset` instance

        Override this method to do the things necessary to generate query code and execute
        it against a particular backend
        """
        raise NotImplementedError
