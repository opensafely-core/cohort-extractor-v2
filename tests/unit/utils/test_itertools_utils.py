import hypothesis as hyp
import hypothesis.strategies as st
import pytest

from ehrql.utils.itertools_utils import eager_iterator, iter_flatten, iter_groups


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


SEPARATOR = object()


@pytest.mark.parametrize(
    "stream,expected",
    [
        (
            [],
            [],
        ),
        (
            [SEPARATOR],
            [[]],
        ),
        (
            [SEPARATOR, 1, 2, SEPARATOR, SEPARATOR, 3, 4],
            [[1, 2], [], [3, 4]],
        ),
    ],
)
def test_iter_groups(stream, expected):
    results = [list(group) for group in iter_groups(stream, SEPARATOR)]
    assert results == expected


@hyp.given(
    nested=st.lists(
        st.lists(st.integers(), max_size=5),
        max_size=5,
    )
)
def test_iter_groups_roundtrips(nested):
    flattened = []
    for inner in nested:
        flattened.append(SEPARATOR)
        for item in inner:
            flattened.append(item)

    results = [list(group) for group in iter_groups(flattened, SEPARATOR)]
    assert results == nested


def test_iter_groups_rejects_invalid_stream():
    stream_no_separator = [1, 2]
    with pytest.raises(
        AssertionError,
        match="Invalid iterator: does not start with `separator` value",
    ):
        list(iter_groups(stream_no_separator, SEPARATOR))


def test_iter_groups_rejects_out_of_order_reads():
    stream = [SEPARATOR, 1, 2, SEPARATOR, 3, 4]
    with pytest.raises(
        AssertionError,
        match="Cannot consume next group until current group has been exhausted",
    ):
        list(iter_groups(stream, SEPARATOR))


def test_iter_groups_allows_overreading_groups():
    stream = [SEPARATOR, 1, 2, SEPARATOR, 3, 4]
    # We call `list` on each group twice: this should make no difference because on the
    # second call the group should be exhausted and so result in an empty list
    results = [list(group) + list(group) for group in iter_groups(stream, SEPARATOR)]
    assert results == [[1, 2], [3, 4]]
