from functools import reduce

from ehrql.query_engines.in_memory_database import apply_function
from ehrql.query_engines.local_file import LocalFileQueryEngine
from ehrql.query_language import Dataset, DateDifference
from ehrql.query_model.introspection import get_table_nodes
from ehrql.query_model.nodes import AggregateByPatient, Function
from ehrql.query_model.nodes import Dataset as DatasetQM


class DebugQueryEngine(LocalFileQueryEngine):
    def evaluate_dataset(self, dataset):
        variables_qm = {k: v._qm_node for k, v in dataset.variables.items()}
        if getattr(dataset, "population", None) is None:
            if not variables_qm:
                return EmptyDataset()
            else:
                table_nodes = get_table_nodes(*variables_qm.values())
                population_qm = reduce(
                    Function.Or,
                    map(AggregateByPatient.Exists, table_nodes),
                )
        else:
            population_qm = dataset.population._qm_node
            table_nodes = get_table_nodes(population_qm, *variables_qm.values())
        self.populate_database(table_nodes)
        return self.get_results_as_patient_table(
            DatasetQM(population=population_qm, variables=variables_qm)
        )

    def evaluate(self, element):
        if isinstance(element, Dataset):
            return self.evaluate_dataset(element)

        original_element = element
        element = (
            element.days if isinstance(original_element, DateDifference) else element
        )

        table_nodes = get_table_nodes(element._qm_node)
        self.populate_database(table_nodes)
        self.cache = {}
        column = self.visit(element._qm_node)

        if isinstance(original_element, DateDifference):
            column = apply_function(format_date_difference, column)
        return column


def format_date_difference(obj):
    if obj is None:
        return ""
    return f"{obj} days"


class EmptyDataset:
    """This class exists to render something nice when a user tries to inspect a dataset
    with no columns with debugger.show()."""

    def to_records(self, convert_null=False):
        return [{"patient_id": ""}]
