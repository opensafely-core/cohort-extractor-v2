"""This module provides classes for building a cohort using the DSL.

Database tables are modelled by PatientFrame (a collection of records with one record
per patient) and EventFrame (a collection of records with multiple records per patient).

Through filtering, sorting, aggregating, and selecting columns, we transform instances
of PatientFrame/EventFrame into instances of PatientSeries.

A PatientSeries represents a mapping from a patient to a value, and can be assigned to a
Cohort.  In the future, a PatientSeries will be able to be combined with another
PatientSeries or a single value to produce a new PatientSeries.

All classes except Cohort are intended to be immutable.

Methods are designed so that users can only perform actions that are semantically
meaningful.  This means that the order of operations is restricted.  In a terrible ASCII
railway diagram:

             +---+
             |   V
      filter |  EventFrame -----------------------+
             |   |   |                            |
             +---+   | sort_by                    |
                     V                            |
             SortedEventFrame                     |
                     |                            |
                     | (first/last)_for_patient   | (count/exists)_for_patient
                     V                            |
                PatientFrame                      |
                     |                            |
                     | select_column              |
                     V                            |
          +--> PatientSeries <--------------------+
  round_X |          |
          +----------+

To support providing helpful error messages, we can implement __getattr__ on each class.
This will intercept any lookup of a missing attribute, so that if eg a user tries to
select a column from a SortedEventFrame, we can tell them they need to aggregate the
SortedEventFrame first_for_patient.

This docstring, and the function docstrings in this module are not currently intended
for end users.
"""

from __future__ import annotations

from dataclasses import dataclass

from .query_model_old import BaseTable, Codelist, Comparator, Value, ValueFromAggregate


class Cohort:
    """
    Represents the cohort of patients in the defined study.
    """

    def set_population(self, population: PatientSeries) -> None:
        """
        Sets the population that are included within the Cohort.

        Args:
            population: A boolean series indicating if any given patient
                are included within the Cohort
        """

        self.population = population
        value = population.value

        if not (
            isinstance(value, ValueFromAggregate) and value.source.function == "exists"
        ):
            raise ValueError(
                "Population variable must return a boolean. Did you mean to use `exists_for_patient()`?"
            )

    def add_variable(self, name: str, variable: PatientSeries) -> None:
        """
        Add a variable to this Cohort with a given name.

        Args:
            name: The name of the variable to add
            variable: The PatientSeries to add as the named variable.
        """

        self.__setattr__(name, variable)

    def __setattr__(self, name: str, variable: PatientSeries) -> None:
        if not isinstance(variable, PatientSeries):
            raise TypeError(
                f"{name} must be a single value per patient (got '{variable.__class__.__name__}')"
            )
        super().__setattr__(name, variable)


class PatientSeries:
    """
    Represents a column indexed by patient.

    Can be used as a variable in a Cohort, or as an input when computing another
    variable.
    """

    def __init__(self, value: Value | Comparator):
        self.value = value

    def _is_comparator(self) -> bool:
        return isinstance(self.value, Comparator)

    def __eq__(self, other: PatientSeries | Comparator | str | int) -> PatientSeries:  # type: ignore[override]
        # All python objects have __eq__ and __ne__ defined, so overriding these methods
        # involves overriding them on a superclass (`object`), which results in
        # a typing error as it violates the violates the Liskov substitution principle
        # https://mypy.readthedocs.io/en/stable/common_issues.html#incompatible-overrides
        # We are deliberately overloading the operators here, hence the ignore
        other_value = other.value if isinstance(other, PatientSeries) else other
        return PatientSeries(value=self.value == other_value)

    def __ne__(self, other: PatientSeries | Comparator | str | int) -> PatientSeries:  # type: ignore[override]
        other_value = other.value if isinstance(other, PatientSeries) else other
        return PatientSeries(value=self.value != other_value)

    def __hash__(self) -> int:
        return hash(repr(self.value))

    def __invert__(self) -> PatientSeries:
        if self._is_comparator():
            comparator_value = ~self.value
        else:
            comparator_value = Comparator(
                lhs=self.value, operator="__ne__", rhs=None, negated=True
            )
        return PatientSeries(value=comparator_value)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(value={self.value})"


class Predicate:
    def __init__(
        self,
        column: Column,
        operator: str,
        other: str | bool | int | Codelist | None,
    ) -> None:
        self._column = column
        self._operator = operator
        self._other = other

    def apply_to(self, table: BaseTable) -> BaseTable:
        return table.filter(self._column.name, **{self._operator: self._other})


@dataclass
class Column:
    name: str
    series_type: type

    def is_not_null(self):
        return Predicate(self, "not_equals", None)


class IdColumn(Column):
    def __init__(self, name):
        super().__init__(name, PatientSeries)


class BoolColumn(Column):
    def __init__(self, name):
        super().__init__(name, PatientSeries)

    def is_true(self) -> Predicate:
        return Predicate(self, "equals", True)

    def is_false(self) -> Predicate:
        return Predicate(self, "equals", False)

    def __eq__(self, other: bool) -> Predicate:  # type: ignore[override]  # deliberately inconsistent with object
        if other:
            return self.is_true()
        else:
            return self.is_false()

    def __ne__(self, other: bool) -> Predicate:  # type: ignore[override]  # deliberately inconsistent with object
        if other:
            return self.is_false()
        else:
            return self.is_true()


class DateColumn(Column):
    def __init__(self, name):
        super().__init__(name, PatientSeries)

    def __eq__(self, other: str) -> Predicate:  # type: ignore[override]  # deliberately inconsistent with object
        return Predicate(self, "equals", other)

    def __ne__(self, other: str) -> Predicate:  # type: ignore[override]  # deliberately inconsistent with object
        return Predicate(self, "not_equals", other)

    def __gt__(self, other: str) -> Predicate:
        return Predicate(self, "greater_than", other)

    def __ge__(self, other: str) -> Predicate:
        return Predicate(self, "greater_than_or_equals", other)

    def __lt__(self, other: str) -> Predicate:
        return Predicate(self, "less_than", other)

    def __le__(self, other: str) -> Predicate:
        return Predicate(self, "less_than_or_equals", other)


class CodeColumn(Column):
    def __init__(self, name):
        super().__init__(name, PatientSeries)

    def __eq__(self, other: str) -> Predicate:  # type: ignore[override]  # deliberately inconsistent with object
        return Predicate(self, "equals", other)

    def __ne__(self, other: str) -> Predicate:  # type: ignore[override]  # deliberately inconsistent with object
        return Predicate(self, "not_equals", other)

    def is_in(self, codelist: Codelist) -> Predicate:
        return Predicate(self, "is_in", codelist)


class IntColumn(Column):
    def __init__(self, name):
        super().__init__(name, PatientSeries)

    def __eq__(self, other: int) -> Predicate:  # type: ignore[override]  # deliberately inconsistent with object
        return Predicate(self, "equals", other)

    def __ne__(self, other: int) -> Predicate:  # type: ignore[override]  # deliberately inconsistent with object
        return Predicate(self, "not_equals", other)

    def __gt__(self, other: int) -> Predicate:
        return Predicate(self, "greater_than", other)

    def __ge__(self, other: int) -> Predicate:
        return Predicate(self, "greater_than_or_equals", other)

    def __lt__(self, other: int) -> Predicate:
        return Predicate(self, "less_than", other)

    def __le__(self, other: int) -> Predicate:
        return Predicate(self, "less_than_or_equals", other)


class FloatColumn(Column):
    def __init__(self, name):
        super().__init__(name, PatientSeries)


class StrColumn(Column):
    def __init__(self, name):
        super().__init__(name, PatientSeries)
