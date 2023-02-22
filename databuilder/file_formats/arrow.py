import datetime
from itertools import islice

import pyarrow

from databuilder.file_formats.validation import ValidationError, validate_headers

PYARROW_TYPE_MAP = {
    bool: pyarrow.bool_,
    # Note ints are handled separately
    float: pyarrow.float64,
    str: pyarrow.string,
    datetime.date: pyarrow.date32,
}

# When dumping a `pyarrow.Table` or `pandas.DataFrame` to disk, pyarrow takes care of
# chunking up the RecordBatches into "reasonable" sized pieces for us based on the
# number of bytes consumed. But when streaming results to disk as we do below we have to
# do the chunking ourselves. Tracking bytes consumed and splitting batches accordingly
# gets very fiddly and my understanding is that for our purposes the precise size
# doesn't really matter. If we set it very low (tens of rows) then we might get
# performance issues and file bloating due to the overhead each batch adds. If we set it
# very high (millions of rows) then we negate the point of streaming results to disk and
# our memory usage will get noticebly high. Between these bounds I think it makes very
# little practice difference to us.
#
# Reading around bits of old blog posts suggests that we want batches in roughly the
# single to low double-digit megabyte range. Assuming 30 columns, each of an average of
# 32 bits wide, then 64,000 rows takes about 7.7MB, which seems roughly in the right
# ballpark.
ROWS_PER_BATCH = 64000


def write_dataset_arrow(filename, results, column_specs):
    schema, batch_to_pyarrow = get_schema_and_convertor(column_specs)
    options = pyarrow.ipc.IpcWriteOptions(compression="zstd", use_threads=True)

    with pyarrow.OSFile(str(filename), "wb") as sink:
        with pyarrow.ipc.new_file(sink, schema, options=options) as writer:
            for results_batch in batch_and_transpose(results, ROWS_PER_BATCH):
                record_batch = pyarrow.record_batch(
                    batch_to_pyarrow(results_batch), schema=schema
                )
                writer.write(record_batch)


def get_schema_and_convertor(column_specs):
    fields = []
    convertors = []
    for name, spec in column_specs.items():
        field, column_to_pyarrow = get_field_and_convertor(name, spec)
        fields.append(field)
        convertors.append(column_to_pyarrow)

    def batch_to_pyarrow(columns):
        return [f(column) for f, column in zip(convertors, columns)]

    return pyarrow.schema(fields), batch_to_pyarrow


def get_field_and_convertor(name, spec):
    if spec.type == int:
        type_ = smallest_int_type_for_range(spec.min_value, spec.max_value)
    else:
        type_ = PYARROW_TYPE_MAP[spec.type]()

    if spec.categories is not None:
        # Although pyarrow.dictionary indices can obviously never be negative we use
        # `-1` as the minimum below so we always get a signed type; this is because
        # Pandas can't read dictionaries with unsigned index types. See:
        # https://github.com/opensafely-core/databuilder/issues/945
        index_type = smallest_int_type_for_range(-1, len(spec.categories) - 1)
        value_type = type_
        type_ = pyarrow.dictionary(index_type, value_type, ordered=True)
        column_to_pyarrow = make_column_to_pyarrow_with_categories(
            index_type, value_type, spec.categories
        )
    else:
        column_to_pyarrow = make_column_to_pyarrow(type_)

    field = pyarrow.field(name, type_, nullable=spec.nullable)
    return field, column_to_pyarrow


def make_column_to_pyarrow(type_):
    def column_to_pyarrow(column):
        return pyarrow.array(column, type=type_, size=len(column))

    return column_to_pyarrow


def smallest_int_type_for_range(minimum, maximum):
    """
    Return smallest pyarrow integer type capable of representing all values in the
    supplied range

    Note: this was cribbed from the OpenPrescribing codebase and handles a large range
    of types than we need right now.
    """
    # If either bound is unknown return the default type
    if minimum is None or maximum is None:
        return pyarrow.int64()
    signed = minimum < 0
    abs_max = max(maximum, abs(minimum))
    if signed:
        if abs_max < 1 << 7:
            return pyarrow.int8()
        elif abs_max < 1 << 15:
            return pyarrow.int16()
        elif abs_max < 1 << 31:
            return pyarrow.int32()
        elif abs_max < 1 << 63:
            return pyarrow.int64()
        else:
            assert False
    else:
        if abs_max < 1 << 8:
            return pyarrow.uint8()
        elif abs_max < 1 << 16:
            return pyarrow.uint16()
        elif abs_max < 1 << 32:
            return pyarrow.uint32()
        elif abs_max < 1 << 64:
            return pyarrow.uint64()
        else:
            assert False


def make_column_to_pyarrow_with_categories(index_type, value_type, categories):
    value_array = pyarrow.array(categories, type=value_type)
    # NULL values should remain NULL
    mapping = {None: None}
    for index, category in enumerate(categories):
        mapping[category] = index

    def column_to_pyarrow(column):
        indices = map(mapping.__getitem__, column)
        index_array = pyarrow.array(indices, type=index_type, size=len(column))
        # This looks a bit like we're including another copy of the `value_array` along
        # with each batch of results. However, Arrow only stores a single copy of this
        # and enforces that subsequent batches use the same set of values.
        return pyarrow.DictionaryArray.from_arrays(index_array, value_array)

    return column_to_pyarrow


def batch_and_transpose(iterable, batch_size):
    """
    Takes an iterable over rows and returns an iterator over batches of columns e.g.

    >>> results = batch_and_transpose(
    ...   [(1, "a"), (2, "b"), (3, "c"), (4, "d")],
    ...   batch_size=3,
    ... )
    >>> list(results)
    [[(1, 2, 3), ('a', 'b', 'c')], [(4,), ('d',)]]

    This is the structure required by Arrow, which is a columar format.
    """
    iterator = iter(iterable)

    def next_transposed_batch():
        row_batch = islice(iterator, batch_size)
        return list(zip(*row_batch))

    return iter(next_transposed_batch, [])


def validate_dataset_arrow(filename, column_specs):
    target_schema, _ = get_schema_and_convertor(column_specs)
    # Arrow enforces that all record batches have a consistent schema and that any
    # categorical columns use the same dictionary, so we only need to get the first
    # batch in order to validate
    batch = get_first_record_batch_from_file(filename)
    validate_headers(batch.schema.names, target_schema.names)
    if not batch.schema.equals(target_schema):
        # This isn't most user-friendly error message, but it will do for now
        raise ValidationError(
            f"File does not have expected schema\n\n"
            f"Schema:\n{batch.schema.to_string()}\n\n"
            f"Expected:\n{target_schema.to_string()}"
        )
    for name, spec in column_specs.items():
        if spec.categories is None:
            continue
        column_categories = batch.column(name).dictionary.to_pylist()
        if column_categories != list(spec.categories):
            raise ValidationError(
                f"Unexpected categories in column '{name}'\n"
                f"Categories: {', '.join(column_categories)}\n"
                f"Expected: {', '.join(spec.categories)}\n"
            )


def get_first_record_batch_from_file(filename):
    with pyarrow.OSFile(str(filename), "rb") as f:
        with pyarrow.ipc.open_file(f) as reader:
            return reader.get_batch(0)


def get_table_from_file(filename):
    with pyarrow.memory_map(str(filename), "rb") as f:
        with pyarrow.ipc.open_file(f) as reader:
            return reader.read_all()
