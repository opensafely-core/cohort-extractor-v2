import dataclasses
from functools import reduce

from ehrql.dummy_data import DummyDataGenerator
from ehrql.measures.calculate import (
    get_all_group_by_columns,
    get_measure_results,
    series_as_bool,
    substitute_interval_parameters,
)
from ehrql.query_engines.in_memory import InMemoryQueryEngine
from ehrql.query_engines.in_memory_database import InMemoryDatabase
from ehrql.query_model.nodes import Dataset, Function


class DummyMeasuresDataGenerator:
    def __init__(self, measures, dummy_data_config, **kwargs):
        self.measures = measures
        combined = CombinedMeasureComponents.from_measures(measures)
        self.generator = DummyDataGenerator(
            get_dataset(combined),
            population_size=get_population_size(dummy_data_config, combined),
            timeout=dummy_data_config.timeout,
            **kwargs,
        )

    def get_data(self):
        return self.generator.get_data()

    def get_results(self):
        database = InMemoryDatabase(self.get_data())
        engine = InMemoryQueryEngine(database)
        return get_measure_results(engine, self.measures)


@dataclasses.dataclass
class CombinedMeasureComponents:
    """
    Represents a de-duplicated collection of all the components used in a collection of
    measures
    """

    denominators: set
    numerators: set
    groups: set
    intervals: set

    @classmethod
    def from_measures(cls, measures):
        return cls(
            denominators={series_as_bool(m.denominator) for m in measures},
            numerators={m.numerator for m in measures},
            groups=get_all_group_by_columns(measures).values(),
            intervals={interval for m in measures for interval in m.intervals},
        )


def get_dataset(combined):
    """
    Return a query model dataset suitable for passing to the dummy data generator which
    should produce dummy data of the right shape to use for calculating measures
    """
    dataset_placeholders = Dataset(
        # Use the union of all denominators as the population
        population=reduce(Function.Or, combined.denominators),
        variables={
            f"column_{i}": column
            for i, column in enumerate([*combined.numerators, *combined.groups])
        },
        events={},
    )

    # Use the maximum range over all intervals as a date range
    min_interval_start = min(interval[0] for interval in combined.intervals)
    max_interval_end = max(interval[1] for interval in combined.intervals)

    return substitute_interval_parameters(
        dataset_placeholders, (min_interval_start, max_interval_end)
    )


def get_population_size(dummy_data_config, combined):
    """
    Return the configured population size, or if none is configured
    make a totally unscientific guess as to how many dummy patients to generate to
    produce a "big enough" population to generate a "reasonable" amount of non-zero
    measure results
    """
    if dummy_data_config.population_size is not None:
        return dummy_data_config.population_size
    return (
        10
        * len(combined.denominators)
        * len(combined.intervals)
        # Denominators and intervals are both guaranteed to be non-empty, but we
        # need to make sure we produce a non-zero value when `groups` is empty
        * max(1, len(combined.groups))
    )
