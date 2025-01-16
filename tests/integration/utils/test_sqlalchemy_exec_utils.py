import pytest
import sqlalchemy
import sqlalchemy.orm

from ehrql.utils.sqlalchemy_exec_utils import fetch_table_in_batches


Base = sqlalchemy.orm.declarative_base()


class SomeTable(Base):
    __tablename__ = "some_table"
    pk = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    foo = sqlalchemy.Column(sqlalchemy.String)


def test_fetch_table_in_batches_unique(engine):
    if engine.name == "in_memory":
        pytest.skip("SQL tests do not apply to in-memory engine")

    table_size = 15
    batch_size = 6

    table_data = [(i, f"foo{i}") for i in range(table_size)]

    engine.setup([SomeTable(pk=row[0], foo=row[1]) for row in table_data])

    table = SomeTable.__table__

    with engine.sqlalchemy_engine().connect() as connection:
        results = fetch_table_in_batches(
            connection.execute,
            table,
            table.c.pk,
            key_is_unique=True,
            batch_size=batch_size,
        )
        results = list(results)

    assert results == table_data
