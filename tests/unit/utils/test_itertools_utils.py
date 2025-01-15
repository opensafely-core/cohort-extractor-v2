import pytest

from ehrql.utils.itertools_utils import eager_iterator, iter_flatten


def test_eager_iterator():
    results = eager_iterator(iter([0, 1, 2]))
    assert list(results) == [0, 1, 2]


def test_eager_iterator_works_on_empty_iterators():
    results = eager_iterator(iter([]))
    assert list(results) == []


def test_eager_iterator_triggers_errors_early():
    def generator_with_error():
        raise ValueError("fail")
        yield  # pragma: no cover

    results = generator_with_error()
    with pytest.raises(ValueError, match="^fail$"):
        eager_iterator(results)


def test_eager_iterator_still_mostly_lazy():
    i = iter(range(3))
    assert i.__length_hint__() == 3
    # Check that making it eager consumes exactly one item
    eager = eager_iterator(i)
    assert i.__length_hint__() == 2
    # Check that consuming the eager iterator consumes the rest of the items
    assert list(eager) == [0, 1, 2]
    assert i.__length_hint__() == 0


def test_eager_iterator_works_on_lists():
    results = eager_iterator([1, 2, 3])
    assert list(results) == [1, 2, 3]


def test_iter_flatten():
    nested = [
        1,
        2,
        (3, (4, [5]), [6, 7]),
        [8, (i for i in range(9, 11))],
        "foo",
    ]
    flattened = list(iter_flatten(nested))
    assert flattened == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, "foo"]
