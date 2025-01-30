import functools
import itertools
import logging
import random
import string
import time
from datetime import date, timedelta

from ehrql.dummy_data.query_info import QueryInfo
from ehrql.query_engines.in_memory import InMemoryQueryEngine
from ehrql.query_engines.in_memory_database import InMemoryDatabase
from ehrql.query_model.introspection import all_inline_patient_ids
from ehrql.query_model.nodes import Dataset
from ehrql.tables import Constraint
from ehrql.utils.regex_utils import create_regex_generator


log = logging.getLogger()


CHARS = string.ascii_letters + string.digits + ".-+_"

# Use caching to avoid constantly re-creating the generators
get_regex_generator = functools.cache(create_regex_generator)


class DummyDataGenerator:
    def __init__(
        self,
        dataset,
        population_size=10,
        batch_size=5000,
        random_seed="BwRV3spP",
        timeout=60,
        today=None,
    ):
        self.dataset = dataset
        self.population_size = population_size
        self.batch_size = batch_size
        self.random_seed = random_seed
        self.timeout = timeout
        # TODO: I dislike using today's date as part of the data generation because it
        # makes the results non-deterministic. However until we're able to infer a
        # suitable time range by inspecting the query, this will have to do.
        self.today = today if today is not None else date.today()
        self.patient_generator = DummyPatientGenerator(
            self.dataset, self.random_seed, self.today
        )
        log.info("Using legacy dummy data generation")

    def get_data(self):
        generator = self.patient_generator
        data = generator.get_empty_data()
        found = 0
        generated = 0

        # Create a version of the query with just the population definition, and an
        # in-memory engine to run it against
        population_query = Dataset(
            population=self.dataset.population, variables={}, events={}
        )
        database = InMemoryDatabase()
        engine = InMemoryQueryEngine(database)

        log.info(
            f"Attempting to generate {self.population_size} matching patients "
            f"(random seed: {self.random_seed}, timeout: {self.timeout}s)"
        )
        log.info(
            "Use `dataset.configure_dummy_data(population_size=N)` "
            "to change number of patients generated"
        )
        start = time.time()

        for patient_id_batch in self.get_patient_id_batches():  # pragma: no branch
            # Generate batches of patient data (just enough to determine population
            # membership) and find those matching the population definition
            patient_batch = {
                patient_id: generator.get_patient_data_for_population_condition(
                    patient_id
                )
                for patient_id in patient_id_batch
            }
            generated += len(patient_batch)
            database.populate(merge_table_data(*patient_batch.values()))
            results = engine.get_results(population_query)
            # Accumulate all data from matching patients, returning once we have enough
            for row in results:
                # Because of the existence of InlinePatientTables it's possible to get
                # patients out of a population which we didn't put in. We want to ignore
                # these.
                if row.patient_id not in patient_batch:
                    continue

                extend_table_data(
                    data,
                    patient_batch[row.patient_id],
                    # Include additional data needed for the dataset but not required just
                    # to determine population membership
                    generator.get_remaining_patient_data(row.patient_id),
                )
                found += 1
                if found >= self.population_size:
                    break

            if found >= self.population_size:
                return data

            log.info(f"Generated {generated} patients, found {found} matching")

            if time.time() - start > self.timeout:
                log.warning(
                    f"Failed to find {self.population_size} matching patients within "
                    f"{self.timeout} seconds — giving up"
                )
                log.info(
                    f"Use e.g. `dataset.configure_dummy_data(timeout={self.timeout * 2})` "
                    f"to try for longer"
                )
                return data

    def get_patient_id_batches(self):
        id_stream = self.get_patient_id_stream()
        while True:
            yield itertools.islice(id_stream, self.batch_size)

    def get_patient_id_stream(self):
        # Where a query involves inline tables we want to extract all the patient IDs
        # and include them in the IDs for which we're going to generate dummy data
        inline_patient_ids = all_inline_patient_ids(self.dataset)
        yield from sorted(inline_patient_ids)
        for i in range(1, 2**63):  # pragma: no branch
            if i not in inline_patient_ids:
                yield i

    def get_results_tables(self):
        database = InMemoryDatabase(self.get_data())
        engine = InMemoryQueryEngine(database)
        return engine.get_results_tables(self.dataset)

    def get_results(self):
        tables = self.get_results_tables()
        yield from next(tables)
        for remaining in tables:
            assert False, "Expected only one results table"


class DummyPatientGenerator:
    def __init__(self, dataset, random_seed, today):
        self.rnd = random.Random()
        self.random_seed = random_seed
        self.today = today
        self.query_info = QueryInfo.from_dataset(dataset)

    def get_patient_data_for_population_condition(self, patient_id):
        # Generate data for just those tables needed for determining whether the patient
        # is included in the population
        return self.get_patient_data(patient_id, self.query_info.population_table_names)

    def get_remaining_patient_data(self, patient_id):
        # Generate data for any tables not included above
        return self.get_patient_data(patient_id, self.query_info.other_table_names)

    def get_patient_data(self, patient_id, table_names):
        # Generate some basic demographic facts about the patient which subsequent table
        # generators can use to ensure a consistent patient history
        self.generate_patient_facts(patient_id)
        data = {}
        for name in table_names:
            # Seed the random generator per-table, so that we get the same data no
            # matter what order the tables are generated in
            self.rnd.seed(f"{self.random_seed}:{patient_id}:{name}")
            table_info = self.query_info.tables[name]
            # Support specialised generators for individual tables, otherwise just make
            # some empty rows
            get_rows = getattr(self, f"rows_for_{table_info.name}", self.empty_rows)
            rows = get_rows(table_info)
            for row in rows:
                # Fill in any values that haven't already been set by a specialised
                # generator
                self.populate_row(table_info, row)
            table_node = table_info.table_node
            column_names = table_node.schema.column_names
            data[table_node] = [
                (patient_id, *[row[c] for c in column_names]) for row in rows
            ]
        return data

    def generate_patient_facts(self, patient_id):
        # Seed the random generator using the patient_id so we always generate the same
        # data for the same patient
        self.rnd.seed(f"{self.random_seed}:{patient_id}")
        # TODO: We could obviously generate more realistic age distributions than this
        date_of_birth = self.today - timedelta(days=self.rnd.randrange(0, 120 * 365))
        age_days = self.rnd.randrange(105 * 365)
        date_of_death = date_of_birth + timedelta(days=age_days)

        self.date_of_birth = date_of_birth
        self.date_of_death = date_of_death if date_of_death < self.today else None
        self.events_start = self.date_of_birth
        self.events_end = min(self.today, date_of_death)

    def rows_for_patients(self, table_info):
        row = {
            "date_of_birth": self.date_of_birth,
            "date_of_death": self.date_of_death,
        }
        # Apply any FirstOfMonth constraints
        for key, value in row.items():
            if key in table_info.columns and value is not None:
                if table_info.columns[key].get_constraint(Constraint.FirstOfMonth):
                    row[key] = value.replace(day=1)
        return [row]

    def rows_for_practice_registrations(self, table_info):
        # TODO: Generate more interesting registration histories; for now, we just
        # assume that every patient is permanently registered with a single practice
        # from birth
        row = {
            "start_date": self.events_start,
            "end_date": None,
        }
        return [row]

    def empty_rows(self, table_info):
        # Generate a small handful of events for event-level tables
        max_rows = 1 if table_info.has_one_row_per_patient else 16
        row_count = self.rnd.randrange(max_rows + 1)
        return [{} for _ in range(row_count)]

    def populate_row(self, table_info, row):
        # Remove any columns created by table generators that aren't used in the query
        for extra_column in row.keys() - table_info.columns:
            del row[extra_column]
        # Populate any columns used in the query which haven't already been set
        for name, column_info in table_info.columns.items():
            if name not in row:
                row[name] = self.get_random_value(column_info)

    def get_random_value(self, column_info):
        # TODO: This never returns None although for realism it sometimes should
        if cat_constraint := column_info.get_constraint(Constraint.Categorical):
            # TODO: It's obviously not true in general that categories are equiprobable
            return self.rnd.choice(cat_constraint.values)
        elif range_constraint := column_info.get_constraint(Constraint.ClosedRange):
            return self.rnd.randrange(
                range_constraint.minimum,
                range_constraint.maximum + 1,
                range_constraint.step,
            )
        elif column_info.values_used:
            if self.rnd.randint(0, len(column_info.values_used)) != 0:
                return self.rnd.choice(column_info.values_used)
        elif column_info.type is bool:
            return self.rnd.choice((True, False))
        elif column_info.type is int:
            # TODO: This distributon is obviously ridiculous but will do for now
            return self.rnd.randrange(100)
        elif column_info.type is float:
            # TODO: As is this
            return self.rnd.random() * 100
        elif column_info.type is str:
            # If the column must match a regex then generate matching strings
            if regex_constraint := column_info.get_constraint(Constraint.Regex):
                generator = get_regex_generator(regex_constraint.regex)
                return generator(self.rnd)
            # A random ASCII string is unlikely to be very useful here, but it at least
            # makes it a bit clearer what the issue is (that we don't know enough about
            # the column to generate anything more helpful) rather than the blank string
            # we always used to return
            return "".join(
                self.rnd.choice(CHARS) for _ in range(self.rnd.randrange(16))
            )
        elif column_info.type is date:
            # Use an exponential distribution to preferentially generate recent events
            # (mean of one year ago). This works OK for the our immediate purposes but
            # we'll no doubt have to iterate on this.
            days_ago = int(self.rnd.expovariate(1 / 365))
            event_date = self.events_end - timedelta(days=days_ago)
            # Clip to the available time range
            event_date = max(event_date, self.events_start)
            # Apply any FirstOfMonth constraints
            if column_info.get_constraint(Constraint.FirstOfMonth):
                event_date = event_date.replace(day=1)
            return event_date
        else:
            assert False, f"Unhandled type: {column_info.type}"

    def get_empty_data(self):
        return {
            table_info.table_node: [] for table_info in self.query_info.tables.values()
        }


def extend_table_data(target, *others):
    for other in others:
        for key, value in other.items():
            target.setdefault(key, []).extend(value)


def merge_table_data(*dicts):
    target = {}
    extend_table_data(target, *dicts)
    return target
