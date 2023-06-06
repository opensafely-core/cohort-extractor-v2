import datetime
from collections import defaultdict

from ehrql import tables
from ehrql.codes import BaseCode
from ehrql.query_language import BaseFrame, PatientFrame, get_all_series_from_class
from ehrql.utils.module_utils import get_submodules

from .common import reformat_docstring


SORT_ORDER = {k: i for i, k in enumerate(["beta.tpp", "beta.core"])}


def build_schemas(backends=()):
    module_name_to_backends = build_module_name_to_backend_map(backends)

    schemas = []
    for module in get_submodules(tables):
        module_tables = list(build_tables(module))
        if not module_tables:
            continue

        docstring = reformat_docstring(module.__doc__)
        dotted_path = module.__name__
        hierarchy = dotted_path.removeprefix(f"{tables.__name__}.").split(".")
        name = ".".join(hierarchy)
        implemented_by = [
            backend_name for backend_name in module_name_to_backends[name]
        ]

        schemas.append(
            {
                "name": name,
                "dotted_path": dotted_path,
                "hierarchy": hierarchy,
                "docstring": docstring,
                "implemented_by": implemented_by,
                "tables": sorted(module_tables, key=lambda t: t["name"]),
            }
        )

    schemas.sort(key=sort_key)
    return schemas


def build_module_name_to_backend_map(backends):
    module_name_to_backends = defaultdict(list)
    for backend in backends:
        for module_name in backend["implements"]:
            module_name_to_backends[module_name].append(backend["name"])
    return module_name_to_backends


def build_tables(module):
    for name, obj in vars(module).items():
        if not isinstance(obj, BaseFrame):
            continue
        cls = obj.__class__
        docstring = reformat_docstring(cls.__doc__)
        columns = [
            build_column(name, series)
            for name, series in get_all_series_from_class(cls).items()
        ]

        yield {
            "name": name,
            "docstring": docstring,
            "columns": columns,
            "has_one_row_per_patient": issubclass(cls, PatientFrame),
        }


def build_column(name, series):
    return {
        "name": name,
        "description": series.description,
        "type": get_name_for_type(series.type_),
        "constraints": [c.description for c in series.constraints],
    }


def get_name_for_type(type_):
    if issubclass(type_, BaseCode):
        return f"{type_.__doc__} code"
    return {
        bool: "boolean",
        int: "integer",
        float: "float",
        str: "string",
        datetime.date: "date",
    }[type_]


def sort_key(obj):
    k = obj["name"]
    return SORT_ORDER.get(k, float("+inf")), k
