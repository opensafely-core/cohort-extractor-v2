"""
This module contains some utilities for doing runtime type-checking. It is in no sense
complete in that there are large areas of Python's type system which it doesn't attempt
to handle. Its aim is to implement just enough behaviour to provide the validation
needed by the Query Model.
"""
import typing
from collections.abc import Mapping, Set
from functools import singledispatch


def get_typevars(typespec):
    "Return set of all TypeVars nested anywhere inside `typespec`"
    if isinstance(typespec, typing.TypeVar):
        return {typespec}
    else:
        return set().union(*[get_typevars(arg) for arg in typing.get_args(typespec)])


def type_matches(spec, target_spec, typevar_context):
    """
    Checks that the type specification given by `spec` matches the specification given
    by `target_spec`

    For example:

        `dict[str, FileNotFoundError]` matches `dict[Any, OSError]`

    Because `str` matches `Any` and `FileNotFoundError` is a subclass of `OSError`.

    The target specification may contain TypeVars. The first match for each variable
    will bind its value, recording it in the `typevar_context` dict. Subsequent uses of
    the variable will fail to match if they don't have the same type. By sharing the
    `typevar_context` dict across different calls to this function you can enforce
    consistent interpretation of the TypeVar.

    For example, both the below calls will match:

        T = TypeVar("T")
        type_matches(dict[int, int], dict[T, T], {})
        type_matches(dict[str, str], dict[T, T], {})

    But this fails:

        type_matches(dict[int, str], dict[T, T], {})

    And so does the second example here:

        ctx = {}
        type_matches(dict[int, int], dict[T, T], ctx)
        type_matches(dict[str, str], dict[T, T], ctx)

    Because although it's internally consistent it is inconsistent with the previous
    example whose context it shares.
    """
    # If `target_spec` is a type variable
    if isinstance(target_spec, typing.TypeVar):
        # Check the type constraints are met, if any
        if target_spec.__constraints__:
            if not any(
                type_matches(spec, constraint, typevar_context)
                for constraint in target_spec.__constraints__
            ):
                return False
        # If we've already assigned a value for this variable (and it wasn't the Any
        # type) then check it matches
        if (
            target_spec in typevar_context
            and typevar_context[target_spec] != typing.Any
        ):
            if spec != typing.Any and typevar_context[target_spec] != spec:
                return False
        # Otherwise record this value as the value of the TypeVar
        else:
            typevar_context[target_spec] = spec
        return True

    # `Any` is the easy case: it just matches everything
    if spec is typing.Any or target_spec is typing.Any:
        return True

    target_spec_origin = typing.get_origin(target_spec)

    # If there's no origin type that means `target_spec` is an ordinary class
    if target_spec_origin is None:
        if spec == bool and target_spec == int:
            # This is inconsistent with Python's type hierarchy, but considering bool to be an int makes typing our
            # operations very much harder since it allows operations like True + True => 2.
            return False
        return spec is not None and issubclass(spec, target_spec)
    elif target_spec_origin is typing.Union:
        # For union types we just need to match one of the arguments
        return any(
            type_matches(spec, arg, typevar_context)
            for arg in typing.get_args(target_spec)
        )
    else:
        # Otherwise we get origin and args for `spec` and check that each element
        # matches
        spec_origin = typing.get_origin(spec)
        if not type_matches(spec_origin, target_spec_origin, typevar_context):
            return False
        target_spec_args = typing.get_args(target_spec)
        spec_args = typing.get_args(spec)
        for spec_arg, target_spec_arg in zip(spec_args, target_spec_args):
            if not type_matches(spec_arg, target_spec_arg, typevar_context):
                return False
        return True


@singledispatch
def get_typespec(value):
    """
    Return a type specification for the supplied value. In simple cases this is just
    like `type()` e.g.

        get_typespec(1) == int

    But this function knows how to destructure some container types so that e.g.

        get_typespec({1, 2, 3}) == Set[int]

    Additionally, through the magic of singledispatch, it can be taught to destructure
    other container types it doesn't yet know about.
    """
    type_ = type(value)
    assert not hasattr(type_, "__class_getitem__"), (
        f"{type_} takes type arguments and so should register its own `get_typespec`"
        f" implementation"
    )
    return type_


@get_typespec.register(Set)
def get_typespec_for_set(value):
    member_types = {get_typespec(i) for i in value}
    # We enforce this constraint because it works for our current use case and is
    # simple. In theory we could find the common base class here and use that.
    if len(member_types) > 1:
        raise TypeError(f"Sets must be of homogeneous type: {value!r}")
    elif member_types:
        member_type = list(member_types)[0]
    else:
        # Allow empty sets
        member_type = typing.Any
    return type(value)[member_type]


@get_typespec.register(Mapping)
def get_typespec_for_mapping(value):
    key_types = {get_typespec(i) for i in value.keys()}
    value_types = {get_typespec(i) for i in value.values()}
    # We enforce these constraints because they work for our current use case and are
    # simple. In theory we could find the common base class here and use that.
    if len(key_types) > 1:
        raise TypeError(f"Mappings must be of homogeneous key type: {value!r}")
    elif len(value_types) > 1:
        raise TypeError(f"Mappings must be of homogeneous value type: {value!r}")
    elif key_types and value_types:
        key_type = list(key_types)[0]
        value_type = list(value_types)[0]
    else:
        # Allow empty mappings
        key_type = typing.Any
        value_type = typing.Any
    return type(value)[key_type, value_type]
