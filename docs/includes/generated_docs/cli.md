```
ehrql [--help] [--version] COMMAND_NAME ...
```
The command line interface for ehrQL, a query language for electronic health
record (EHR) data.

<div class="attr-heading" id="ehrql.command_name">
  <tt>COMMAND_NAME</tt>
  <a class="headerlink" href="#ehrql.command_name" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Name of the sub-command to execute.
<div class="attr-heading">
  <a href="#generate-dataset"><tt>generate-dataset</tt></a>
</div>
<p class="indent">
Take a dataset definition file and output a dataset.
</p>

<div class="attr-heading">
  <a href="#generate-measures"><tt>generate-measures</tt></a>
</div>
<p class="indent">
Take a measures definition file and output measures.
</p>

<div class="attr-heading">
  <a href="#sandbox"><tt>sandbox</tt></a>
</div>
<p class="indent">
Start the ehrQL sandbox environment.
</p>

<div class="attr-heading">
  <a href="#quiz"><tt>quiz</tt></a>
</div>
<p class="indent">
Start the ehrQL quiz.
</p>

<div class="attr-heading">
  <a href="#dump-quiz-file"><tt>dump-quiz-file</tt></a>
</div>
<p class="indent">
Dump the file for answering the quiz to the current directory.
</p>

<div class="attr-heading">
  <a href="#dump-example-data"><tt>dump-example-data</tt></a>
</div>
<p class="indent">
Dump example data for the ehrQL tutorial to the current directory.
</p>

<div class="attr-heading">
  <a href="#dump-dataset-sql"><tt>dump-dataset-sql</tt></a>
</div>
<p class="indent">
Output the SQL that would be executed to fetch the results of the dataset
definition.
</p>

<div class="attr-heading">
  <a href="#create-dummy-tables"><tt>create-dummy-tables</tt></a>
</div>
<p class="indent">
Generate dummy tables and write them out as files – one per table, CSV by
default.
</p>

<div class="attr-heading">
  <a href="#assure"><tt>assure</tt></a>
</div>
<p class="indent">
Command for running assurance tests.
</p>

<div class="attr-heading">
  <a href="#test-connection"><tt>test-connection</tt></a>
</div>
<p class="indent">
Internal command for testing the database connection configuration.
</p>

<div class="attr-heading">
  <a href="#serialize-definition"><tt>serialize-definition</tt></a>
</div>
<p class="indent">
Internal command for serializing a definition file to a JSON representation.
</p>

<div class="attr-heading">
  <a href="#isolation-report"><tt>isolation-report</tt></a>
</div>
<p class="indent">
Internal command for testing code isolation support.
</p>

<div class="attr-heading">
  <a href="#graph-query"><tt>graph-query</tt></a>
</div>
<p class="indent">
Output the dataset definition's query graph
</p>

<div class="attr-heading">
  <a href="#debug"><tt>debug</tt></a>
</div>
<p class="indent">
Internal command for getting debugging information from a dataset
definition; used by the [OpenSAFELY VSCode extension][opensafely-vscode].
</p>

</div>

<div class="attr-heading" id="ehrql.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#ehrql.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="ehrql.version">
  <tt>--version</tt>
  <a class="headerlink" href="#ehrql.version" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Show the exact version of ehrQL in use and then exit.

</div>


<h2 id="generate-dataset" data-toc-label="generate-dataset" markdown>
  generate-dataset
</h2>
```
ehrql generate-dataset DEFINITION_FILE [--help] [--output DATASET_FILE]
      [--test-data-file TEST_DATA_FILE] [--dummy-data-file DUMMY_DATA_FILE]
      [--dummy-tables DUMMY_TABLES_PATH] [--dsn DSN]
      [--query-engine QUERY_ENGINE_CLASS] [--backend BACKEND_CLASS]
      [ -- ... PARAMETERS ...]
```
Take a dataset definition file and output a dataset.

ehrQL is designed so that exactly the same command can be used to output a dummy
dataset when run on your own computer and then output a real dataset when run
inside the secure environment as part of an OpenSAFELY pipeline.

<div class="attr-heading" id="generate-dataset.definition_file">
  <tt>DEFINITION_FILE</tt>
  <a class="headerlink" href="#generate-dataset.definition_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the Python file where the dataset is defined.

</div>

<div class="attr-heading" id="generate-dataset.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#generate-dataset.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="generate-dataset.output">
  <tt>--output DATASET_FILE</tt>
  <a class="headerlink" href="#generate-dataset.output" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the file where the dataset will be written (console by default).

The file extension determines the file format used. Supported formats are:
`.arrow`, `.csv`, `.csv.gz`

</div>

<div class="attr-heading" id="generate-dataset.test-data-file">
  <tt>--test-data-file TEST_DATA_FILE</tt>
  <a class="headerlink" href="#generate-dataset.test-data-file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Takes a test dataset definition file.

</div>

<div class="attr-heading" id="generate-dataset.dummy-data-file">
  <tt>--dummy-data-file DUMMY_DATA_FILE</tt>
  <a class="headerlink" href="#generate-dataset.dummy-data-file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to a dummy dataset.

This allows you to take complete control of the dummy dataset. ehrQL
will ensure that the column names, types and categorical values match what
they will be in the real dataset, but does no further validation.

Note that the dummy dataset doesn't need to be of the same type as the
real dataset (e.g. you can use a `.csv` file here to produce a `.arrow`
file).

This argument is ignored when running against real tables.

</div>

<div class="attr-heading" id="generate-dataset.dummy-tables">
  <tt>--dummy-tables DUMMY_TABLES_PATH</tt>
  <a class="headerlink" href="#generate-dataset.dummy-tables" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to directory of files (one per table) to use as dummy tables
(see [`create-dummy-tables`](#create-dummy-tables)).

Files may be in any supported format: `.arrow`, `.csv`, `.csv.gz`

This argument is ignored when running against real tables.

</div>

<div class="attr-heading" id="generate-dataset.user_args">
  <tt>PARAMETERS</tt>
  <a class="headerlink" href="#generate-dataset.user_args" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.


</div>

<div class="attr-heading">
  <strong>Internal Arguments</strong>
</div>
<div markdown="block" class="indent">
You should not normally need to use these arguments: they are for the
internal operation of ehrQL and the OpenSAFELY platform.
<div class="attr-heading" id="generate-dataset.dsn">
  <tt>--dsn DSN</tt>
  <a class="headerlink" href="#generate-dataset.dsn" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Data Source Name: URL of remote database, or path to data on disk
(defaults to value of DATABASE_URL environment variable).

</div>

<div class="attr-heading" id="generate-dataset.query-engine">
  <tt>--query-engine QUERY_ENGINE_CLASS</tt>
  <a class="headerlink" href="#generate-dataset.query-engine" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Dotted import path to Query Engine class, or one of: `mssql`, `sqlite`, `localfile`, `trino`, `csv`

</div>

<div class="attr-heading" id="generate-dataset.backend">
  <tt>--backend BACKEND_CLASS</tt>
  <a class="headerlink" href="#generate-dataset.backend" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Dotted import path to Backend class, or one of: `emis`, `tpp`

</div>

</div>


<h2 id="generate-measures" data-toc-label="generate-measures" markdown>
  generate-measures
</h2>
```
ehrql generate-measures DEFINITION_FILE [--help] [--output OUTPUT_FILE]
      [--dummy-data-file DUMMY_DATA_FILE] [--dummy-tables DUMMY_TABLES_PATH]
      [--dsn DSN] [--query-engine QUERY_ENGINE_CLASS] [--backend BACKEND_CLASS]
      [ -- ... PARAMETERS ...]
```
Take a measures definition file and output measures.

<div class="attr-heading" id="generate-measures.definition_file">
  <tt>DEFINITION_FILE</tt>
  <a class="headerlink" href="#generate-measures.definition_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the Python file where measures are defined.

</div>

<div class="attr-heading" id="generate-measures.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#generate-measures.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="generate-measures.output">
  <tt>--output OUTPUT_FILE</tt>
  <a class="headerlink" href="#generate-measures.output" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the file where the measures will be written (console by default),
supported formats: `.arrow`, `.csv`, `.csv.gz`

</div>

<div class="attr-heading" id="generate-measures.dummy-data-file">
  <tt>--dummy-data-file DUMMY_DATA_FILE</tt>
  <a class="headerlink" href="#generate-measures.dummy-data-file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to dummy measures output.

This allows you to take complete control of the dummy measures output. ehrQL
will ensure that the column names, types and categorical values match what
they will be in the real measures output, but does no further validation.

Note that the dummy measures output doesn't need to be of the same type as the
real measures output (e.g. you can use a `.csv` file here to produce a `.arrow`
file).

This argument is ignored when running against real tables.

</div>

<div class="attr-heading" id="generate-measures.dummy-tables">
  <tt>--dummy-tables DUMMY_TABLES_PATH</tt>
  <a class="headerlink" href="#generate-measures.dummy-tables" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to directory of files (one per table) to use as dummy tables
(see [`create-dummy-tables`](#create-dummy-tables)).

Files may be in any supported format: `.arrow`, `.csv`, `.csv.gz`

This argument is ignored when running against real tables.

</div>

<div class="attr-heading" id="generate-measures.user_args">
  <tt>PARAMETERS</tt>
  <a class="headerlink" href="#generate-measures.user_args" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.


</div>

<div class="attr-heading">
  <strong>Internal Arguments</strong>
</div>
<div markdown="block" class="indent">
You should not normally need to use these arguments: they are for the
internal operation of ehrQL and the OpenSAFELY platform.
<div class="attr-heading" id="generate-measures.dsn">
  <tt>--dsn DSN</tt>
  <a class="headerlink" href="#generate-measures.dsn" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Data Source Name: URL of remote database, or path to data on disk
(defaults to value of DATABASE_URL environment variable).

</div>

<div class="attr-heading" id="generate-measures.query-engine">
  <tt>--query-engine QUERY_ENGINE_CLASS</tt>
  <a class="headerlink" href="#generate-measures.query-engine" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Dotted import path to Query Engine class, or one of: `mssql`, `sqlite`, `localfile`, `trino`, `csv`

</div>

<div class="attr-heading" id="generate-measures.backend">
  <tt>--backend BACKEND_CLASS</tt>
  <a class="headerlink" href="#generate-measures.backend" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Dotted import path to Backend class, or one of: `emis`, `tpp`

</div>

</div>


<h2 id="sandbox" data-toc-label="sandbox" markdown>
  sandbox
</h2>
```
ehrql sandbox DUMMY_TABLES_PATH [--help]
```
Start the ehrQL sandbox environment.

<div class="attr-heading" id="sandbox.dummy_tables_path">
  <tt>DUMMY_TABLES_PATH</tt>
  <a class="headerlink" href="#sandbox.dummy_tables_path" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to directory of data files (one per table), supported formats are:
`.arrow`, `.csv`, `.csv.gz`

</div>

<div class="attr-heading" id="sandbox.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#sandbox.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>


<h2 id="quiz" data-toc-label="quiz" markdown>
  quiz
</h2>
```
ehrql quiz [QUIZ_FILE_PATH] [--help]
```
Start the ehrQL quiz.

<div class="attr-heading" id="quiz.quiz_file_path">
  <tt>QUIZ_FILE_PATH</tt>
  <a class="headerlink" href="#quiz.quiz_file_path" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to the quiz file. Default is `quiz_answers.py`.

</div>

<div class="attr-heading" id="quiz.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#quiz.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>


<h2 id="dump-quiz-file" data-toc-label="dump-quiz-file" markdown>
  dump-quiz-file
</h2>
```
ehrql dump-quiz-file [--help]
```
Dump the file for answering the quiz to the current directory.

<div class="attr-heading" id="dump-quiz-file.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#dump-quiz-file.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>


<h2 id="dump-example-data" data-toc-label="dump-example-data" markdown>
  dump-example-data
</h2>
```
ehrql dump-example-data [--help]
```
Dump example data for the ehrQL tutorial to the current directory.

<div class="attr-heading" id="dump-example-data.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#dump-example-data.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>


<h2 id="dump-dataset-sql" data-toc-label="dump-dataset-sql" markdown>
  dump-dataset-sql
</h2>
```
ehrql dump-dataset-sql DEFINITION_FILE [--help] [--output OUTPUT_FILE]
      [--query-engine QUERY_ENGINE_CLASS] [--backend BACKEND_CLASS]
      [ -- ... PARAMETERS ...]
```
Output the SQL that would be executed to fetch the results of the dataset
definition.

By default, this command will output SQL suitable for the SQLite database.
To get the SQL as it would be run against the real tables you will to supply
the appropriate `--backend` argument, for example `--backend tpp`.

Note that due to configuration differences this may not always exactly match
what gets run against the real tables.

<div class="attr-heading" id="dump-dataset-sql.definition_file">
  <tt>DEFINITION_FILE</tt>
  <a class="headerlink" href="#dump-dataset-sql.definition_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the Python file where the dataset is defined.

</div>

<div class="attr-heading" id="dump-dataset-sql.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#dump-dataset-sql.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="dump-dataset-sql.output">
  <tt>--output OUTPUT_FILE</tt>
  <a class="headerlink" href="#dump-dataset-sql.output" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
SQL output file (outputs to console by default).

</div>

<div class="attr-heading" id="dump-dataset-sql.query-engine">
  <tt>--query-engine QUERY_ENGINE_CLASS</tt>
  <a class="headerlink" href="#dump-dataset-sql.query-engine" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Dotted import path to Query Engine class, or one of: `mssql`, `sqlite`, `localfile`, `trino`, `csv`

</div>

<div class="attr-heading" id="dump-dataset-sql.backend">
  <tt>--backend BACKEND_CLASS</tt>
  <a class="headerlink" href="#dump-dataset-sql.backend" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Dotted import path to Backend class, or one of: `emis`, `tpp`

</div>

<div class="attr-heading" id="dump-dataset-sql.user_args">
  <tt>PARAMETERS</tt>
  <a class="headerlink" href="#dump-dataset-sql.user_args" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.


</div>


<h2 id="create-dummy-tables" data-toc-label="create-dummy-tables" markdown>
  create-dummy-tables
</h2>
```
ehrql create-dummy-tables DEFINITION_FILE DUMMY_TABLES_PATH [--help]
      [ -- ... PARAMETERS ...]
```
Generate dummy tables and write them out as files – one per table, CSV by
default.

This command generates the same dummy tables that the `generate-dataset`
command would generate, but instead of using them to produce a dummy
dataset, it writes them out as individual files.

The directory containing these files can then be used as the
[`--dummy-tables`](#generate-dataset.dummy-tables) argument to
`generate-dataset` to produce the dummy dataset.

The files can be edited in any way you wish, giving you full control over
the dummy tables.

<div class="attr-heading" id="create-dummy-tables.definition_file">
  <tt>DEFINITION_FILE</tt>
  <a class="headerlink" href="#create-dummy-tables.definition_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the Python file where the dataset is defined.

</div>

<div class="attr-heading" id="create-dummy-tables.dummy_tables_path">
  <tt>DUMMY_TABLES_PATH</tt>
  <a class="headerlink" href="#create-dummy-tables.dummy_tables_path" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to directory where files (one per table) will be written.

By default these will be CSV files. To generate files in other formats add
`:<format>` to the directory name e.g.
`my_outputs:arrow`, `my_outputs:csv`, `my_outputs:csv.gz`

</div>

<div class="attr-heading" id="create-dummy-tables.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#create-dummy-tables.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="create-dummy-tables.user_args">
  <tt>PARAMETERS</tt>
  <a class="headerlink" href="#create-dummy-tables.user_args" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.


</div>


<h2 id="assure" data-toc-label="assure" markdown>
  assure
</h2>
```
ehrql assure TEST_DATA_FILE [--help] [ -- ... PARAMETERS ...]
```
Command for running assurance tests.

<div class="attr-heading" id="assure.test_data_file">
  <tt>TEST_DATA_FILE</tt>
  <a class="headerlink" href="#assure.test_data_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the file where the test data is defined.

</div>

<div class="attr-heading" id="assure.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#assure.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="assure.user_args">
  <tt>PARAMETERS</tt>
  <a class="headerlink" href="#assure.user_args" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.


</div>


<h2 id="test-connection" data-toc-label="test-connection" markdown>
  test-connection
</h2>
```
ehrql test-connection [--help] [-b BACKEND_CLASS] [-u URL]
```
Internal command for testing the database connection configuration.

Note that **this in an internal command** and not intended for end users.

<div class="attr-heading" id="test-connection.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#test-connection.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="test-connection.b">
  <tt>--backend, -b BACKEND_CLASS</tt>
  <a class="headerlink" href="#test-connection.b" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Dotted import path to Backend class, or one of: `emis`, `tpp`

</div>

<div class="attr-heading" id="test-connection.u">
  <tt>--url, -u URL</tt>
  <a class="headerlink" href="#test-connection.u" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Database connection string.

</div>


<h2 id="serialize-definition" data-toc-label="serialize-definition" markdown>
  serialize-definition
</h2>
```
ehrql serialize-definition DEFINITION_FILE [--help]
      [--definition-type DEFINITION_TYPE] [--output OUTPUT_FILE]
      [--dummy-tables DUMMY_TABLES_PATH] [--display-format RENDER_FORMAT]
      [ -- ... PARAMETERS ...]
```
Internal command for serializing a definition file to a JSON representation.

Note that **this in an internal command** and not intended for end users.

<div class="attr-heading" id="serialize-definition.definition_file">
  <tt>DEFINITION_FILE</tt>
  <a class="headerlink" href="#serialize-definition.definition_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Definition file path

</div>

<div class="attr-heading" id="serialize-definition.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#serialize-definition.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="serialize-definition.definition-type">
  <tt>-t, --definition-type DEFINITION_TYPE</tt>
  <a class="headerlink" href="#serialize-definition.definition-type" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Options: `dataset`, `measures`, `test`, `debug`

</div>

<div class="attr-heading" id="serialize-definition.output">
  <tt>-o, --output OUTPUT_FILE</tt>
  <a class="headerlink" href="#serialize-definition.output" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Output file path (stdout by default)

</div>

<div class="attr-heading" id="serialize-definition.dummy-tables">
  <tt>--dummy-tables DUMMY_TABLES_PATH</tt>
  <a class="headerlink" href="#serialize-definition.dummy-tables" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to directory of files (one per table) to use as dummy tables
(see [`create-dummy-tables`](#create-dummy-tables)).

Files may be in any supported format: `.arrow`, `.csv`, `.csv.gz`

This argument is ignored when running against real tables.

</div>

<div class="attr-heading" id="serialize-definition.display-format">
  <tt>--display-format RENDER_FORMAT</tt>
  <a class="headerlink" href="#serialize-definition.display-format" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Render format for debug command, default ascii

</div>

<div class="attr-heading" id="serialize-definition.user_args">
  <tt>PARAMETERS</tt>
  <a class="headerlink" href="#serialize-definition.user_args" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.


</div>


<h2 id="isolation-report" data-toc-label="isolation-report" markdown>
  isolation-report
</h2>
```
ehrql isolation-report [--help]
```
Internal command for testing code isolation support.

Note that **this in an internal command** and not intended for end users.

<div class="attr-heading" id="isolation-report.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#isolation-report.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>


<h2 id="graph-query" data-toc-label="graph-query" markdown>
  graph-query
</h2>
```
ehrql graph-query DEFINITION_FILE [--help] OUTPUT_FILE [ -- ... PARAMETERS ...]
```
Output the dataset definition's query graph

<div class="attr-heading" id="graph-query.definition_file">
  <tt>DEFINITION_FILE</tt>
  <a class="headerlink" href="#graph-query.definition_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the Python file where the dataset is defined.

</div>

<div class="attr-heading" id="graph-query.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#graph-query.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="graph-query.output_file">
  <tt>OUTPUT_FILE</tt>
  <a class="headerlink" href="#graph-query.output_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
SVG output file.

</div>

<div class="attr-heading" id="graph-query.user_args">
  <tt>PARAMETERS</tt>
  <a class="headerlink" href="#graph-query.user_args" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.


</div>


<h2 id="debug" data-toc-label="debug" markdown>
  debug
</h2>
```
ehrql debug DEFINITION_FILE [--help] [--dummy-tables DUMMY_TABLES_PATH]
      [--display-format RENDER_FORMAT] [ -- ... PARAMETERS ...]
```
Internal command for getting debugging information from a dataset
definition; used by the [OpenSAFELY VSCode extension][opensafely-vscode].

Note that **this in an internal command** and not intended for end users.

[opensafely-vscode]: https://marketplace.visualstudio.com/items?itemName=bennettoxford.opensafely

<div class="attr-heading" id="debug.definition_file">
  <tt>DEFINITION_FILE</tt>
  <a class="headerlink" href="#debug.definition_file" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path of the Python file where the dataset is defined.

</div>

<div class="attr-heading" id="debug.help">
  <tt>-h, --help</tt>
  <a class="headerlink" href="#debug.help" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
show this help message and exit

</div>

<div class="attr-heading" id="debug.dummy-tables">
  <tt>--dummy-tables DUMMY_TABLES_PATH</tt>
  <a class="headerlink" href="#debug.dummy-tables" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Path to directory of files (one per table) to use as dummy tables
(see [`create-dummy-tables`](#create-dummy-tables)).

Files may be in any supported format: `.arrow`, `.csv`, `.csv.gz`

</div>

<div class="attr-heading" id="debug.display-format">
  <tt>--display-format RENDER_FORMAT</tt>
  <a class="headerlink" href="#debug.display-format" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Render format for debug command, default ascii

</div>

<div class="attr-heading" id="debug.user_args">
  <tt>PARAMETERS</tt>
  <a class="headerlink" href="#debug.user_args" title="Permanent link">🔗</a>
</div>
<div markdown="block" class="indent">
Parameters are extra arguments you can pass to your Python definition file. They must be
supplied after all ehrQL arguments and separated from the ehrQL arguments with a
double-dash ` -- `.


</div>
