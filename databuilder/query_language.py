import dataclasses
import datetime
import enum
from typing import Union

from databuilder.codes import BaseCode, Codelist
from databuilder.query_model import nodes as qm
from databuilder.query_model.nodes import get_series_type, has_one_row_per_patient
from databuilder.query_model.population_validation import validate_population_definition
from databuilder.utils import date_utils

# This gets populated by the `__init_subclass__` methods of EventSeries and
# PatientSeries. Its structure is:
#
#   (<type>, <is_patient_level>): <SeriesClass>
#
# For example:
#
#   (bool, False): BoolEventSeries,
#   (bool, True): BoolPatientSeries,
#
REGISTERED_TYPES = {}


# Because ehrQL classes override `__eq__` we can't use them as dictionary keys. So where
# the query model expects dicts we represent them as lists of pairs, which the
# `_apply()` function can convert to dicts when it passes them to the query model.
class _DictArg(list):
    "Internal class for passing around dictionary arguments"


class Dataset:
    def __init__(self):
        object.__setattr__(self, "variables", {})

    def set_population(self, population):
        validate_population_definition(population.qm_node)
        self.variables["population"] = population

    def __setattr__(self, name, value):
        if name == "population":
            raise AttributeError(
                "Cannot set variable 'population'; use set_population() instead"
            )
        if name in self.variables:
            raise AttributeError(f"'{name}' is already set and cannot be reassigned")
        if name == "variables":
            raise AttributeError("'variables' is not an allowed variable name")
        if name.startswith("__"):
            raise AttributeError(
                f"Variable names must not start with underscores (you defined a variable '{name}')"
            )
        if not isinstance(value, BaseSeries):
            raise TypeError(
                f"Invalid variable '{name}'. Dataset variables must be values not whole rows"
            )
        if not qm.has_one_row_per_patient(value.qm_node):
            raise TypeError(
                f"Invalid variable '{name}'. Dataset variables must return one row per patient"
            )
        self.variables[name] = value

    def __getattr__(self, name):
        if name in self.variables:
            return self.variables[name]
        raise AttributeError(f"Variable '{name}' has not been defined")


def compile(dataset):  # noqa A003
    return {k: v.qm_node for k, v in dataset.variables.items()}


# BASIC SERIES TYPES
#


@dataclasses.dataclass(frozen=True)
class BaseSeries:
    qm_node: qm.Node

    def __hash__(self):
        # The issue here is not mutability but the fact that we overload `__eq__` for
        # syntatic sugar, which makes these types spectacularly ill-behaved as dict keys
        raise TypeError(f"unhashable type: {self.__class__.__name__!r}")

    def __bool__(self):
        raise TypeError(
            "The keywords 'and', 'or', and 'not' cannot be used with ehrQL, please "
            "use the operators '&', '|' and '~' instead.\n"
            "(You will also see this error if you try use a chained comparison, "
            "such as 'a < b < c'.)"
        )

    @staticmethod
    def _cast(value):
        # Series have the opportunity to cast arguments to their methods e.g. to convert
        # ISO date strings to date objects. By default, this is a no-op.
        return value

    # These are the basic operations that apply to any series regardless of type or
    # dimension
    def __eq__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.EQ, self, other)

    def __ne__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.NE, self, other)

    def is_null(self):
        return _apply(qm.Function.IsNull, self)

    def is_not_null(self):
        return self.is_null().__invert__()

    def is_in(self, other):
        # For iterable arguments, apply any necessary casting and convert to the
        # immutable Set type required by the query model. We don't accept arbitrary
        # iterables here because too many types in Python are iterable and there's the
        # potential for confusion amongst the less experienced of our users.
        if isinstance(other, (tuple, list, set, frozenset, dict)):
            other = frozenset(map(self._cast, other))
        return _apply(qm.Function.In, self, other)

    def is_not_in(self, other):
        return self.is_in(other).__invert__()

    def map_values(self, mapping, default=None):
        """
        Accepts a dictionary mapping one set of values to another and applies that
        mapping to the series
        """
        return case(
            *[
                when(self == from_value).then(to_value)
                for from_value, to_value in mapping.items()
            ],
            default=default,
        )

    def if_null_then(self, other):
        return case(
            when(self.is_not_null()).then(self),
            default=self._cast(other),
        )


class EventSeries(BaseSeries):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Register the series using its `_type` attribute
        REGISTERED_TYPES[cls._type, False] = cls

    # If we end up with any type-agnostic aggregations (count non-null, maybe?) then
    # they would be defined here as well


class PatientSeries(BaseSeries):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Register the series using its `_type` attribute
        REGISTERED_TYPES[cls._type, True] = cls


# BOOLEAN SERIES
#


class BoolFunctions:
    def __invert__(self):
        return _apply(qm.Function.Not, self)

    def __and__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.And, self, other)

    def __or__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.Or, self, other)


class BoolEventSeries(BoolFunctions, EventSeries):
    _type = bool


class BoolPatientSeries(BoolFunctions, PatientSeries):
    _type = bool


# METHODS COMMON TO ALL COMPARABLE TYPES
#


class ComparableFunctions:
    def __lt__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.LT, self, other)

    def __le__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.LE, self, other)

    def __ge__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.GE, self, other)

    def __gt__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.GT, self, other)


class ComparableAggregations:
    def minimum_for_patient(self):
        return _apply(qm.AggregateByPatient.Min, self)

    def maximum_for_patient(self):
        return _apply(qm.AggregateByPatient.Max, self)


# STRING SERIES
#


class StrFunctions(ComparableFunctions):
    def contains(self, other):
        other = self._cast(other)
        return _apply(qm.Function.StringContains, self, other)


class StrAggregations(ComparableAggregations):
    "Empty for now"


class StrEventSeries(StrFunctions, StrAggregations, EventSeries):
    _type = str


class StrPatientSeries(StrFunctions, PatientSeries):
    _type = str


# NUMERIC SERIES
#


class NumericFunctions(ComparableFunctions):
    def __neg__(self):
        return _apply(qm.Function.Negate, self)

    def __add__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.Add, self, other)

    def __radd__(self, other):
        return self + other

    def __sub__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.Subtract, self, other)

    def __rsub__(self, other):
        return other + -self

    def __mul__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.Multiply, self, other)

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.TrueDivide, self, other)

    def __rtruediv__(self, other):
        return self / other

    def __floordiv__(self, other):
        other = self._cast(other)
        return _apply(qm.Function.FloorDivide, self, other)

    def __rfloordiv__(self, other):
        return self // other

    def as_int(self):
        return _apply(qm.Function.CastToInt, self)

    def as_float(self):
        return _apply(qm.Function.CastToFloat, self)


class NumericAggregations(ComparableAggregations):
    def sum_for_patient(self):
        return _apply(qm.AggregateByPatient.Sum, self)

    def mean_for_patient(self):
        return _apply(qm.AggregateByPatient.Mean, self)


class IntEventSeries(NumericFunctions, NumericAggregations, EventSeries):
    _type = int


class IntPatientSeries(NumericFunctions, PatientSeries):
    _type = int


class FloatFunctions(NumericFunctions):
    @staticmethod
    def _cast(value):
        """
        Casting int literals to floats. We dont support casting to float for IntSeries.
        """
        if isinstance(value, int):
            return float(value)
        return value


class FloatEventSeries(FloatFunctions, NumericAggregations, EventSeries):
    _type = float


class FloatPatientSeries(FloatFunctions, PatientSeries):
    _type = float


# DATE SERIES
#


def parse_date_if_str(value):
    if isinstance(value, str):
        return datetime.date.fromisoformat(value)
    else:
        return value


class DateFunctions(ComparableFunctions):
    @staticmethod
    def _cast(value):
        return parse_date_if_str(value)

    @property
    def year(self):
        return _apply(qm.Function.YearFromDate, self)

    @property
    def month(self):
        return _apply(qm.Function.MonthFromDate, self)

    @property
    def day(self):
        return _apply(qm.Function.DayFromDate, self)

    def to_first_of_year(self):
        return _apply(qm.Function.ToFirstOfYear, self)

    def to_first_of_month(self):
        return _apply(qm.Function.ToFirstOfMonth, self)

    def is_before(self, other):
        return self.__lt__(other)

    def is_on_or_before(self, other):
        return self.__le__(other)

    def is_after(self, other):
        return self.__gt__(other)

    def is_on_or_after(self, other):
        return self.__ge__(other)

    def is_between(self, start, end):
        return (self > start) & (self < end)

    def is_on_or_between(self, start, end):
        return (self >= start) & (self <= end)

    def __add__(self, other):
        if isinstance(other, Duration):
            if other.units is Duration.Units.DAYS:
                return _apply(qm.Function.DateAddDays, self, other.value)
            elif other.units is Duration.Units.MONTHS:
                return _apply(qm.Function.DateAddMonths, self, other.value)
            elif other.units is Duration.Units.YEARS:
                return _apply(qm.Function.DateAddYears, self, other.value)
            else:
                assert False
        else:
            return NotImplemented

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        other = self._cast(other)
        if isinstance(other, Duration):
            return self.__add__(other.__neg__())
        elif isinstance(other, (datetime.date, DateEventSeries, DatePatientSeries)):
            return DateDifference(self, other)
        else:
            return NotImplemented

    def __rsub__(self, other):
        other = self._cast(other)
        if isinstance(other, (datetime.date, DateEventSeries, DatePatientSeries)):
            return DateDifference(other, self)
        else:
            return NotImplemented


class DateAggregations(ComparableAggregations):
    "Empty for now"


class DateEventSeries(DateFunctions, DateAggregations, EventSeries):
    _type = datetime.date


class DatePatientSeries(DateFunctions, PatientSeries):
    _type = datetime.date


@dataclasses.dataclass
class DateDifference:
    lhs: Union[datetime.date, DateEventSeries, DatePatientSeries]
    rhs: Union[datetime.date, DateEventSeries, DatePatientSeries]

    @property
    def days(self):
        return _apply(qm.Function.DateDifferenceInDays, self.lhs, self.rhs)

    @property
    def weeks(self):
        return self.days // 7

    @property
    def months(self):
        return _apply(qm.Function.DateDifferenceInMonths, self.lhs, self.rhs)

    @property
    def years(self):
        return _apply(qm.Function.DateDifferenceInYears, self.lhs, self.rhs)


@dataclasses.dataclass
class Duration:
    Units = enum.Enum("Units", ["DAYS", "MONTHS", "YEARS"])

    value: Union[int, IntEventSeries, IntPatientSeries]
    units: Units

    def __add__(self, other):
        other = parse_date_if_str(other)
        if isinstance(self.value, int) and isinstance(other, datetime.date):
            # If we're adding a static duration to a static date we can perfom the date
            # arithmetic ourselves
            if self.units is Duration.Units.DAYS:
                return date_utils.date_add_days(other, self.value)
            elif self.units is Duration.Units.MONTHS:
                return date_utils.date_add_months(other, self.value)
            elif self.units is Duration.Units.YEARS:
                return date_utils.date_add_years(other, self.value)
            else:
                assert False
        elif isinstance(other, datetime.date):
            # If we're adding a dynamic duration to a static date, we have to wrap the
            # date up as a Series and let the method in DateFunctions handle it
            return _to_series(other).__add__(self)
        elif isinstance(other, Duration) and self.units == other.units:
            # Durations with the same units can be added
            return Duration(units=self.units, value=(self.value + other.value))
        else:
            # Nothing else is handled
            return NotImplemented

    def __sub__(self, other):
        return self.__add__(other.__neg__())

    def __radd__(self, other):
        return self.__add__(other)

    def __rsub__(self, other):
        return self.__neg__().__add__(other)

    def __neg__(self):
        return Duration(self.value.__neg__(), self.units)


def days(value):
    return Duration(value, Duration.Units.DAYS)


def weeks(value):
    return days(value * 7)


def months(value):
    return Duration(value, Duration.Units.MONTHS)


def years(value):
    return Duration(value, Duration.Units.YEARS)


# CODE SERIES
#


class CodeFunctions:
    def _cast(self, value):
        if isinstance(value, str):
            return self._type(value)
        else:
            return value

    def to_category(self, categorisation, default=None):
        return self.map_values(categorisation, default=default)


class CodeEventSeries(CodeFunctions, EventSeries):
    _type = BaseCode


class CodePatientSeries(CodeFunctions, PatientSeries):
    _type = BaseCode


# CONVERT QUERY MODEL SERIES TO EHRQL SERIES
#


def _wrap(qm_node):
    """
    Wrap a query model series in the ehrQL series class appropriate for its type and
    dimension
    """
    type_ = get_series_type(qm_node)
    is_patient_level = has_one_row_per_patient(qm_node)
    try:
        cls = REGISTERED_TYPES[type_, is_patient_level]
        return cls(qm_node)
    except KeyError:
        # If we don't have a match for exactly this type then we should have one for a
        # superclass
        matches = [
            cls
            for ((target_type, target_dimension), cls) in REGISTERED_TYPES.items()
            if issubclass(type_, target_type) and is_patient_level == target_dimension
        ]
        assert len(matches) == 1
        cls = matches[0]
        wrapped = cls(qm_node)
        wrapped._type = type_
        return wrapped


def _apply(qm_cls, *args):
    """
    Applies a query model operation `qm_cls` to its arguments which can be either ehrQL
    series or static values, returns an ehrQL series
    """
    # Convert all arguments into query model nodes
    qm_args = map(_convert, args)
    qm_node = qm_cls(*qm_args)
    # Wrap the resulting node back up in an ehrQL series
    return _wrap(qm_node)


def _convert(arg):
    # Unpack dictionary arguments
    if isinstance(arg, _DictArg):
        return {_convert(key): _convert(value) for key, value in arg}
    # If it's an ehrQL series then get the wrapped query model node
    elif isinstance(arg, BaseSeries):
        return arg.qm_node
    # If it's a Codelist extract the set of codes and put it in a Value wrapper
    elif isinstance(arg, Codelist):  # pragma: no cover
        return qm.Value(frozenset(arg.codes))
    # Otherwise it's a static value and needs to be put in a query model Value wrapper
    else:
        return qm.Value(arg)


def _to_series(value):
    """
    Return `value` as an ehrQL series

    If it's already an ehrQL series this is a no-op; if it's a static value it will get
    wrapped in a Series of the appropriate type.
    """
    return _wrap(_convert(value))


# FRAME TYPES
#


class BaseFrame:
    def __init__(self, qm_node):
        self.qm_node = qm_node

    def __getattr__(self, name):
        if not name.startswith("__"):
            return self._select_column(name)
        else:
            raise AttributeError(f"object has no attribute {name!r}")

    def _select_column(self, name):
        return _wrap(qm.SelectColumn(source=self.qm_node, name=name))

    def exists_for_patient(self):
        return _wrap(qm.AggregateByPatient.Exists(source=self.qm_node))

    def count_for_patient(self):
        return _wrap(qm.AggregateByPatient.Count(source=self.qm_node))


class PatientFrame(BaseFrame):
    pass


class EventFrame(BaseFrame):
    def take(self, series):
        return EventFrame(
            qm.Filter(
                source=self.qm_node,
                condition=_convert(series),
            )
        )

    def drop(self, series):
        return EventFrame(
            qm.Filter(
                source=self.qm_node,
                condition=qm.Function.Or(
                    lhs=qm.Function.Not(_convert(series)),
                    rhs=qm.Function.IsNull(_convert(series)),
                ),
            )
        )

    def sort_by(self, *order_series):
        qm_node = self.qm_node
        # We expect series to be supplied highest priority first and, as the most
        # recently applied Sort operation has the highest priority, we need to apply
        # them in reverse order
        for series in reversed(order_series):
            qm_node = qm.Sort(
                source=qm_node,
                sort_by=_convert(series),
            )
        return SortedEventFrame(qm_node)


class SortedEventFrame(BaseFrame):
    def first_for_patient(self):
        return PatientFrame(
            qm.PickOneRowPerPatient(
                position=qm.Position.FIRST,
                source=self.qm_node,
            )
        )

    def last_for_patient(self):
        return PatientFrame(
            qm.PickOneRowPerPatient(
                position=qm.Position.LAST,
                source=self.qm_node,
            )
        )


# FRAME CONSTRUCTOR ENTRYPOINTS
#


class SchemaError(Exception):
    ...


# A class decorator which replaces the class definition with an appropriately configured
# instance of the class. Obviously this is a _bit_ odd, but I think worth it overall.
# Using classes to define tables is (as far as I can tell) the only way to get nice
# autocomplete and type-checking behaviour for column names. But we don't actually want
# these classes accessible anywhere: users should only be interacting with instances of
# the classes, and having the classes themselves in the module namespaces only makes
# autocomplete more confusing and error prone.
def table(cls):
    try:
        qm_class = {
            (PatientFrame,): qm.SelectPatientTable,
            (EventFrame,): qm.SelectTable,
        }[cls.__bases__]
    except KeyError:
        raise SchemaError(
            "Schema class must subclass either `PatientFrame` or `EventFrame`"
        )

    qm_node = qm_class(
        name=cls.__name__,
        schema=get_table_schema_from_class(cls),
    )
    return cls(qm_node)


def get_table_schema_from_class(cls):
    # Get all `Series` objects on the class and determine the schema from them
    schema = {
        series.name: qm.Column(series.type_, constraints=series.constraints)
        for series in vars(cls).values()
        if isinstance(series, Series)
    }
    return qm.TableSchema(**schema)


# Defines a PatientFrame along with the data it contains. Takes a list (or
# any iterable) of row tuples of the form:
#
#    (patient_id, column_1_in_schema, column_2_in_schema, ...)
#
def table_from_rows(rows):
    def decorator(cls):
        if cls.__bases__ != (PatientFrame,):
            raise SchemaError("`@table_from_rows` can only be used with `PatientFrame`")
        qm_node = qm.InlinePatientTable(
            rows=qm.IterWrapper(rows),
            schema=get_table_schema_from_class(cls),
        )
        return cls(qm_node)

    return decorator


# A descriptor which will return the appropriate type of series depending on the type of
# frame it belongs to i.e. a PatientSeries subclass for PatientFrames and an EventSeries
# subclass for EventFrames. This lets schema authors use a consistent syntax when
# defining frames of either type.
class Series:
    def __init__(
        self,
        type_,
        description="",
        constraints=(),
        required=True,
        implementation_notes_to_add_to_description="",
        notes_for_implementors="",
    ):
        self.type_ = type_
        self.description = description
        self.constraints = constraints
        self.required = required
        self.implementation_notes_to_add_to_description = (
            implementation_notes_to_add_to_description
        )
        self.notes_for_implementors = notes_for_implementors

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        # Prevent users attempting to interact with the class rather than an instance
        if instance is None:
            raise SchemaError("Missing `@table` decorator on schema class")
        return instance._select_column(self.name)


def get_tables_from_namespace(namespace):
    """
    Yield all ehrQL tables contained in `namespace`
    """
    for attr, value in vars(namespace).items():
        if isinstance(value, BaseFrame):
            yield attr, value


# CASE EXPRESSION FUNCTIONS
#


# TODO: There's no explicit error handling on using this wrong e.g. not calling `then()`
# or passing the wrong sort of thing as `condition`. The query model will prevent any
# invalid queries being created, but we should invest time in making the errors as
# immediate and as friendly as possible.
class when:
    def __init__(self, condition):
        self._condition = condition

    def then(self, value):
        new = self.__class__(self._condition)
        new._value = value
        return new


def case(*when_thens, default=None):
    cases = _DictArg((case._condition, case._value) for case in when_thens)
    # If we don't want a default then we shouldn't supply an argument, or else it will
    # get converted into `Value(None)` which is not what we want
    if default is None:
        return _apply(qm.Case, cases)
    else:
        return _apply(qm.Case, cases, default)
