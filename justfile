set dotenv-load := true
set positional-arguments


export VIRTUAL_ENV  := env_var_or_default("VIRTUAL_ENV", ".venv")

export BIN := VIRTUAL_ENV + if os_family() == "unix" { "/bin" } else { "/Scripts" }
export PIP := BIN + if os_family() == "unix" { "/python -m pip" } else { "/python.exe -m pip" }


alias help := list

# List available commands
list:
    @just --list --unsorted


# Ensure valid virtualenv
virtualenv:
    #!/usr/bin/env bash
    set -euo pipefail

    # allow users to specify python version in .env
    PYTHON_VERSION=${PYTHON_VERSION:-python3.11}

    # create venv and upgrade pip
    if [[ ! -d $VIRTUAL_ENV ]]; then
      $PYTHON_VERSION -m venv $VIRTUAL_ENV
      $PIP install --upgrade pip
    fi


# Run pip-compile with our standard settings
pip-compile *ARGS: devenv
    #!/usr/bin/env bash
    set -euo pipefail

    $BIN/pip-compile --allow-unsafe --generate-hashes --strip-extras "$@"


update-dependencies: devenv
  just pip-compile -U requirements.prod.in
  just pip-compile -U requirements.dev.in

# Ensure dev and prod requirements installed and up to date
devenv: virtualenv
    #!/usr/bin/env bash
    set -euo pipefail

    for req_file in requirements.dev.txt requirements.prod.txt pyproject.minimal.toml; do
      # If we've installed this file before and the original hasn't been
      # modified since then bail early
      record_file="$VIRTUAL_ENV/$req_file"
      if [[ -e "$record_file" && "$record_file" -nt "$req_file" ]]; then
        continue
      fi

      if cmp --silent "$req_file" "$record_file"; then
        # If the timestamp has been changed but not the contents (as can happen
        # when switching branches) then just update the timestamp
        touch "$record_file"
      else
        # Otherwise actually install the requirements

        if [[ "$req_file" == *.txt ]]; then
          # --no-deps is recommended when using hashes, and also works around a
          # bug with constraints and hashes. See:
          # https://pip.pypa.io/en/stable/topics/secure-installs/#do-not-use-setuptools-directly
          $PIP install --no-deps --requirement "$req_file"
        elif [[ "$req_file" == *.toml ]]; then
          $PIP install --no-deps --editable "$(dirname "$req_file")"
        else
          echo "Unhandled file: $req_file"
          exit 1
        fi

        # Make a record of what we just installed
        cp "$req_file" "$record_file"
      fi
    done

    if [[ ! -f .git/hooks/pre-commit ]]; then
      $BIN/pre-commit install
    fi


# Lint and check formatting but don't modify anything
check: devenv
    #!/usr/bin/env bash

    failed=0

    check() {
      # Display the command we're going to run, in bold and with the "$BIN/"
      # prefix removed if present
      echo -e "\e[1m=> ${1#"$BIN/"}\e[0m"
      # Run it
      eval $1
      # Increment the counter on failure
      if [[ $? != 0 ]]; then
        failed=$((failed + 1))
        # Add spacing to separate the error output from the next check
        echo -e "\n"
      fi
    }

    check "$BIN/ruff format --diff --quiet ."
    check "$BIN/ruff check --output-format=full ."
    check "docker run --rm -i ghcr.io/hadolint/hadolint:v2.12.0-alpine < Dockerfile"

    if [[ $failed > 0 ]]; then
      echo -en "\e[1;31m"
      echo "   $failed checks failed"
      echo -e "\e[0m"
      exit 1
    fi


# Fix any automatically fixable linting or formatting errors
fix: devenv
    $BIN/ruff format .
    $BIN/ruff check --fix .


# Build the ehrQL docker image
build-ehrql image_name="ehrql-dev" *args="":
    #!/usr/bin/env bash
    set -euo pipefail

    export BUILD_DATE=$(date -u +'%y-%m-%dT%H:%M:%SZ')
    export GITREF=$(git rev-parse --short HEAD)

    [[ -v CI ]] && echo "::group::Build ehrql Docker image (click to view)" || echo "Build ehrql Docker image"
    DOCKER_BUILDKIT=1 docker build . --build-arg BUILD_DATE="$BUILD_DATE" --build-arg GITREF="$GITREF" --tag {{ image_name }} {{ args }}
    [[ -v CI ]] && echo "::endgroup::" || echo ""


# Build a docker image tagged `ehrql:dev` that can be used in `project.yaml` for local testing
build-ehrql-for-os-cli: build-ehrql
    docker tag ehrql-dev ghcr.io/opensafely-core/ehrql:dev


# Tear down the persistent docker containers we create to run tests again
remove-database-containers:
    docker rm --force ehrql-mssql ehrql-trino


# Create an MSSQL docker container with the TPP database schema and print connection strings
create-tpp-test-db: devenv
    $BIN/python -m pytest -o python_functions=create tests/lib/create_tpp_test_db.py


# Open an interactive SQL Server shell running against MSSQL
connect-to-mssql:
    # Only pass '-t' argument to Docker if stdin is a TTY so you can pipe a SQL
    # file to this commmand as well as using it interactively.
    docker exec -i `[ -t 0 ] && echo '-t'` \
        ehrql-mssql \
            /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'Your_password123!' -d test


# Open an interactive trino shell
connect-to-trino:
    docker exec -it ehrql-trino trino --catalog trino --schema default


###################################################################
# Testing targets
###################################################################

# Run all or some pytest tests
test *ARGS: devenv
    $BIN/python -m pytest "$@"


# Run the acceptance tests only
test-acceptance *ARGS: devenv
    $BIN/python -m pytest tests/acceptance "$@"


# Run the backend validation tests only
test-backend-validation *ARGS: devenv
    $BIN/python -m pytest tests/backend_validation "$@"


# Run the ehrql-in-docker tests only
test-docker *ARGS: devenv
    $BIN/python -m pytest tests/docker "$@"


# Run the docs examples tests only
test-docs-examples *ARGS: devenv
    $BIN/python -m pytest tests/docs "$@"


# Run the integration tests only
test-integration *ARGS: devenv
    $BIN/python -m pytest tests/integration "$@"


# Run the spec tests only
test-spec *ARGS: devenv
    $BIN/python -m pytest tests/spec "$@"


# Run the unit tests only
test-unit *ARGS: devenv
    $BIN/python -m pytest tests/unit "$@"
    $BIN/python -m pytest --doctest-modules ehrql


# Run the generative tests only, configured to use more than the tiny default
# number of examples. Optional args are passed to pytest.
#
# Set GENTEST_DEBUG env var to see stats.
# Set GENTEST_EXAMPLES to change the number of examples generated.
# Set GENTEST_MAX_DEPTH to change the depth of generated query trees.
#
# Run generative tests using more than the small deterministic set of examples used in CI
test-generative *ARGS: devenv
    GENTEST_EXAMPLES=${GENTEST_EXAMPLES:-200} \
    GENTEST_RANDOMIZE=${GENTEST_RANDOMIZE:-t} \
      $BIN/python -m pytest tests/generative "$@"


# Run all test as they will be run in  CI (checking code coverage etc)
@test-all *ARGS: devenv generate-docs
    #!/usr/bin/env bash
    set -euo pipefail

    GENTEST_EXAMPLES=${GENTEST_EXAMPLES:-100} \
    GENTEST_CHECK_IGNORED_ERRORS=t \
      $BIN/python -m pytest \
        --cov=ehrql \
        --cov=tests \
        --cov-report=html \
        --cov-report=term-missing:skip-covered \
        "$@"
    $BIN/python -m pytest --doctest-modules ehrql


# Convert a raw failing example from Hypothesis's output into a simplified test case
gentest-example-simplify *ARGS: devenv
    $BIN/python -m tests.lib.gentest_example_simplify "$@"


# Run a generative test example defined in the supplied file
gentest-example-run example *ARGS: devenv
    GENTEST_EXAMPLE_FILE='{{example}}' \
    $BIN/python -m pytest \
        tests/generative/test_query_model.py::test_query_model_example_file \
            "$@"


generate-docs OUTPUT_DIR="docs/includes/generated_docs": devenv
    $BIN/python -m ehrql.docs {{ OUTPUT_DIR }}
    echo "Generated data for documentation in {{ OUTPUT_DIR }}"


# Run the documentation server: to configure the port, append: ---dev-addr localhost:<port>
docs-serve *ARGS: devenv generate-docs
    # Run the MkDocs server with `--clean` to enforce the `exclude_docs` option.
    # This removes false positives that pertain to the autogenerated documentation includes.
    "$BIN"/mkdocs serve --clean "$@"


# Build the documentation
docs-build *ARGS: devenv generate-docs
    "$BIN"/mkdocs build --clean "$@"


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


update-external-studies: devenv
    $BIN/python -m tests.acceptance.update_external_studies


update-patient-level-table-definitions: devenv
    #!/usr/bin/env bash
    set -euo pipefail

    echo 'Updating the patient level table definitions'
    $BIN/python -m tests.autocomplete.update_table_definitions


update-tpp-schema: devenv
    #!/usr/bin/env bash
    set -euo pipefail

    echo 'Fetching latest tpp_schema.csv'
    $BIN/python -m tests.lib.update_tpp_schema fetch
    echo 'Building new tpp_schema.py'
    $BIN/python -m tests.lib.update_tpp_schema build


update-pledge: devenv
    #!/usr/bin/env bash
    set -euo pipefail
    URL_RECORD_FILE="bin/cosmopolitan-release-url.txt"
    ZIP_URL="$(
      $BIN/python -c \
        'import requests; print([
            asset["browser_download_url"]
            for release in requests.get("https://api.github.com/repos/jart/cosmopolitan/releases").json()
            for asset in release["assets"]
            if asset["name"].startswith("cosmos-") and asset["name"].endswith(".zip")
        ][0])'
    )"
    echo "Latest Cosmopolitation release: $ZIP_URL"
    if grep -Fxqs "$ZIP_URL" "$URL_RECORD_FILE"; then
       echo "Already up to date."
       exit 0
    fi

    if [[ "$(uname -s)" != "Linux" ]]; then
      echo "This command can only be run on a Linux system because we need to"
      echo " \"assimilate\" `pledge` to be a regular Linux executable"
      exit 1
    fi

    echo "Downloading ..."
    TMP_FILE="$(mktemp)"
    curl --location --output "$TMP_FILE" "$ZIP_URL"
    unzip -o -j "$TMP_FILE" bin/pledge -d bin/
    rm "$TMP_FILE"

    # Rewrite the file header so it becomes a native Linux executable which we
    # can run directly without needing a shell. See:
    # https://justine.lol/apeloader/
    echo "Assimilating ..."
    sh bin/pledge --assimilate

    echo "Complete."
    echo "$ZIP_URL" > "$URL_RECORD_FILE"
