import contextlib
import inspect
import sys

from ehrql.query_engines.in_memory_database import (
    EventColumn,
    PatientColumn,
)
from ehrql.query_engines.sandbox import SandboxQueryEngine
from ehrql.query_language import BaseFrame, BaseSeries, Dataset
from ehrql.query_model import nodes as qm
from ehrql.renderers import truncate_table
from ehrql.utils.docs_utils import exclude_from_docs


@exclude_from_docs
def debug(
    element,
    *other_elements,
    label: str | None = None,
    head: int | None = None,
    tail: int | None = None,
):
    """
    Show the output of the specified element within a dataset definition

    _element_<br>
    Any element within the dataset definition file; can be a string, constant value etc,
    but will typically be a dataset variable (filtered table, column, or a dataset itself.)

    _label_<br>
    Optional label which will be printed in the debug output.

    _head_<br>
    Show only the first N lines. If the output is an ehrQL column, table or dataset, it will
    print only the first N lines of the table.

    _tail_<br>
    Show only the last N lines. If the output is an ehrQL column, table or dataset, it will
    print only the last N lines of the table.

    head and tail arguments can be combined, e.g. to show the first and last 5 lines of a table:

      debug(<table>, head=5, tail=5)
    """
    line_no = inspect.getframeinfo(sys._getframe(1))[1]
    elements = [element, *other_elements]

    if hasattr(element, "__repr_related__") and elements_are_related_series(elements):
        element_reprs = [element.__repr_related__(*other_elements)]
    else:
        element_reprs = [repr(el) for el in elements]

    if head or tail:
        element_reprs = [
            truncate_table(el_repr, head, tail) for el_repr in element_reprs
        ]
    label = f" {label}" if label else ""
    print(f"Debug line {line_no}:{label}", file=sys.stderr)
    for el_repr in element_reprs:
        print(el_repr, file=sys.stderr)


def stop():
    """
    Stop loading the dataset definition at this point.
    """
    line_no = inspect.getframeinfo(sys._getframe(1))[1]
    print(f"Stopping at line {line_no}", file=sys.stderr)


@contextlib.contextmanager
def activate_debug_context(*, dummy_tables_path, render_function):
    # Record original methods
    BaseFrame__repr__ = BaseFrame.__repr__
    BaseSeries__repr__ = BaseSeries.__repr__
    Dataset__repr__ = Dataset.__repr__

    query_engine = SandboxQueryEngine(dummy_tables_path)

    # Temporarily overwrite __repr__ methods to display contents
    BaseFrame.__repr__ = lambda self: query_engine.evaluate(self)._render_(
        render_function
    )
    BaseSeries.__repr__ = lambda self: query_engine.evaluate(self)._render_(
        render_function
    )
    Dataset.__repr__ = lambda self: query_engine.evaluate_dataset(self)._render_(
        render_function
    )
    # Add additional method for displaying related series together
    BaseSeries.__repr_related__ = lambda *args: render_function(
        related_columns_to_records([query_engine.evaluate(series) for series in args])
    )

    try:
        yield
    finally:
        # Restore original methods
        BaseFrame.__repr__ = BaseFrame__repr__
        BaseSeries.__repr__ = BaseSeries__repr__
        Dataset.__repr__ = Dataset__repr__
        del BaseSeries.__repr_related__


def elements_are_related_series(elements):
    qm_nodes = [getattr(el, "_qm_node", None) for el in elements]
    if not all(isinstance(node, qm.Series) for node in qm_nodes):
        return False
    domains = {qm.get_domain(node) for node in qm_nodes}
    return len(domains) == 1


def related_columns_to_records(columns):
    if isinstance(columns[0], PatientColumn):
        return related_patient_columns_to_records(columns)
    elif isinstance(columns[0], EventColumn):
        return related_event_columns_to_records(columns)
    else:
        assert False


def related_patient_columns_to_records(columns):
    for patient_id in columns[0].patient_to_value.keys():
        record = {"patient_id": patient_id}
        for i, column in enumerate(columns, start=1):
            record[f"series_{i}"] = column[patient_id]
        yield record


def related_event_columns_to_records(columns):
    for patient_id, row in columns[0].patient_to_rows.items():
        for row_id in row.keys():
            record = {"patient_id": patient_id, "row_id": row_id}
            for i, column in enumerate(columns, start=1):
                record[f"series_{i}"] = column[patient_id][row_id]
            yield record
