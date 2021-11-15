from cohortextractor.concepts import tables
from cohortextractor.definition import Cohort, pick_first_value, register
from cohortextractor.definition.base import cohort_registry
from cohortextractor.query_language import table
from cohortextractor.query_utils import get_column_definitions

from .lib.util import TestCohort


def test_minimal_cohort_definition():
    # Nothing in the registry yet
    assert not cohort_registry.cohorts

    # old DSL
    class OldCohort(TestCohort):
        #  Define tables of interest, filtered to relevant values
        code = table("clinical_events").first_by("date").get("code")

    # new DSL
    cohort = Cohort()
    registrations = tables.practice_registrations
    cohort.population = registrations.select_column(
        registrations.patient_id
    ).make_one_row_per_patient(pick_first_value)
    events = tables.clinical_events
    cohort.code = events.select_column(events.code).make_one_row_per_patient(
        pick_first_value
    )

    register(cohort)
    assert cohort in cohort_registry.cohorts

    assert_cohorts_equivalent(cohort, OldCohort)


def test_filter():
    class OldCohort:
        # Define tables of interest, filtered to relevant values
        code = (
            table("clinical_events")
            .filter("date", greater_than="2021-01-01")
            .first_by("date")
            .get("code")
        )

    cohort = Cohort()
    events = tables.clinical_events
    cohort.code = (
        events.filter(events.date, greater_than="2021-01-01")
        .select_column(events.code)
        .make_one_row_per_patient(pick_first_value)
    )

    assert_cohorts_equivalent(cohort, OldCohort)


def test_multiple_filters():
    class OldCohort:
        # Define tables of interest, filtered to relevant values
        code = (
            table("clinical_events")
            .filter("date", greater_than="2021-01-01")
            .filter("date", less_than="2021-10-10")
            .first_by("date")
            .get("code")
        )

    cohort = Cohort()
    events = tables.clinical_events
    cohort.code = (
        events.filter(events.date, greater_than="2021-01-01")
        .filter(events.date, less_than="2021-10-10")
        .select_column(events.code)
        .make_one_row_per_patient(pick_first_value)
    )

    assert_cohorts_equivalent(cohort, OldCohort)


def assert_cohorts_equivalent(dsl_cohort, qm_cohort):
    """Verify that a cohort defined via Query Model objects has the same columns as a
    cohort defined via the DSL.

    Since some Query Model objects override `.__eq__`, we cannot compare two objects
    with `==`.  Instead, we compare their representations, which, thanks to dataclasses,
    contain all the information we need to compare for equality.
    """

    # Cohorts are equivalent if they have the same columns...
    dsl_col_defs = get_column_definitions(dsl_cohort)
    qm_col_defs = get_column_definitions(qm_cohort)
    assert dsl_col_defs.keys() == qm_col_defs.keys()

    # ...and if the columns are the same.
    for k in dsl_col_defs:
        assert repr(dsl_col_defs[k]) == repr(qm_col_defs[k])
