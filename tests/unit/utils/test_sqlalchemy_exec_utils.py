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
        if self.call_count > 500:  # pragma: no cover
            raise RuntimeError("High query count: stuck in infinite loop?")

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
def test_fetch_table_in_batches_unique(table_data, batch_size):
    connection = FakeConnection(table_data)

    results = fetch_table_in_batches(
        connection.execute,
        sql_table,
        sql_table.c.key,
        key_is_unique=True,
        batch_size=batch_size,
    )

    assert sorted(results) == sorted(table_data)

    # If the batch size doesn't exactly divide the table size then we need an extra
    # query to fetch the remaining results. If it _does_ exactly divide it then we need
    # an extra query to confirm that there are no more results. Hence in either case we
    # expect one more query than `table_size // batch_size`.
    expected_query_count = (len(table_data) // batch_size) + 1
    assert connection.call_count == expected_query_count


# The algorithm we're using for non-unique batching fails if there are more than
# `batch_size` values with the same key. So first we generate a batch size (shareable
# between strategies) and then we use that to limit the number of repeated keys in the
# table data we generate (or to deliberately exceed it to test the error handling).
batch_size = st.shared(st.integers(min_value=2, max_value=10))


@st.composite
def table_data_strategy(draw, max_repeated_keys, include_example_over_max=False):
    # Generate a list of integers, which is how many times we're going to repeat each
    # key (possibly zero for some keys)
    repeats = draw(
        st.lists(
            st.integers(min_value=0, max_value=max_repeated_keys),
            max_size=100,
        )
    )
    # If required, generate an example which exceeds the maximum and include it
    if include_example_over_max:
        example = draw(st.integers(max_repeated_keys + 1, max_repeated_keys + 10))
        index = draw(st.integers(0, len(repeats)))
        repeats.insert(index, example)
    # Transform to a list of repeated keys
    keys = [key for key, n in enumerate(repeats) for _ in range(n)]
    # Pair each key occurrence with a unique value
    return [(key, i) for i, key in enumerate(keys)]


@hyp.given(
    batch_size=batch_size,
    table_data=batch_size.flatmap(
        lambda batch_size: table_data_strategy(max_repeated_keys=batch_size - 1),
    ),
)
def test_fetch_table_in_batches_nonunique(batch_size, table_data):
    connection = FakeConnection(table_data)
    log_messages = []

    results = fetch_table_in_batches(
        connection.execute,
        sql_table,
        sql_table.c.key,
        key_is_unique=False,
        batch_size=batch_size,
        log=log_messages.append,
    )

    assert sorted(results) == sorted(table_data)

    # Make sure we get the row count correct in the logs
    assert f"Fetch complete, total rows: {len(table_data)}" in log_messages


@hyp.given(
    batch_size=batch_size,
    table_data=batch_size.flatmap(
        lambda batch_size: table_data_strategy(
            max_repeated_keys=batch_size - 1,
            # Deliberately include an instance of too many repeated keys in order to
            # trigger an error
            include_example_over_max=True,
        ),
    ),
)
def test_fetch_table_in_batches_nonunique_raises_if_batch_too_small(
    batch_size, table_data
):
    connection = FakeConnection(table_data)

    results = fetch_table_in_batches(
        connection.execute,
        sql_table,
        sql_table.c.key,
        key_is_unique=False,
        batch_size=batch_size,
    )

    with pytest.raises(AssertionError, match="`batch_size` too small to make progress"):
        list(results)


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
