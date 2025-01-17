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
