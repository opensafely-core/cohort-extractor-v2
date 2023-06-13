from datetime import date

from ehrql import years
from ehrql.measures import INTERVAL, DummyMeasuresDataGenerator, Measures
from ehrql.tables import Constraint, EventFrame, PatientFrame, Series, table


@table
class patients(PatientFrame):
    sex = Series(
        str,
        constraints=[Constraint.Categorical(["male", "female"])],
    )
    region = Series(
        str,
        constraints=[
            Constraint.Categorical(["London", "The North", "The Countryside"])
        ],
    )


@table
class events(EventFrame):
    date = Series(date)
    code = Series(
        str,
        constraints=[Constraint.Categorical(["abc", "def", "foo"])],
    )


def test_dummy_measures_data_generator():
    events_in_interval = events.where(events.date.is_during(INTERVAL))
    event_count = events_in_interval.count_for_patient()
    foo_event_count = events_in_interval.where(events.code == "foo").count_for_patient()
    had_event = events_in_interval.exists_for_patient()

    intervals = years(2).starting_on("2020-01-01")
    measures = Measures()

    measures.define_measure(
        "foo_events_by_sex",
        numerator=foo_event_count,
        denominator=event_count,
        group_by=dict(sex=patients.sex),
        intervals=intervals,
    )
    measures.define_measure(
        "had_event_by_region",
        numerator=had_event,
        denominator=patients.exists_for_patient(),
        group_by=dict(region=patients.region),
        intervals=intervals,
    )

    results = DummyMeasuresDataGenerator(measures).get_results()
    results = list(results)

    # Check we generated the right number of rows: 2 rows for each breakdown by sex, 3
    # for each breakdown by region
    assert len(results) == (len(intervals) * 2) + (len(intervals) * 3)

    # The dummy data results go through the same code path as the real thing, so we
    # don't need to worry about them being correct; rather than challenge is making sure
    # we generate enough dummy data that matches the numerator/denominator conditions
    # that the results are not empty. So below we assert that, for every numerator and
    # denominator in every interval, something matched i.e. the count was above zero.
    numerators = [row[4] for row in results]
    denominators = [row[5] for row in results]

    assert all(v > 0 for v in numerators)
    assert all(v > 0 for v in denominators)