import importlib.util
import textwrap

from hypothesis.vendor.pretty import pretty

from ehrql.query_model.nodes import (
    AggregateByPatient,
    Function,
    SelectColumn,
    SelectPatientTable,
)
from tests.generative.test_query_model import data_setup, schema
from tests.lib.gentest_example_simplify import simplify


# Basic smoketest as a crude guard against breakage
def test_gentest_example_simplify():
    population = AggregateByPatient.Exists(
        SelectPatientTable("p0", schema),
    )
    variable = Function.Negate(
        SelectColumn(SelectPatientTable("p0", schema), "i1"),
    )
    data = [
        {"type": data_setup.P0, "patient_id": 1},
    ]
    partial_output = textwrap.dedent(
        f"""\
        # As might be formatted when copied directly from Hypothesis output
          population={pretty(population)},
          variable={pretty(variable)},
          data={pretty(data)}
        """
    )
    source = simplify(partial_output)
    module = exec_as_module(source)
    assert module.population == population
    assert module.variable == variable
    assert module.data == data

    # Confirm we're idempotent
    assert source == simplify(source)


def exec_as_module(source):
    spec = importlib.util.spec_from_loader("some_module", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(source, module.__dict__)
    return module
