import collections
import graphlib
from itertools import islice

import sqlalchemy
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import (
    AsBoolean,
    BinaryExpression,
    BooleanClauseList,
    UnaryExpression,
    operators,
)
from sqlalchemy.sql.expression import ClauseElement, Executable


def is_predicate(clause):
    """
    Some boolean expressions are guaranteed to be boolean-typed by virtue of their
    syntax, e.g.

      a == b

    Others happen to be boolean-typed by virtue of the columns they use, but you can't
    tell just by looking at them, e.g.

      some_table.some_boolean_column

    We call the former class "predicates".

    While some databases treat both classes of boolean expression as equivalent, others
    have rules about which syntactic contexts accept predicates and which accept boolean
    expressions. As the two are semantically equivalent we can always convert from one
    to other, but we need to know which is which so we can apply the appropriate
    conversion rules.
    """
    if isinstance(clause, BooleanClauseList | AsBoolean):
        return True
    if isinstance(clause, BinaryExpression):
        return clause._is_implicitly_boolean
    # We have to identify `NOT ...` expressions by the operator they use
    if isinstance(clause, UnaryExpression) and clause.operator is operators.inv:
        return True
    return False


class GeneratedTable(sqlalchemy.Table):
    """
    This wraps a standard SQLAlchemy Table and adds a pair of extra attributes
    which are a sequence of queries needed to create and populate this table and a
    sequence (possibly empty) of queries needed to clean it up.

    This provides a generic mechanism for constructing "multi-step" queries i.e. queries
    that require creating intermediate objects before fetching their results. These
    intermediate objects could be temporary tables, persistent tables, views, or
    anything else so long as it functions syntactically as a table.
    """

    setup_queries = ()
    cleanup_queries = ()

    @classmethod
    def from_query(cls, name, query, metadata=None, **kwargs):
        """
        Create a GeneratedTable whose column structure matches that of the supplied query
        """
        if metadata is None:
            metadata = sqlalchemy.MetaData()
        columns = [
            sqlalchemy.Column(c.name, c.type, key=c.key) for c in query.selected_columns
        ]
        return cls(name, metadata, *columns, **kwargs)


def get_setup_and_cleanup_queries(queries):
    """
    Given a list of SQLAlchemy queries find all GeneratedTables embeded in them and
    return a pair:

        setup_queries, cleanup_queries

    which are the combination of all the setup and cleanup queries from those
    GeneratedTables in the correct order for execution.
    """
    # GeneratedTables can be arbitrarily nested in that their setup queries can
    # themselves contain references to GeneratedTables and so on. We need to
    # recursively unpack these and get them in the right order so that each query is
    # only executed after its dependencies have been executed.
    #
    # Fortunately, Python's graphlib can do most of the work for us here. We just need to
    # give it a sequence of pairs of tables (A, B) indicating that A depends on B and it
    # returns a suitable ordering over the tables.
    sorter = graphlib.TopologicalSorter()
    for parent_table, table in get_generated_table_dependencies(queries):
        # A parent_table of None indicates a root table (i.e. one with no dependants) so
        # we record its existence without specifying any dependencies
        if parent_table is None:
            sorter.add(table)
        # An oddity of the GeneratedTable class is that instances generally hold a
        # reference to themselves: one of the setup queries for table X will often be
        # "create a table with the structure given by X". We ignore this apparent
        # (though not actual) circularity.
        elif parent_table is table:
            pass
        # Otherwise we record the dependency between the two tables
        else:
            sorter.add(parent_table, table)

    # Tim Peters requests that you hold his beer ...
    tables = list(sorter.static_order())

    setup_queries = flatten_iter(t.setup_queries for t in tables)
    # Concatenate cleanup queries into one list, but in reverse order to that which we
    # created them in. This means that if there are any database-level dependencies
    # between the tables (e.g. if one is a materialized view over another) then we don't
    # risk errors by trying to delete objects which still have dependents.
    cleanup_queries = flatten_iter(t.cleanup_queries for t in reversed(tables))

    return setup_queries, cleanup_queries


def get_generated_table_dependencies(queries, parent_table=None, seen_tables=None):
    """
    Recursively find all GeneratedTable objects referenced by any query in `queries` and
    yield as pairs of dependencies:

        table_X, table_Y_which_is_referenced_by_X

    Note that the same table may appear multiple times in this sequence.
    """
    if seen_tables is None:
        seen_tables = set()

    for query in queries:
        for table in get_generated_tables(query):
            yield parent_table, table
            # Don't recurse into the same table twice
            if table not in seen_tables:
                seen_tables.add(table)
                child_queries = [*table.setup_queries, *table.cleanup_queries]
                yield from get_generated_table_dependencies(
                    child_queries, parent_table=table, seen_tables=seen_tables
                )


def get_generated_tables(clause):
    """
    Return any GeneratedTable objects directly referenced by a SQLAlchemy ClauseElement
    """
    return [elem for elem in iterate_unique(clause) if isinstance(elem, GeneratedTable)]


def flatten_iter(nested_iters):
    return [i for sub_iter in nested_iters for i in sub_iter]


def clause_as_str(clause, dialect):
    """
    Return a SQL clause as a string in the supplied SQL dialect with any included
    parameters interpolated in
    """
    compiled = clause.compile(
        dialect=dialect,
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled).strip()


def iterate_unique(clause):
    """
    Iterate over all unique query elements referenced by `clause`

    This is almost a verbatim copy of `sqlalchemy.sql.visitors.iterate()` with the
    difference that this keeps track of which elements have already been seen and avoids
    recursing into them again. For certain query structures this can make a huge
    difference to how long it takes to retrieve all the elements.

    Original code from:
    https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0_0/lib/sqlalchemy/sql/visitors.py#L829-L867

    Copyright (C) 2005-2023 the SQLAlchemy authors and contributors

    This function is part of SQLAlchemy and is released under the MIT License:
    https://www.opensource.org/licenses/mit-license.php
    """
    yield clause
    children = clause.get_children()

    if not children:
        return

    stack = collections.deque([children])
    seen = set()
    while stack:
        t_iterator = stack.popleft()
        for t in t_iterator:
            # Some SQLAlchemy objects overload equality so they aren't safe to use
            # directly in sets but we can track them by ID
            key = id(t)
            if key not in seen:
                seen.add(key)
                yield t
                stack.append(t.get_children())


class InsertMany:
    """
    Wraps up the query "insert this iterator of rows into this table" so that we can
    execute it in the most efficient way possible, without the caller having to worry
    about what that might be.

    Acts enough like a SQLAlchemy ClauseElement for our purposes.
    """

    # The batch_size here doesn't make a huge difference as SQLAlchemy does its own
    # internal batching optimisied for the specific database dialect. It just needs to
    # be big enough that it gives SQLAlchemy's batching enough to work with, but not so
    # big that we need to worry about memory consumption.
    def __init__(self, table, rows, batch_size=10000):
        self.table = table
        self.rows = rows
        self.batch_size = batch_size

    def get_children(self):
        return [self.table]

    # Called when the clause is executed
    def _execute_on_connection(self, connection, distilled_params, execution_options):
        assert not distilled_params, "Cannot supply parameters to InsertMany clause"
        insert_statement = self.table.insert()
        keys = self.table.columns.keys()
        # SQLAlchemy's insert-multiple-rows interface wants rows supplied as dicts
        # rather than tuples
        params = map(lambda values: dict(zip(keys, values)), self.rows)
        while params_batch := list(islice(params, self.batch_size)):
            connection.execute(
                insert_statement,
                params_batch,
                execution_options=execution_options,
            )

    def compile(self, *args, **kwargs):  # NOQA: A003
        insert_statement = self.table.insert()
        # If we're not trying to render a statement with literal values instead of
        # parameters then we just pass directly through to the default `compile()`
        # method
        if not (
            "compile_kwargs" in kwargs and kwargs["compile_kwargs"].get("literal_binds")
        ):
            return insert_statement.compile(*args, **kwargs)
        # If we *are* trying to render with literal values then things are bit more
        # tricky because there's no direct parallel to multi-row inserts in plain
        # SQL-as-text. So instead we compile a multi-statement string which does the
        # same thing.
        sql = []
        for row in self.rows:
            bound_insert = insert_statement.values(row)
            compiled = bound_insert.compile(*args, **kwargs)
            sql.append(str(compiled).strip())
        # Note, we're returning a string here, rather than a CompiledSQL object. This
        # works fine for our purposes. We can consider doing something more complicated
        # if the need arises.
        return ";\n".join(sql)


class CreateTableAs(Executable, ClauseElement):
    inherit_cache = True

    def __init__(self, table, selectable):
        self.table = table
        self.selectable = selectable

    def get_children(self):
        return (self.table, self.selectable)


@compiles(CreateTableAs)
def visit_create_table_as(element, compiler, **kw):
    return "CREATE TABLE {} AS {}".format(
        compiler.process(element.table, asfrom=True, **kw),
        compiler.process(element.selectable, asfrom=True, **kw),
    )
