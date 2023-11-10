import dataclasses
import datetime
from collections import namedtuple

from ehrql.query_language import (
    VALID_VARIABLE_NAME_RE,
    BoolPatientSeries,
    DummyDataConfig,
    Duration,
    IntPatientSeries,
    Parameter,
    PatientSeries,
)
from ehrql.query_model.nodes import Series


class ValidationError(Exception):
    pass


# Parameters to be used in place of date values when constructing the ehrQL queries
# which define the measures. For ergonomic's sake, we wrap the pair of dates up in a
# namedtuple.
INTERVAL = namedtuple("INTERVAL", ["start_date", "end_date"])(
    start_date=Parameter("interval_start_date", datetime.date),
    end_date=Parameter("interval_end_date", datetime.date),
)

INTERVAL.__class__.__doc__ = """
This is a placeholder value to be used when defining numerator, denominator and group_by
columns in a measure. This allows these definitions to be written once and then be
automatically evaluated over multiple different intervals. It can be used just like any
pair of dates in ehrQL e.g.
```py
clinical_events.date.is_during(INTERVAL)
```
"""

INTERVAL.__class__.start_date.__doc__ = """
Placeholder for the start date (inclusive) of the interval. Can be used like any other
date e.g.
```py
clinical_events.date.is_on_or_after(INTERVAL.start_date)
```
"""

INTERVAL.__class__.end_date.__doc__ = """
Placeholder for the end date (inclusive) of the interval. Can be used like any other
date e.g.
```py
clinical_events.date.is_on_or_before(INTERVAL.end_date)
```
"""


@dataclasses.dataclass
class Measure:
    name: str
    numerator: Series[bool] | Series[int]
    denominator: Series[bool] | Series[int]
    group_by: dict[str, Series]
    intervals: tuple[tuple[datetime.date, datetime.date]]


# This provides an interface for construction a list of `Measure` instances (as above)
# and consists almost entirely of validation logic
class Measures:
    """
    Create a collection of measures with [`create_measures`](#create_measures).
    """

    # These names are used in the measures output table and so can't be used as group_by
    # column names
    RESERVED_NAMES = {
        "measure",
        "numerator",
        "denominator",
        "ratio",
        "interval_start",
        "interval_end",
    }

    def __init__(self):
        self._measures = {}
        self._defaults = {}
        self.dummy_data_config = DummyDataConfig(population_size=None)

    def define_measure(
        self,
        name,
        numerator: BoolPatientSeries | IntPatientSeries | None = None,
        denominator: BoolPatientSeries | IntPatientSeries | None = None,
        group_by: dict[str, PatientSeries] | None = None,
        intervals: list[tuple[datetime.date, datetime.date]] | None = None,
    ):
        """
        Add a measure to the list of measures to be generated.

        _name_<br>
        The name of the measure, as a string.

        _numerator_<br>
        The numerator definition, which must be a patient series but can be either
        boolean or integer.

        _denominator_<br>
        The denominator definition, which must be a patient series but can be either
        boolean or integer.

        _group_by_<br>
        Optional groupings to break down the results by. Must be supplied as a
        dictionary of the form:
        ```py
        {
            "group_name": group_definition,
            ...
        }
        ```

        _intervals_<br>
        A list of start/end date pairs over which to evaluate the measures. These can be
        most conveniently generated using the `starting_on()`/`ending_on()` methods on
        [`years`](#years), [`months`](#months), and [`weeks`](#weeks) e.g.
        ```py
        intervals = months(12).starting_on("2020-01-01")
        ```

        The `numerator`, `denominator` and `intervals` arguments can be omitted if
        default values for them have been set using
        [`define_defaults()`](#Measures.define_defaults).
        """
        # Merge supplied kwargs with defaults and validate
        supplied_kwargs = {
            "numerator": numerator,
            "denominator": denominator,
            "group_by": group_by,
            "intervals": intervals,
        }
        kwargs = {
            key: value if value is not None else self._defaults.get(key)
            for key, value in supplied_kwargs.items()
        }
        self._validate_kwargs(kwargs)

        # It's valid not to supply any group by columns, but we need an empty dict not a
        # None value to make things work
        if kwargs["group_by"] is None:
            kwargs["group_by"] = {}

        # Ensure all required arguments are provided (either directly or by defaults)
        for key, value in kwargs.items():
            if value is None:
                raise ValidationError(
                    f"No value supplied for '{key}' and no default defined"
                )

        # Ensure measure names are valid
        if not VALID_VARIABLE_NAME_RE.match(name):
            raise ValidationError(
                f"Measure names must start with a letter and contain only"
                f" alphanumeric characters and underscores, got: {name!r}"
            )
        # Ensure measure names are unique
        if name in self._measures:
            raise ValidationError(f"Measure already defined with name: {name}")

        # Ensure group_by column definitions are consistent across measures
        for group_name, definition in get_all_group_by_columns(
            self._measures.values()
        ).items():
            if group_name not in kwargs["group_by"]:
                continue
            if kwargs["group_by"][group_name]._qm_node != definition:
                raise ValidationError(
                    f"Inconsistent definition for `group_by` column: {group_name}"
                )

        # Add measure
        self._measures[name] = Measure(
            name=name,
            numerator=kwargs["numerator"]._qm_node,
            denominator=kwargs["denominator"]._qm_node,
            group_by={
                group_name: series._qm_node
                for group_name, series in kwargs["group_by"].items()
            },
            intervals=tuple(sorted(set(kwargs["intervals"]))),
        )

    def define_defaults(
        self,
        numerator: BoolPatientSeries | IntPatientSeries | None = None,
        denominator: BoolPatientSeries | IntPatientSeries | None = None,
        group_by: dict[str, PatientSeries] | None = None,
        intervals: list[tuple[datetime.date, datetime.date]] | None = None,
    ):
        """
        When defining several measures which share common arguments you can reduce
        repetition by defining default values for the measures.

        Note that you can only define a single set of defaults and attempting to call
        this method more than once is an error.
        """
        kwargs = {
            "numerator": numerator,
            "denominator": denominator,
            "group_by": group_by,
            "intervals": intervals,
        }
        if self._defaults:
            raise ValidationError(
                "Defaults already set; cannot call `define_defaults()` more than once"
            )
        self._validate_kwargs(kwargs)
        self._defaults = kwargs

    def _validate_kwargs(self, kwargs):
        self._validate_num_denom(kwargs["numerator"], "numerator")
        self._validate_num_denom(kwargs["denominator"], "denominator")
        self._validate_intervals(kwargs["intervals"])
        self._validate_group_by(kwargs["group_by"])

    def _validate_num_denom(self, value, name):
        if value is None:
            return
        if not isinstance(value, PatientSeries):
            raise ValidationError(
                f"`{name}` must be a one row per patient series,"
                f" got '{type(value)}': {value!r}"
            )
        if value._type not in (bool, int):
            raise ValidationError(
                f"`{name}` must be a boolean or integer series, got '{value._type}'"
            )

    def _validate_intervals(self, intervals):
        if intervals is None:
            return
        if isinstance(intervals, Duration):
            raise ValidationError(
                f"You must supply a date using `{intervals!r}.starting_on('<DATE>')`"
                f" or `{intervals!r}.ending_on('<DATE>')`"
            )
        if not isinstance(intervals, list):
            raise ValidationError(
                f"`intervals` must be a list, got '{type(intervals)}': {intervals!r}"
            )
        for interval in intervals:
            self._validate_interval(interval)

    def _validate_interval(self, interval):
        if (
            not isinstance(interval, tuple)
            or len(interval) != 2
            or not all(isinstance(i, datetime.date) for i in interval)
        ):
            raise ValidationError(
                f"`intervals` must contain pairs of dates, got: {interval!r}"
            )
        if interval[0] > interval[1]:
            raise ValidationError(
                f"Interval start date must be before end date, got: {interval!r}"
            )

    def _validate_group_by(self, group_by):
        if group_by is None:
            return
        if not isinstance(group_by, dict):
            raise ValidationError(
                f"`group_by` must be a dictionary, got '{type(group_by)}': {group_by!r}"
            )
        for key, value in group_by.items():
            if not isinstance(key, str):
                raise ValidationError(
                    f"`group_by` names must be strings, got '{type(key)}': {key!r}"
                )
            if not VALID_VARIABLE_NAME_RE.match(key):
                raise ValidationError(
                    f"`group_by` names must start with a letter and contain only"
                    f" alphanumeric characters and underscores, got: {key!r}"
                )
            if not isinstance(value, PatientSeries):
                raise ValidationError(
                    f"`group_by` values must be one row per patient series,"
                    f"  at '{key}' got '{type(value)}': {value!r}"
                )
        disallowed = self.RESERVED_NAMES.intersection(group_by)
        if disallowed:
            raise ValidationError(
                f"disallowed `group_by` column name: {', '.join(disallowed)}"
            )

    def configure_dummy_data(self, *, population_size):
        """
        Configure the dummy data to be generated.

        ```py
        measures.configure_dummy_data(population_size=10000)
        ```
        """
        self.dummy_data_config.population_size = population_size

    def __iter__(self):
        return iter(self._measures.values())

    def __len__(self):
        return len(self._measures)


def create_measures():
    """
    A measure definition file must define a collection of measures called `measures`.

    ```py
    measures = create_measures()
    ```
    """
    return Measures()


def get_all_group_by_columns(measures):
    """
    Merge all `group_by` dictionaries into a single, flat dictionary
    """
    # We don't need to worry about collisions here because we enforce during measure
    # construction that each name refers consistently to a single column definition
    return {
        name: column
        for measure in measures
        for name, column in measure.group_by.items()
    }
