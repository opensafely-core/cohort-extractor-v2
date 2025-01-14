import contextlib
import urllib.parse

from ehrql.file_formats.arrow import (
    ArrowRowsReader,
    write_rows_arrow,
)
from ehrql.file_formats.base import FileValidationError
from ehrql.file_formats.csv import (
    CSVGZRowsReader,
    CSVRowsReader,
    write_rows_csv,
    write_rows_csv_gz,
)
from ehrql.utils.itertools_utils import eager_iterator


FILE_FORMATS = {
    ".arrow": (write_rows_arrow, ArrowRowsReader),
    ".csv": (write_rows_csv, CSVRowsReader),
    ".csv.gz": (write_rows_csv_gz, CSVGZRowsReader),
}


def write_rows(filename, rows, column_specs):
    extension = get_file_extension(filename)
    writer = FILE_FORMATS[extension][0]
    # `rows` is often a generator which won't actually execute until we start consuming
    # it. We want to make sure we trigger any potential errors (or relevant log output)
    # before we create the output file, write headers etc. But we don't want to read the
    # whole thing into memory. So we wrap it in a function which draws the first item
    # upfront, but doesn't consume the rest of the iterator.
    rows = eager_iterator(rows)
    # We use None for stdout
    if filename is not None:
        filename.parent.mkdir(parents=True, exist_ok=True)
    writer(filename, rows, column_specs)


def read_rows(filename, column_specs, allow_missing_columns=False):
    extension = get_file_extension(filename)
    if extension not in FILE_FORMATS:
        raise FileValidationError(f"Unsupported file type: {extension}")
    if not filename.is_file():
        raise FileValidationError(f"Missing file: {filename}")
    reader = FILE_FORMATS[extension][1]
    return reader(filename, column_specs, allow_missing_columns=allow_missing_columns)


def read_tables(filename, table_specs, allow_missing_columns=False):
    # If we've got a single-table input file and only a single table to read then that's
    # fine, but it needs slightly special handling
    if not input_filename_supports_multiple_tables(filename):
        if len(table_specs) == 1:
            column_specs = list(table_specs.values())[0]
            rows = read_rows(
                filename,
                column_specs,
                allow_missing_columns=allow_missing_columns,
            )
            yield from [rows]
            return
        else:
            files = list(table_specs.keys())
            suffix = filename.suffix
            raise FileValidationError(
                f"Attempting to read {len(table_specs)} tables, but input only "
                f"provides a single table\n"
                f"      Try moving -> {filename}\n"
                f"              to -> {filename.parent / filename.stem}/{files[0]}{suffix}\n"
                f"          adding -> {', '.join(f + suffix for f in files[1:])}\n"
                f"  and using path -> {filename.parent / filename.stem}/"
            )

    extension = get_extension_from_directory(filename)
    # Using ExitStack here allows us to open and validate all files before emiting any
    # rows while still correctly closing all open files if we raise an error part way
    # through
    with contextlib.ExitStack() as stack:
        yield from [
            stack.enter_context(
                read_rows(
                    get_table_filename(filename, table_name, extension),
                    column_specs,
                    allow_missing_columns=allow_missing_columns,
                )
            )
            for table_name, column_specs in table_specs.items()
        ]


def write_tables(filename, tables, table_specs):
    # If we've got a single-table output file and only a single table to write then
    # that's fine, but it needs slightly special handling
    if not output_filename_supports_multiple_tables(filename):
        if len(table_specs) == 1:
            column_specs = list(table_specs.values())[0]
            rows = next(iter(tables))
            return write_rows(filename, rows, column_specs)
        else:
            raise FileValidationError(
                f"Attempting to write {len(table_specs)} tables, but output only "
                f"supports a single table\n"
                f"  Instead of -> {filename}\n"
                f"         try -> "
                f"{filename.parent / filename.stem}/:{filename.suffix.lstrip('.')}"
            )

    filename, extension = split_directory_and_extension(filename)
    for rows, (table_name, column_specs) in zip(tables, table_specs.items()):
        table_filename = get_table_filename(filename, table_name, extension)
        write_rows(table_filename, rows, column_specs)


def get_file_extension(filename):
    if filename is None:
        # If we have no filename we're writing to stdout, so default to CSV
        return ".csv"
    elif filename.suffix == ".gz":
        return "".join(filename.suffixes[-2:])
    else:
        return filename.suffix


def get_extension_from_directory(filename):
    if not filename.exists():
        raise FileValidationError(f"Missing directory: {filename}")
    if not filename.is_dir():
        raise FileValidationError(f"Not a directory: {filename}")

    # We could enforce that data directories only contain a single type of file, but
    # that seems unnecessarily strict (you might want a README, or have temporary editor
    # backup files in there) so instead we only enforce that there's a single type of
    # _data_ file.
    extensions = {get_file_extension(f) for f in filename.iterdir()}
    matching = extensions.intersection(FILE_FORMATS.keys())
    if not matching:
        raise FileValidationError(f"No supported file formats found in: {filename}")
    elif len(matching) > 1:
        raise FileValidationError(
            f"Found multiple file formats ({', '.join(sorted(matching))}) "
            f"in: {filename}"
        )
    else:
        return list(matching)[0]


def split_directory_and_extension(filename):
    # This is slightly unpleasant in that we've invented our own syntax for saying "I
    # want a directory here with files of this type in it" e.g.
    #
    #     path/to/my/directory:csv
    #
    # But I don't seen an obvious alternative and I hope it's reasonably natural.
    name, separator, extension = filename.name.rpartition(":")
    if not separator:
        return filename, ""
    elif not name:
        return filename.parent, f".{extension}"
    else:
        return filename.with_name(name), f".{extension}"


def input_filename_supports_multiple_tables(filename):
    # At present, supplying a directory is the only way to provide multiple input
    # tables, but it's not inconceivable that in future we might support single-file
    # multiple-table formats e.g SQLite or DuckDB files. If we do then updating this
    # function and its sibling below should be all that's required.
    return filename.is_dir()


def output_filename_supports_multiple_tables(filename):
    if filename is None:
        return False
    # Again, at present only directories support multiple output tables but see above
    extension = split_directory_and_extension(filename)[1]
    return extension != ""


def get_table_filename(base_filename, table_name, extension):
    # Use URL quoting as an easy way of escaping any potentially problematic characters
    # in filenames
    safe_name = urllib.parse.quote(table_name, safe="")
    return base_filename / f"{safe_name}{extension}"
