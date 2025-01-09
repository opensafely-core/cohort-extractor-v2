from datetime import datetime

import pytest

from tests.lib.docker import ContainerError
from tests.lib.inspect_utils import function_body_as_string
from tests.lib.tpp_schema import AllowedPatientsWithTypeOneDissent, Patient


@function_body_as_string
def trivial_dataset_definition():
    from ehrql import create_dataset
    from ehrql.tables.tpp import patients

    dataset = create_dataset()
    year = patients.date_of_birth.year
    dataset.define_population(year >= 1940)
    dataset.year = year

    dataset.configure_dummy_data(
        population_size=10,
        additional_population_constraint=patients.date_of_death.is_null(),
    )


def test_generate_dataset_in_container(study, mssql_database):
    mssql_database.setup(
        Patient(Patient_ID=1, DateOfBirth=datetime(1943, 5, 5)),
        AllowedPatientsWithTypeOneDissent(Patient_ID=1),
    )

    study.setup_from_string(trivial_dataset_definition)
    study.generate_in_docker(mssql_database, "ehrql.backends.tpp.TPPBackend")
    results = study.results()

    assert len(results) == 1
    assert results[0]["year"] == "1943"


def test_generate_dataset_with_disallowed_operations_in_container(
    study, mssql_database
):
    # End-to-end test to confirm that disallowed operations are blocked when running
    # inside the Docker container. Obviously the below is not a valid dataset definition
    # but we're interested in whether it raises a permissions error vs some other sort
    # of error.
    @function_body_as_string
    def dataset_definition():
        import socket

        # If code isolation is working correctly this should raise a permissions error
        # rather than a timeout
        try:
            socket.create_connection(("192.0.2.0", 53), timeout=0.001)
        except TimeoutError:
            pass

    study.setup_from_string(dataset_definition)
    with pytest.raises(
        ContainerError, match=r"PermissionError: \[Errno 1\] Operation not permitted"
    ):
        study.generate_in_docker(mssql_database, "tpp")
