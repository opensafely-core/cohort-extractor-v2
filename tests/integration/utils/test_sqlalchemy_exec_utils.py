import pytest
import sqlalchemy
import sqlalchemy.orm

from ehrql.utils.sqlalchemy_exec_utils import fetch_table_in_batches


Base = sqlalchemy.orm.declarative_base()


class SomeTable(Base):
    __tablename__ = "some_table"
    pk = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=False)
    key = sqlalchemy.Column(sqlalchemy.Integer)
    foo = sqlalchemy.Column(sqlalchemy.String)


def test_fetch_table_in_batches_unique(engine):
    if engine.name == "in_memory":
        pytest.skip("SQL tests do not apply to in-memory engine")

    table_size = 15
    batch_size = 6

    table_data = [(i, i, f"foo{i}") for i in range(table_size)]

    engine.setup([SomeTable(pk=row[0], key=row[1], foo=row[2]) for row in table_data])

    table = SomeTable.__table__

    with engine.sqlalchemy_engine().connect() as connection:
        results = fetch_table_in_batches(
            connection.execute,
            table,
            table.c.key,
            key_is_unique=True,
            batch_size=batch_size,
        )
        results = list(results)

    assert results == table_data


def test_fetch_table_in_batches_nonunique(engine):
    if engine.name == "in_memory":
        pytest.skip("SQL tests do not apply to in-memory engine")

    batch_size = 6
    repeats = [1, 2, 3, 4, 5, 0, 5, 4, 3, 2, 1]
    keys = [key for key, n in enumerate(repeats) for _ in range(n)]
    table_data = [(i, key, f"foo{i}") for i, key in enumerate(keys)]

    engine.setup([SomeTable(pk=row[0], key=row[1], foo=row[2]) for row in table_data])

    table = SomeTable.__table__

    with engine.sqlalchemy_engine().connect() as connection:
        results = fetch_table_in_batches(
            connection.execute,
            table,
            table.c.key,
            key_is_unique=False,
            batch_size=batch_size,
        )
        results = sorted(results)

    assert results == table_data
