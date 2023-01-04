import contextlib
import os
import pprint
from collections import defaultdict

import pytest

from databuilder.query_model.nodes import count_nodes, node_types

from . import variable_strategies


class Recorder:
    _inputs = set()

    def record_inputs(self, variable, data):
        hashable_data = frozenset(self._hashable(item) for item in data)
        self._inputs.add((variable, hashable_data))

    @property
    def variables(self):  # pragma: no cover
        return {i[0] for i in self._inputs}

    @property
    def records(self):  # pragma: no cover
        return {i[1] for i in self._inputs}

    @property
    def unique_inputs(self):  # pragma: no cover
        return self._inputs

    @staticmethod
    def _hashable(item):
        copy = item.copy()

        # SQLAlchemy ORM objects aren't hashable, but the name is good enough for us
        copy["type"] = copy["type"].__name__

        # There are only a small number of values in each record and their order is predictable,
        # so we can record just the values as a tuple and recover the field names later
        # if we want them.
        return tuple(copy.values())


@pytest.fixture(scope="session")
def recorder(request):  # pragma: no cover
    recorder_ = Recorder()

    yield recorder_.record_inputs

    if "GENTEST_COMPREHENSIVE" in os.environ:
        check_comprehensive(recorder_)

    if "GENTEST_DEBUG" in os.environ:
        with output_enabled(request):
            show_input_summary(recorder_)


def check_comprehensive(recorder):  # pragma: no cover
    operations_seen = {o for v in recorder.variables for o in node_types(v)}
    variable_strategies.assert_includes_all_operations(operations_seen)


def show_input_summary(recorder):  # pragma: no cover
    print()
    print(f"\n{len(recorder.unique_inputs)} unique input combinations")
    show_variables_summary(recorder)
    show_records_summary(recorder)


def show_variables_summary(recorder):  # pragma: no cover
    print(f"\n{len(recorder.variables)} unique queries")

    counts = [count_nodes(example) for example in recorder.variables]
    print("\nwith this node count distribution")
    for count, num in histogram(counts):
        print(f"{count:3}\t{num}")

    if recorder.variables:
        print("\nlargest query")
        by_size = sorted(recorder.variables, key=lambda v: count_nodes(v))
        pprint.pprint(by_size[-1])

    all_node_types = [
        type_.__name__
        for variable in recorder.variables
        for type_ in node_types(variable)
    ]
    type_histo = histogram(all_node_types)
    print("\nand these node types")
    for type_, num in sorted(type_histo, key=lambda item: item[1], reverse=True):
        print(f"{type_:25}{num}")


def show_records_summary(recorder):  # pragma: no cover
    observed_records = recorder.records
    print(f"\n{len(observed_records)} unique datasets")

    record_counts = [len(records) for records in observed_records]
    print("\nwith this size distribution")
    for count, num in histogram(record_counts):
        print(f"{count:3}\t{num}")


def histogram(samples):  # pragma: no cover
    h = defaultdict(int)
    for sample in samples:
        h[sample] = h[sample] + 1
    return sorted(h.items())


@contextlib.contextmanager
def output_enabled(request):  # pragma: no cover
    capturemanager = request.config.pluginmanager.getplugin("capturemanager")
    with capturemanager.global_and_fixture_disabled():
        yield
