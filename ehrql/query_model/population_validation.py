from ehrql.query_engines.in_memory import InMemoryQueryEngine
from ehrql.query_engines.in_memory_database import EventTable, PatientTable
from ehrql.query_model.nodes import (
    Dataset,
    Series,
    ValidationError,
    get_series_type,
    has_one_row_per_patient,
)


def validate_population_definition(population):
    """
    Test that a given Series is suitable for use as a population definition
    """
    if not isinstance(population, Series):
        raise ValidationError(
            "population definition must be a `query_model.Series` instance"
        )
    if (
        not has_one_row_per_patient(population)
        or get_series_type(population) is not bool
    ):
        raise ValidationError(
            "population definition must be a one-row-per-patient series of boolean type"
        )
    # We exclude population definitions which evaluate as True when all their inputs are
    # NULL. Here's why.
    #
    # A population definition is a boolean series which is True for all patients who
    # should be included in the population. In SQL terms, you can think of a boolean
    # series as a function, or expression, which takes a row of patient values
    # (potentially drawn from many different tables) and returns True, False or NULL.
    #
    # It is possible to construct definitions which take the value True when all their
    # inputs are NULL. The most trivial example is:
    #
    #   Value(True)
    #
    # i.e. always, unconditionally True for everyone. This might seem silly, but we used
    # to think it was a convenient way to say "just give me all the patients" in test
    # cases.
    #
    # A slightly less trivial example is:
    #
    #   Function.Not(AggregateByPatient.Exists(SelectTable("ons_deaths")))
    #
    # i.e. give me all patients for whom we do not have a death record from ONS. Here
    # the `Exists` aggregation returns False when there is no corresponding row for the
    # patient in the `ons_deaths` table, and the `Not` function transforms that value
    # into True.
    #
    # In both these cases, the expression can be True when evaluated on patients which
    # do not exist in any of the tables referenced by the expression itself. This means
    # that the population we end up with is sensitive to the "universe" of patients we
    # decide to feed in. And some natural-sounding universes, e.g. the union of all
    # patients featuring anywhere in the database, are awkward and expensive to compute.
    #
    # Excluding such definitions means that the minimum set of patients needed to
    # evalute the expression (all patients featuring in tables referenced in the
    # expression) gives the same results as with any larger set. So the question of
    # exactly how we define the patient "universe" goes away.
    #
    # As well as simplifying the implementation there are also good scientific reasons
    # to exclude these kinds of population definitions: a well constructed study should
    # start with a positively defined population (e.g. all patients registered with a
    # practice as of a certain date) from which some patients are then excluded. A
    # population definition like "all patients who have not died" doesn't unambiguously
    # define a universe of patients and so should not be allowed even if we could
    # reliably interpret it.
    #
    # To determine whether a population definition meets this criterion we evaluate it
    # against a variant of the InMemoryQueryEngine which acts as if all its tables are
    # empty. Definitions which evaluate True under these circumstances must be rejected.
    if EmptyQueryEngine(None).series_evaluates_true(population):
        # TODO: Wording could do with more thought here
        raise ValidationError(
            "population definition must not evaluate as True for NULL inputs"
        )
    return True


class EmptyQueryEngine(InMemoryQueryEngine):
    """
    Uses the in-memory query engine to model a database where all referenced tables are
    assumed to exist but are empty. We can then test whether a given series would
    evaluate True under these circumstances.
    """

    # We exploit the fact that the in-memory engine tracks which patients exist
    # independently of the tables they are in; so we can pretend we have a single
    # patient in our "universe" despite all tables being empty.
    @property
    def all_patients(self):
        return {1}

    def series_evaluates_true(self, series):
        results = self.get_results(Dataset(population=series, variables={}, events={}))
        return bool(list(results))

    def visit_SelectTable(self, node):
        column_names = ["patient_id", "row_id", *node.schema.column_names]
        return EventTable.from_records(column_names, row_records=[])

    def visit_SelectPatientTable(self, node):
        column_names = ["patient_id", *node.schema.column_names]
        return PatientTable.from_records(column_names, row_records=[])

    def visit_InlinePatientTable(self, node):
        return self.visit_SelectPatientTable(node)
