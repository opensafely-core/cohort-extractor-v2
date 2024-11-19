import code
import readline
import rlcompleter
import subprocess
import sys

from ehrql.query_engines.sandbox import SandboxQueryEngine
from ehrql.query_language import BaseFrame, BaseSeries, Dataset
from ehrql.utils.traceback_utils import get_trimmed_traceback


def run(dummy_tables_path):
    # Create a query engine using data at given path.  A user will be able to interact
    # with this data via a Python REPL.
    engine = SandboxQueryEngine(dummy_tables_path)

    # Overwrite __repr__ methods to display contents of frame/series.
    BaseFrame.__repr__ = lambda self: repr(engine.evaluate(self))
    BaseSeries.__repr__ = lambda self: repr(engine.evaluate(self))
    Dataset.__repr__ = lambda self: repr(engine.evaluate_dataset(self))

    # Set up readline etc.
    sys.__interactivehook__()

    # Set up exception handler to trim tracebacks
    sys.excepthook = excepthook

    # Set up namespace for tab-completion.
    namespace = {}
    readline.set_completer(rlcompleter.Completer(namespace).complete)

    # Start running a Python REPL.
    code.interact(local=namespace)


def excepthook(type_, exc, tb):
    traceback = get_trimmed_traceback(exc, "<console>")
    sys.stderr.write(traceback)


def run_quiz(quiz_file_path):  # pragma: no cover
    subprocess.call(["python", str(quiz_file_path)])
