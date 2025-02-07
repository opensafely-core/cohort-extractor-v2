from functools import cache, singledispatchmethod


# This is needed to make `singledispatchmethod` play nicely with `cache`, and also to
# make `cache` behave sensibly with instance methods.
#
# First, it's not possible to just decorate `singledispatchmethod` with `cache` like so:
#
#   class Foo:
#       @cache
#       @singledispatchmethod
#       def example(self, value):
#           ...
#
#       @example.register(Bar)
#       def bar_impl(self, value):
#           ...
#
#       @example.register(Baz)
#       def baz_impl(self, value):
#           ...
#
# Because the cache-decorated method no longer has the `register()` method available.
#
# Instead you need to decorate each individual method like so:
#
#   class Foo:
#       @singledispatchmethod
#       @cache
#       def example(self, value):
#           ...
#
#       @example.register(Bar)
#       @cache
#       def bar_impl(self, value):
#           ...
#
#       @example.register(Baz)
#       @cache
#       def baz_impl(self, value):
#           ...
#
# Not only is this repetitive and error prone but it makes it much harder to clear the
# cache as now you need to call `cache_clear()` on each individual method.
#
# Secondly, `@cache` doesn't behave quite as you might want on instance methods. Rather
# than create independent caches per instance it creates a single shared cache for the
# class.  As this cache is keyed on `self` as one of its arguments it behaves _sort of
# like_ an instance cache, if you squint. But its contents never get garbage collected
# unless you explicity call `cache_clear()`. And if you do call `cache_clear()` it
# empties the cache for all instances, not just the instance whose method you called it
# on.
#
# The below decorator is desiged to address both these issues and provide a true
# per-instance cache that works with `singledispatchmethod`.
class singledispatchmethod_with_cache(singledispatchmethod):
    """
    Modifies `singledispatchmethod` to wrap the decorated method with `functools.cache`
    """

    def __set_name__(self, owner, name):
        # Record the name of the method
        self.attribute_name = name

    def __get__(self, obj, cls=None):
        bound_method = super().__get__(obj, cls)
        cached_method = cache(bound_method)
        # Set the cached method as an attribute on the instance so that subsequent
        # `obj.method` references get the same cached method back. Without this, each
        # reference would generate a new method with its own isolated cache, rendering
        # the whole thing pointless.
        obj.__dict__[self.attribute_name] = cached_method
        return cached_method
