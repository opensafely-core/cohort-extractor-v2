import datetime

import sqlalchemy.types
from sqlalchemy.dialects.mssql.pymssql import MSDialect_pymssql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ClauseElement, Executable


# MS-SQL can misinterpret ISO dates, depending on its localisation settings so
# we need to use particular date formats which we know will be consistently
# interpreted. We do this by defining custom SQLAlchemy types. See:
# https://github.com/opensafely-core/databuilder/issues/92
# http://msdn.microsoft.com/en-us/library/ms180878.aspx
# https://stackoverflow.com/a/25548626/559140
class _MSSQLDateTimeBase:
    text_type = sqlalchemy.types.Text()

    def process_bind_param(self, value, dialect):
        """
        Convert a Python value to a form suitable for passing as a parameter to
        the database connector
        """
        if value is None:
            # TODO: test this branch
            return None  # pragma: no cover
        # We accept ISO formated strings as well
        if isinstance(value, str):
            value = self.date_type.fromisoformat(value)
        if not isinstance(value, self.date_type):
            raise TypeError(f"Expected {self.date_type} or str got: {value!r}")
        return value.strftime(self.format_str)

    def process_literal_param(self, value, dialect):
        """
        Convert a Python value into an escaped string suitable for
        interpolating directly into an SQL string
        """
        # Use the above method to convert to a string first
        value = self.process_bind_param(value, dialect)
        # Use the Text literal processor to quote and escape that string
        literal_processor = self.text_type.literal_processor(dialect)
        return literal_processor(value)


class MSSQLDate(_MSSQLDateTimeBase, sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.Date
    cache_ok = True
    date_type = datetime.date
    # See https://stackoverflow.com/a/25548626/559140
    format_str = "%Y%m%d"


class MSSQLDateTime(_MSSQLDateTimeBase, sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.DateTime
    cache_ok = True
    date_type = datetime.datetime
    # See https://stackoverflow.com/a/25548626/559140
    format_str = "%Y-%m-%dT%H:%M:%S"


class MSSQLDialect(MSDialect_pymssql):

    supports_statement_cache = True

    colspecs = MSDialect_pymssql.colspecs | {
        sqlalchemy.types.Date: MSSQLDate,
        sqlalchemy.types.DateTime: MSSQLDateTime,
    }


class SelectStarInto(Executable, ClauseElement):
    inherit_cache = True

    def __init__(self, table, selectable):
        self.table = table
        self.selectable = selectable

    def get_children(self):
        return (self.table, self.selectable)


@compiles(SelectStarInto)
def visit_select_star_into(element, compiler, **kw):
    return "SELECT * INTO {} FROM {}".format(
        compiler.process(element.table, asfrom=True, **kw),
        compiler.process(element.selectable, asfrom=True, **kw),
    )
