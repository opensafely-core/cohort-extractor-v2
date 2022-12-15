import datetime
import re

import pytest

from databuilder.query_model.table_schema import Column, Constraint, TableSchema


def test_table_schema_equality():
    t1 = TableSchema(i=Column(int))
    t2 = TableSchema(i=Column(int))
    t3 = TableSchema(j=Column(int))
    assert t1 == t2
    assert t1 != t3
    assert t1 != "a fish"


def test_table_schema_hash():
    t1 = TableSchema(i=Column(int))
    t2 = TableSchema(i=Column(int))
    d = {t1: "hello"}
    assert d[t2] == "hello"


def test_repr_roundtrip():
    schema = TableSchema(
        c1=Column(int),
        c2=Column(datetime.date),
    )

    assert eval(repr(schema)) == schema


def test_from_primitives():
    t1 = TableSchema.from_primitives(
        c1=int,
        c2=str,
    )
    t2 = TableSchema(
        c1=Column(int),
        c2=Column(str),
    )
    assert t1 == t2


def test_get_column():
    schema = TableSchema(i=Column(int))
    assert schema.get_column("i") == Column(int)


def test_get_column_type():
    schema = TableSchema(i=Column(int))
    assert schema.get_column_type("i") is int


def test_column_names():
    schema = TableSchema(
        c1=Column(int),
        c2=Column(datetime.date),
    )
    assert schema.column_names == ["c1", "c2"]


def test_column_types():
    schema = TableSchema(
        c1=Column(int),
        c2=Column(datetime.date),
    )
    assert schema.column_types == [("c1", int), ("c2", datetime.date)]


def test_get_column_categories():
    schema = TableSchema(
        c1=Column(
            str,
            constraints=[
                Constraint.Categorical(["a", "b", "c"]),
            ],
        ),
    )
    assert schema.get_column_categories("c1") == ("a", "b", "c")


def test_get_column_categories_where_no_categories_defined():
    schema = TableSchema(c1=Column(str))
    assert schema.get_column_categories("c1") is None


def test_categorical_constraint_casts_lists_to_tuple():
    assert Constraint.Categorical([1, 2, 3]) == Constraint.Categorical((1, 2, 3))


def test_categorical_constraint_description():
    assert Constraint.Categorical([1, 2, 3]).description == "Must be one of: 1, 2, 3"


def test_column_casts_constraint_lists_to_tuple():
    column = Column(str, constraints=[Constraint.NotNull(), Constraint.Unique()])
    assert column.constraints == (Constraint.NotNull(), Constraint.Unique())


def test_supplying_multiple_instances_of_same_constraint_raises_error():
    with pytest.raises(
        ValueError, match="'Constraint.Categorical' specified more than once"
    ):
        Column(
            int,
            constraints=[
                Constraint.Categorical([1, 2]),
                Constraint.Categorical([3, 4]),
            ],
        )


def test_supplying_class_instead_of_instance_raises_error():
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Constraint should be instance not class e.g."
            " 'Constraint.NotNull()' not 'Constraint.NotNull'"
        ),
    ):
        Column(int, constraints=[Constraint.NotNull])
