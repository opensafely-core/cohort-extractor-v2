import random
from unittest import mock

import hypothesis as hyp
import hypothesis.strategies as st
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
        self.table_data = list(table_data)
        self.random = random.Random(202412190902)

    def execute(self, query):
        self.call_count += 1
        compiled = query.compile()
        sql = str(compiled).replace("\n", "").strip()
        params = compiled.params

        if sql == "SELECT t.key, t.value FROM t ORDER BY t.key LIMIT :param_1":
            limit = params["param_1"]
            return self.sorted_data()[:limit]
        elif sql == (
            "SELECT t.key, t.value FROM t WHERE t.key > :key_1 "
            "ORDER BY t.key LIMIT :param_1"
        ):
            limit, min_key = params["param_1"], params["key_1"]
            return [row for row in self.sorted_data() if row[0] > min_key][:limit]
        else:
            assert False, f"Unexpected SQL: {sql}"

    def sorted_data(self):
        # For the column we're not explicitly sorting by we want to return the rows in
        # an arbitrary order each time to simulate the behaviour of MSSQL
        self.random.shuffle(self.table_data)
        return sorted(self.table_data, key=lambda i: i[0])


sql_table = sqlalchemy.table(
    "t",
    sqlalchemy.Column("key"),
    sqlalchemy.Column("value"),
)


@hyp.given(
    table_data=st.lists(
        st.tuples(st.integers(), st.integers()),
        unique_by=lambda i: i[0],
        max_size=100,
    ),
    batch_size=st.integers(min_value=1, max_value=10),
)
def test_fetch_table_in_batches(table_data, batch_size):
    connection = FakeConnection(table_data)

    results = fetch_table_in_batches(
        connection.execute, sql_table, sql_table.c.key, batch_size=batch_size
    )

    assert sorted(results) == sorted(table_data)

    # If the batch size doesn't exactly divide the table size then we need an extra
    # query to fetch the remaining results. If it _does_ exactly divide it then we need
    # an extra query to confirm that there are no more results. Hence in either case we
    # expect one more query than `table_size // batch_size`.
    expected_query_count = (len(table_data) // batch_size) + 1
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
