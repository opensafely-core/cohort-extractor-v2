import inspect

import ehrql
from ehrql import query_language as ql
from ehrql.docs.common import (
    get_arguments,
    get_class_attrs,
    get_docstring,
    get_name_for_type,
)


EXCLUDE_FROM_DOCS = {
    ql.BaseCode,
    ql.BaseMultiCodeString,
    ql.Series,
    # We document `WhenThen` and `when` as part of `case`
    ql.WhenThen,
    ql.when,
    ql.DummyDataConfig,
    ql.Error,
    ql.int_property,  # Internal thing for type hints and autocomplete
    ql.EventTable,
}


# We're deliberately not including the reverse operators here (e.g. `__radd__`) because
# I don't think it adds anything but confusion to have them in the docs
OPERATORS = {
    "__eq__": "==",
    "__ne__": "!=",
    "__invert__": "~",
    "__and__": "&",
    "__or__": "|",
    "__lt__": ">",
    "__le__": ">=",
    "__gt__": "<",
    "__ge__": "<=",
    "__neg__": "-",
    "__add__": "+",
    "__sub__": "-",
    "__mul__": "*",
    "__truediv__": "/",
    "__floordiv__": "//",
}


# This class doesn't exist in the query language because we have to dynamically generate
# sorted frame classes for each individual table (see `make_sorted_event_frame_class()`)
# but we add it here so we can document the available methods
class SortedEventFrame(ql.SortedEventFrameMethods, ql.EventFrame):
    """
    Frame which contains multiple rows per patient and has had one or more sort
    operations applied.
    """


def build_language():
    # The namespace we're going to document includes all the public names in `ehrql`,
    # plus all the classes in `ehrql.query_language` which we haven't explicitly
    # excluded
    ehrql_namespace = [(name, getattr(ehrql, name)) for name in ehrql.__all__]
    ql_namespace = vars(ql).items()
    namespace = {
        name: value for name, value in ehrql_namespace if is_included_object(value)
    }
    namespace.update(
        {name: value for name, value in ql_namespace if is_included_class(value)}
    )

    # Add class which exists only for documentation purposes – see above
    namespace["SortedEventFrame"] = SortedEventFrame

    sections = {
        "dataset": dict(
            create_dataset=namespace["create_dataset"],
            Dataset=namespace["Dataset"],
        ),
        "frames": {
            name: attr
            for name, attr in namespace.items()
            if is_proper_subclass(attr, ql.BaseFrame)
        },
        "series": {
            name: attr
            for name, attr in namespace.items()
            if is_proper_subclass(attr, ql.PatientSeries, ql.EventSeries)
        },
        "date_arithmetic": dict(
            DateDifference=ql.DateDifference,
            **{
                name: attr
                for name, attr in namespace.items()
                if is_proper_subclass(attr, ql.Duration)
            },
        ),
        "codelists": dict(
            codelist_from_csv=namespace["codelist_from_csv"],
        ),
        "functions": dict(
            case=namespace["case"],
            maximum_of=namespace["maximum_of"],
            minimum_of=namespace["minimum_of"],
        ),
        "measures": {
            "create_measures": namespace["create_measures"],
            "Measures": namespace["Measures"],
            "INTERVAL": namespace["INTERVAL"],
        },
    }

    # Check that the documentation is complete
    included_values = [
        value
        for section_values in sections.values()
        for value in section_values.values()
    ]
    undocumented = get_missing_values(namespace.values(), included_values)
    assert not undocumented, (
        f"The following classes are neither included in nor explicitly excluded from"
        f" the reference documentation: {undocumented!r}"
    )

    return {
        section: [
            build_value_details(name, value) for name, value in section_values.items()
        ]
        for section, section_values in sections.items()
    }


def is_included_class(cls):
    if not inspect.isclass(cls):
        return False
    if not cls.__module__.startswith("ehrql."):
        return False
    if cls in EXCLUDE_FROM_DOCS:
        return False
    return True


def is_proper_subclass(cls, *targets):
    if not inspect.isclass(cls):
        return False
    return issubclass(cls, targets) and cls not in targets


def build_value_details(name, value):
    if inspect.isclass(value):
        return {"type": "class", **build_class_details(name, value)}
    elif inspect.isfunction(value):
        return {"type": "function", **build_function_details(name, value)}
    elif isinstance(value, tuple) and value.__class__ is not tuple:
        return {"type": "namedtuple", **build_namedtuple_details(name, value)}
    else:
        assert False, f"Unhandled type: {value!r}"


def build_class_details(name, cls):
    return {
        "name": name,
        "docstring": get_class_docstring(cls),
        "methods": sorted(
            [
                build_method_details(attr_name, attr)
                for attr_name, attr in get_class_attrs(cls).items()
                if is_included_attr(attr_name, attr)
            ],
            key=method_order,
        ),
        "init_arguments": get_arguments(cls.__init__, ignore_self=True),
    }


def is_included_attr(name, attr):
    if name.startswith("_") and name not in OPERATORS:
        return False
    if getattr(attr, "exclude_from_docs", None):
        return False
    return inspect.isfunction(attr) or inspect.isdatadescriptor(attr)


def is_included_object(value):
    return not getattr(value, "exclude_from_docs", None)


def method_order(details):
    # We generally present methods in the order they were defined but because of the
    # inheritance hierarchy this can lead to methods which naturally belong together
    # being spread apart. By clustering various types of method together we get a more
    # natural presentation.
    if details["operator"]:
        return 0
    elif details["is_property"]:
        return 1
    elif "for_patient" not in details["name"]:
        return 2
    else:
        return 3


def build_method_details(name, method):
    is_property = inspect.isdatadescriptor(method)
    if is_property:
        arguments = {}
    else:
        arguments = get_arguments(method, ignore_self=True)
    return {
        "name": name,
        "arguments": arguments,
        "operator": OPERATORS.get(name),
        "is_property": is_property,
        "docstring": get_docstring(method),
    }


def build_function_details(name, function):
    return {
        "name": name,
        "docstring": get_docstring(function),
        "arguments": get_arguments(function),
    }


def build_namedtuple_details(name, value):
    cls = value.__class__
    return {
        "name": name,
        "docstring": get_docstring(cls),
        "fields": [
            {
                "name": field,
                "docstring": get_docstring(getattr(cls, field)),
            }
            for field in cls._fields
        ],
    }


def get_missing_values(target_values, included_values):
    # We track values by ID because we need to be able to use this with values which
    # aren't hashable and/or have weird equality behaviour
    included_value_ids = {id(value) for value in included_values}
    # For classes, we consider a class included in the docs if we include any of its
    # subclasses
    for value in included_values:
        if inspect.isclass(value):
            included_value_ids.update(id(parent) for parent in value.__mro__)
    # Ignore explicitly excluded values
    included_value_ids.update(id(value) for value in EXCLUDE_FROM_DOCS)
    return [value for value in target_values if id(value) not in included_value_ids]


def get_class_docstring(cls):
    default = (
        generate_docstring_for_series(cls)
        if is_proper_subclass(cls, ql.BaseSeries)
        else None
    )
    return get_docstring(cls, default=default)


def generate_docstring_for_series(series):
    if is_proper_subclass(series, ql.PatientSeries):
        dimension = "One row per patient"
    elif is_proper_subclass(series, ql.EventSeries):
        dimension = "Multiple rows per patient"
    else:
        assert False
    return f"{dimension} series of type `{get_name_for_type(series._type)}`"
