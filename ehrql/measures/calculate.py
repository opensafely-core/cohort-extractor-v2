import datetime
import time
from collections import defaultdict

from ehrql.measures.measures import get_all_group_by_columns
from ehrql.query_model.column_specs import ColumnSpec, get_column_spec_from_series
from ehrql.query_model.nodes import (
    Dataset,
    Function,
    GroupedSum,
    Value,
    get_series_type,
)
from ehrql.query_model.transforms import substitute_parameters


class MeasuresTimeout(Exception):
    pass


def get_measure_results(query_engine, measures, timeout=259200.0):
    # Group measures by denominator and intervals as we'll handle them together
    grouped = defaultdict(list)
    for measure in measures:
        group_id = (measure.denominator, measure.intervals)
        grouped[group_id].append(measure)

    all_group_by_columns = get_all_group_by_columns(measures).keys()

    measure_timer = MeasureTimer.from_grouped(timeout, grouped)
    for measure_group in grouped.values():
        calculator = MeasureCalculator(measure_group)
        results = calculator.get_results(query_engine)
        for measure, interval, numerator, denominator, group_dict in results:
            ratio = numerator / denominator if denominator else None
            yield (
                measure.name,
                interval[0],
                interval[1],
                ratio,
                numerator,
                denominator,
                # Return a column for every group used across all measures, even if this
                # particular measure doesn't use that group
                *(group_dict.get(name) for name in all_group_by_columns),
            )
            measure_timer.check_timeout(interval)


def get_column_specs_for_measures(measures):
    return {
        "measure": ColumnSpec(
            str,
            categories=tuple(measure.name for measure in measures),
            nullable=False,
        ),
        "interval_start": ColumnSpec(datetime.date, nullable=False),
        "interval_end": ColumnSpec(datetime.date, nullable=False),
        "ratio": ColumnSpec(float),
        "numerator": ColumnSpec(int),
        "denominator": ColumnSpec(int),
        **{
            name: get_column_spec_from_series(column)
            for name, column in get_all_group_by_columns(measures).items()
        },
    }


class MeasureTimer:
    def __init__(self, timeout, num_iterations):
        self.timeout = timeout
        self.num_iterations = num_iterations
        self.previous_interval = None
        self.counter = 0

    @classmethod
    def from_grouped(cls, timeout, grouped):
        num_iterations = sum(
            [len(intervals) for denominator, intervals in grouped.keys()]
        )
        timer = MeasureTimer(timeout, num_iterations)
        timer.start()
        return timer

    def start(self):
        self.start_time = time.time()

    def check_timeout(self, interval):
        if interval != self.previous_interval:
            self.counter += 1
            self.previous_interval = interval
            if self.counter >= 12:
                self.elapsed_time = time.time() - self.start_time
                projected_time = self.elapsed_time / self.counter * self.num_iterations
                if projected_time > self.timeout:
                    raise MeasuresTimeout(
                        f"Generating measures exceeded {self.timeout}s time limit."
                    )


class MeasureCalculator:
    def __init__(self, measures):
        self.denominator = None
        self.intervals = None
        self.population = None
        self.variables = {}
        self.measures = []
        self.grouped_sums = {}
        for measure in measures:
            self.add_measure(measure)
        self.placeholder_dataset = Dataset(
            population=self.population,
            variables=self.variables,
            events={},
            measures=self.grouped_sums,
        )

    def get_results(self, query_engine):
        for interval in self.intervals:
            results = self.get_results_for_interval(query_engine, interval)
            for measure, numerator, denominator, *groups in results:
                group_dict = dict(zip(measure.group_by.keys(), groups))
                yield measure, interval, numerator, denominator, group_dict

    def get_results_for_interval(self, query_engine, interval):
        # Build the query for this interval by replacing the interval start/end
        # placeholders with actual dates
        dataset = substitute_interval_parameters(self.placeholder_dataset, interval)

        for i, table in enumerate(query_engine.get_results_tables(dataset)):
            for row in table:
                yield self.measures[i], *row

    def add_measure(self, measure):
        # Record denominator and intervals from first measure
        if self.denominator is None:
            self.denominator = measure.denominator
            self.intervals = measure.intervals
            self.population = series_as_bool(self.denominator)
        else:
            assert measure.denominator == self.denominator
            assert measure.intervals == self.intervals

        numerator_key = self.add_variable(series_as_int(measure.numerator))
        denominator_key = self.add_variable(series_as_int(measure.denominator))
        group_keys = [self.add_variable(column) for column in measure.group_by.values()]
        self.measures.append(measure)
        self.grouped_sums[measure.name] = GroupedSum(
            sum_over=(numerator_key, denominator_key), group_by=tuple(group_keys)
        )

    def add_variable(self, variable):
        # Return the name and position of `variable` in the variables dict, adding it if not
        # already present
        try:
            return next(
                k for k, v in enumerate(self.variables.items()) if v == variable
            )
        except StopIteration:
            index = len(self.variables)
            key = f"column_{index}"
            self.variables[key] = variable
            return key


def series_as_bool(series):
    series_type = get_series_type(series)
    if series_type is bool:
        return series
    elif series_type is int:
        return Function.GT(series, Value(0))
    else:
        assert False


def series_as_int(series):
    series_type = get_series_type(series)
    if series_type is int:
        return series
    elif series_type is bool:
        return Function.CastToInt(series)
    else:
        assert False


def substitute_interval_parameters(dataset, interval):
    return substitute_parameters(
        dataset,
        interval_start_date=interval[0],
        interval_end_date=interval[1],
    )
