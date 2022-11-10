import traceback
from pathlib import Path

# Note that if this file is moved, this will need to be updated.
package_root = Path(__file__).resolve().parent


# The presence of any of these strings in a traceback line indicates that the line
# almost certainly came from our library code, which we don't want to show to users.
strings_to_trim = [
    # Indicates that the line comes from the databuilder package.
    str(package_root),
    # Indicates that the line comes from the code that imports a dataset definition from
    # a user-supplied path.
    "frozen importlib._bootstrap",
    # Indicates that the line comes from instantiating a dataclass class (because when a
    # dataclass class is defined, a string execed).
    'File "<string>", line 5, in __init__',
]


def get_trimmed_traceback(exc):
    """Return only the relevant traceback lines from the supplied exception

    We only want to show lines from a user's own code, and not lines from our library
    code.
    """
    tb_fragments = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb_fragments = [
        fragment
        for fragment in tb_fragments
        if not any(s in fragment for s in strings_to_trim)
    ]
    return "".join(tb_fragments).strip()
