import itertools
from types import GeneratorType


def eager_iterator(iterator):
    """
    Transparently wraps an iterator, but eagerly consumes the first item so as to
    execute any generator set up code and trigger any errors which might occur
    """
    iterator = iter(iterator)
    try:
        first_item = next(iterator)
    except StopIteration:
        # If the original iterator was empty there's nothing more to do
        return iterator
    # Otherwise chain the first item back on to the front and continue
    return itertools.chain([first_item], iterator)


def iter_flatten(iterable, iter_classes=(list, tuple, GeneratorType)):
    """
    Iterate over `iterable` recursively flattening any lists, tuples or generators
    encountered
    """
    for item in iterable:
        if isinstance(item, iter_classes):
            yield from iter_flatten(item, iter_classes)
        else:
            yield item


def iter_groups(iterable, separator):
    """
    Split a flat iterator of items into a nested iterator of groups of items. Groups are
    delineated by the presence of a sentinel `separator` value which marks the start of
    each group.

    For example, the iterator:

        - SEPARATOR
        - 1
        - 2
        - SEPARATOR
        - 3
        - 4

    Will be transformed into the nested iterator:

        -
          - 1
          - 2
        -
          - 3
          - 4

    This is useful for situations where a nested iterator is the natural API for
    representing the data but the flat iterator is much easier to generate correctly.
    """
    iterator = iter(iterable)
    try:
        first_item = next(iterator)
    except StopIteration:
        return
    assert first_item is separator, (
        f"Invalid iterator: does not start with `separator` value {separator!r}"
    )
    while True:
        group_iter = GroupIterator(iterator, separator)
        yield group_iter
        # Prevent the caller from trying to consume the next group before they've
        # finished consuming the current one (as would happen if you naively called
        # `list()` on the result of `iter_groups()`)
        assert group_iter._group_complete, (
            "Cannot consume next group until current group has been exhausted"
        )
        if group_iter._exhausted:
            break


class GroupIterator:
    def __init__(self, iterator, separator):
        self._iterator = iterator
        self._separator = separator
        self._group_complete = False
        self._exhausted = False

    def __iter__(self):
        return self

    def __next__(self):
        if self._group_complete:
            raise StopIteration()
        try:
            value = next(self._iterator)
        except StopIteration:
            self._group_complete = True
            self._exhausted = True
            raise
        if value is self._separator:
            self._group_complete = True
            raise StopIteration()
        else:
            return value
