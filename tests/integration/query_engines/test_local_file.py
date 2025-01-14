from pathlib import Path

from ehrql import Dataset
from ehrql.query_engines.local_file import LocalFileQueryEngine
from ehrql.tables import EventFrame, PatientFrame, Series, table


FIXTURES = Path(__file__).parents[2] / "fixtures" / "local_file_engine"


@table
class patients(PatientFrame):
    sex = Series(str)


@table
class events(EventFrame):
    score = Series(int)
    # Columns in the schema which aren't in the data files should just end up NULL
    expected_missing = Series(bool)


def test_local_file_query_engine():
    dataset = Dataset()
    dataset.sex = patients.sex
    dataset.total_score = events.score.sum_for_patient()
    # Check that missing columns end up NULL
    dataset.missing = events.where(
        events.expected_missing.is_null()
    ).count_for_patient()

    dataset.define_population(patients.exists_for_patient())
    dataset_qm = dataset._compile()

    query_engine = LocalFileQueryEngine(FIXTURES)
    results = query_engine.get_results(dataset_qm)

    assert list(results) == [
        (1, "M", 9, 3),
        (2, "F", 15, 2),
        (3, None, None, 0),
    ]
