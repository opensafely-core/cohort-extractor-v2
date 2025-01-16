import time

from sqlalchemy import select
from sqlalchemy.exc import InternalError, OperationalError


def fetch_table_in_batches(
    execute, table, key_column, key_is_unique, batch_size=32000, log=lambda *_: None
):
    """
    Returns an iterator over all the rows in a table by querying it in batches

    Args:
        execute: callable which accepts a SQLAlchemy query and returns results (can be
            just a Connection.execute method)
        table: SQLAlchemy TableClause
        key_column: reference to an orderable column on `table`, used for
            paging (note that this will need an index on it to avoid terrible
            performance)
        key_is_unique: if the key_column contains only unique values then we can use a
            simpler and more efficient algorithm to do the paging
        batch_size: how many results to fetch in each batch
        log: callback to receive log messages
    """
    if key_is_unique:
        return fetch_table_in_batches_unique(
            execute, table, key_column, batch_size, log
        )
    else:
        return fetch_table_in_batches_nonunique(
            execute, table, key_column, batch_size, log
        )


def fetch_table_in_batches_unique(
    execute, table, key_column, batch_size=32000, log=lambda *_: None
):
    """
    Returns an iterator over all the rows in a table by querying it in batches using a
    unique key column
    """
    assert batch_size > 0
    batch_count = 1
    total_rows = 0
    min_key = None

    key_column_index = table.columns.values().index(key_column)

    log(
        f"Fetching rows from '{table}' in batches of {batch_size} using unique "
        f"column '{key_column.name}'"
    )
    while True:
        query = select(table).order_by(key_column).limit(batch_size)
        if min_key is not None:
            query = query.where(key_column > min_key)

        log(f"Fetching batch {batch_count}")
        results = execute(query)

        row_count = 0
        for row in results:
            row_count += 1
            yield row

        total_rows += row_count
        batch_count += 1

        if row_count < batch_size:
            log(f"Fetch complete, total rows: {total_rows}")
            break
        else:
            min_key = row[key_column_index]


def fetch_table_in_batches_nonunique(
    execute, table, key_column, batch_size=32000, log=lambda *_: None
):
    """
    Returns an iterator over all the rows in a table by querying it in batches using a
    non-unique key column

    The algorithm below is designed (and tested) to work correctly without relying on
    sort-stability. That is, if we repeatedly ask the database for results sorted by X
    then rows with the same value for X may be returned in a different order each time.

    Handling this involves some inefficiency in the form of slightly overlapping
    batches. If we have a table like this:

         patient_id | value
        ------------+-------
         1          | a
         1          | b
         2          | c
         3          | d
         3          | e
         4          | f

    And we fetch a batch of four, ordered by `patient_id` we could get results like this
    (note the different order of `values`):

         patient_id | value
        ------------+-------
         1          | b
         1          | a
         2          | c
         3          | e

    We can be sure we've got all the results for patients 1 and 2, but we don't know how
    many more results there might be for patient 3. And we can't say "give me results
    for patients 3 and above but skip the first one" because we can't guarantee that the
    row we've already got (with value `e`) is going to be the first row in the next set
    of results.

    So instead, we have to ask for the next batch with `patient_id` greater than 2:

         patient_id | value
        ------------+-------
         3          | d
         3          | e
         4          | f

    Now, because we get to rows for patient 4, we can be sure we've got all the rows for
    patient 3. And, because we requested a batch of size four and only got three
    results, we know we've reached the end of the table, and therefore that we've got
    all the rows for patient 4 as well.

    But in order to do this we ended up fetching some rows for patient 3 twice. In
    general, the degree of inefficiency here will depend on the number of repeated keys
    you get at the end of batch relative to the batch size. Given that we use batch
    sizes in at least the tens of thousands the maximum number of rows per patient is
    likely to be so far below this that the inefficiency will be negligable.

    There is also an edge case where if the maximum number of rows per patients equals
    or exceeds the batch size then the algorithm can make no progress at all. Again,
    given the likely sizes involved this seems very unlikely but we add a check to raise
    an explicit error if this ever happens.
    """
    assert batch_size > 1
    batch_count = 1
    total_rows = 0
    current_key = None
    last_fully_fetched_key = None
    accumulated_rows = []

    key_column_index = table.columns.values().index(key_column)

    log(
        f"Fetching rows from '{table}' in batches of {batch_size} using non-unique "
        f"column '{key_column.name}'"
    )
    while True:
        query = select(table).order_by(key_column).limit(batch_size)
        if last_fully_fetched_key is not None:
            query = query.where(key_column > last_fully_fetched_key)

        log(f"Fetching batch {batch_count}")
        results = execute(query)

        # We iterate over the results for the batch, accumulating rows in a list
        row_count = 0
        for row in results:
            row_count += 1
            next_key = row[key_column_index]
            # Whenever the value of the key changes we know we've now got a complete set
            # of rows with the _previous_ key, so we emit those rows, empty the
            # accumulator, and mark the new value of the key as the current one
            if next_key != current_key:
                yield from accumulated_rows
                accumulated_rows.clear()
                last_fully_fetched_key = current_key
                current_key = next_key
            accumulated_rows.append(row)

        # The total number of rows we've emitted is the number we've read minus any
        # still left in the accumulator
        total_rows += row_count - len(accumulated_rows)
        batch_count += 1

        if row_count < batch_size:
            # If we got fewer rows than we asked for then we've reach the end of the
            # table: emit any remaining rows, log, and exit
            yield from accumulated_rows
            total_rows += len(accumulated_rows)
            log(f"Fetch complete, total rows: {total_rows}")
            break
        elif row_count == len(accumulated_rows):
            # If we didn't emit _any_ rows then we must have a group of rows with the
            # same key that is equal to, or larger than, the batch size. We cannot
            # handle this situation so we throw an error. (Given the sizes involved it
            # seems unlikely we could hit this in production.)
            raise AssertionError("`batch_size` too small to make progress")
        else:
            # Otherwise we empty the accumulator and fetch another batch
            accumulated_rows.clear()


def execute_with_retry_factory(
    connection, max_retries=0, retry_sleep=0, backoff_factor=1, log=lambda *_: None
):
    """
    Wraps the `execute` method of a `Connection` object in logic which retries on
    certain classes of error, using an exponential backoff strategy.

    In order to handle errors triggered while the results are being iterated, the
    wrapper consumes the results iterator returns the results as a list instead.
    """

    def execute_with_retry(*args, **kwargs):
        retries = 0
        next_sleep = retry_sleep

        while True:
            if retries > 0:
                log(f"Retrying query (attempt {retries} / {max_retries})")
            try:
                return list(connection.execute(*args, **kwargs))
            except (OperationalError, InternalError) as e:
                if retries >= max_retries:
                    raise
                retries += 1
                log(f"{e.__class__.__name__}: {e}")
                # Note that as we're running with DB-API-level AUTOCOMMIT isolation
                # level, this rollback should be purely internal to SQLAlchemy and
                # should have no effect on the database itself. For gory details see:
                # https://docs.sqlalchemy.org/en/20/core/connections.html#understanding-the-dbapi-level-autocommit-isolation-level
                log("Rolling back SQLAlchemy internal transaction state")
                connection.rollback()
                log(f"Waiting {next_sleep}s before retrying")
                time.sleep(next_sleep)
                next_sleep *= backoff_factor

    return execute_with_retry
