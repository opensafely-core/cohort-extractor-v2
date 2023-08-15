# just has no idiom for setting a default value for an environment variable
# so we shell out, as we need VIRTUAL_ENV in the justfile environment
export VIRTUAL_ENV  := `echo ${VIRTUAL_ENV:-.venv}`

# TODO: make it /scripts on windows?
export BIN := VIRTUAL_ENV + "/bin"
export PIP := BIN + "/python -m pip"
# enforce our chosen pip compile flags
export COMPILE := BIN + "/pip-compile --allow-unsafe --generate-hashes"
# Disable hash randomisation. The kinds of DoS attacks hash seed randomisation
# is designed to protect against don't apply to ehrQL, and having consistent
# output makes debugging much easier
export PYTHONHASHSEED := "0"


alias help := list

# list available commands
list:
    @just --list


# clean up temporary files
clean:
    rm -rf .venv  # default just-managed venv

# ensure valid virtualenv
_virtualenv:
    #!/usr/bin/env bash
    set -euo pipefail

    # allow users to specify python version in .env
    PYTHON_VERSION=${PYTHON_VERSION:-python3.11}

    # create venv and upgrade pip
    test -d $VIRTUAL_ENV || { $PYTHON_VERSION -m venv $VIRTUAL_ENV && $PIP install --upgrade pip; }

    # Error if venv does not contain the version of Python we expect
    test -e $BIN/$PYTHON_VERSION || { echo "Did not find $PYTHON_VERSION in $VIRTUAL_ENV (try deleting and letting it re-build)"; exit 1; }

    # ensure we have pip-tools so we can run pip-compile
    test -e $BIN/pip-compile || $PIP install pip-tools


_compile src dst *args: _virtualenv
    #!/usr/bin/env bash
    set -euo pipefail

    # exit if src file is older than dst file (-nt = 'newer than', but we negate with || to avoid error exit code)
    test "${FORCE:-}" = "true" -o {{ src }} -nt {{ dst }} || exit 0
    $BIN/pip-compile --allow-unsafe --generate-hashes --output-file={{ dst }} {{ src }} {{ args }}


# update requirements.prod.txt if pyproject.toml has changed
requirements-prod *args:
    {{ just_executable() }} _compile pyproject.toml requirements.prod.txt {{ args }}


# update requirements.dev.txt if requirements.dev.in has changed
requirements-dev *args: requirements-prod
    {{ just_executable() }} _compile requirements.dev.in requirements.dev.txt {{ args }}


# ensure prod requirements installed and up to date
prodenv: requirements-prod
    #!/usr/bin/env bash
    set -euo pipefail

    # exit if .txt file has not changed since we installed them (-nt == "newer than', but we negate with || to avoid error exit code)
    test requirements.prod.txt -nt $VIRTUAL_ENV/.prod || exit 0

    $PIP install -r requirements.prod.txt
    touch $VIRTUAL_ENV/.prod


# && dependencies are run after the recipe has run. Needs just>=0.9.9. This is
# a killer feature over Makefiles.
#
# ensure dev requirements installed and up to date
devenv: prodenv requirements-dev && _install-precommit
    #!/usr/bin/env bash
    set -euo pipefail

    # exit if .txt file has not changed since we installed them (-nt == "newer than', but we negate with || to avoid error exit code)
    test requirements.dev.txt -nt $VIRTUAL_ENV/.dev || exit 0

    $PIP install -r requirements.dev.txt
    touch $VIRTUAL_ENV/.dev


# ensure precommit is installed
_install-precommit:
    #!/usr/bin/env bash
    set -euo pipefail

    BASE_DIR=$(git rev-parse --show-toplevel)
    test -f $BASE_DIR/.git/hooks/pre-commit || $BIN/pre-commit install


# upgrade dev or prod dependencies (specify package to upgrade single package, all by default)
upgrade env package="": _virtualenv
    #!/usr/bin/env bash
    set -euo pipefail

    opts="--upgrade"
    test -z "{{ package }}" || opts="--upgrade-package {{ package }}"
    FORCE=true {{ just_executable() }} requirements-{{ env }} $opts


black *args=".": devenv
    $BIN/black --check {{ args }}

ruff *args=".": devenv
    $BIN/ruff {{ args }}

# runs the various dev checks but does not change any files
check *args: devenv black ruff
    docker pull hadolint/hadolint
    docker run --rm -i hadolint/hadolint < Dockerfile

# runs the format (black) and other code linting (ruff) checks and fixes the files
fix: devenv
    $BIN/black .
    $BIN/ruff --fix .


# build the ehrql docker image
build-ehrql:
    #!/usr/bin/env bash
    set -euo pipefail

    export BUILD_DATE=$(date -u +'%y-%m-%dT%H:%M:%SZ')
    export GITREF=$(git rev-parse --short HEAD)

    [[ -v CI ]] && echo "::group::Build ehrql (click to view)" || echo "Build ehrql"
    DOCKER_BUILDKIT=1 docker build --build-arg BUILD_DATE="$BUILD_DATE" --build-arg GITREF="$GITREF" . -t ehrql-dev
    [[ -v CI ]] && echo "::endgroup::" || echo ""


# Build a docker image that can then be used locally via the OpenSAFELY CLI. You must also change project.yaml
# in the study you're running to specify `dev` as the `ehrql` version (like `run: ehrql:dev ...`).
build-ehrql-for-os-cli: build-ehrql
    docker tag ehrql-dev ghcr.io/opensafely-core/ehrql:dev


# tear down the persistent docker containers we create to run tests again
remove-database-containers:
    docker rm --force ehrql-mssql

# open an interactive SQL Server shell running against MSSQL
connect-to-mssql:
    docker exec -it ehrql-mssql /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'Your_password123!'

###################################################################
# Testing targets
###################################################################

# Run all or some pytest tests. Optional args are passed to pytest, including the path of tests to run.
test *ARGS="tests": devenv
    $BIN/python -m pytest {{ ARGS }}

# Run the acceptance tests only. Optional args are passed to pytest.
test-acceptance *ARGS: devenv
    $BIN/python -m pytest tests/acceptance {{ ARGS }}

# Run the backend validation tests only. Optional args are passed to pytest.
test-backend-validation *ARGS: devenv
    $BIN/python -m pytest tests/backend_validation {{ ARGS }}

# Run the ehrql-in-docker tests only. Optional args are passed to pytest.
test-docker *ARGS: devenv
    $BIN/python -m pytest tests/docker {{ ARGS }}

# Run the integration tests only. Optional args are passed to pytest.
test-integration *ARGS: devenv
    $BIN/python -m pytest tests/integration {{ ARGS }}

# Run the spec tests only. Optional args are passed to pytest.
test-spec *ARGS: devenv
    $BIN/python -m pytest tests/spec {{ ARGS }}

# Run the unit tests only. Optional args are passed to pytest.
test-unit *ARGS: devenv
    $BIN/python -m pytest tests/unit {{ ARGS }}
    $BIN/python -m pytest --doctest-modules ehrql

# Run the generative tests only. Optional args are passed to pytest.
#
# Set GENTEST_DEBUG env var to see stats.
# Set GENTEST_EXAMPLES to change the number of examples generated.
test-generative *ARGS: devenv
    $BIN/python -m pytest tests/generative {{ ARGS }}

# Run by CI. Run all tests, checking code coverage. Optional args are passed to pytest.
# (The `@` prefix means that the script is echoed first for debugging purposes.)
@test-all *ARGS: devenv generate-docs
    #!/usr/bin/env bash
    set -euo pipefail

    examples=${GENTEST_EXAMPLES:-200}
    [[ -v CI ]] && echo "::group::Run tests (click to view)" || echo "Run tests"
    GENTEST_EXAMPLES=$examples GENTEST_COMPREHENSIVE=t $BIN/python -m pytest \
        --cov=ehrql \
        --cov=tests \
        --cov-report=html \
        --cov-report=term-missing:skip-covered \
        --hypothesis-seed=1234 \
        {{ ARGS }}
    $BIN/python -m pytest --doctest-modules ehrql
    [[ -v CI ]]  && echo "::endgroup::" || echo ""

generate-docs OUTPUT_DIR="docs/includes/generated_docs": devenv
    $BIN/python -m ehrql.docs {{ OUTPUT_DIR }}
    echo "Generated data for documentation in {{ OUTPUT_DIR }}"

precommit-generate-docs *args: generate-docs

update-external-studies: devenv
    $BIN/python -m tests.acceptance.update_external_studies

update-tpp-schema: devenv
    #!/usr/bin/env bash
    set -euo pipefail

    echo 'Fetching latest tpp_schema.csv'
    $BIN/python -m tests.lib.update_tpp_schema fetch
    echo 'Building new tpp_schema.py'
    $BIN/python -m tests.lib.update_tpp_schema build

# Run the documentation server: to configure the port, append: ---dev-addr localhost:<port>
docs-serve *ARGS: devenv generate-docs
    "$BIN"/mkdocs serve {{ ARGS }}

# Build the documentation
docs-build *ARGS: devenv generate-docs
    "$BIN"/mkdocs build {{ ARGS }}

# Run the snippet tests
docs-test: devenv
    echo "Not implemented here"

# Check the dataset public docs are current
docs-check-generated-docs-are-current: generate-docs
    #!/usr/bin/env bash
    set -euo pipefail

    # https://stackoverflow.com/questions/3878624/how-do-i-programmatically-determine-if-there-are-uncommitted-changes
    # git diff --exit-code won't pick up untracked files, which we also want to check for.
    if [[ -z $(git status --porcelain ./docs/includes/generated_docs/; git clean -nd ./docs/includes/generated_docs/) ]]
    then
      echo "Generated docs directory is current and free of other files/directories."
    else
      echo "Generated docs directory contains files/directories not in the repository."
      git diff ./docs/includes/generated_docs/; git clean -n ./docs/includes/generated_docs/
      exit 1
    fi
