import importlib.util
import textwrap
from pathlib import Path

from hypothesis.vendor.pretty import pretty

from ehrql.query_model.nodes import (
    AggregateByPatient,
    Case,
    Dataset,
    Function,
    InlinePatientTable,
    SelectColumn,
    SelectPatientTable,
    Value,
)
from tests.generative.test_query_model import data_setup, schema
from tests.lib.gentest_example_simplify import simplify


# Basic smoketest as a crude guard against breakage
def test_gentest_example_simplify():
    population = AggregateByPatient.Exists(
        InlinePatientTable(rows=(), schema=schema),
    )
    # This silly example was constructed purely for the purposes of getting 100%
    # coverage of `QueryModelRepr`
    variable = Function.In(
        Case(
            {
                Value(True): Function.MaximumOf(
                    (SelectColumn(SelectPatientTable("p0", schema), "i1"),),
                )
            },
            default=None,
        ),
        Value(frozenset({1, 2, 3})),
    )
    dataset = Dataset(
        population=population,
        variables={"v": variable},
        events={},
    )
    data = [
        {"type": data_setup.P0, "patient_id": 1},
    ]
    partial_output = textwrap.dedent(
        f"""\
        # As might be formatted when copied directly from Hypothesis output
          dataset={pretty(dataset)},
          data={pretty(data)}
        """
    )
    source = simplify(partial_output)
    module = exec_as_module(source)
    assert module.dataset == dataset
    assert module.data == data

    # Confirm we're idempotent
    assert source == simplify(source)


# Check that the simplify command works on a file which is itself tested to be
# executable by the gentests
def test_gentest_example_simplify_on_real_example():
    orig_source = (
        Path(__file__).parents[1].joinpath("generative", "example.py").read_text()
    )
    orig_module = exec_as_module(orig_source)

    simplified_source = simplify(orig_source)
    simplified_module = exec_as_module(simplified_source)

    assert simplified_module.dataset == orig_module.dataset
    assert simplified_module.data == orig_module.data


def exec_as_module(source):
    spec = importlib.util.spec_from_loader("some_module", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(source, module.__dict__)
    return module
