from ehrql import days, maximum_of, minimum_of, weeks
from ehrql.tables import core, emis, tpp


# A file to keep track of things where we get good autocomplete behaviour.
#
# Anything in this file is automatically checked by the test file test_autocomplete.py,
# though it must be formatted correctly or the tests will fail. Currently you can:
#
# - write a single command and confirm the type e.g.:
#     core.patients.date_of_birth  ## type:DatePatientSeries
#
# - assign a single command to a variable and confirm the type e.g.:
#     bool_invert = ~core.patients.exists_for_patient()  ## type:BoolPatientSeries
#
# - either of the above but spanning multiple lines e.g.
#     bool_and = (
#       core.patients.exists_for_patient() & core.patients.exists_for_patient()
#     )  ## type:BoolPatientSeries

# Currently all columns on all tables have type of "Series | Any",
# so we don't get autocomplete. Providing type hints on the Series
# class, and on the @table decorator means the column types are
# correct e.g. IntPatientSeries, DateEventSeries etc. and therefore
# we get autocomplete for all the properties and methods on each series.
core.patients.date_of_birth  ## type:DatePatientSeries
core.patients.sex  ## type:StrPatientSeries
core.ons_deaths.underlying_cause_of_death  ## type:CodePatientSeries

core.clinical_events.date  ## type:DateEventSeries
core.clinical_events.numeric_value  ## type:FloatEventSeries
core.clinical_events.snomedct_code  ## type:CodeEventSeries
tpp.apcs.all_diagnoses  ## type:MultiCodeStringEventSeries

tpp.addresses.has_postcode  ## type:BoolEventSeries
tpp.addresses.address_id  ## type:IntEventSeries


# There are some methods that always return the same type
core.clinical_events.snomedct_code.count_distinct_for_patient()  ## type:IntPatientSeries
core.clinical_events.numeric_value.mean_for_patient()  ## type:FloatPatientSeries
core.clinical_events.date.count_episodes_for_patient(weeks(1))  ## type:IntPatientSeries
core.patients.exists_for_patient()  ## type:BoolPatientSeries
core.patients.count_for_patient()  ## type:IntPatientSeries
bool_eq = days(100) == days(100)  ## type:bool
bool_neq = days(100) != days(100)  ## type:bool

# There are some things that return the same type as the calling
# object or one of the arguments

bool_and = (
    core.patients.exists_for_patient() & core.patients.exists_for_patient()
)  ## type:BoolPatientSeries
bool_or = (
    core.patients.exists_for_patient() | core.patients.exists_for_patient()
)  ## type:BoolPatientSeries
bool_invert = ~core.patients.exists_for_patient()  ## type:BoolPatientSeries
numeric_neg = -core.clinical_events.numeric_value  ## type:FloatEventSeries
core.clinical_events.date.to_first_of_year()  ## type:DateEventSeries
core.patients.date_of_birth.to_first_of_month()  ## type:DatePatientSeries
duration_negation = -days(100)  ## type:days
core.patients.sex.when_null_then(core.patients.sex)  ## type:StrPatientSeries
duration_add = days(100) + core.patients.date_of_birth  ## type:DatePatientSeries
duration_radd = core.clinical_events.date + days(100)  ## type:DateEventSeries
duration_add_duration = days(100) + days(100)  ## type:days
# duration_rsub = core.clinical_events.date - days(100)  ## type: DateEventSeries
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
base_eq = core.patients.sex == core.patients.sex  ## type:BoolPatientSeries
base_ne = (
    core.clinical_events.date != core.clinical_events.date
)  ## type:BoolEventSeries
core.patients.sex.is_null()  ## type:BoolPatientSeries
core.clinical_events.date.is_not_null()  ## type:BoolEventSeries
core.patients.sex.is_in([])  ## type:BoolPatientSeries
core.clinical_events.snomedct_code.is_not_in([])  ## type:BoolEventSeries

#
# ComparableFunctions
#
comparable_lt = (
    core.clinical_events.numeric_value < core.clinical_events.numeric_value
)  ## type:BoolEventSeries
comparable_le = (
    core.clinical_events.numeric_value <= core.clinical_events.numeric_value
)  ## type:BoolEventSeries
comparable_gt = (
    core.clinical_events.numeric_value > core.clinical_events.numeric_value
)  ## type:BoolEventSeries
comparable_ge = (
    core.clinical_events.numeric_value >= core.clinical_events.numeric_value
)  ## type:BoolEventSeries

#
# StrFunctions
#
core.patients.sex.contains("m")  ## type:BoolPatientSeries

#
# NumericFunctions
#
numeric_truediv = core.clinical_events.numeric_value / 10  ## type:FloatEventSeries
numeric_rtruediv = 10 / core.clinical_events.numeric_value  ## type:FloatEventSeries
numeric_floordiv = core.clinical_events.numeric_value // 10  ## type:IntEventSeries
numeric_rfloordiv = 10 // core.clinical_events.numeric_value  ## type:IntEventSeries
core.clinical_events.numeric_value.as_int()  ## type:IntEventSeries
core.clinical_events.numeric_value.as_float()  ## type:FloatEventSeries

#
# DateFunctions
#
date_str = "2024-01-01"
core.patients.date_of_birth.is_before(date_str)  ## type:BoolPatientSeries
core.patients.date_of_birth.is_on_or_before(date_str)  ## type:BoolPatientSeries
core.patients.date_of_birth.is_after(date_str)  ## type:BoolPatientSeries
core.patients.date_of_birth.is_on_or_after(date_str)  ## type:BoolPatientSeries
core.clinical_events.date.is_between_but_not_on(
    date_str, date_str
)  ## type:BoolEventSeries
core.clinical_events.date.is_on_or_between(date_str, date_str)  ## type:BoolEventSeries
core.clinical_events.date.is_during((date_str, date_str))  ## type:BoolEventSeries


#
# MultiCodeStringFunctions
#
tpp.apcs.all_diagnoses.contains("N13")  ## type:BoolEventSeries
tpp.apcs.all_diagnoses.contains_any_of(["N13"])  ## type:BoolEventSeries

#
# Couple of random list[tuple] types
starting_on = weeks(3).starting_on("2000-01-01")[0][0]  ## type:date
ending_on = weeks(3).ending_on("2000-01-01")[0][0]  ## type:date

#
# Things that aggregate from EventSeries to PatientSeries
# but that need to maintain the type (int, float, bool etc)
core.clinical_events.numeric_value.sum_for_patient()  ## type:FloatPatientSeries
core.clinical_events.numeric_value.as_int().sum_for_patient()  ## type:IntPatientSeries

core.clinical_events.numeric_value.minimum_for_patient()  ## type:FloatPatientSeries
core.clinical_events.numeric_value.as_int().minimum_for_patient()  ## type:IntPatientSeries
tpp.addresses.msoa_code.minimum_for_patient()  ## type:StrPatientSeries
core.clinical_events.date.minimum_for_patient()  ## type:DatePatientSeries

core.clinical_events.numeric_value.maximum_for_patient()  ## type:FloatPatientSeries
core.clinical_events.numeric_value.as_int().maximum_for_patient()  ## type:IntPatientSeries
tpp.addresses.msoa_code.maximum_for_patient()  ## type:StrPatientSeries
core.clinical_events.date.maximum_for_patient()  ## type:DatePatientSeries

#
# NumericFunctions which maintain the series (Event or Patient)
# and the type (int or float)

numeric_add = core.clinical_events.numeric_value + 10  ## type:FloatEventSeries
numeric_radd = 10 + core.clinical_events.numeric_value.as_int()  ## type:IntEventSeries
numeric_add_patient = (
    core.clinical_events.numeric_value.maximum_for_patient() + 10
)  ## type:FloatPatientSeries
numeric_radd_patient = (
    10 + core.clinical_events.numeric_value.as_int().maximum_for_patient()
)  ## type:IntPatientSeries
numeric_add_series = (
    core.clinical_events.numeric_value + core.clinical_events.numeric_value
)  ## type:FloatEventSeries

numeric_sub = core.clinical_events.numeric_value - 10  ## type:FloatEventSeries
numeric_rsub = 10 - core.clinical_events.numeric_value.as_int()  ## type:IntEventSeries
numeric_sub_patient = (
    core.clinical_events.numeric_value.maximum_for_patient() - 10
)  ## type:FloatPatientSeries
numeric_rsub_patient = (
    10 - core.clinical_events.numeric_value.as_int().maximum_for_patient()
)  ## type:IntPatientSeries
numeric_sub_series = (
    core.clinical_events.numeric_value - core.clinical_events.numeric_value
)  ## type:FloatEventSeries

numeric_mul = core.clinical_events.numeric_value * 10  ## type:FloatEventSeries
numeric_rmul = 10 * core.clinical_events.numeric_value.as_int()  ## type:IntEventSeries
numeric_mul_patient = (
    core.clinical_events.numeric_value.maximum_for_patient() * 10
)  ## type:FloatPatientSeries
numeric_rmul_patient = (
    10 * core.clinical_events.numeric_value.as_int().maximum_for_patient()
)  ## type:IntPatientSeries
numeric_mul_series = (
    core.clinical_events.numeric_value * core.clinical_events.numeric_value
)  ## type:FloatEventSeries

#
# Horizontal aggregations
# The type checker casts eveything to the first series. But the only
# type we can easily get is the first arg. So if the first thing is
# a series then that's fine. Otherwise we ignore
#
max_of_float = maximum_of(
    core.clinical_events.numeric_value, 10
)  ## type:FloatEventSeries
max_of_int = maximum_of(
    core.clinical_events.numeric_value.as_int(), 10
)  ## type:IntEventSeries
max_of_date = maximum_of(
    core.clinical_events.date, "2024-01-01"
)  ## type:DateEventSeries
max_of_float_patient = maximum_of(
    core.clinical_events.numeric_value.maximum_for_patient(), 10
)  ## type:FloatPatientSeries
max_of_int_patient = maximum_of(
    core.clinical_events.numeric_value.maximum_for_patient().as_int(), 10
)  ## type:IntPatientSeries
max_of_date_patient = maximum_of(
    core.patients.date_of_birth, "2024-01-01"
)  ## type:DatePatientSeries
min_of_float = minimum_of(
    core.clinical_events.numeric_value, 10
)  ## type:FloatEventSeries
min_of_int = minimum_of(
    core.clinical_events.numeric_value.as_int(), 10
)  ## type:IntEventSeries
min_of_date = minimum_of(
    core.clinical_events.date, "2024-01-01"
)  ## type:DateEventSeries
min_of_float_patient = minimum_of(
    core.clinical_events.numeric_value.minimum_for_patient(), 10
)  ## type:FloatPatientSeries
min_of_int_patient = minimum_of(
    core.clinical_events.numeric_value.minimum_for_patient().as_int(), 10
)  ## type:IntPatientSeries
min_of_date_patient = minimum_of(
    core.patients.date_of_birth, "2024-01-01"
)  ## type:DatePatientSeries

# properties
core.patients.date_of_birth.day  ## type:IntPatientSeries
core.patients.date_of_birth.month  ## type:IntPatientSeries
core.patients.date_of_birth.year  ## type:IntPatientSeries
core.clinical_events.date.day  ## type:IntEventSeries
core.clinical_events.date.month  ## type:IntEventSeries
core.clinical_events.date.year  ## type:IntEventSeries

# Table methods not yet tested
tpp.patients.is_alive_on(date_str)  ## type:BoolPatientSeries
tpp.patients.is_dead_on(date_str)  ## type:BoolPatientSeries
tpp.decision_support_values.electronic_frailty_index()  ## type:decision_support_values
tpp.practice_registrations.spanning_with_systmone(
    date_str, date_str
)  ## type:practice_registrations
emis.patients.has_practice_registration_spanning(
    date_str, date_str
)  ## type:BoolPatientSeries
core.patients.is_alive_on(date_str)  ## type:BoolPatientSeries
core.patients.is_dead_on(date_str)  ## type:BoolPatientSeries
core.practice_registrations.exists_for_patient_on(date_str)  ## type:BoolPatientSeries
core.practice_registrations.spanning(date_str, date_str)  ## type:practice_registrations

# query_language series methods not yet tested
core.clinical_events.date.is_after(date_str)  ## type: BoolEventSeries
core.clinical_events.date.is_before(date_str)  ## type: BoolEventSeries
core.clinical_events.date.is_on_or_after(date_str)  ## type: BoolEventSeries
core.clinical_events.date.is_on_or_before(date_str)  ## type: BoolEventSeries
core.clinical_events.date.to_first_of_month()  ## type: DateEventSeries
core.clinical_events.snomedct_code.is_in([])  ## type: BoolEventSeries
core.clinical_events.snomedct_code.is_null()  ## type: BoolEventSeries
core.clinical_events.snomedct_code.is_null().as_int()  ## type: IntEventSeries
core.clinical_events.snomedct_code.when_null_then(3)  ## type: CodeEventSeries
core.patients.date_of_birth.day.as_float()  ## type: FloatPatientSeries
core.patients.date_of_birth.day.as_int()  ## type: IntPatientSeries
core.patients.date_of_birth.is_between_but_not_on(
    date_str, date_str
)  ## type: BoolPatientSeries
core.patients.date_of_birth.is_during((date_str, date_str))  ## type: BoolPatientSeries
core.patients.date_of_birth.is_on_or_between(
    date_str, date_str
)  ## type: BoolPatientSeries
core.patients.date_of_birth.to_first_of_year()  ## type: DatePatientSeries
core.patients.sex.is_not_in(["male"])  ## type: BoolPatientSeries
core.patients.sex.is_not_null()  ## type: BoolPatientSeries
core.patients.sex.is_null().as_int()  ## type: IntPatientSeries
tpp.apcs.all_diagnoses.is_in([])  ## type:NoReturn
tpp.apcs.all_diagnoses.is_not_in([])  ## type:NoReturn
tpp.addresses.msoa_code.contains([])  ## type: BoolEventSeries

# query_language non-series methods
core.clinical_events.where(
    core.clinical_events.snomedct_code.is_in([])
)  ## type:clinical_events
core.clinical_events.except_where(
    core.clinical_events.snomedct_code.is_in([])
)  ## type:clinical_events

# Duration methods
days(100).starting_on("2045-01-01")  ## type: list[tuple[date, date]]
days(100).ending_on("2045-01-01")  ## type: list[tuple[date, date]]

# first/last_for_patient
first_code = (
    core.clinical_events.sort_by(core.clinical_events.date)
    .first_for_patient()
    .snomedct_code
)  ## type:CodePatientSeries
first_val = (
    core.clinical_events.sort_by(core.clinical_events.date)
    .last_for_patient()
    .numeric_value
)  ## type:FloatPatientSeries
first_date = (
    core.clinical_events.sort_by(core.clinical_events.date).last_for_patient().date
)  ## type:DatePatientSeries

fist_addr_str = (
    tpp.addresses.sort_by(tpp.addresses.start_date).first_for_patient().msoa_code
)  ## type:StrPatientSeries
fist_addr_int = (
    tpp.addresses.sort_by(tpp.addresses.start_date).first_for_patient().address_type
)  ## type:IntPatientSeries

core.clinical_events.sort_by(
    core.clinical_events.date
)  ## type: SortedEventFrameMethods[ClinicalEvents]
core.clinical_events.sort_by(
    core.clinical_events.date
).first_for_patient()  ## type: ClinicalEvents
core.clinical_events.sort_by(
    core.clinical_events.date
).last_for_patient()  ## type: ClinicalEvents

tpp.addresses.for_patient_on(date_str)  ## type: Addresses

tpp.apcs.sort_by(tpp.apcs.admission_date).first_for_patient().all_diagnoses.contains(
    "N17"
)  ## type: BoolPatientSeries
tpp.apcs.sort_by(
    tpp.apcs.admission_date
).first_for_patient().all_diagnoses.contains_any_of(["N17"])  ## type: BoolPatientSeries
tpp.apcs.sort_by(tpp.apcs.admission_date).first_for_patient().all_diagnoses.is_in(
    ["N17"]
)  ## type: NoReturn
tpp.apcs.sort_by(tpp.apcs.admission_date).first_for_patient().all_diagnoses.is_not_in(
    ["N17"]
)  ## type: NoReturn
