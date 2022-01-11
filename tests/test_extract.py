from databuilder.query_model import Table

from .lib.contracts import Events
from .lib.mock_backend import CTV3Events, RegistrationHistory
from .lib.util import OldCohortWithPopulation


def test_pick_a_single_value(engine):
    input_data = [
        RegistrationHistory(PatientId=1),
        CTV3Events(PatientId=1, EventCode="xyz"),
    ]
    engine.setup(input_data)

    class Cohort(OldCohortWithPopulation):
        code = Table(Events).first_by("patient_id").get("code")

    expected = [{"patient_id": 1, "code": "xyz"}]

    actual = engine.extract(Cohort)
    assert actual == expected
