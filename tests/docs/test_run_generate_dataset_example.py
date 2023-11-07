import textwrap
import unittest

import pytest

from . import test_complete_examples


def test_run_generate_dataset_example(tmp_path):
    example = test_complete_examples.DatasetDefinitionExample(
        path="test",
        fence_number=1,
        source=textwrap.dedent(
            """\
            from ehrql import create_dataset
            from ehrql.tables.beta.tpp import patients

            dataset = create_dataset()
            dataset.define_population(patients.exists_for_patient())
            """
        ),
    )
    test_complete_examples.test_ehrql_generate_dataset_example(tmp_path, example)


def test_run_generate_dataset_example_failing(tmp_path):
    example = test_complete_examples.DatasetDefinitionExample(
        path="test",
        fence_number=1,
        source=textwrap.dedent(
            """\
            from ehrql import create_dataset

            dataset = create_dataset()
            dataset.define_population(not_a_function())
            """
        ),
    )
    with pytest.raises(test_complete_examples.DatasetDefinitionTestError) as exc_info:
        test_complete_examples.test_ehrql_generate_dataset_example(tmp_path, example)
    assert type(exc_info.value) is test_complete_examples.DatasetDefinitionTestError


def test_run_generate_dataset_example_failing_codelist_from_csv_call(tmp_path):
    example = test_complete_examples.DatasetDefinitionExample(
        path="test",
        fence_number=1,
        source=textwrap.dedent(
            """\
            from ehrql import codelist_from_csv, create_dataset
            from ehrql.tables.beta.tpp import patients

            codes = codelist_from_csv()

            dataset = create_dataset()
            dataset.define_population(patients.exists_for_patient())
            """
        ),
    )

    with pytest.raises(
        test_complete_examples.DatasetDefinitionTestError,
        match=r"generate_dataset failed for example",
    ) as exc_info:
        test_complete_examples.test_ehrql_generate_dataset_example(tmp_path, example)
    assert type(exc_info.value) is test_complete_examples.DatasetDefinitionTestError


def test_run_generate_dataset_example_gives_unreadable_csv(tmp_path):
    example = test_complete_examples.DatasetDefinitionExample(
        path="test",
        fence_number=1,
        source=textwrap.dedent(
            """\
            from ehrql import create_dataset
            from ehrql.tables.beta.tpp import patients

            dataset = create_dataset()
            dataset.define_population(patients.exists_for_patient())
            """
        ),
    )
    with unittest.mock.patch("ehrql.main.generate_dataset", return_value=None):
        with pytest.raises(
            test_complete_examples.DatasetDefinitionTestError,
            match=r"Check of output dataset CSV failed for example",
        ) as exc_info:
            test_complete_examples.test_ehrql_generate_dataset_example(
                tmp_path, example
            )
    assert type(exc_info.value) is test_complete_examples.DatasetDefinitionTestError
