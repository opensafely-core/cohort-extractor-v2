from ehrql import case, when, months, INTERVAL, Measures, minimum_of, maximum_of
from ehrql.tables.tpp import (
    patients, 
    addresses,
    practice_registrations,
    clinical_events)

import codelists

from dataset_definition import make_dataset_lowerGI

from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("--start-date", type=str)
parser.add_argument("--intervals", type=int)

args = parser.parse_args()

start_date = args.start_date
intervals = args.intervals

##########

index_date = INTERVAL.start_date

dataset = make_dataset_lowerGI(index_date=index_date, end_date=INTERVAL.end_date)

dataset.elig_cohort = dataset.entry_date.is_on_or_before(INTERVAL.end_date) & dataset.exit_date.is_after(index_date) & patients.date_of_birth.is_not_null()

##########

## Define demographic variables

age = patients.age_on(dataset.entry_date)
age_group = case(
        when(age < 30).then("16-29"),
        when(age < 40).then("30-39"),
        when(age < 50).then("40-49"),
        when(age < 60).then("50-59"),
        when(age < 70).then("60-69"),
        when(age < 80).then("70-79"),
        when(age < 90).then("80-89"),
        when(age >= 90).then("90+"),
        otherwise="missing",
)

sex = patients.sex

imd = addresses.for_patient_on(dataset.entry_date).imd_rounded
imd5 = case(
        when((imd >=0) & (imd < int(32844 * 1 / 5))).then("1 (most deprived)"),
        when(imd < int(32844 * 2 / 5)).then("2"),
        when(imd < int(32844 * 3 / 5)).then("3"),
        when(imd < int(32844 * 4 / 5)).then("4"),
        when(imd < int(32844 * 5 / 5)).then("5 (least deprived)"),
        otherwise="unknown"
)

#########################

measures = Measures()
measures.configure_disclosure_control(enabled=False)

measures.define_defaults(intervals=months(intervals).starting_on(start_date))

#measures.define_measure(
    #name="fit_test_rate", 
    #numerator=dataset.fit_test_any,
    #denominator=dataset.elig_cohort,
    #group_by={"imd": imd5}
    #)

measures.define_measure(
    name="ida_symp_rate", 
    numerator=dataset.ida_symp,
    denominator=dataset.elig_cohort,
    group_by={"imd": imd5}
    )

measures.define_measure(
    name="cibh_symp_rate", 
    numerator=dataset.cibh_symp,
    denominator=dataset.elig_cohort,
    group_by={"imd": imd5}
    )

measures.define_measure(
    name="abdomass_symp_rate", 
    numerator=dataset.abdomass_symp,
    denominator=dataset.elig_cohort,
    group_by={"imd": imd5}
    )

measures.define_measure(
    name="prbleed_symp_50_rate", 
    numerator=dataset.prbleed_symp_50,
    denominator=dataset.elig_cohort,
    group_by={"imd": imd5}
    )

measures.define_measure(
    name="wl_symp_50_rate", 
    numerator=dataset.wl_symp_50,
    denominator=dataset.elig_cohort,
    group_by={"imd": imd5}
    )

measures.define_measure(
    name="abdopain_symp_50_rate", 
    numerator=dataset.abdopain_symp_50,
    denominator=dataset.elig_cohort,
    group_by={"imd": imd5}
    )

measures.define_measure(
    name="anaemia_symp_60_rate", 
    numerator=dataset.anaemia_symp_60,
    denominator=dataset.elig_cohort,
    group_by={"imd": imd5}
    )

#measures.define_measure(
    #name="fit_6_rate", 
    #numerator=dataset.fit_6_all_lowerGI,
    #denominator=dataset.elig_cohort,
    #group_by={"imd": imd5}
    #)

#measures.define_measure(
    #name="ca_6_rate", 
    #numerator=dataset.ca_6_all_lowerGI,
    #denominator=dataset.lowerGI_any_symp,
    #group_by={"imd": imd5}
    #)