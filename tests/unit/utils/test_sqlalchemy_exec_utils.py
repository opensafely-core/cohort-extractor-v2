from unittest import mock

import pytest
import sqlalchemy
from sqlalchemy.exc import OperationalError

from ehrql.utils.sqlalchemy_exec_utils import (
    execute_with_retry_factory,
    fetch_table_in_batches,
)


# Pretend to be a SQL connection that understands just two forms of query
class FakeConnection:
    call_count = 0

    def __init__(self, table_data):
        self.table_data = table_data

    def execute(self, query):
        self.call_count += 1
        compiled = query.compile()
        sql = str(compiled).replace("\n", "").strip()
        params = compiled.params

        if sql == "SELECT t.key, t.value FROM t ORDER BY t.key LIMIT :param_1":
            limit = params["param_1"]
            return self.table_data[:limit]
        elif sql == (
            "SELECT t.key, t.value FROM t WHERE t.key > :key_1 "
            "ORDER BY t.key LIMIT :param_1"
        ):
            limit, min_key = params["param_1"], params["key_1"]
            return [row for row in self.table_data if row[0] > min_key][:limit]
        else:
            assert False, f"Unexpected SQL: {sql}"


sql_table = sqlalchemy.table(
    "t",
    sqlalchemy.Column("key"),
    sqlalchemy.Column("value"),
)


@pytest.mark.parametrize(
    "table_size,batch_size",
    [
        (20, 5),
        (20, 6),
        (0, 10),
        (9, 1),
    ],
)
def test_fetch_table_in_batches(table_size, batch_size):
    table_data = [(i, f"foo{i}") for i in range(table_size)]

    connection = FakeConnection(table_data)

    results = fetch_table_in_batches(
        connection.execute, sql_table, sql_table.c.key, batch_size=batch_size
    )

    assert list(results) == table_data

    # If the batch size doesn't exactly divide the table size then we need an extra
    # query to fetch the remaining results. If it _does_ exactly divide it then we need
    # an extra query to confirm that there are no more results. Hence in either case we
    # expect one more query than `table_size // batch_size`.
    expected_query_count = (table_size // batch_size) + 1
    assert connection.call_count == expected_query_count


ERROR = OperationalError("A bad thing happend", {}, None)


@mock.patch("time.sleep")
def test_execute_with_retry(sleep):
    log_messages = []

    def error_during_iteration():
        yield 1
        yield 2
        raise ERROR

    connection = mock.Mock(
        **{
            "execute.side_effect": [
                ERROR,
                ERROR,
                error_during_iteration(),
                ("it's", "OK", "now"),
            ]
        }
    )

    execute_with_retry = execute_with_retry_factory(
        connection,
        max_retries=3,
        retry_sleep=10,
        backoff_factor=2,
        log=log_messages.append,
    )

    # list() is always called on the successful return value
    assert execute_with_retry() == ["it's", "OK", "now"]
    assert connection.execute.call_count == 4
    assert connection.rollback.call_count == 3
    assert sleep.mock_calls == [mock.call(t) for t in [10, 20, 40]]
    assert "Retrying query (attempt 3 / 3)" in log_messages


@mock.patch("time.sleep")
def test_execute_with_retry_exhausted(sleep):
    connection = mock.Mock(
        **{
            "execute.side_effect": [ERROR, ERROR, ERROR, ERROR],
        }
    )
    execute_with_retry = execute_with_retry_factory(
        connection, max_retries=3, retry_sleep=10, backoff_factor=2
    )
    with pytest.raises(OperationalError):
        execute_with_retry()
    assert connection.execute.call_count == 4
    assert connection.rollback.call_count == 3
    assert sleep.mock_calls == [mock.call(t) for t in [10, 20, 40]]
