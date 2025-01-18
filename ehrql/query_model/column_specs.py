import dataclasses
from functools import singledispatch
from typing import TypeVar

from ehrql.query_model.nodes import (
    AggregateByPatient,
    Case,
    Constraint,
    SelectColumn,
    SelectPatientTable,
    Value,
    get_root_frame,
    get_series_type,
)


T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class ColumnSpec:
    type: type[T]  # noqa: A003
    nullable: bool = True
    categories: tuple[T] | None = None
    min_value: T | None = None
    max_value: T | None = None


def get_table_specs(dataset):
    """
    Return the specifications for all the results tables this Dataset will produce
    """
    # At present, Datasets only ever produce a single results table (which we call
    # `dataset`) but this gives us the API we need for future expansion
    return {"dataset": get_column_specs_from_variables(dataset.variables)}


def get_column_specs_from_variables(variables):
    """
    Given a dict of dataset variables return a dict of ColumnSpec objects, given
    the types (and other associated metadata) of all the columns in the output
    """
    # TODO: It may not be universally true that IDs are ints. Internally the EMIS IDs
    # are SHA512 hashes stored as hex strings which we convert to ints. But we can't
    # guarantee always to be able to pull this trick.
    column_specs = {"patient_id": ColumnSpec(int, nullable=False)}
    for name, series in variables.items():
        column_specs[name] = get_column_spec_from_series(series)
    return column_specs


def get_column_specs_from_schema(schema):
    # This is a little bit convoluted, but allows us to get consistent behaviour by
    # reusing all the logic above: we create a table node and then create some variables
    # by selecting each column in the schema from it.
    table = SelectPatientTable(name="table", schema=schema)
    variables = {
        column_name: SelectColumn(source=table, name=column_name)
        for column_name in schema.column_names
    }
    return get_column_specs_from_variables(variables)


def get_column_spec_from_series(series):
    type_ = get_series_type(series)
    categories = get_categories(series)
    min_value, max_value = get_range(series)
    if hasattr(type_, "_primitive_type"):
        type_ = type_._primitive_type()
        if categories:
            categories = tuple(c._to_primitive_type() for c in categories)
    return ColumnSpec(
        type_,
        nullable=True,
        categories=categories,
        min_value=min_value,
        max_value=max_value,
    )


@singledispatch
def get_categories(series):
    # As a default, we assume that operations destroy category information and then
    # define specific implementations for operations which preserve categories
    return None


@get_categories.register(SelectColumn)
def get_categories_for_select_column(series):
    # When selecting a column we can ask the underlying table schema for the
    # corresponding categories
    root = get_root_frame(series.source)
    return root.schema.get_column_categories(series.name)


@get_categories.register(AggregateByPatient.Min)
@get_categories.register(AggregateByPatient.Max)
def get_categories_for_min_max(series):
    # The min/max aggregations preserve the categories of their inputs
    return get_categories(series.source)


@get_categories.register(Value)
def get_categories_for_value(series):
    # Static values can be considered categoricals with a single available category
    return (series.value,)


@get_categories.register(Case)
def get_categories_for_case(series):
    # The categories for a Case expression are the combined categories of all its output
    # values, with the proviso that if any output value is non-categorical then the
    # whole expression is non-categorical also
    output_values = list(series.cases.values())
    if series.default is not None:
        output_values.append(series.default)
    all_categories = []
    for output_value in output_values:
        categories = get_categories(output_value)
        # Bail if we've got a non-categorical output value
        if categories is None:
            return None
        all_categories.extend(categories)
    # De-duplicate categories while maintaining their original order
    return tuple(dict.fromkeys(all_categories).keys())


@singledispatch
def get_range(series):
    # For most operations we don't even try to determine the numerical range
    return None, None


@get_range.register(AggregateByPatient.Count)
def get_range_for_count(series):
    # Per-patient row counts can never be negative and we think 65,535 is a reasonable
    # upper bound, meaning they can be stored in a 16-bit unsigned int, thus reducing
    # memory pressure. For counts anywhere near this high the user should be classifying
    # them into buckets rather than retrieving the raw numbers in any case.
    return 0, 2**16 - 1


@get_range.register(SelectColumn)
def get_range_for_select_column(series):
    # When selecting a column we can use the underlying column constraints to return
    # a valid range, if the column has a range constraint
    root = get_root_frame(series.source)
    range_constraint = root.schema.get_column_constraint_by_type(
        series.name, Constraint.ClosedRange
    )
    if range_constraint:
        return range_constraint.minimum, range_constraint.maximum
    return None, None
