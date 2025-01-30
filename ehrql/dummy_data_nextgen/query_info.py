import dataclasses
from collections import defaultdict
from collections.abc import Mapping
from functools import cached_property, lru_cache

from ehrql.query_engines.in_memory import InMemoryQueryEngine
from ehrql.query_engines.in_memory_database import InMemoryDatabase, Rows
from ehrql.query_model.introspection import all_unique_nodes, get_table_nodes
from ehrql.query_model.nodes import (
    AggregateByPatient,
    Case,
    Column,
    Dataset,
    Function,
    InlinePatientTable,
    Node,
    SelectColumn,
    SelectPatientTable,
    SelectTable,
    TableSchema,
    Value,
    get_input_nodes,
    get_root_frame,
)
from ehrql.query_model.query_graph_rewriter import QueryGraphRewriter


@dataclasses.dataclass(unsafe_hash=True)
class ColumnInfo:
    """
    Captures information about a column as used in a particular dataset definition
    """

    name: str
    type: type  # NOQA: A003
    constraints: tuple = ()
    query: Node | None = None
    _values_used: set = dataclasses.field(default_factory=set, hash=False)

    @classmethod
    def from_column(cls, name, column, query):
        type_ = column.type_
        if hasattr(type_, "_primitive_type"):
            type_ = type_._primitive_type()
        return cls(
            name,
            type_,
            query=query,
            constraints=tuple(column.constraints),
        )

    def __post_init__(self):
        self._constraints_by_type = {type(c): c for c in self.constraints}

    def record_value(self, value):
        if hasattr(value, "_to_primitive_type"):
            value = value._to_primitive_type()
        self._values_used.add(value)

    @cached_property
    def values_used(self):
        return sorted(self._values_used)

    def get_constraint(self, type_):
        return self._constraints_by_type.get(type_)


@dataclasses.dataclass
class TableInfo:
    """
    Captures information about a table as used in a particular dataset definition
    """

    name: str
    has_one_row_per_patient: bool
    columns: dict[str, ColumnInfo] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_table(cls, table):
        return cls(
            name=table.name,
            has_one_row_per_patient=isinstance(table, SelectPatientTable),
        )

    @cached_property
    def table_node(self):
        """
        Return a query model table node whose schema contains just the subset of the
        original schema which is actually used in the query
        """
        cls = {False: SelectTable, True: SelectPatientTable}[
            self.has_one_row_per_patient
        ]
        schema = TableSchema(
            **{
                col_info.name: Column(col_info.type, constraints=col_info.constraints)
                for col_info in self.columns.values()
            }
        )
        return cls(self.name, schema=schema)


@dataclasses.dataclass
class QueryInfo:
    """
    Captures information about a dataset definition, including the specific tables and
    columns used and the values expected in those columns
    """

    tables: dict[str, TableInfo]
    population_table_names: list[str]
    other_table_names: list[str]

    @classmethod
    def from_dataset(cls, dataset):
        assert isinstance(dataset, Dataset)
        all_nodes = all_unique_nodes(dataset)
        by_type = get_nodes_by_type(all_nodes)

        tables = {
            # Create a TableInfo object …
            table.name: TableInfo.from_table(table)
            # … for every table used in the query (sorted for consistency)
            for table in sort_by_name(
                by_type[SelectTable] | by_type[SelectPatientTable]
            )
        }

        column_info_by_column: dict[SelectColumn, ColumnInfo] = {}

        # For every column used in the query (sorted for consistency) …
        for column in sort_by_name(by_type[SelectColumn]):
            table = get_root_frame(column.source)
            # We're only interested in "standard" tables here
            if isinstance(table, InlinePatientTable):
                continue
            elif isinstance(table, SelectTable | SelectPatientTable):
                pass
            else:
                assert False
            name = column.name
            table_info = tables[table.name]
            column_info = table_info.columns.get(name)
            if column_info is None:
                # … insert a ColumnInfo object into the appropriate table
                base_column = SelectColumn(source=table, name=column.name)

                specialized_query = specialize(dataset.population, base_column)

                # TODO: We should actually check whether it's a False value here and raise an
                # error if it is.
                if specialized_query is not None and is_value(specialized_query):
                    specialized_query = None
                if specialized_query is not None:
                    assert tuple(columns_for_query(specialized_query)) == (base_column,)
                column_info = ColumnInfo.from_column(
                    name,
                    table.schema.get_column(name),
                    query=specialized_query,
                )
                table_info.columns[name] = column_info
            # Record the ColumnInfo object associated with each SelectColumn node
            column_info_by_column[column] = column_info

        # Record values used in equality and substring comparisons
        for node in by_type[Function.EQ] | by_type[Function.StringContains]:
            # The query model in theory supports "1 == x" style comparisons (i.e.  with
            # the column on the RHS) but there's no way to generate such constructions
            # using ehrQL so we only bother handling the "x == 1" orientation here.
            if not (isinstance(node.lhs, SelectColumn) and isinstance(node.rhs, Value)):
                continue
            if column_info := column_info_by_column.get(node.lhs):
                column_info.record_value(node.rhs.value)

        # Record values used in containment comparisons
        for node in by_type[Function.In]:
            if not (isinstance(node.lhs, SelectColumn) and isinstance(node.rhs, Value)):
                continue
            if column_info := column_info_by_column.get(node.lhs):
                for value in node.rhs.value:
                    column_info.record_value(value)

        # Record which tables are used in determining population membership and which
        # are not
        population_table_names = {
            node.name for node in get_table_nodes(dataset.population)
        }

        other_table_names = tables.keys() - population_table_names

        return cls(
            tables=tables,
            population_table_names=sorted(population_table_names),
            other_table_names=sorted(other_table_names),
        )


def get_nodes_by_type(nodes):
    by_type = defaultdict(set)
    for node in nodes:
        by_type[type(node)].add(node)
    return by_type


def sort_by_name(iterable):
    return sorted(iterable, key=lambda i: i.name)


@lru_cache
def is_value(query):
    if query is None:
        return True
    elif isinstance(query, Value):
        return True
    else:
        children = get_input_nodes(query)
        return children and all(is_value(child) for child in children)


@lru_cache
def columns_for_query(query: Node):
    """Returns all columns referenced in a given query."""
    return frozenset(
        {
            subnode
            for subnode in all_unique_nodes(query)
            if isinstance(subnode, SelectColumn)
            and isinstance(
                subnode.source, SelectTable | SelectPatientTable | InlinePatientTable
            )
        }
    )


def specialize(query, column) -> Node | None:
    """Takes query and specialises it to one that only references column.
    Satisfying the resulting query is necessary but not in general sufficient
    to satisfy the source query.
    """
    assert len(columns_for_query(column)) == 1
    if is_value(query):
        return query
    match query:
        case Function.And(lhs=lhs, rhs=rhs):
            lhs = specialize(lhs, column)
            rhs = specialize(rhs, column)
            if lhs is None:
                return rhs
            if rhs is None:
                return lhs
            result = Function.And(lhs, rhs)
            assert len(columns_for_query(result)) <= 1
            return result
        case Function.Or(lhs=lhs, rhs=rhs):
            lhs = specialize(lhs, column)
            rhs = specialize(rhs, column)
            if lhs is None or rhs is None:
                return None
            result = Function.Or(lhs=lhs, rhs=rhs)
            assert len(columns_for_query(result)) <= 1
            return result

        # TODO: This could really use a nicer way of handling it.
        # All of them create some sort of follow on obligations though
        # that can only be handled by creating additional records,
        # so for this first pass generation of data we do need to
        # exclude them.
        case (
            AggregateByPatient.Count()
            | AggregateByPatient.CountDistinct()
            | AggregateByPatient.Exists()
        ):
            return None
        case (
            (
                Function.EQ(rhs=Case())
                | Function.NE(rhs=Case())
                | Function.LT(rhs=Case())
                | Function.GT(rhs=Case())
                | Function.LE(rhs=Case())
                | Function.GE(rhs=Case())
            ) as comp
        ) if column not in columns_for_query(comp.rhs):
            case_statement = comp.rhs
            if case_statement.default is None:
                rewritten = None
            else:
                rewritten = comp.__class__(lhs=comp.lhs, rhs=case_statement.default)
            for v in case_statement.cases.values():
                if v is None:
                    continue
                part = comp.__class__(lhs=comp.lhs, rhs=v)
                if rewritten is None:
                    rewritten = part
                else:
                    rewritten = Function.Or(rewritten, part)
            return specialize(rewritten, column)
        case (
            (
                Function.EQ(lhs=Case())
                | Function.NE(lhs=Case())
                | Function.LT(lhs=Case())
                | Function.GT(lhs=Case())
                | Function.LE(lhs=Case())
                | Function.GE(lhs=Case())
            ) as comp
        ) if column not in columns_for_query(comp.lhs):
            opposites: dict[type, type] = {
                Function.LT: Function.GT,
                Function.LE: Function.GE,
            }
            opposites.update([(v, k) for k, v in opposites.items()])
            assert len(opposites) == 4
            opposite_type = opposites.get(type(comp), type(comp))
            return specialize(opposite_type(lhs=comp.rhs, rhs=comp.lhs), column)
        case (
            (
                Function.EQ()
                | Function.NE()
                | Function.LT()
                | Function.GT()
                | Function.LE()
                | Function.GE()
            ) as comp
        ):
            lhs = specialize(comp.lhs, column)
            rhs = specialize(comp.rhs, column)
            if lhs is None or rhs is None:
                return None
            return type(comp)(lhs=lhs, rhs=rhs)
        case SelectColumn() as q:
            if column == q:
                assert len(columns_for_query(q)) == 1
                return q
            else:
                return None
        case _:
            fields = query.__dataclass_fields__
            specialized = {}
            for k in fields:
                v = getattr(query, k)
                if isinstance(v, Node):
                    v = specialize(v, column)
                    if v is None:
                        return None
                elif isinstance(v, Mapping):
                    items = list(v.items())
                    new_items = {}
                    for x, y in items:
                        x = specialize(x, column)
                        if x is None:
                            return None
                        y = specialize(y, column)
                        if y is None:
                            return None
                        new_items[x] = y
                    v = type(v)(new_items)
                else:
                    try:
                        values = list(v)
                    except TypeError:
                        pass
                    else:
                        new_values = []
                        for elt in values:
                            elt = specialize(elt, column)
                            if elt is None:
                                return None
                            new_values.append(elt)
                        v = type(v)(new_values)
                specialized[k] = v
            return type(query)(**specialized)


def filter_values(query, values):
    """Returns the subset of `values` that can appear in a result for `query`.

    `query` may only refer to a single column (which `values` will be interpreted
    as belonging to).
    """
    (column,) = columns_for_query(query)
    source = get_root_frame(column)
    column_name = column.name
    simplified_schema = TableSchema(
        dummy_column_for_sorting=Column(int),
        **{column_name: source.schema.get_column(column_name)},
    )
    fake_table = type(source)(name=source.name, schema=simplified_schema)
    replacement_column = SelectColumn(source=fake_table, name=column_name)
    database = InMemoryDatabase(
        {fake_table: [(i, i, v) for i, v in enumerate(values, 1)]}
    )
    engine = InMemoryQueryEngine(database)

    rewriter = QueryGraphRewriter()
    rewriter.replace(column, replacement_column)

    rows = list(
        engine.get_results(
            Dataset(population=rewriter.rewrite(query), variables={}, events={}),
        )
    )

    # If we're picking from an event frame we may get a Rows object rather than
    # a value back. We only care about the distinct values that can be returned
    # here, so we just care about what values are in the rows.
    result = []
    for row in rows:
        value = database.tables[fake_table.name][column_name][row.patient_id]
        if isinstance(value, Rows):
            result.extend(value.values())
        else:
            result.append(value)
    for v in result:
        assert not isinstance(v, Rows)

    return result
