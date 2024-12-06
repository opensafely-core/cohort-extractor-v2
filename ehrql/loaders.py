import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap

import ehrql
from ehrql.debugger import activate_debug_context
from ehrql.measures import Measures
from ehrql.query_language import Dataset, modify_exception
from ehrql.renderers import DISPLAY_RENDERERS
from ehrql.serializer import deserialize
from ehrql.utils.traceback_utils import get_trimmed_traceback


PLEDGE_BIN = pathlib.Path(ehrql.__file__).parents[1] / "bin" / "pledge"


class DefinitionError(Exception):
    "Error in or with the user-supplied definition file"


def load_dataset_definition(definition_file, user_args, environ):
    return load_definition_in_subprocess("dataset", definition_file, user_args, environ)


def load_measure_definitions(definition_file, user_args, environ):
    return load_definition_in_subprocess(
        "measures", definition_file, user_args, environ
    )


def load_test_definition(definition_file, user_args, environ):
    return load_definition_in_subprocess("test", definition_file, user_args, environ)


def load_debug_definition(
    definition_file, user_args, environ, dummy_tables_path, render_format
):
    return load_definition_in_subprocess(
        "debug", definition_file, user_args, environ, dummy_tables_path, render_format
    )


def load_definition_in_subprocess(
    definition_type,
    definition_file,
    user_args,
    environ,
    dummy_tables_path=None,
    render_format=None,
):
    # We always run code isolated if we can (even if we don't need to) for parity with
    # production so users have the best chance of catching potential issues early
    if isolation_is_supported():
        subprocess_run = subprocess_run_isolated
    else:
        # But where isolation is not available or required we fallback to running in a
        # non-isolated subprocess so ehrQL is still usable
        if not isolation_is_required(environ):
            subprocess_run = subprocess.run
        else:
            # Obviously if isolation is required and unavailable we should stop
            raise RuntimeError(
                "The current environment does not support the 'pledge' isolation "
                "mechanism and so cannot safely execute untrusted user code.\n"
                "\n"
                "If you are confident that this doesn't matter in your context "
                "(e.g. you are a developer trying to run ehrQL locally to test it) "
                "then you can disable the isolation mechanism by setting the "
                "environment variable:\n"
                "\n    EHRQL_ISOLATE_USER_CODE=never\n\n"
                "If you're not sure whether this is the right thing to do then the "
                "answer is 'no'."
            )

    dummy_tables_args = (
        ["--dummy-tables", dummy_tables_path] if dummy_tables_path else []
    )
    renderer_args = ["--display-format", render_format] if render_format else []
    result = subprocess_run(
        [
            sys.executable,
            "-m",
            "ehrql",
            "serialize-definition",
            "--definition-type",
            definition_type,
            *dummy_tables_args,
            *renderer_args,
            definition_file,
            "--",
            *user_args,
        ],
        env={
            # Our Docker image relies on PYTHONPATH to make the ehrql package available
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            # Our entrypoint will emit warnings if we don't set this
            "PYTHONHASHSEED": "0",
            # `pledge` requires this to be set
            "TMPDIR": tempfile.gettempdir(),
        },
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise DefinitionError(result.stderr.removesuffix("\n"))
    else:
        # Pass through any warnings or logs generated by the subprocess
        print(result.stderr, file=sys.stderr, end="")
    return deserialize(
        result.stdout,
        # Disallow referencing files outside of the current working directory
        root_dir=pathlib.Path.cwd(),
    )


def isolation_is_supported():
    try:
        result = subprocess.run([PLEDGE_BIN, "-T", "pledge", "-T", "unveil"])
        return result.returncode == 0
    except OSError:  # pragma: no cover
        # Required for non-Linux platforms where we can't even execute the binary
        return False


def subprocess_run_isolated(args, **kwargs):
    return subprocess.run(
        [
            PLEDGE_BIN,
            # Configure "pledge" to restrict avilable operations to the minimum needed
            # to execute a definition file and serialize the result, which are:
            # - stdio: allow stdio and benign system calls
            # - rpath: read-only path ops
            # - prot_exec: allow creating executable memory
            #
            # In particular, anything related to networking or socket communication,
            # executing other processes, and any filesystem modifications are all
            # disallowed. For a full list of the syscalls implied by these settings see:
            # https://justine.lol/pledge/#promises
            "-p",
            "stdio rpath prot_exec",
            # Use "unveil" to expose the filesystem read-only. Note that this still does
            # not provide unfettered access to the /proc tree so in particular it's not
            # possible to read other processes environment variables.
            "-v",
            "r:/",
            # Quiet: don't log messages from pledge to stderr
            "-q",
            *args,
        ],
        **kwargs,
    )


def isolation_is_required(environ):
    config = environ.get("EHRQL_ISOLATE_USER_CODE", "default")
    if config == "default":
        # This is awkward. The simplest and safest thing to do would be to require
        # isolation everywhere. But we can't guarantee that Pledge will work in all the
        # heterogenous local environments in which we need to run (the available
        # isolation primitives are determined by the host kernel, which is shared by the
        # containers – Docker's leaky abstraction). So we only want to *require*
        # isolation support in production. But we use the same Docker image in all
        # environments so we can't bake this config into the image. So, by default, we
        # switch behaviour on whether the DATABASE_URL environment variable is set.
        return bool(environ.get("DATABASE_URL"))
    elif config == "always":
        # We also allow explicity requiring isolation. We should get Job Runner to set
        # this rather than relying on the behaviour above, although we need that
        # behaviour to avoid failing open.
        return True
    elif config == "never":
        # This is useful when working on ehrQL locally in an environment (e.g. macOS)
        # where isolation is not supported.
        return False
    else:
        raise RuntimeError(
            f"Invalid value {config!r} for EHRQL_ISOLATE_USER_CODE environment"
            f" variable, must be one of: default, always, never"
        )


def isolation_report(cwd):
    # Run a series of checks to confirm that certain operations which are ordinarily
    # allowed in a subprocess are blocked in an isolated subprocess
    return {
        "subprocess.run": isolation_report_for_function(subprocess.run, cwd),
        "subprocess_run_isolated": isolation_report_for_function(
            subprocess_run_isolated, cwd
        ),
    }


def isolation_report_for_function(run_function, cwd):
    # Map operation names to a snippet of code which tests whether we have permission to
    # perform that operation
    operation_tests = {
        "touch": "pathlib.Path('.').touch()",
        "open_socket": (
            "try:\n"
            "    socket.create_connection(('192.0.2.0', 53), timeout=0.001)\n"
            "except (ConnectionRefusedError, TimeoutError):\n"
            "    pass"
        ),
        "exec": "subprocess.run(['/bin/true'])",
        "read_env_vars": "pathlib.Path(f'/proc/{os.getppid()}/environ').read_bytes()",
    }
    # Compile the snippets into a test script
    code_lines = [
        "import os, pathlib, socket, subprocess",
        *[
            f"try:\n"
            f"{textwrap.indent(test_code, prefix='    ')}\n"
            f"except PermissionError:\n"
            f"    print('{test_name}: BLOCKED')\n"
            f"else:\n"
            f"    print('{test_name}: ALLOWED')\n"
            for test_name, test_code in operation_tests.items()
        ],
    ]
    # Run the test script
    result = run_function(
        [sys.executable, "-c", "\n".join(code_lines)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        cwd=cwd,
        env={
            # `pledge` requires this to be set
            "TMPDIR": tempfile.gettempdir(),
        },
    )
    # Parse out the results
    return {
        key: value
        for key, _, value in [
            line.partition(": ") for line in result.stdout.splitlines()
        ]
    }


# The `_unsafe` functions below are so named because they import user-supplied code
# directly into the running process. They should therefore only be run in either an
# isolated subprocess, or in local/test contexts.


def load_dataset_definition_unsafe(definition_file, user_args, **kwargs):
    module = load_module(definition_file, user_args)
    variable_definitions = get_variable_definitions_from_module(module)
    return variable_definitions, module.dataset.dummy_data_config


def load_test_definition_unsafe(definition_file, user_args, **kwargs):
    module = load_module(definition_file, user_args)
    variable_definitions = get_variable_definitions_from_module(module)
    return variable_definitions, module.test_data


def load_debug_definition_unsafe(
    definition_file, user_args, dummy_tables_path, render_format
):
    render_function = DISPLAY_RENDERERS[render_format]
    with activate_debug_context(
        dummy_tables_path=dummy_tables_path, render_function=render_function
    ):
        load_module(definition_file, user_args)


def get_variable_definitions_from_module(module):
    try:
        dataset = module.dataset
    except AttributeError:
        raise DefinitionError(
            "Did not find a variable called 'dataset' in dataset definition file"
        )
    if not isinstance(dataset, Dataset):
        raise DefinitionError("'dataset' must be an instance of ehrql.Dataset")
    if not hasattr(dataset, "population"):
        raise DefinitionError(
            "A population has not been defined; define one with define_population()"
        )
    return dataset._compile()


def load_measure_definitions_unsafe(definition_file, user_args, **kwargs):
    module = load_module(definition_file, user_args)
    try:
        measures = module.measures
    except AttributeError:
        raise DefinitionError(
            "Did not find a variable called 'measures' in measures definition file"
        )
    if not isinstance(measures, Measures):
        raise DefinitionError("'measures' must be an instance of ehrql.Measures")
    if len(measures) == 0:
        raise DefinitionError("No measures defined")
    return (
        list(measures),
        measures.dummy_data_config,
        measures.disclosure_control_config,
    )


DEFINITION_LOADERS = {
    "dataset": load_dataset_definition_unsafe,
    "measures": load_measure_definitions_unsafe,
    "test": load_test_definition_unsafe,
    "debug": load_debug_definition_unsafe,
}


def load_definition_unsafe(
    definition_type, definition_file, user_args, environ, **kwargs
):
    if isolation_is_required(environ):
        raise RuntimeError(
            "Unexpected call to unsafe loader function in an environment which "
            "requires user code isolation."
        )
    return DEFINITION_LOADERS[definition_type](definition_file, user_args, **kwargs)


def load_module(module_path, user_args=()):
    # Taken from the official recipe for importing a module from a file path:
    # https://docs.python.org/3.9/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    module = importlib.util.module_from_spec(spec)
    # Temporarily add the directory containing the definition to the start of `sys.path`
    # (just as `python path/to/script.py` would) so that the definition can import
    # library modules from that directory
    original_sys_path = sys.path.copy()
    sys.path.insert(0, str(module_path.parent.absolute()))
    # Temporarily modify `sys.argv` so it contains any user-supplied arguments and
    # generally looks as it would had you run: `python script.py some args --here`
    original_sys_argv = sys.argv.copy()
    sys.argv = [str(module_path), *user_args]
    # Force any user generated output (prints etc) to stderr so it doe not get
    # mixed up with anything we might want to output ourselves
    original_sys_stdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        # Give the query langauge the chance to modify or replace the exception
        exc = modify_exception(exc)
        traceback = get_trimmed_traceback(exc, module.__file__)
        raise DefinitionError(f"Error loading file '{module_path}':\n\n{traceback}")
    finally:
        sys.path = original_sys_path
        sys.argv = original_sys_argv
        sys.stdout = original_sys_stdout
