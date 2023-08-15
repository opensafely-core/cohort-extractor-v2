import itertools
import logging.config
import os
import re
from contextlib import contextmanager
from datetime import timedelta
from time import monotonic

import structlog


SQLSERVER_TIMING_REGEX = re.compile(
    r"""
        .*SQL\sServer\s(?P<timing_type>parse\sand\scompile\stime|Execution\sTime).*  # SQl Server Statistics time message prefix
        .*CPU\stime\s=\s(?P<cpu_time>\d+)\sms  # cpu time in ms
        .*elapsed\stime\s=\s(?P<elapsed_time>\d+)\sms  # elapsed time in ms
        """,
    flags=re.S | re.X,
)


class TimingCounter:
    """
    A wrapper around an itertools counter which keeps track of the
    current and next values of the counter
    """

    def __init__(self):
        self.counter = itertools.count()
        self.current = None
        self.next = 0

    def __next__(self):
        # increment the counter, set the current and next values with it,
        # and return it
        self.current = next(self.counter)
        self.next = self.current + 1
        return self.current


timing_log_counter = TimingCounter()

pre_chain = [
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
]

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


def init_logging():
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "formatter": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(),
                    "foreign_pre_chain": pre_chain,
                }
            },
            "handlers": {
                "console": {
                    "level": "DEBUG",
                    "class": "logging.StreamHandler",
                    "formatter": "formatter",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": os.getenv("LOG_LEVEL", "INFO"),
            },
            "loggers": {
                "sqlalchemy.engine": {
                    "handlers": ["console"],
                    "level": "INFO" if os.getenv("LOG_SQL") else "WARN",
                    "propagate": False,
                },
                "pyhive": {
                    "handlers": ["console"],
                    "level": "INFO" if os.getenv("LOG_SQL") else "WARN",
                    "propagate": False,
                },
            },
        }
    )


def log_stats(logger, **kwargs):
    logger.info("cohortextractor-stats", **kwargs)


@contextmanager
def log_execution_time(logger, **log_kwargs):
    log_kwargs["timing_id"] = next(timing_log_counter)
    log_kwargs["state"] = "started"

    # pop sql-related kwargs
    sql = log_kwargs.pop("sql", None)
    truncate_all_sql = log_kwargs.pop("truncate", False)

    start = monotonic()
    # log that we're starting timing
    log_stats(logger, timing="start", time=start, **log_kwargs)

    def _truncate(lines):
        return "\n".join([*lines, "[truncated]"])

    if sql:
        sql_lines = sql.split("\n")
        first_non_comment_line = next(
            line.strip()
            for line in sql_lines
            if line and not line.strip().startswith("--")
        )
        if first_non_comment_line.startswith("INSERT"):
            # INSERTS can be lengthy, and are batched in 999s; logging all the lines here
            # is not helpful and creates huge logs, so just log the first line for illustration
            sql = _truncate([first_non_comment_line])
        elif len(sql_lines) > 999 or (truncate_all_sql and len(sql_lines) > 1):
            # Limit the SQL logged to a max 1000 lines
            # Or, if we get the `truncate` flag, truncate any SQL (e.g. for reruns with multiple index dates)
            sql = _truncate(sql_lines[:999])

        # log the SQL itself separately
        log_stats(logger, timing_id=log_kwargs["timing_id"], sql=sql)

    try:
        yield
    except Exception:
        # exceptions will be raised where they occur; just log that it happened
        log_kwargs["state"] = "error"
        raise
    else:
        log_kwargs["state"] = "ok"
    finally:
        stop = monotonic()
        elapsed_time = stop - start
        log_kwargs.update(
            timing="stop",
            time=stop,
            execution_time_secs=elapsed_time,
            execution_time=str(timedelta(seconds=elapsed_time)),
        )
        log_stats(logger, **log_kwargs)


class BaseLoggingWrapper:
    """
    Wraps a class instance and provides a logger instance as an attribute.

    Subclasses can implement their own methods to override methods on the
    wrapped instance and make use of the logger.

    Any attribute or method called on the wrapper calls its own implementation if
    one exists, otherwise calls it on the class instance
    """

    def __init__(self, logger, wrapped_instance):
        self.logger = logger
        self.wrapped_instance = wrapped_instance

    def __getattr__(self, attr):
        if attr in dir(self):
            return attr
        return getattr(self.wrapped_instance, attr)


class LoggingCursor(BaseLoggingWrapper):
    """
    Provides a database cursor instance that willl log the execution time of any
    `execute` call
    """

    def __init__(self, logger, cursor, truncate=False, time_stats=False):
        super().__init__(logger, cursor)
        self.cursor = cursor
        self.truncate = truncate
        self.time_stats = time_stats

    def __iter__(self):
        return self.cursor.__iter__()

    def __next__(self):
        return self.cursor.__next__()

    def execute(self, query, *args, log_desc=None, **kwargs):
        with log_execution_time(
            self.logger, sql=query, description=log_desc, truncate=self.truncate
        ):
            if self.time_stats:
                # Wrap the query in the sql server stats timing
                query = f"""
                SET STATISTICS TIME ON
                {query}
                SET STATISTICS TIME OFF
                """
            self.cursor.execute(query, *args, **kwargs)


class LoggingDatabaseConnection(BaseLoggingWrapper):
    """
    Provides a database connection instance with a LoggingCursor
    """

    def __init__(self, logger, database_connection, truncate=False, time_stats=False):
        super().__init__(logger, database_connection)
        self.db_connection = database_connection
        self.truncate = truncate
        self.time_stats = time_stats
        if time_stats:
            self.set_mssql_message_logger()

    def cursor(self):
        return LoggingCursor(
            self.logger,
            self.db_connection.cursor(),
            truncate=self.truncate,
            time_stats=self.time_stats,
        )

    def set_mssql_message_logger(self):
        def stats_msg_handler(msgstate, severity, srvname, procname, line, msgtext):
            """
            Log parse, compile and execution timing messages sent by the server.
            """
            try:
                if timing_match := SQLSERVER_TIMING_REGEX.match(msgtext.decode()):
                    self.logger.info(
                        "sqlserver-stats",
                        description=timing_match.group("timing_type")
                        .lower()
                        .replace(" ", "_"),
                        cpu_time_secs=int(timing_match.group("cpu_time")) / 1000,
                        elapsed_time_secs=int(timing_match.group("elapsed_time"))
                        / 1000,
                        # SQL Server statistics timing is only set to ON for timed query execution, so
                        # we may be able match it to the query it timed by tagging it with the current timing id
                        # This may result in multiple execution timings logged against one timing id if
                        # query execution is delayed until the time of fetching
                        timing_id=timing_log_counter.current,
                    )
            except Exception as e:
                # Don't raise any exceptions from the message handling itself, just log them
                self.logger.error(
                    "sqlserver-stats",
                    description="Exception in SQL server message handling",
                    exc_info=e,
                )

        self.db_connection.connection.connection._conn.set_msghandler(stats_msg_handler)
