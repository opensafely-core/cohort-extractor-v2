import operator
import statistics
from collections import namedtuple

from ehrql.query_engines.base import BaseQueryEngine
from ehrql.query_engines.in_memory_database import (
    EventTable,
    PatientColumn,
    PatientTable,
    apply_function,
    disregard_null,
    handle_null,
)
from ehrql.query_model import nodes as qm
from ehrql.query_model.introspection import all_inline_patient_ids
from ehrql.query_model.transforms import apply_transforms
from ehrql.utils import date_utils, math_utils


T = True
F = False
N = None


class InMemoryQueryEngine(BaseQueryEngine):
    """A query engine for use in tests.

    Along with the in-memory database, this is intended to support fast query language
    tests, and a to provide a reference implementation for other engines.
    """

    def get_results_tables(self, dataset, measures=None):
        for table in self.get_results_as_in_memory_tables(dataset):
            if measures is not None:
                for sum_over_indexes, group_by_indexes in measures:
                    measure_groups = dict()
                    for record in table.to_records():
                        record_values = list(record.values())
                        measure_group_key = tuple(
                            record_values[group_index]
                            for group_index in group_by_indexes
                        )
                        measure_groups.setdefault(
                            measure_group_key, [0 for _ in sum_over_indexes]
                        )
                        for i, sum_over_index in enumerate(sum_over_indexes):
                            if record_values[sum_over_index] is not None:
                                measure_groups[measure_group_key][i] += record_values[
                                    sum_over_index
                                ]
                    yield (
                        (*group_counts, *group_key)
                        for group_key, group_counts in measure_groups.items()
                    )
            else:
                # The row_id column is an internal implementation detail of the in-memory
                # engine and should not appear in the results
                columns = [
                    name for name in table.name_to_col.keys() if name != "row_id"
                ]
                Row = namedtuple("Row", columns)
                yield (Row(*(r[c] for c in columns)) for r in table.to_records())

    def get_results_as_in_memory_tables(self, dataset):
        assert isinstance(dataset, qm.Dataset)

        self.cache = {}

        dataset = apply_transforms(dataset)

        # If the query contains any InlinePatientTables then we need to include all the
        # patient IDs contained in those in our big list of all the patients
        all_patients = self.all_patients.union(all_inline_patient_ids(dataset))

        # Determine the population
        population = self.visit(dataset.population)
        assert isinstance(population, PatientColumn)

        # Build PatientColumns for the ID and each patient-level variable
        name_to_col = {
            "patient_id": PatientColumn(
                {patient: patient for patient in all_patients},
                default=None,
            )
        }
        for name, node in dataset.variables.items():
            col = self.visit(node)
            assert isinstance(col, PatientColumn)
            name_to_col[name] = col

        # Combine the columns into a PatientTable
        table = PatientTable(name_to_col)
        # Filter out any rows associated with patients not in the population
        table = table.filter(population)

        # Build any specified EventTables
        other_tables = [
            self.visit(frame).filter(population) for frame in dataset.events.values()
        ]

        return [table, *other_tables]

    @property
    def database(self):
        # Hack!  When other engine classes are instantiated, they are passed the URL to
        # a database to connect to.  Since our database is just an object in our
        # process, we instantiate this engine with an instance of the database.  See
        # InMemoryDatabase.host_url.
        return self.dsn

    @property
    def tables(self):
        return self.database.tables

    @property
    def all_patients(self):
        return self.database.all_patients

    def visit(self, node):
        value = self.cache.get(node)
        if value is None:
            visitor = getattr(self, f"visit_{type(node).__name__}")
            value = visitor(node)
            self.cache[node] = value
        return value

    def visit_Code(self, node):
        assert False

    def visit_Value(self, node):
        if isinstance(node.value, frozenset):
            value = frozenset(self.convert_value(v) for v in node.value)
        else:
            value = self.convert_value(node.value)
        return PatientColumn(
            {patient: value for patient in self.all_patients},
            default=value,
        )

    def visit_NoneType(self, node):
        return PatientColumn({}, None)

    def convert_value(self, value):
        if hasattr(value, "_to_primitive_type"):
            return value._to_primitive_type()
        else:
            return value

    def visit_SelectTable(self, node):
        return self.tables[node.name]

    def visit_SelectPatientTable(self, node):
        return self.tables[node.name]

    def visit_SelectColumn(self, node):
        return self.visit(node.source)[node.name]

    def visit_Filter(self, node):
        return self.visit(node.source).filter(self.visit(node.condition))

    def visit_Sort(self, node):
        source = self.visit(node.source)
        sort_column = self.visit(node.sort_by)
        return source.sort(sort_column.sort_index())

    def visit_PickOneRowPerPatient(self, node):
        ix = {
            qm.Position.FIRST: 0,
            qm.Position.LAST: -1,
        }[node.position]
        return self.visit(node.source).pick_at_index(ix)

    def visit_PickOneRowPerPatientWithColumns(self, node):
        return self.visit_PickOneRowPerPatient(node)

    def visit_Exists(self, node):
        return self.visit(node.source).exists()

    def visit_Count(self, node):
        return self.visit(node.source).count()

    def visit_CountDistinct(self, node):
        def count_distinct(series):
            return len(set(series))

        col = self.visit(node.source)
        return col.aggregate_values(count_distinct, default=0)

    def visit_CountEpisodes(self, node):
        def count_episodes(dates):
            # The `aggregate_values` method below filters out Nones and handles empty
            # lists so we don't need to deal with those here
            dates = sorted(dates)
            return 1 + sum(
                1 if (dates[i] - dates[i - 1]).days > node.maximum_gap_days else 0
                for i in range(1, len(dates))
            )

        col = self.visit(node.source)
        return col.aggregate_values(count_episodes, default=0)

    def visit_Min(self, node):
        col = self.visit(node.source)
        return col.aggregate_values(min, default=None)

    def visit_Max(self, node):
        col = self.visit(node.source)
        return col.aggregate_values(max, default=None)

    def visit_Sum(self, node):
        col = self.visit(node.source)
        return col.aggregate_values(sum, default=None)

    def visit_Mean(self, node):
        col = self.visit(node.source)
        return col.aggregate_values(statistics.fmean, default=None)

    def visit_CombineAsSet(self, node):
        col = self.visit(node.source)
        return col.aggregate_values(frozenset, default=frozenset())

    def visit_unary_op(self, node, op):
        series = self.visit(node.source)
        return apply_function(op, series)

    def visit_unary_op_with_null(self, node, op):
        return self.visit_unary_op(node, handle_null(op))

    def visit_binary_op(self, node, op):
        lhs = self.visit(node.lhs)
        rhs = self.visit(node.rhs)
        return apply_function(op, lhs, rhs)

    def visit_nary_op(self, node, op):
        sources = [*node.sources]
        columns = [self.visit(s) for s in sources]
        return apply_function(op, *columns)

    def visit_nary_op_disregarding_null(self, node, op):
        return self.visit_nary_op(node, disregard_null(op))

    def visit_binary_op_with_null(self, node, op):
        return self.visit_binary_op(node, handle_null(op))

    def visit_EQ(self, node):
        return self.visit_binary_op_with_null(node, operator.eq)

    def visit_NE(self, node):
        return self.visit_binary_op_with_null(node, operator.ne)

    def visit_LT(self, node):
        return self.visit_binary_op_with_null(node, operator.lt)

    def visit_LE(self, node):
        return self.visit_binary_op_with_null(node, operator.le)

    def visit_GT(self, node):
        return self.visit_binary_op_with_null(node, operator.gt)

    def visit_GE(self, node):
        return self.visit_binary_op_with_null(node, operator.ge)

    def visit_And(self, node):
        def op(lhs, rhs):
            return {
                (T, T): T,
                (T, N): N,
                (T, F): F,
                (N, T): N,
                (N, N): N,
                (N, F): F,
                (F, T): F,
                (F, N): F,
                (F, F): F,
            }[lhs, rhs]

        return self.visit_binary_op(node, op)

    def visit_Or(self, node):
        def op(lhs, rhs):
            return {
                (T, T): T,
                (T, N): T,
                (T, F): T,
                (N, T): T,
                (N, N): N,
                (N, F): N,
                (F, T): T,
                (F, N): N,
                (F, F): F,
            }[lhs, rhs]

        return self.visit_binary_op(node, op)

    def visit_Not(self, node):
        def op(value):
            return {
                T: F,
                N: N,
                F: T,
            }[value]

        return self.visit_unary_op(node, op)

    def visit_IsNull(self, node):
        def op(value):
            return value is None

        return self.visit_unary_op(node, op)

    def visit_Negate(self, node):
        return self.visit_unary_op_with_null(node, operator.neg)

    def visit_Add(self, node):
        return self.visit_binary_op_with_null(node, operator.add)

    def visit_Subtract(self, node):
        return self.visit_binary_op_with_null(node, operator.sub)

    def visit_Multiply(self, node):
        return self.visit_binary_op_with_null(node, operator.mul)

    def visit_TrueDivide(self, node):
        return self.visit_binary_op_with_null(node, math_utils.truediv)

    def visit_FloorDivide(self, node):
        return self.visit_binary_op_with_null(node, math_utils.floordiv)

    def visit_CastToInt(self, node):
        return self.visit_unary_op_with_null(node, int)

    def visit_CastToFloat(self, node):
        return self.visit_unary_op_with_null(node, float)

    def visit_DateAddDays(self, node):
        return self.visit_binary_op_with_null(node, date_utils.date_add_days)

    def visit_DateAddMonths(self, node):
        return self.visit_binary_op_with_null(node, date_utils.date_add_months)

    def visit_DateAddYears(self, node):
        return self.visit_binary_op_with_null(node, date_utils.date_add_years)

    def visit_DateDifferenceInDays(self, node):
        return self.visit_binary_op_with_null(node, date_utils.date_difference_in_days)

    def visit_DateDifferenceInMonths(self, node):
        return self.visit_binary_op_with_null(
            node, date_utils.date_difference_in_months
        )

    def visit_DateDifferenceInYears(self, node):
        return self.visit_binary_op_with_null(node, date_utils.date_difference_in_years)

    def visit_YearFromDate(self, node):
        return self.visit_unary_op_with_null(node, date_utils.year_from_date)

    def visit_MonthFromDate(self, node):
        return self.visit_unary_op_with_null(node, date_utils.month_from_date)

    def visit_DayFromDate(self, node):
        return self.visit_unary_op_with_null(node, date_utils.day_from_date)

    def visit_ToFirstOfYear(self, node):
        return self.visit_unary_op_with_null(node, date_utils.to_first_of_year)

    def visit_ToFirstOfMonth(self, node):
        return self.visit_unary_op_with_null(node, date_utils.to_first_of_month)

    def visit_StringContains(self, node):
        return self.visit_binary_op_with_null(node, operator.contains)

    def visit_In(self, node):
        def op(lhs, rhs):
            if len(rhs) == 0:
                return False
            elif lhs is None:
                return None
            else:
                return lhs in rhs

        return self.visit_binary_op(node, op)

    def visit_Case(self, node):
        cases = [
            (self.visit(condition), self.visit(value))
            for condition, value in node.cases.items()
        ]
        default = self.visit(node.default)
        # Flatten arguments into a single list for easier handling
        arguments = [default, *[i for pair in cases for i in pair]]
        return apply_function(case_flattened, *arguments)

    def visit_InlinePatientTable(self, node):
        col_names = node.schema.column_names
        return PatientTable.from_records(
            col_names=["patient_id"] + col_names,
            row_records=node.rows,
        )

    def visit_MaximumOf(self, node):
        return self.visit_nary_op_disregarding_null(node, max)

    def visit_MinimumOf(self, node):
        return self.visit_nary_op_disregarding_null(node, min)

    def visit_SeriesCollectionFrame(self, node):
        columns = [self.visit(series) for series in node.members.values()]
        # Combine the list of columns into a single column of tuples (doing things
        # this way allows us to use `apply_fuction` which handles lining everything
        # up correctly for us)
        combined = apply_function(lambda *args: args, *columns)
        # Expand the single column of tuples out into a table of multiple columns
        return EventTable.from_records(
            ["patient_id", "row_id", *node.members.keys()],
            (
                (record["patient_id"], record["row_id"], *record["value"])
                for record in combined.to_records()
            ),
        )


def case_flattened(default, *cases):
    """
    Implements CASE WHEN x THEN y ELSE x END logic but takes its arguments in a
    flattened form:

        default, condition_1, value_1, condition_2, value_2, ... condition_N, value_N

    This means it can be passed directly to `apply_function_to_columns` without needing
    to do any special argument handling.
    """
    for condition, value in zip(cases[::2], cases[1::2]):
        if condition:
            return value
    return default
