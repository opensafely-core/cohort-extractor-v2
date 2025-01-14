from ehrql import days, maximum_of, minimum_of, weeks
from ehrql.tables.core import clinical_events, patients
from ehrql.tables.tpp import addresses, apcs, ons_deaths


# A file to keep track of things where we get good autocomplete behaviour.
#
# Anything in this file is automatically checked by the test file test_autocomplete.py,
# though it must be formatted correctly or the tests will fail. Currently you can:
#
# - write a single command and confirm the type e.g.:
#     patients.date_of_birth  ## type:DatePatientSeries
#
# - assign a single command to a variable and confirm the type e.g.:
#     bool_invert = ~patients.exists_for_patient()  ## type:BoolPatientSeries
#
# - either of the above but spanning multiple lines e.g.
#     bool_and = (
#       patients.exists_for_patient() & patients.exists_for_patient()
#     )  ## type:BoolPatientSeries

# Currently all columns on all tables have type of "Series | Any",
# so we don't get autocomplete. Providing type hints on the Series
# class, and on the @table decorator means the column types are
# correct e.g. IntPatientSeries, DateEventSeries etc. and therefore
# we get autocomplete for all the properties and methods on each series.
patients.date_of_birth  ## type:DatePatientSeries
patients.sex  ## type:StrPatientSeries
ons_deaths.underlying_cause_of_death  ## type:CodePatientSeries

clinical_events.date  ## type:DateEventSeries
clinical_events.numeric_value  ## type:FloatEventSeries
clinical_events.snomedct_code  ## type:CodeEventSeries
apcs.all_diagnoses  ## type:MultiCodeStringEventSeries

addresses.has_postcode  ## type:BoolEventSeries
addresses.address_id  ## type:IntEventSeries


# There are some methods that always return the same type
clinical_events.snomedct_code.count_distinct_for_patient()  ## type:IntPatientSeries
clinical_events.numeric_value.mean_for_patient()  ## type:FloatPatientSeries
clinical_events.date.count_episodes_for_patient(weeks(1))  ## type:IntPatientSeries
patients.exists_for_patient()  ## type:BoolPatientSeries
patients.count_for_patient()  ## type:IntPatientSeries
days(100) == days(100)  ## type:bool
days(100) != days(100)  ## type:bool

# There are some things that return the same type as the calling
# object or one of the arguments

bool_and = (
    patients.exists_for_patient() & patients.exists_for_patient()
)  ## type:BoolPatientSeries
bool_or = (
    patients.exists_for_patient() | patients.exists_for_patient()
)  ## type:BoolPatientSeries
bool_invert = ~patients.exists_for_patient()  ## type:BoolPatientSeries
numeric_neg = -clinical_events.numeric_value  ## type:FloatEventSeries
clinical_events.date.to_first_of_year()  ## type:DateEventSeries
patients.date_of_birth.to_first_of_month()  ## type:DatePatientSeries
duration_negation = -days(100)  ## type:days
patients.sex.when_null_then(patients.sex)  ## type:StrPatientSeries
duration_add = days(100) + patients.date_of_birth  ## type:DatePatientSeries
duration_radd = clinical_events.date + days(100)  ## type:DateEventSeries
duration_add_duration = days(100) + days(100)  ## type:days
# duration_rsub = clinical_events.date - days(100)  ## type: DateEventSeries
# !!! the above doesn't work and thinks its a DateDifference. I assume
# !!! because the NotImplemented on the DateFunctions __sub__ method
# !!! is only known at runtime
# !!! commenting out until we fix it
duration_sub_duration = days(100) - days(100)  ## type: days


# There are loads of things that return a series where the typ
# (int, str, float etc.) is fixed, but it can be a PatientSeries
# or an EventSeries depending on whether the calling object is a
# PatientSeries or an EventSeries. This can be achieved with two
# overloaded methods and type hints

#
# BaseSeries
#
base_eq = patients.sex == patients.sex  ## type:BoolPatientSeries
base_ne = clinical_events.date != clinical_events.date  ## type:BoolEventSeries
patients.sex.is_null()  ## type:BoolPatientSeries
clinical_events.date.is_not_null()  ## type:BoolEventSeries
patients.sex.is_in([])  ## type:BoolPatientSeries
clinical_events.snomedct_code.is_not_in([])  ## type:BoolEventSeries

#
# ComparableFunctions
#
comparable_lt = (
    clinical_events.numeric_value < clinical_events.numeric_value
)  ## type:BoolEventSeries
comparable_le = (
    clinical_events.numeric_value <= clinical_events.numeric_value
)  ## type:BoolEventSeries
comparable_gt = (
    clinical_events.numeric_value > clinical_events.numeric_value
)  ## type:BoolEventSeries
comparable_ge = (
    clinical_events.numeric_value >= clinical_events.numeric_value
)  ## type:BoolEventSeries

#
# StrFunctions
#
patients.sex.contains("m")  ## type:BoolPatientSeries

#
# NumericFunctions
#
numeric_truediv = clinical_events.numeric_value / 10  ## type:FloatEventSeries
numeric_rtruediv = 10 / clinical_events.numeric_value  ## type:FloatEventSeries
numeric_floordiv = clinical_events.numeric_value // 10  ## type:IntEventSeries
numeric_rfloordiv = 10 // clinical_events.numeric_value  ## type:IntEventSeries
clinical_events.numeric_value.as_int()  ## type:IntEventSeries
clinical_events.numeric_value.as_float()  ## type:FloatEventSeries

#
# DateFunctions
#
date_str = "2024-01-01"
patients.date_of_birth.is_before(date_str)  ## type:BoolPatientSeries
patients.date_of_birth.is_on_or_before(date_str)  ## type:BoolPatientSeries
patients.date_of_birth.is_after(date_str)  ## type:BoolPatientSeries
patients.date_of_birth.is_on_or_after(date_str)  ## type:BoolPatientSeries
clinical_events.date.is_between_but_not_on(date_str, date_str)  ## type:BoolEventSeries
clinical_events.date.is_on_or_between(date_str, date_str)  ## type:BoolEventSeries
clinical_events.date.is_during((date_str, date_str))  ## type:BoolEventSeries


#
# MultiCodeStringFunctions
#
apcs.all_diagnoses.contains("N13")  ## type:BoolEventSeries
apcs.all_diagnoses.contains_any_of(["N13"])  ## type:BoolEventSeries

#
# Couple of random list[tuple] types
starting_on = weeks(3).starting_on("2000-01-01")[0][0]  ## type:date
ending_on = weeks(3).ending_on("2000-01-01")[0][0]  ## type:date

#
# Things that aggregate from EventSeries to PatientSeries
# but that need to maintain the type (int, float, bool etc)
clinical_events.numeric_value.sum_for_patient()  ## type:FloatPatientSeries
clinical_events.numeric_value.as_int().sum_for_patient()  ## type:IntPatientSeries

clinical_events.numeric_value.minimum_for_patient()  ## type:FloatPatientSeries
clinical_events.numeric_value.as_int().minimum_for_patient()  ## type:IntPatientSeries
addresses.msoa_code.minimum_for_patient()  ## type:StrPatientSeries
clinical_events.date.minimum_for_patient()  ## type:DatePatientSeries

clinical_events.numeric_value.maximum_for_patient()  ## type:FloatPatientSeries
clinical_events.numeric_value.as_int().maximum_for_patient()  ## type:IntPatientSeries
addresses.msoa_code.maximum_for_patient()  ## type:StrPatientSeries
clinical_events.date.maximum_for_patient()  ## type:DatePatientSeries

#
# NumericFunctions which maintain the series (Event or Patient)
# and the type (int or float)

numeric_add = clinical_events.numeric_value + 10  ## type:FloatEventSeries
numeric_radd = 10 + clinical_events.numeric_value.as_int()  ## type:IntEventSeries
numeric_add_patient = (
    clinical_events.numeric_value.maximum_for_patient() + 10
)  ## type:FloatPatientSeries
numeric_radd_patient = (
    10 + clinical_events.numeric_value.as_int().maximum_for_patient()
)  ## type:IntPatientSeries
numeric_add_series = (
    clinical_events.numeric_value + clinical_events.numeric_value
)  ## type:FloatEventSeries

numeric_sub = clinical_events.numeric_value - 10  ## type:FloatEventSeries
numeric_rsub = 10 - clinical_events.numeric_value.as_int()  ## type:IntEventSeries
numeric_sub_patient = (
    clinical_events.numeric_value.maximum_for_patient() - 10
)  ## type:FloatPatientSeries
numeric_rsub_patient = (
    10 - clinical_events.numeric_value.as_int().maximum_for_patient()
)  ## type:IntPatientSeries
numeric_sub_series = (
    clinical_events.numeric_value - clinical_events.numeric_value
)  ## type:FloatEventSeries

numeric_mul = clinical_events.numeric_value * 10  ## type:FloatEventSeries
numeric_rmul = 10 * clinical_events.numeric_value.as_int()  ## type:IntEventSeries
numeric_mul_patient = (
    clinical_events.numeric_value.maximum_for_patient() * 10
)  ## type:FloatPatientSeries
numeric_rmul_patient = (
    10 * clinical_events.numeric_value.as_int().maximum_for_patient()
)  ## type:IntPatientSeries
numeric_mul_series = (
    clinical_events.numeric_value * clinical_events.numeric_value
)  ## type:FloatEventSeries

#
# Horizontal aggregations
# The type checker casts eveything to the first series. But the only
# type we can easily get is the first arg. So if the first thing is
# a series then that's fine. Otherwise we ignore
#
max_of_float = maximum_of(clinical_events.numeric_value, 10)  ## type:FloatEventSeries
max_of_int = maximum_of(
    clinical_events.numeric_value.as_int(), 10
)  ## type:IntEventSeries
max_of_date = maximum_of(clinical_events.date, "2024-01-01")  ## type:DateEventSeries
max_of_float_patient = maximum_of(
    clinical_events.numeric_value.maximum_for_patient(), 10
)  ## type:FloatPatientSeries
max_of_int_patient = maximum_of(
    clinical_events.numeric_value.maximum_for_patient().as_int(), 10
)  ## type:IntPatientSeries
max_of_date_patient = maximum_of(
    patients.date_of_birth, "2024-01-01"
)  ## type:DatePatientSeries
min_of_float = minimum_of(clinical_events.numeric_value, 10)  ## type:FloatEventSeries
min_of_int = minimum_of(
    clinical_events.numeric_value.as_int(), 10
)  ## type:IntEventSeries
min_of_date = minimum_of(clinical_events.date, "2024-01-01")  ## type:DateEventSeries
min_of_float_patient = minimum_of(
    clinical_events.numeric_value.minimum_for_patient(), 10
)  ## type:FloatPatientSeries
min_of_int_patient = minimum_of(
    clinical_events.numeric_value.minimum_for_patient().as_int(), 10
)  ## type:IntPatientSeries
min_of_date_patient = minimum_of(
    patients.date_of_birth, "2024-01-01"
)  ## type:DatePatientSeries

# properties
patients.date_of_birth.day  ## type:IntPatientSeries
patients.date_of_birth.month  ## type:IntPatientSeries
patients.date_of_birth.year  ## type:IntPatientSeries
clinical_events.date.day  ## type:IntEventSeries
clinical_events.date.month  ## type:IntEventSeries
clinical_events.date.year  ## type:IntEventSeries
