"""
This is a copy of the old query model whose only role is to define the test cases in the
accompanying query engine test suite. It needs to be a copy so that this code can stay
exactly as it is while we gradually refactor the query engine to accept the new query
model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_OPERATOR_MAPPING = {
    "equals": "__eq__",
    "not_equals": "__ne__",
    "less_than": "__lt__",
    "less_than_or_equals": "__le__",
    "greater_than": "__gt__",
    "greater_than_or_equals": "__ge__",
    "on_or_before": "__le__",
    "on_or_after": "__ge__",
    "is_in": "in_",
    "not_in": "not_in",
}


class ValidationError(Exception):
    ...


def table(name):
    return Table(name)


# A note about dataclasses...  We will need to store instances of the classes in this
# module in sets, which requires them to be hashable.  As such, we require instances to
# be frozen.  This means we cannot mutate the fields of an instance once it has been
# created.  Additionally, in order for the comparison operators on Value and its
# subclasses to work, we need to stop dataclasses from overriding these methods on the
# subclasses.


@dataclass(frozen=True)
class QueryNode:
    pass


@dataclass(frozen=True)
class Comparator(QueryNode):
    """A generic comparator to represent a comparison between a source object and a
    value.

    The simplest comparator is created from an expression such as `foo > 3` and will
    have a lhs ('foo'; a Value object), operator ('__gt__') and a rhs (3; a simple type
    - str/int/float/None).  The lhs and rhs of a Comparator can themselves be
    Comparators, which are to be connected with self.connector.
    """

    connector: Any = None
    negated: bool = False
    lhs: Any = None
    operator: Any = None
    rhs: Any = None

    def __and__(self, other):
        return self._combine(other, "and_")

    def __or__(self, other):
        return self._combine(other, "or_")

    def __invert__(self):
        return type(self)(
            connector=self.connector,
            negated=not self.negated,
            lhs=self.lhs,
            operator=self.operator,
            rhs=self.rhs,
        )

    def __eq__(self, other):
        return self._compare(other, "__eq__")

    def __ne__(self, other):  # pragma: no cover
        return self._compare(other, "__ne__")

    def _combine(self, other, conn):
        assert isinstance(other, Comparator)
        return type(self)(connector=conn, lhs=self, rhs=other)

    def _compare(self, other, operator):
        return type(self)(operator=operator, lhs=self, rhs=other)


def boolean_comparator(obj, negated=False):
    """returns a comparator which represents a comparison against null values"""
    return Comparator(lhs=obj, operator="__ne__", rhs=None, negated=negated)


class BaseTable(QueryNode):
    def get(self, column):
        return Column(source=self, column=column)

    def filter(self, *args, **kwargs):  # noqa: A003
        """
        args: max 1 arg, a field name (str)
        kwargs:
           - either one or more "equals" filters, or
           - k=v pairs of operator=filter conditions to be applied to a single field (the arg)
        Filter formats:
        - equals: `filter(a=b, c=d)` (allows multiple in one query)
        - between: `filter("a", between=[start_date_column, end_date_column]})`
        - others: `filter("a", less_than=b)`
        """
        include_null = kwargs.pop("include_null", False)
        if not args:
            # No args; this is an equals filter
            assert kwargs
            node = self
            # apply each of the equals filters, converted into a field arg and single equals kwarg
            for field, value in kwargs.items():
                node = node.filter(field, equals=value)
            return node
        elif len(kwargs) > 1:
            # filters on a specific field, apply each filter in turn
            node = self
            for operator, value in kwargs.items():
                node = node.filter(*args, **{operator: value})
            return node

        operator, value = list(kwargs.items())[0]
        if operator == "between":
            # convert a between filter into its two components
            return self.filter(*args, on_or_after=value[0], on_or_before=value[1])

        if operator in ("equals", "not_equals") and isinstance(
            value, (Codelist, Column)
        ):  # pragma: no cover
            raise TypeError(
                f"You can only use '{operator}' to filter a column by a single value.\n"
                f"To filter using a {value.__class__.__name__}, use 'is_in/not_in'."
            )

        if operator == "is_in" and not isinstance(value, (Codelist, Column)):
            # convert non-codelist in values to tuple
            value = tuple(value)
        assert len(args) == len(kwargs) == 1

        operator = _OPERATOR_MAPPING[operator]
        return FilteredTable(
            source=self,
            column=args[0],
            operator=operator,
            value=value,
            or_null=include_null,
        )

    def earliest(self, *columns):
        columns = columns or ("date",)
        return self.first_by(*columns)

    def latest(self, *columns):
        columns = columns or ("date",)
        return self.last_by(*columns)

    def first_by(self, *columns):
        assert columns
        return Row(source=self, sort_columns=columns, descending=False)

    def last_by(self, *columns):
        assert columns
        return Row(source=self, sort_columns=columns, descending=True)

    def date_in_range(
        self, date, start_column="date_start", end_column="date_end", include_null=True
    ):
        """
        A filter that returns rows for which a date falls between a start and end date (inclusive).
        Null end date values are included by default
        """
        return self.filter(start_column, less_than_or_equals=date).filter(
            end_column, greater_than_or_equals=date, include_null=include_null
        )

    def exists(self, column="patient_id"):
        return self.aggregate("exists", column)

    def count(self, column="patient_id"):
        return self.aggregate("count", column)

    def sum(self, column):  # noqa: A003
        return self.aggregate("sum", column)

    def aggregate(self, function, column):
        output_column = f"{column}_{function}"
        row = RowFromAggregate(self, function, column, output_column)
        return ValueFromAggregate(row, output_column)


@dataclass(frozen=True)
class Table(BaseTable):
    name: str

    def age_as_of(self, reference_date):
        if self.name != "patients":
            raise NotImplementedError(
                "This method is only available on the patients table"
            )
        return DateDifference(
            self.first_by("patient_id").get("date_of_birth"),
            reference_date,
            units="years",
        )


# @dataclass(unsafe_hash=True)
@dataclass(frozen=True)
class FilteredTable(BaseTable):
    source: Any
    column: Any
    operator: Any
    value: Any
    or_null: bool = False


@dataclass(frozen=True)
class Column(QueryNode):
    source: Any
    column: Any


@dataclass(frozen=True)
class Row(QueryNode):
    source: Any
    sort_columns: Any
    descending: Any

    def get(self, column):
        return ValueFromRow(source=self, column=column)


@dataclass(frozen=True)
class RowFromAggregate(QueryNode):
    source: QueryNode
    function: Any
    input_column: Any
    output_column: Any


class Value(QueryNode):
    @staticmethod
    def _other_as_comparator(other):
        if isinstance(other, Value):
            other = boolean_comparator(other)  # pragma: no cover
        return other

    def _get_comparator(self, operator, other):
        other = self._other_as_comparator(other)
        return Comparator(lhs=self, operator=operator, rhs=other)

    def __gt__(self, other):
        return self._get_comparator("__gt__", other)

    def __ge__(self, other):  # pragma: no cover
        return self._get_comparator("__ge__", other)

    def __lt__(self, other):
        return self._get_comparator("__lt__", other)

    def __le__(self, other):
        return self._get_comparator("__le__", other)

    def __eq__(self, other):
        return self._get_comparator("__eq__", other)

    def __ne__(self, other):
        return self._get_comparator("__ne__", other)

    def __and__(self, other):
        other = self._other_as_comparator(other)
        return boolean_comparator(self) & other

    def __or__(self, other):  # pragma: no cover
        other = self._other_as_comparator(other)
        return boolean_comparator(self) | other

    def __invert__(self):
        return boolean_comparator(self, negated=True)

    def __hash__(self):
        return id(self)


@dataclass(frozen=True, eq=False, order=False)
class ValueFromRow(Value):
    source: Any
    column: Any


@dataclass(frozen=True, eq=False, order=False)
class ValueFromAggregate(Value):
    source: RowFromAggregate
    column: Any


def categorise(mapping, default=None):
    mapping = {
        key: boolean_comparator(value) if isinstance(value, Value) else value
        for key, value in mapping.items()
    }
    return ValueFromCategory(mapping, default)


@dataclass(frozen=True, eq=False, order=False)
class ValueFromCategory(Value):
    definitions: dict
    default: str | int | float | None


@dataclass(frozen=True)
class Codelist(QueryNode):
    codes: tuple
    system: str
    has_categories: bool = False

    def __post_init__(self):
        if self.has_categories:
            raise NotImplementedError("Categorised codelists are currently unsupported")

    def __repr__(self):  # pragma: no cover
        if len(self.codes) > 5:
            codes = self.codes[:5] + ("...",)
        else:
            codes = self.codes
        return f"Codelist(system={self.system}, codes={codes})"


class ValueFromFunction(Value):
    def __init__(self, *args):
        self.arguments = args


class DateDifference(ValueFromFunction):
    def __init__(self, start, end, units="years"):
        super().__init__(start, end, units)
        self.units = units


class DateAddition(ValueFromFunction):
    pass


class DateDeltaAddition(ValueFromFunction):
    pass


class DateSubtraction(ValueFromFunction):
    pass


class DateDeltaSubtraction(ValueFromFunction):
    pass


class RoundToFirstOfMonth(ValueFromFunction):
    pass


class RoundToFirstOfYear(ValueFromFunction):
    pass
