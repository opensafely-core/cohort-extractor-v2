"""
Apply modifications to the query graph which make it easier to work with or allow us to
generate more efficient SQL.

This involves adding new kinds of nodes to the query model. However we deliberately
define these nodes outside of the core query_model module because we're trying to
maintain separation of three types of concern:

    1. capturing the semantics of the query (which is the query model's job);
    2. worrying about expressiveness and ease of use (which is ehrQL's job);
    3. worrying about efficient execution (which is the query engines' job).

The transformations applied here are all about efficient execution, and therefore we
want to keep them separate from the core query model classes.
"""
import copy
from collections.abc import MutableSet
from typing import Any

from databuilder.query_model import (
    Case,
    Function,
    PickOneRowPerPatient,
    SelectColumn,
    Sort,
    Value,
    all_nodes,
    get_input_nodes,
    get_series_type,
)


class PickOneRowPerPatientWithColumns(PickOneRowPerPatient):
    # The actual type here is `frozenset[Series]` but our type-checking code can't
    # currently handle the mixed type sets we get here (e.g. `Series[bool]` and
    # `Series[int]`). We've decided that, as this is an internal class not part of the
    # public API, it's not worth complicating the type-checking code for this use case.
    selected_columns: Any


def apply_transforms(variables):
    # For algorithmic ease we're going to be mutating the query objects. Since the QM
    # graph is a notionally immutable structure consisting of "frozen" dataclasses, we need
    # to do that carefully. In particular:
    #
    # 1. We copy the data that is passed in so that callers don't observe side-effects.
    # 2. We copy the results on the way out to rectify the state of containers that depend
    #    on object hashes which may have changed unexpectedly (specifically the frozenset used
    #    to hold selected columns).
    # 3. When we store QM nodes in equality/hash-sensitive containers during this manipulation
    #    we use customized versions of those containers which ignore the __eq__() and
    #    __hash__() implementations provided by dataclasses.
    variables = copy.deepcopy(variables)
    nodes = all_nodes_from_variables(variables)
    add_selected_columns_to_pick_row(nodes)
    include_all_selected_columns_in_sorts(nodes)

    variables = copy.deepcopy(variables)  # see comment above

    return variables


def add_selected_columns_to_pick_row(nodes):
    """
    Replace instances of `PickOneRowPerPatient` with `PickOneRowPerPatientWithColumns`
    which track the columns that are going to be selected and allow us to generate the
    appropriate query
    """
    for node in nodes:
        if not isinstance(node, PickOneRowPerPatient):
            continue

        # Get the name of any columns selected from this node
        dependers = get_dependers(node, nodes)
        column_names = {c.name for c in dependers if isinstance(c, SelectColumn)}

        # Record the selected columns.
        selected_columns = frozenset(
            SelectColumn(node.source, name) for name in column_names
        )

        # Modify the node in-place to have the new type
        force_setattr(node, "__class__", PickOneRowPerPatientWithColumns)
        force_setattr(node, "selected_columns", selected_columns)


def include_all_selected_columns_in_sorts(nodes):
    """
    We want to ensure that results are consistent when picking the first or last of a sorted
    frame, even when the sorting specified in the variable definition isn't sufficient to completely
    specify the order. To that end we add extra sorts for each column that is ultimately going to
    be returned from the sorted table.

    This has the additional benefit that the order is the same between different DBMSes, which
    doesn't help our users but makes testing a bit easier.
    """
    for node in nodes:
        if not isinstance(node, PickOneRowPerPatientWithColumns):
            continue

        sorts = get_immediate_sorts(node)

        # Get the name of any columns selected from this node
        column_names = {c.name for c in node.selected_columns}

        # We only add sorts for columns which don't already have sorts specified.
        #
        # Note that we only consider "direct" column sorts, not those where we're sorting on the
        # result of a calculation on a column. We do that because 1) extracting the referenced columns
        # from within a complex expression is complicated and 2) such calculations might return the
        # same value for distinct column values and so not completely determine the order. Adding
        # the sort in cases where the result of the calculation would have completely determined the
        # order can never change the results and is, at worst, a slight inefficiency.
        existing_sorted_column_names = {
            sort.sort_by.name
            for sort in sorts
            if isinstance(sort.sort_by, SelectColumn)
        }
        sorts_to_add = column_names - existing_sorted_column_names

        # We introduce an arbitrary canonical order for the added sorts (lexically by column name) so
        # that the sort order is stable.
        ordered_sorts_to_add = sorted(sorts_to_add)

        # The new sorts come below the existing ones in the stack -- meaning that they have lower
        # priority and are only used to disambiguate between rows for which the sort order would
        # otherwise be undefined.
        lowest_sort = sorts[-1]
        for column_name in ordered_sorts_to_add:
            column = SelectColumn(lowest_sort.source, column_name)
            new_sort = Sort(source=lowest_sort.source, sort_by=make_sortable(column))
            force_setattr(lowest_sort, "source", new_sort)
            force_setattr(lowest_sort.sort_by, "source", new_sort)
            lowest_sort = new_sort


def get_immediate_sorts(node):
    """
    The source of a PickOneRowPerPatient[WithColumns] is always a Sort, which itself may be
    stacked on top of further Sort nodes. Return just those Sort nodes, from top to bottom.
    """
    sorts = []
    source = node.source
    while isinstance(source, Sort):
        sorts.append(source)
        source = source.source
    return sorts


def make_sortable(col):
    if get_series_type(col) == bool:
        # Some databases can't sort booleans (including SQL Server), so we map them to integers
        return Case(
            cases={col: Value(2), Function.Not(col): Value(1)}, default=Value(0)
        )
    return col


def all_nodes_from_variables(variables):
    nodes = IdentitySet()  # see comment in apply_transforms()
    for query in variables.values():
        query_nodes = all_nodes(query)
        for query_node in query_nodes:
            nodes.add(query_node)
    return nodes


def get_dependers(node, nodes):
    """
    Return all members of `nodes` that have `node` as an input
    """
    dependers = []
    for other_node in nodes:
        if node in get_input_nodes(other_node):
            dependers.append(other_node)
    return dependers


class IdentitySet(MutableSet):
    """
    This set considers objects equal if and only if they are identical, even if they
    have overridden __eq__() and __hash__().

    Adapted with gratitude from https://stackoverflow.com/a/17039643/400467.
    """

    def __init__(self, seq=()):
        self._set = {Ref(v) for v in seq}

    def add(self, value):
        self._set.add(Ref(value))

    def discard(self, value):
        self._set.discard(Ref(value))

    def __contains__(self, value):
        return Ref(value) in self._set

    def __len__(self):
        return len(self._set)

    def __iter__(self):
        return (ref.referent for ref in self._set)

    def __repr__(self):
        return f"{type(self).__name__}({list(self)})"


class Ref:
    def __init__(self, referent):
        self.referent = referent

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.referent is other.referent

    def __hash__(self):
        return id(self.referent)


# We can't modify attributes on frozen dataclass instances in the normal way, so we have
# to use this
force_setattr = object.__setattr__
