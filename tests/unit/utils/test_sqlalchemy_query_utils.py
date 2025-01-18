import pytest
import sqlalchemy
from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.sql.visitors import iterate

from ehrql.utils.sqlalchemy_query_utils import (
    CreateTableAs,
    GeneratedTable,
    InsertMany,
    clause_as_str,
    get_setup_and_cleanup_queries,
    is_predicate,
)
from ehrql.utils.string_utils import strip_indent


table = sqlalchemy.Table(
    "some_table",
    sqlalchemy.MetaData(),
    sqlalchemy.Column("i", type_=sqlalchemy.Integer()),
    sqlalchemy.Column("b", type_=sqlalchemy.Boolean()),
)

integer = table.c.i
boolean = table.c.b


@pytest.mark.parametrize(
    "expected,clause",
    [
        # All comparisons are predicates
        (True, integer == integer),
        (True, integer >= integer),
        (True, integer > integer),
        (True, integer < integer),
        (True, integer <= integer),
        (True, integer != integer),
        # As are boolean operations
        (True, boolean | boolean),
        (True, boolean & boolean),
        (True, ~boolean),
        # And combined boolean operations
        (True, ~(boolean & boolean)),
        (True, ~(boolean | boolean)),
        (True, ~boolean | ~boolean),
        (True, ~boolean & ~boolean),
        # And null checks
        (True, integer.is_(None)),
        (True, integer.is_not(None)),
        #
        # But not direct references to boolean columns
        (False, boolean),
        # Or other, non-boolean, binary operations
        (False, integer + integer),
        # Or arbitrary function calls
        (False, sqlalchemy.func.log10(integer)),
    ],
)
def test_is_predicate(expected, clause):
    assert is_predicate(clause) == expected, f"Expected {expected}: {clause}"


def test_get_setup_and_cleanup_queries_basic():
    # Make a temporary table
    temp_table = _make_temp_table("temp_table", "foo")
    temp_table.setup_queries.append(
        temp_table.insert().values(foo="bar"),
    )

    # Select something from it
    query = sqlalchemy.select(temp_table.c.foo)

    # Check that we get the right queries in the right order
    assert _queries_as_strs([query]) == [
        "CREATE TABLE temp_table (\n\tfoo NULL\n)",
        "INSERT INTO temp_table (foo) VALUES (:foo)",
        "SELECT temp_table.foo \nFROM temp_table",
        "DROP TABLE temp_table",
    ]


def test_get_setup_and_cleanup_queries_nested():
    # Make a temporary table
    temp_table1 = _make_temp_table("temp_table1", "foo")
    temp_table1.setup_queries.append(
        temp_table1.insert().values(foo="bar"),
    )

    # Make a second temporary table ...
    temp_table2 = _make_temp_table("temp_table2", "baz")
    temp_table2.setup_queries.append(
        # ... populated by a SELECT query against the first table
        temp_table2.insert().from_select(
            [temp_table2.c.baz], sqlalchemy.select(temp_table1.c.foo)
        ),
    )

    # Select something from the second table
    query = sqlalchemy.select(temp_table2.c.baz)

    # Check that we create and drop the temporary tables in the right order
    assert _queries_as_strs([query]) == [
        "CREATE TABLE temp_table1 (\n\tfoo NULL\n)",
        "INSERT INTO temp_table1 (foo) VALUES (:foo)",
        "CREATE TABLE temp_table2 (\n\tbaz NULL\n)",
        "INSERT INTO temp_table2 (baz) SELECT temp_table1.foo \nFROM temp_table1",
        "SELECT temp_table2.baz \nFROM temp_table2",
        "DROP TABLE temp_table2",
        "DROP TABLE temp_table1",
    ]


def test_get_setup_and_cleanup_queries_multiple():
    # Make a temporary table
    temp_table1 = _make_temp_table("temp_table1", "foo")
    temp_table1.setup_queries.append(
        temp_table1.insert().values(foo="bar"),
    )

    # Make a second temporary table ...
    temp_table2 = _make_temp_table("temp_table2", "baz")
    temp_table2.setup_queries.append(
        # ... populated by a SELECT query against the first table
        temp_table2.insert().from_select(
            [temp_table2.c.baz], sqlalchemy.select(temp_table1.c.foo)
        ),
    )

    # Select something from the second table
    query_1 = sqlalchemy.select(temp_table2.c.baz)

    # Select something from the first table
    query_2 = sqlalchemy.select(temp_table1.c.foo)

    # Check that we create and drop the temporary tables in the right order
    assert _queries_as_strs([query_1, query_2]) == [
        "CREATE TABLE temp_table1 (\n\tfoo NULL\n)",
        "INSERT INTO temp_table1 (foo) VALUES (:foo)",
        "CREATE TABLE temp_table2 (\n\tbaz NULL\n)",
        "INSERT INTO temp_table2 (baz) SELECT temp_table1.foo \nFROM temp_table1",
        "SELECT temp_table2.baz \nFROM temp_table2",
        "SELECT temp_table1.foo \nFROM temp_table1",
        "DROP TABLE temp_table2",
        "DROP TABLE temp_table1",
    ]


def _make_temp_table(name, *columns):
    table = GeneratedTable(
        name, sqlalchemy.MetaData(), *[sqlalchemy.Column(c) for c in columns]
    )
    table.setup_queries = [
        sqlalchemy.schema.CreateTable(table),
    ]
    table.cleanup_queries = [sqlalchemy.schema.DropTable(table)]
    return table


def _queries_as_strs(queries):
    setup_queries, cleanup_queries = get_setup_and_cleanup_queries(queries)
    return (
        [str(q).strip() for q in setup_queries]
        + [str(q).strip() for q in queries]
        + [str(q).strip() for q in cleanup_queries]
    )


def test_clause_as_str():
    table = sqlalchemy.table("foo", sqlalchemy.Column("bar"))
    query = sqlalchemy.select(table.c.bar).where(table.c.bar > 100)
    query_str = clause_as_str(query, DefaultDialect())
    assert query_str == "SELECT foo.bar \nFROM foo \nWHERE foo.bar > 100"


def test_clause_as_str_with_insert_many():
    table = sqlalchemy.Table(
        "t",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("i", sqlalchemy.Integer()),
        sqlalchemy.Column("s", sqlalchemy.String()),
    )
    statement = InsertMany(
        table,
        [
            (1, "a"),
            (2, "b"),
            (3, "c"),
        ],
    )

    query_str = clause_as_str(statement, DefaultDialect())
    assert query_str == strip_indent(
        """
        INSERT INTO t (i, s) VALUES (1, 'a');
        INSERT INTO t (i, s) VALUES (2, 'b');
        INSERT INTO t (i, s) VALUES (3, 'c')
        """
    )


def test_insert_many_compile():
    table = sqlalchemy.Table(
        "t",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("i", sqlalchemy.Integer()),
        sqlalchemy.Column("s", sqlalchemy.String()),
    )
    statement = InsertMany(
        table,
        [
            (1, "a"),
            (2, "b"),
            (3, "c"),
        ],
    )

    query_str = statement.compile(dialect=DefaultDialect())
    assert str(query_str).strip() == "INSERT INTO t (i, s) VALUES (:i, :s)"


def test_get_setup_and_cleanup_queries_with_insert_many():
    # Confirm that the InsertMany class acts enough like a SQLAlchemy ClauseElement for
    # our setup/cleanup code to work with it
    table = sqlalchemy.Table(
        "t",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("i", sqlalchemy.Integer()),
    )
    statement = InsertMany(table, rows=[])
    setup_cleanup = get_setup_and_cleanup_queries([statement])
    assert setup_cleanup == ([], [])


def test_generated_table_from_query():
    query = sqlalchemy.select(
        sqlalchemy.literal(1).label("number"),
        sqlalchemy.literal("a").label("string"),
    )
    table = GeneratedTable.from_query("some_table", query, schema="some_schema")
    assert str(sqlalchemy.schema.CreateTable(table)).strip() == (
        "CREATE TABLE some_schema.some_table (\n\tnumber INTEGER, \n\tstring VARCHAR\n)"
    )


def test_generated_table_from_query_with_metadata():
    metadata = sqlalchemy.MetaData()
    query = sqlalchemy.select(sqlalchemy.literal(1).label("number"))
    table = GeneratedTable.from_query("some_table", query, metadata=metadata)
    assert table.metadata is metadata


def test_create_table_as():
    query = sqlalchemy.select(
        sqlalchemy.literal(1).label("number"),
        sqlalchemy.literal("a").label("string"),
    )
    table = sqlalchemy.table("test")
    create_table = CreateTableAs(table, query)

    assert str(create_table) == (
        "CREATE TABLE test AS SELECT :param_1 AS number, :param_2 AS string"
    )


def test_create_table_as_can_be_iterated():
    # If we don't define the `get_children()` method on `CreateTableAs` we won't get an
    # error when attempting to iterate the resulting element structure: it will just act
    # as a leaf node. But as we rely heavily on query introspection we need to ensure we
    # can iterate over query structures.
    query = sqlalchemy.select(
        sqlalchemy.literal(1).label("number"),
        sqlalchemy.literal("a").label("string"),
    )
    table = sqlalchemy.table("test")
    create_table = CreateTableAs(table, query)

    # Check that the original elements show up when iterated
    assert any([e is table for e in iterate(create_table)])
    assert any([e is query for e in iterate(create_table)])


# The below tests exercise obscure corners of SQLAlchemy which used to have bugs that we
# had to workaroud. These have been fixed in SQLAlchemy 2 but we retain the tests for
# their warm fuzzy value.


def test_clause_as_str_with_create_index_on_sqlite():
    # Setting `literal_binds=True` (as we do in `clause_as_str()`) while compiling
    # CreateIndex used to blow up with a TypeError in the SQLite dialect. We confirm
    # that this is no longer the case.
    table = sqlalchemy.Table("foo", sqlalchemy.MetaData(), sqlalchemy.Column("bar"))
    index = sqlalchemy.Index(None, table.c.bar)
    create_index = sqlalchemy.schema.CreateIndex(index)
    dialect = SQLiteDialect_pysqlite(paramstyle="named")

    query_str = clause_as_str(create_index, dialect)
    assert query_str == "CREATE INDEX ix_foo_bar ON foo (bar)"


def test_clause_as_str_with_expanding_bindparameter_and_bind_expression():
    # This exercises an obscure corner of SQLAlchemy which used to be buggy: using
    # "literal_binds" to compile a clause which combines expanding BindParameters with a
    # bind expression.

    # Create a custom type with a "bind_expression", see:
    # https://docs.sqlalchemy.org/en/14/core/type_api.html#sqlalchemy.types.TypeEngine.bind_expression
    class CustomType(sqlalchemy.types.TypeDecorator):
        impl = sqlalchemy.types.String
        cache_ok = True

        # This means that every time we reference a value of this type it gets wrapped
        # in a function call
        def bind_expression(self, bindvalue):
            return sqlalchemy.func.upper(bindvalue)

    table = sqlalchemy.Table(
        "tbl", sqlalchemy.MetaData(), sqlalchemy.Column("col", CustomType())
    )

    # With a single value comparison like `==` we can compile this to either a
    # parameterised string, or a string containing literals and it works as expected
    equality_expr = table.c.col == "abc"
    assert (
        str(equality_expr.compile(compile_kwargs={"render_postcompile": True}))
        == "tbl.col = upper(:col_1)"
    )
    assert (
        str(equality_expr.compile(compile_kwargs={"literal_binds": True}))
        == "tbl.col = upper('abc')"
    )

    # With a multi-valued comparison like `IN` we get an "expanding" BindParameter, see:
    # https://docs.sqlalchemy.org/en/14/core/sqlelement.html#sqlalchemy.sql.expression.bindparam.params.expanding
    contains_expr = table.c.col.in_(["abc", "def"])
    # We can compile this to a parameterised string and get the expected output
    assert (
        str(contains_expr.compile(compile_kwargs={"render_postcompile": True}))
        == "tbl.col IN (upper(:col_1_1), upper(:col_1_2))"
    )

    # Attempting to compile it with parameters replaced by string literals used to blow
    # up with:
    #
    #     AttributeError("'NoneType' object has no attribute 'group'")
    #
    # We confirm it no longer does.
    compiled = clause_as_str(contains_expr, DefaultDialect())
    assert compiled == "tbl.col IN (upper('abc'), upper('def'))"


def test_clause_as_string_with_repeated_expanding_bindparameter():
    # Previously we would blow up with a KeyError when the same "expanding" (i.e.
    # multi-valued) BindParameter was used more than once within a query
    table = sqlalchemy.Table(
        "tbl",
        sqlalchemy.MetaData(),
        sqlalchemy.Column("col_1", sqlalchemy.Integer()),
        sqlalchemy.Column("col_2", sqlalchemy.Integer()),
    )
    multi_valued = sqlalchemy.literal([1, 2])
    clause = table.c.col_1.in_(multi_valued) | table.c.col_2.in_(multi_valued)
    compiled = clause_as_str(clause, DefaultDialect())
    assert compiled == "tbl.col_1 IN (1, 2) OR tbl.col_2 IN (1, 2)"
