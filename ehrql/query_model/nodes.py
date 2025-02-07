import dataclasses
import typing
from collections.abc import Container, Iterable, Iterator, Mapping, Set
from datetime import date
from enum import Enum
from functools import cache, singledispatch
from types import GenericAlias
from typing import Any, TypeVar

from ehrql.codes import BaseCode
from ehrql.query_model.table_schema import Column, Constraint, TableSchema
from ehrql.utils.typing_utils import get_typespec, get_typevars, type_matches


# The below classes and functions are the public API surface of the query model
__all__ = [
    "Node",
    "Series",
    "Value",
    "Parameter",
    "SelectTable",
    "SelectPatientTable",
    "InlinePatientTable",
    "SelectColumn",
    "Filter",
    "Sort",
    "PickOneRowPerPatient",
    "Position",
    "AggregateByPatient",
    "Function",
    "Case",
    "Column",
    "Constraint",
    "TableSchema",
    "ValidationError",
    "DomainMismatchError",
    "TypeValidationError",
    "InvalidSortError",
    "PatientDomainError",
    "Dataset",
    "has_one_row_per_patient",
    "has_many_rows_per_patient",
    "get_series_type",
    "get_domain",
    "get_input_nodes",
    "get_root_frame",
]


#
# VALUE TYPES
#


# TypeVars so we can enforce that e.g. comparison functions take two values of the same
# type without specifying what that type has to be
T = TypeVar("T")
Numeric = TypeVar("Numeric", int, float)
Comparable = TypeVar("Comparable", int, float, str, date, BaseCode)


class Position(Enum):
    FIRST = "first"
    LAST = "last"

    def __repr__(self):
        # Gives us `self == eval(repr(self))` as for dataclasses
        return f"{self.__class__.__name__}.{self.name}"


# BASIC QUERY MODEL TYPES
#
# The Query Model consists of operations on "frames" and "series". A frame is a table-like
# thing that has rows and columns, and a series is a column-like thing that contains a
# sequence of values. Frames can be created from SQL tables, and then various filtering,
# transformation and sorting operations can be applied to produce new frames. Likewise,
# a series can be created from a SQL column and then transformed and combined with
# others to produce new series.
#
# Central to the Query Model design is that these frames and series have an additional
# property called their "dimension": do they contain at most one row per patient, or
# might they contain many rows?


class Node:
    "Abstract base class for all objects in the Query Model"

    def __init_subclass__(cls, **kwargs):
        # This looks pointless, but `dataclass` overwrites inherited `__hash__` methods
        # so we need this to be an explictly defined method
        cls.__hash__ = cls.__hash__
        # All nodes in the query model are frozen dataclasses
        dataclasses.dataclass(cls, frozen=True)

    def __hash__(self):
        # Calculating the hash of an object requires recursively calculating the hashes
        # of its children. In a deeply nested query graph this can take some time and,
        # given how frequently `__hash__()` is called, this can end up completely
        # dominating ehrQL's execution time. Given that these are immutable
        # objects we can cache the hash value instead of recalcuting it each time.
        try:
            return self.__hash__cache
        except AttributeError:
            pass
        values = [getattr(self, field.name) for field in dataclasses.fields(self)]
        # We use dicts in several places in the query model and although they are not
        # immutable we pinky-promise not to mutate them and therefore want to make them
        # hashable. The below recipe is based on a recommendation by Raymond Hettinger:
        # https://stackoverflow.com/a/16162138
        hashable_values = tuple(
            v if not isinstance(v, dict) else (frozenset(v), frozenset(v.values()))
            for v in values
        )
        hash_value = hash(hashable_values)
        object.__setattr__(self, "__hash__cache", hash_value)
        return hash_value

    def __post_init__(self):
        # validate the things which have to be checked dynamically
        validate_node(self)


class Frame(Node): ...


class Series(Node):
    # Series have an "inner" type denoting the type of value they contain e.g
    # `Series[int]`. The below method generates generic aliases for these types when
    # they are referenced. We cache them so that multiple references always return the
    # same type object.
    @classmethod
    @cache
    def __class_getitem__(cls, type_):
        return GenericAlias(cls, (type_,))


class OneRowPerPatientFrame(Frame): ...


class ManyRowsPerPatientFrame(Frame): ...


class OneRowPerPatientSeries(Series): ...


class ManyRowsPerPatientSeries(Series): ...


# A frame built from a collection of named series, at least one of which must be a
# ManyRowsPerPatientSeries
class SeriesCollectionFrame(ManyRowsPerPatientFrame):
    members: Mapping[str, Series[Any]]


# Specifies the data to be extracted
class Dataset(OneRowPerPatientFrame):
    # Predicate which defines membership of the dataset
    population: Series[bool]
    # Collection of named OneRowPerPatientSeries objects
    variables: Mapping[str, Series[Any]]
    # Collection of named "event tables" which are themselves collections of named
    # ManyRowsPerPatientSeries objects
    events: Mapping[str, SeriesCollectionFrame]


# A OneRowPerPatientSeries which is the result of aggregating one or more
# ManyRowsPerPatientSeries
class AggregatedSeries(OneRowPerPatientSeries): ...


# OPERATIONS
#
# Operations indicate the kind of thing they return by subclassing one of the basic
# types above.


# `Value` wraps a single static value in a one-row-per-patient series which just has
# that value for every patient. This simplifies the signature of all other operations
# which no longer need to care about static values.
class Value(OneRowPerPatientSeries[T]):
    value: T

    def __post_init__(self):
        super().__post_init__()
        # Because we need to be strict about equality (see `__eq__()` below) we can only
        # accept container types for which we know how to handle equality
        if isinstance(self.value, Container) and not isinstance(
            self.value, frozenset | str
        ):
            raise TypeError(
                f"`Value` class does not know how to handle containers of type:"
                f" {self.value!r}"
            )

    # Python treats certain differently typed values as equal (e.g. `1 == True` and `10
    # == 10.0`) but we need to be stricter about types because some of the databases we
    # run against are strict
    def __eq__(self, other):
        if other.__class__ is self.__class__:
            if self.value.__class__ is not other.value.__class__:
                return False
            elif isinstance(self.value, frozenset):
                return self.__eq__frozenset(self.value, other.value)
            else:
                return self.value == other.value
        return NotImplemented

    @staticmethod
    def __eq__frozenset(value, other_value):
        # Cheap test for identical objects. I expect this to be hit quite frequently
        # because the query model transformation process de-duplicates the query model
        # so equivalent objects get replaced with identical objects.
        if value is other_value:
            return True
        # Cheap test for obviously not equal sets
        if len(value) != len(other_value):
            return False
        value_typed = {(i, type(i)) for i in value}
        other_typed = {(i, type(i)) for i in other_value}
        return value_typed == other_typed


# `Parameter` is a placeholder for a value: it allows us to construct query "templates"
# which can later be turned into queries by substituting in concrete values.
class Parameter(OneRowPerPatientSeries[T]):
    name: str
    type: type[T]  # NOQA: A003


class SelectTable(ManyRowsPerPatientFrame):
    name: str
    schema: TableSchema


class SelectPatientTable(OneRowPerPatientFrame):
    name: str
    schema: TableSchema


class InlinePatientTable(OneRowPerPatientFrame):
    # `rows` is an iterable of tuples specifing the data for the table in the form:
    #
    #     (patient_id, column_1_in_schema, column_2_in_schema, ...)
    #
    # As far as I can tell, Python's type system is incapable of specifying the type we
    # want here, which is: iterable but not an iterator. So we opt of typing here and
    # enforce the types in the post_init method.
    rows: Any
    schema: TableSchema

    def __post_init__(self):
        super().__post_init__()
        # Ensure the wrapped object is iterable (i.e. has an `__iter__` method) but is
        # not an iterator (i.e. has a `__next___` method). It's important that we're
        # able to iterate over the object multiple times without consuming it.
        if not isinstance(self.rows, Iterable):
            raise TypeError(f"{self.__class__.__name__}.rows must be iterable")
        if isinstance(self.rows, Iterator):
            raise TypeError(f"{self.__class__.__name__}.rows must not be an iterator")


class SelectColumn(Series):
    source: Frame
    name: str


class Filter(ManyRowsPerPatientFrame):
    source: ManyRowsPerPatientFrame
    condition: Series[bool]


class Sort(ManyRowsPerPatientFrame):
    source: ManyRowsPerPatientFrame
    sort_by: Series[Comparable]


class PickOneRowPerPatient(OneRowPerPatientFrame):
    source: ManyRowsPerPatientFrame
    position: Position


# Aggregations are operations which take frames and/or series and return a new series.
# Unlike functions (see below), aggregations always return a one-row-per-patient series,
# regardless of the dimension of their inputs. Below are all available aggregations
# (using a class as a namespace).
class AggregateByPatient:
    # The `Exists` and `Count` aggregations are unusual in that they operate on frames
    # rather than series and they don't use the `AggregatedSeries` type, which means
    # they accept inputs both of many-rows-per-patient and one-row-per-patient dimension
    class Exists(OneRowPerPatientSeries[bool]):
        source: Frame

    class Count(OneRowPerPatientSeries[int]):
        source: Frame

    class CountDistinct(AggregatedSeries[int]):
        source: Series[Any]

    class CountEpisodes(AggregatedSeries[int]):
        source: Series[Any]
        # Note this is `int` not `Series[int]`: we only accept a fixed value here
        maximum_gap_days: int

    class Min(AggregatedSeries[Comparable]):
        source: Series[Comparable]

    class Max(AggregatedSeries[Comparable]):
        source: Series[Comparable]

    class Sum(AggregatedSeries[Numeric]):
        source: Series[Numeric]

    class Mean(AggregatedSeries[float]):
        source: Series[Numeric]

    # This is an unusual aggregation in that while it collapses multiple values per patient
    # down to a single value per patient (as all aggregations must) the value it
    # produces is a set-like object containing all of its input values. This enables
    # them to be used as arguments to the In/NotIn fuctions which require something
    # set-like as their RHS argument.
    class CombineAsSet(AggregatedSeries[Set[T]]):
        source: Series[T]


# Functions are operations which take one or more series and return a new series. The
# dimension of the returned series will be the highest dimension of its inputs i.e. if
# any of its inputs has many-rows-per-patient then its output will too. Below are all
# available functions (using a class as a namespace).
class Function:
    # Comparison
    class EQ(Series[bool]):
        lhs: Series[T]
        rhs: Series[T]

    class NE(Series[bool]):
        lhs: Series[T]
        rhs: Series[T]

    class LT(Series[bool]):
        lhs: Series[Comparable]
        rhs: Series[Comparable]

    class LE(Series[bool]):
        lhs: Series[Comparable]
        rhs: Series[Comparable]

    class GT(Series[bool]):
        lhs: Series[Comparable]
        rhs: Series[Comparable]

    class GE(Series[bool]):
        lhs: Series[Comparable]
        rhs: Series[Comparable]

    # Boolean
    class And(Series[bool]):
        lhs: Series[bool]
        rhs: Series[bool]

    class Or(Series[bool]):
        lhs: Series[bool]
        rhs: Series[bool]

    class Not(Series[bool]):
        source: Series[bool]

    # Null handling
    class IsNull(Series[bool]):
        source: Series[Any]

    # Arithmetic
    class Negate(Series[Numeric]):
        source: Series[Numeric]

    class Add(Series[Numeric]):
        lhs: Series[Numeric]
        rhs: Series[Numeric]

    class Subtract(Series[Numeric]):
        lhs: Series[Numeric]
        rhs: Series[Numeric]

    class Multiply(Series[Numeric]):
        lhs: Series[Numeric]
        rhs: Series[Numeric]

    class TrueDivide(Series[float]):
        lhs: Series[Numeric]
        rhs: Series[Numeric]

    class FloorDivide(Series[int]):
        lhs: Series[Numeric]
        rhs: Series[Numeric]

    # Casting numeric types
    class CastToInt(Series[int]):
        source: Series[Numeric] | Series[bool]

    class CastToFloat(Series[float]):
        source: Series[Numeric]

    # Dates
    class DateAddDays(Series[date]):
        lhs: Series[date]
        rhs: Series[int]

    class DateAddMonths(Series[date]):
        lhs: Series[date]
        rhs: Series[int]

    class DateAddYears(Series[date]):
        lhs: Series[date]
        rhs: Series[int]

    class DateDifferenceInDays(Series[int]):
        lhs: Series[date]
        rhs: Series[date]

    class DateDifferenceInMonths(Series[int]):
        lhs: Series[date]
        rhs: Series[date]

    class DateDifferenceInYears(Series[int]):
        lhs: Series[date]
        rhs: Series[date]

    class YearFromDate(Series[int]):
        source: Series[date]

    class MonthFromDate(Series[int]):
        source: Series[date]

    class DayFromDate(Series[int]):
        source: Series[date]

    class ToFirstOfYear(Series[date]):
        source: Series[date]

    class ToFirstOfMonth(Series[date]):
        source: Series[date]

    # Strings
    class StringContains(Series[bool]):
        lhs: Series[str]
        rhs: Series[str]

    # Containment is a special case: its right-hand side must be something vector-like i.e.
    # something containing multiple values. To build a series whose values are vectors,
    # use the `CombineAsSet` aggregation.
    class In(Series[bool]):
        lhs: Series[T]
        rhs: Series[Set[T]]

    # Horizontal Aggregation
    class MinimumOf(Series[Comparable]):
        sources: tuple[Series[Comparable]]

    class MaximumOf(Series[Comparable]):
        sources: tuple[Series[Comparable]]


class Case(Series[T]):
    cases: Mapping[Series[bool], Series[T] | None]
    default: Series[T] | None


# TODO: We don't currently support Join in the DSL or the Query Engine but this is the
# signature it will have when we do. Also note that the Join operation is the one
# exception to the "common domain constraint" explained below as it's the one operation
# which is explicitly designed to take inputs from two different domains and produce a
# single, new domain as output.
#
# class Join(ManyRowsPerPatientFrame):
#     lhs: Frame
#     rhs: Frame


# PUBLIC HELPER FUNCTIONS
#


def has_one_row_per_patient(node):
    "Return whether a Frame or Series has at most one row per patient"
    return get_domain(node) == Domain.PATIENT


def has_many_rows_per_patient(node):
    return not has_one_row_per_patient(node)


def get_series_type(series):
    "Return the type contained within a Series"
    assert isinstance(series, Series)
    typespec = get_typespec(series)
    return typing.get_args(typespec)[0]


# VALIDATION
#


def validate_node(node):
    # Check that the node is hashable
    try:
        hash(node)
    except TypeError as e:
        raise TypeError("Node arguments must be hashable types") from e
    # Check that the types supplied match the types specified
    validate_types(node)
    # As well as types we need to validate the "domain constraint" which specifies how
    # Frames and Series, potentially drawn from different tables, can be combined
    validate_input_domains(node)
    # PickOneRowPerPatient can only be used on sorted frames
    if isinstance(node, PickOneRowPerPatient):
        if not is_sorted(node.source):
            raise TypeValidationError(
                node=node,
                field_name="source",
                expected="SortedFrame",
                received="UnsortedFrame",
            )


class ValidationError(Exception): ...


# DOMAIN VALIDATION
#


class DomainMismatchError(ValidationError): ...


class InvalidSortError(DomainMismatchError): ...


class PatientDomainError(DomainMismatchError): ...


def validate_input_domains(node):
    # The domain of a Frame or Series can be thought of as the set of its primary keys.
    # This determines which other Frames or Series it can be validly composed with. The
    # rules we want to enforce are:
    #
    #  * One-row-per-patient data can be composed with anything: by design every table
    #    has a patient_id column and so data defined purely in terms of patient_id
    #    can be joined with anything.
    #
    #  * Many-rows-per-patient data drawn from different tables can never be combined
    #    — at least, not until we add an explicit JOIN operation.
    #
    #  * Many-rows-per-patient series data drawn from a single underlying table can be
    #    combined if they have had the same set of filters applied to them. That is, it's
    #    legal to combine two series derived from `Table A -> Filter B`, but not a series
    #    derived from `Table A -> Filter B -> Filter C` with one derived from
    #    `Table A -> Filter B`. There's never a need to use such constructions and they
    #    will almost always be the result of user error. It's better to reject them
    #    immediately than give the user unexpected results at query time.
    #
    #    As an example, we reject this erhQL construction because the per-patient
    #    cardinality of the first argument to `+` may be lower than that of the second:
    #
    #        e.where(e.b).i + e.i
    #
    # * Many-rows-per-patient frames can be combined with many-rows-per-patient series
    #   derived from the same underlying table, as long as any filters applied to each
    #   one are identical or make the series a "parent" of the frame. That is, it's legal
    #   to combine `Table A -> Filter B -> Filter C` and a series derived from
    #   `Table A -> Filter B`. But it's not legal to combine `Table A -> Filter D` and a
    #   series derived from `Table A -> Filter E`. Combination of this nature takes place
    #   with the Filter and Sort operations.
    #
    #   That means that filters and sorts can be expressed tersely in ehrQL, like this:
    #
    #       events.where(events.code == "foo").where(events.date >= start_date)
    #
    # We enforce this by modelling domains as a hierarchy. At the root is the patient
    # domain, each table has an unique domain descending from this, and each filter
    # operation creates a new domain descending from the domain of its source.
    #
    # A valid series combination operation is one where the non-patient domains are
    # identical. A valid filter or sort operation is one where the domains of its series
    # input's domain is an ancestor of its frame input's domain.

    if isinstance(node, Filter) or isinstance(node, Sort):
        frame, series = get_input_nodes(node)
        assert isinstance(frame, Frame)
        assert isinstance(series, Series)
        frame_domain = get_domain(frame)
        series_domain = get_domain(series)
        if not series_domain.is_ancestor(frame_domain):
            raise DomainMismatchError(
                f"Attempt to combine series with domain:\n{series_domain}"
                f"\nWith frame with domain:\n{frame_domain}"
            )
        if isinstance(node, Sort) and series_domain == Domain.PATIENT:
            raise InvalidSortError(
                "Attempt to sort frame by a one-row-per-patient series"
            )
    elif isinstance(node, Dataset):
        # We deliberately ignore the `events` property here as that's expected to
        # contain multiple, divergent many-rows-per-patient series
        domains = {
            get_domain(arg) for arg in [node.population, *node.variables.values()]
        }
        if domains != {Domain.PATIENT}:
            raise DomainMismatchError(
                "Dataset can only contain one-row-per-patient series"
            )
    else:
        non_patient_domains = get_input_domains(node) - {Domain.PATIENT}
        if len(non_patient_domains) > 1:
            raise DomainMismatchError(
                f"Attempt to combine unrelated domains:\n{non_patient_domains}"
            )
        if isinstance(node, AggregatedSeries) and len(non_patient_domains) == 0:
            raise PatientDomainError("Attempt to aggregate one-row-per-patient series")
        if isinstance(node, SeriesCollectionFrame) and len(non_patient_domains) == 0:
            raise PatientDomainError(
                "At least one series in collection must have many-rows-per-patient"
            )


@dataclasses.dataclass(frozen=True)
class Domain:
    lineage: tuple

    def create_descendent(self, node):
        return Domain(self.lineage + (node,))

    def is_ancestor(self, other):
        return self.lineage == other.lineage[: len(self.lineage)]

    # Defining this operator means Domains work naturally with `sorted()`
    def __lt__(self, other):
        return self != other and self.is_ancestor(other)

    def get_node(self):
        """
        Returns the Node which created this domain
        """
        assert len(self.lineage) > 1, "Root domains have no associated node"
        return self.lineage[-1]


# We use an arbitrary string to represent the patient domain for more readable debugging
Domain.PATIENT = Domain(("PatientDomain",))


def get_input_domains(node):
    return {get_domain(input_node) for input_node in get_input_nodes(node)}


@singledispatch
def get_domain(node):
    assert False, f"Unhandled node type: {type(node)}"


# Selecting a many-rows-per-patient table creates a new domain which descends from the
# patient domain
@get_domain.register(SelectTable)
def get_domain_for_table(node):
    return Domain.PATIENT.create_descendent(node)


# Filtering a Frame creates a new domain which descends from the domain of the original
# source Frame
@get_domain.register(Filter)
def get_domain_for_filter(node):
    return get_domain(node.source).create_descendent(node)


# Operations of these types are guaranteed to produce output in the patient domain
@get_domain.register(OneRowPerPatientFrame)
@get_domain.register(OneRowPerPatientSeries)
def get_domain_for_one_row_per_patient_operations(node):
    return Domain.PATIENT


# For the remaining operations, their domain is the "smallest" of the domains of their
# inputs i.e. the one furthest from the root
@get_domain.register(Series)
@get_domain.register(Sort)
@get_domain.register(SeriesCollectionFrame)
def get_domain_from_inputs(node):
    return sorted(get_input_domains(node))[-1]


# Quick and lazy way of getting input nodes using dataclass introspection
@singledispatch
def get_input_nodes(node):
    return [
        value
        for value in [getattr(node, field.name) for field in dataclasses.fields(node)]
        if isinstance(value, Node)
    ]


# The above bit of dynamic cheekiness doesn't work for Case whose inputs are
# nested inside a dict object
@get_input_nodes.register(Case)
def get_input_nodes_for_case(node):
    inputs = [*node.cases.keys(), *node.cases.values(), node.default]
    return [i for i in inputs if i is not None]


@get_input_nodes.register(Dataset)
def get_input_nodes_for_dataset(node):
    return [node.population, *node.variables.values(), *node.events.values()]


@get_input_nodes.register(SeriesCollectionFrame)
def get_input_nodes_for_combined_series_frame(node):
    return list(node.members.values())


# Minimum/Maximum of functions contain their inputs inside a tuple
@get_input_nodes.register(Function.MaximumOf)
@get_input_nodes.register(Function.MinimumOf)
def get_input_nodes_for_nary_function(node):
    return [*node.sources]


# SORTEDNESS
#


@singledispatch
def is_sorted(frame):
    assert False, f"Unhandled node type: {type(frame)}"


@is_sorted.register(SelectTable)
def is_sorted_select_table(frame):
    return False


@is_sorted.register(Sort)
def is_sorted_sort(frame):
    return True


@is_sorted.register(Filter)
def is_sorted_filter(frame):
    return is_sorted(frame.source)


# TYPE VALIDATION
#


class TypeValidationError(ValidationError):
    def __init__(self, node, field_name, expected, received):
        self.node = node
        self.field_name = field_name
        self.expected = expected
        self.received = received

    def __str__(self):
        return (
            f"{self.node.__class__.__name__}.{self.field_name} requires "
            f"'{self.expected}' but received '{self.received}'"
        )


def validate_types(node):
    # Within the context of this node, any TypeVars evaluated must take consistent
    # values so we create a single context object to share between all fields
    typevar_context = {}
    for field in dataclasses.fields(node):
        target_typespec = field.type
        value = getattr(node, field.name)
        typespec = get_typespec(value)
        if not type_matches(typespec, target_typespec, typevar_context):
            # Try to make errors a bit more helpful by resolving TypeVars if we can.
            # This means that if validation fails because e.g. `T` has been bound to
            # `int` by one argument and you're trying to supply `str` in the other,
            # you'll get an error saying "requires Series[int]" rather than the less
            # helpful "requires Series[T]"
            if len(typevar_context) == 1:
                typevar_value = list(typevar_context.values())[0]
                resolved_typespec = target_typespec[typevar_value]
            else:
                resolved_typespec = target_typespec
            raise TypeValidationError(
                node=node,
                field_name=field.name,
                expected=resolved_typespec,
                received=typespec,
            )


# See the `get_typespec` function in `typing_utils.py` for a description of what this
# function does in general. Here we're teaching it how to destructure a Series object to
# work out what kind of thing it contains.
@get_typespec.register(Series)
def get_typespec_for_series(series):
    """
    Given a Series object, work out what type of thing it contains so we can return a
    type like `Series[int]` or `Series[bool]`
    """
    inner_type = get_inner_type(series)
    typevars = get_typevars(inner_type)
    # The easy case is when the series type specification doesn't contain any TypeVars
    # so it's just something like `Series[int]` or `Series[str]`
    if not typevars:
        # In this case there's no resolving to be done and the resolved type just *is*
        # the type we started with (which in the examples above would be `int` or `str`)
        resolved_type = inner_type
    # If the specification does contain TypeVars then we need to resolve these against
    # the types used in the inputs and substitute these resolved values back in. So if
    # we have `Series[T]` or `Series[Set[T]]` we need to check its inputs to see what T
    # refers to.
    else:
        # We assume just one TypeVar; we could probably make this work with multiple if
        # we needed to, but I can't see why we ever would
        assert len(typevars) == 1
        typevar = list(typevars)[0]
        # Get the value implied by the input types. Note that if the inputs' signatures
        # themselves contain TypeVars then this will end up recursing until it hits a
        # concrete type.
        typevar_value = resolve_typevar_from_inputs(series, typevar)
        if inner_type is typevar:
            # If what we started with was a plain TypeVar (not nested inside any more
            # complex structure) then our resolved value is just the value of the
            # TypeVar
            resolved_type = typevar_value
        else:
            # Otherwise we have to parameterize the type using the value of the TypeVar
            resolved_type = inner_type[typevar_value]
    return Series[resolved_type]


def get_inner_type(series):
    # A bit of typing magic: given an instance of a class like `Count`
    #
    #     class Count(Series[int]):
    #         ...
    #
    # we want to get back the `int` bit, and below is the incantation to do so.
    #
    # Here `Series[int]` is a generic alias and so doesn't appear in the normal class
    # hierachy. Instead we access it via the `__orig_bases__` attribute. We want the
    # first such generic and, having found it, we want to extract its arguments using
    # `get_args` and take what we know to be the one and only argument.
    inner_type = typing.get_args(series.__orig_bases__[0])[0]
    # It's fine to _accept_ Series[Any] as a type, but there's no reason we should be
    # returning it
    assert inner_type is not Any, "Operations should never return Series[Any]"
    return inner_type


def resolve_typevar_from_inputs(series, typevar):
    # Walk over all the inputs to an operation, matching their actual type against their
    # specified field type; this is not with the intention of validating those types but
    # rather of resolving the values of any type variables included. As soon as we
    # resolve the typevar we're after, we return it.
    #
    # For example, suppose we have an operation like this:
    #
    #   class Add(Series[T]):
    #       lhs: Series[T]
    #       rhs: Series[T]
    #
    # To determine what type of Series this operation returns we need to determine the
    # value of T. If we have an instance of `Add` constructed like this:
    #
    #     add = Add(some_int_series, another_int_series)
    #
    # We can walk over its attributes and match their types against the types in the
    # signature. So `add.lhs` has type `Series[int]` which matches `Series[T]` and in
    # the process tells us that `T == int` by setting `T` in the `typevar_context`
    #
    # As soon as we've resolved the value of T we return it. (Ensuring T is consistent
    # over all the inputs is a separate validation problem handled elsewhere.)
    typevar_context = {}
    for field in dataclasses.fields(series):
        value = getattr(series, field.name)
        typespec = get_typespec(value)
        # We're abusing a side-effect of the validation function here which is to
        # populate the `typevar_context` dict and ignoring the actual validation return
        # value.
        type_matches(typespec, field.type, typevar_context)
        # We happen to always hit this on the first pass, hence the "no cover"
        if typevar in typevar_context:  # pragma: no cover
            return typevar_context[typevar]
    else:
        # If we get here then we've mucked up our Query Model classes somehow: we've
        # included a TypeVar in an operation signature which doesn't itself appear in
        # the signatures for any of its inputs.
        assert False, f"Could not match TypeVar {typevar} in {series}"


@get_typespec.register(SelectColumn)
def get_typespec_for_select_column(column):
    # Find the table from which this SelectColumn operation draws
    root = get_root_frame(column.source)
    type_ = root.schema.get_column_type(column.name)
    return Series[type_]


@singledispatch
def get_root_frame(frame):
    return get_root_frame(frame.source)


@get_root_frame.register(SelectTable)
@get_root_frame.register(SelectPatientTable)
@get_root_frame.register(InlinePatientTable)
def get_root_frame_for_table(frame):
    return frame


def get_table_and_filters(frame):
    """
    Given a ManyRowsPerPatientFrame, destructure it and return the underlying table and
    any filter operations that have been applied, in application order.
    """
    root_frame, filters, _ = get_frame_operations(frame)
    return filters, root_frame


def get_sorts(frame):
    """
    Given a ManyRowsPerPatientFrame, destructure it and return any sort operations that
    have been applied, in application order.
    """
    _, _, sorts = get_frame_operations(frame)
    return sorts


def get_frame_operations(frame):
    """
    Given a ManyRowsPerPatientFrame, destructure it and return the underlying table and
    any filter and sort operations that have been applied, in application order.
    """
    filters = []
    sorts = []
    while True:
        type_ = type(frame)
        if type_ is Filter:
            filters.insert(0, frame)
            frame = frame.source
        elif type_ is Sort:
            sorts.insert(0, frame)
            frame = frame.source
        elif type_ is SelectTable:
            return frame, filters, sorts
        else:
            assert False, f"Unexpected type: {frame}"
