from ehrql import Dataset, years, days, months, minimum_of, maximum_of, case, when
from ehrql.tables.core import patients
from ehrql.tables.tpp import practice_registrations, ons_deaths, clinical_events, clinical_events_ranges

import codelists

def make_dataset_lowerGI(index_date, end_date):
    
    dataset = Dataset()

    reg_date = practice_registrations.where(practice_registrations.start_date.is_on_or_between(index_date, end_date)
                                                    ).sort_by(
                                                        practice_registrations.start_date
                                                    ).first_for_patient().start_date
    
    age_16_date = patients.date_of_birth + years(16)

    dataset.entry_date = maximum_of(reg_date, age_16_date, "2018-03-23")

    death_date = ons_deaths.date

    age_110_date = patients.date_of_birth + years(110)

    dereg_date = practice_registrations.sort_by(practice_registrations.end_date
                                              ).first_for_patient().end_date

    colorectal_ca_diag_date = clinical_events.where(clinical_events.snomedct_code.is_in(codelists.colorectal_diagnosis_codes_snomed)
                                                        ).sort_by(
                                                            clinical_events.date
                                                        ).first_for_patient().date
    
    dataset.exit_date = minimum_of(death_date, age_110_date, dereg_date, colorectal_ca_diag_date, "2023-10-22")

    dataset.death_date = death_date

    def first_event(codelist, l_age, u_age):
        return clinical_events.where(clinical_events.snomedct_code.is_in(codelist)
            ).where(
                clinical_events.date.is_on_or_between(index_date, end_date)
            ).where(
                clinical_events.date.is_on_or_between(dataset.entry_date, dataset.exit_date)
            ).where(
                patients.age_on(clinical_events.date)>=l_age
            ).where(
                patients.age_on(clinical_events.date)<u_age
            ).sort_by(
                clinical_events.date
            ).first_for_patient()
    
    ida_date = first_event(codelists.ida_codes, 16, 111).date
    cibh_date = first_event(codelists.cibh_codes, 16, 111).date
    prbleed_date = first_event(codelists.prbleeding_codes, 16, 111).date
    wl_date = first_event(codelists.wl_codes, 16, 111).date
    abdomass_date = first_event(codelists.abdomass_codes, 16, 111).date
    abdopain_date = first_event(codelists.abdopain_codes, 16, 111).date
    anaemia_date = first_event(codelists.anaemia_codes, 16, 111).date
    prbleed_50_date = first_event(codelists.prbleeding_codes, 50, 111).date
    wl_50_date = first_event(codelists.wl_codes, 50, 111).date
    abdopain_50_date = first_event(codelists.abdopain_codes, 50, 111).date
    anaemia_60_date = first_event(codelists.anaemia_codes, 60, 111).date
    wl_40_date = first_event(codelists.wl_codes, 40, 111).date
    abdopain_40_date = first_event(codelists.abdopain_codes, 40, 111).date
    prbleed_u50_date = first_event(codelists.prbleeding_codes, 16, 50).date
    abdopain_u50_date = first_event(codelists.abdopain_codes, 16, 50).date
    wl_u50_date = first_event(codelists.wl_codes, 16, 50).date

    def prev_event(codelist, symp_date, l_age, u_age):
        return clinical_events.where(clinical_events.snomedct_code.is_in(codelist)
            ).where(
                clinical_events.date.is_on_or_between(symp_date - days(42), symp_date - days(1))
            ).where(
                patients.age_on(clinical_events.date)>=l_age
            ).where(
                patients.age_on(clinical_events.date)<u_age
            ).exists_for_patient()

    def has_event(codelist, l_age, u_age):
        return first_event(codelist, l_age, u_age).exists_for_patient()

    dataset.ida_symp = has_event(codelists.ida_codes, 16, 111) & ~prev_event(codelists.ida_codes, ida_date, 16, 111)
    dataset.cibh_symp = has_event(codelists.cibh_codes, 16, 111) & ~prev_event(codelists.cibh_codes, cibh_date, 16, 111)
    dataset.abdomass_symp = has_event(codelists.abdomass_codes, 16, 111) & ~prev_event(codelists.abdomass_codes, abdomass_date, 16, 111)
    dataset.prbleed_symp = has_event(codelists.prbleeding_codes, 16, 111) & ~prev_event(codelists.prbleeding_codes, prbleed_date, 16, 111)
    dataset.wl_symp = has_event(codelists.wl_codes, 16, 111) & ~prev_event(codelists.wl_codes, wl_date, 16, 111)
    dataset.abdopain_symp = has_event(codelists.abdopain_codes, 16, 111) & ~prev_event(codelists.abdopain_codes, abdopain_date, 16, 111)
    dataset.anaemia_symp = has_event(codelists.anaemia_codes, 16, 111) & ~prev_event(codelists.anaemia_codes, anaemia_date, 16, 111)

    dataset.prbleed_symp_50 = has_event(codelists.prbleeding_codes, 50, 111) & ~prev_event(codelists.prbleeding_codes, prbleed_50_date, 50, 111)
    dataset.wl_symp_50 = has_event(codelists.wl_codes, 50, 111) & ~prev_event(codelists.wl_codes, wl_50_date, 50, 111)
    dataset.abdopain_symp_50 = has_event(codelists.abdopain_codes, 50, 111) & ~prev_event(codelists.abdopain_codes, abdopain_50_date, 50, 111)
    dataset.anaemia_symp_60 = has_event(codelists.anaemia_codes, 60, 111) & ~prev_event(codelists.anaemia_codes, anaemia_60_date, 60, 111)
    dataset.wl_abdopain_symp_40 = has_event(codelists.wl_codes, 40, 111) & has_event(codelists.abdopain_codes, 40, 111) & ~prev_event(codelists.wl_codes, wl_40_date, 40, 111) & ~prev_event(codelists.abdopain_codes, abdopain_40_date, 40, 111)
    dataset.prbleed_abdopain_symp = has_event(codelists.prbleeding_codes, 16, 50) & has_event(codelists.abdopain_codes, 16, 50) & ~prev_event(codelists.prbleeding_codes, prbleed_u50_date, 16, 50) & ~prev_event(codelists.abdopain_codes, abdopain_u50_date, 16, 50)
    dataset.prbleed_wl_symp = has_event(codelists.prbleeding_codes, 16, 50) & has_event(codelists.wl_codes, 16, 50) & ~prev_event(codelists.prbleeding_codes, prbleed_u50_date, 16, 50) & ~prev_event(codelists.wl_codes, wl_u50_date, 16, 50)
    
    dataset.lowerGI_any_symp = (dataset.ida_symp | dataset.cibh_symp | dataset.abdomass_symp | dataset.prbleed_symp | dataset.wl_symp | dataset.abdopain_symp | dataset.anaemia_symp)
    dataset.lowerGI_2ww_symp = (dataset.ida_symp | dataset.cibh_symp | dataset.abdomass_symp | dataset.prbleed_symp_50 | dataset.wl_symp_50 | dataset.abdopain_symp_50 | dataset.anaemia_symp_60 | dataset.wl_abdopain_symp_40 | dataset.prbleed_abdopain_symp | dataset.prbleed_wl_symp)

    def symptom_date(symp_date, symp_event):
        return case(when(symp_event).then(symp_date))
    
    dataset.ida_date = symptom_date(ida_date, dataset.ida_symp)
    dataset.cibh_date = symptom_date(cibh_date, dataset.cibh_symp)
    dataset.prbleed_date = symptom_date(prbleed_date, dataset.prbleed_symp)
    dataset.wl_date = symptom_date(wl_date, dataset.wl_symp)
    dataset.abdomass_date = symptom_date(abdomass_date, dataset.abdomass_symp)
    dataset.abdopain_date = symptom_date(abdopain_date, dataset.abdopain_symp)
    dataset.anaemia_date = symptom_date(anaemia_date, dataset.anaemia_symp)

    dataset.prbleed_50_date = symptom_date(prbleed_50_date, dataset.prbleed_symp_50)
    dataset.wl_50_date = symptom_date(wl_50_date, dataset.wl_symp_50)
    dataset.abdopain_50_date = symptom_date(abdopain_50_date, dataset.abdopain_symp_50)
    dataset.anaemia_60_date = symptom_date(anaemia_60_date, dataset.anaemia_symp_60)
    dataset.wl_abdopain_40_date = case(when(dataset.wl_abdopain_symp_40).then(minimum_of(wl_40_date, abdopain_40_date)))
    dataset.prbleed_abdopain_date = case(when(dataset.prbleed_abdopain_symp).then(minimum_of(prbleed_u50_date, abdopain_u50_date)))
    dataset.prbleed_wl_date = case(when(dataset.prbleed_wl_symp).then(minimum_of(prbleed_u50_date, wl_u50_date)))

    dataset.lowerGI_any_symp_date = minimum_of(dataset.ida_date, dataset.cibh_date, dataset.prbleed_date, dataset.wl_date, dataset.abdomass_date, dataset.abdopain_date, dataset.anaemia_date)
    dataset.lowerGI_2ww_symp_date = minimum_of(dataset.ida_date, dataset.cibh_date, dataset.abdomass_date, dataset.prbleed_50_date, dataset.wl_50_date, dataset.abdopain_50_date, dataset.anaemia_60_date, dataset.wl_abdopain_40_date, dataset.prbleed_abdopain_date, dataset.prbleed_wl_date)

    def colorectal_ca_symp_1year(symp_date):
        return clinical_events.where(clinical_events.snomedct_code.is_in(codelists.colorectal_diagnosis_codes_snomed)
        ).where(
            clinical_events.date.is_on_or_between(symp_date, symp_date + months(12))
        ).sort_by(
            clinical_events.date
        ).first_for_patient().date

    dataset.ca_ida_date = colorectal_ca_symp_1year(dataset.ida_date)
    dataset.ca_cibh_date = colorectal_ca_symp_1year(dataset.cibh_date)
    dataset.ca_prbleed_date = colorectal_ca_symp_1year(dataset.prbleed_date)
    dataset.ca_wl_date = colorectal_ca_symp_1year(dataset.wl_date)
    dataset.ca_abdomass_date = colorectal_ca_symp_1year(dataset.abdomass_date)
    dataset.ca_abdopain_date = colorectal_ca_symp_1year(dataset.abdopain_date)
    dataset.ca_anaemia_date = colorectal_ca_symp_1year(dataset.anaemia_date)

    dataset.ca_prbleed_50_date = colorectal_ca_symp_1year(dataset.prbleed_50_date)
    dataset.ca_wl_50_date = colorectal_ca_symp_1year(dataset.wl_50_date)
    dataset.ca_abdopain_50_date = colorectal_ca_symp_1year(dataset.abdopain_50_date)
    dataset.ca_anaemia_60_date = colorectal_ca_symp_1year(dataset.anaemia_60_date)
    dataset.ca_wl_abdopain_40_date = colorectal_ca_symp_1year(dataset.wl_abdopain_40_date)
    dataset.ca_prbleed_abdopain_date = colorectal_ca_symp_1year(dataset.prbleed_abdopain_date)
    dataset.ca_prbleed_wl_date = colorectal_ca_symp_1year(dataset.prbleed_wl_date)
    
    dataset.ca_lowerGI_any_date = colorectal_ca_symp_1year(dataset.lowerGI_any_symp_date)
    dataset.ca_lowerGI_2ww_date = colorectal_ca_symp_1year(dataset.lowerGI_2ww_symp_date)

    def symp_to_ca_days(ca_date, symp_date):
        return (ca_date - symp_date).days
    
    dataset.ca_ida_days = symp_to_ca_days(dataset.ca_ida_date, dataset.ida_date)
    dataset.ca_cibh_days = symp_to_ca_days(dataset.ca_cibh_date, dataset.cibh_date)
    dataset.ca_prbleed_days = symp_to_ca_days(dataset.ca_prbleed_date, dataset.prbleed_date)
    dataset.ca_wl_days = symp_to_ca_days(dataset.ca_wl_date, dataset.wl_date)
    dataset.ca_abdomass_days = symp_to_ca_days(dataset.ca_abdomass_date, dataset.abdomass_date)
    dataset.ca_abdopain_days = symp_to_ca_days(dataset.ca_abdopain_date, dataset.abdopain_date)
    dataset.ca_anaemia_days = symp_to_ca_days(dataset.ca_anaemia_date, dataset.anaemia_date)
    
    dataset.ca_prbleed_50_days = symp_to_ca_days(dataset.ca_prbleed_50_date, dataset.prbleed_50_date)
    dataset.ca_wl_50_days = symp_to_ca_days(dataset.ca_wl_50_date, dataset.wl_50_date)
    dataset.ca_abdopain_50_days = symp_to_ca_days(dataset.ca_abdopain_50_date, dataset.abdopain_50_date)
    dataset.ca_anaemia_60_days = symp_to_ca_days(dataset.ca_anaemia_60_date, dataset.anaemia_60_date)
    dataset.ca_wl_abdopain_40_days = symp_to_ca_days(dataset.ca_wl_abdopain_40_date, dataset.wl_abdopain_40_date)
    dataset.ca_prbleed_abdopain_days = symp_to_ca_days(dataset.ca_prbleed_abdopain_date, dataset.prbleed_abdopain_date)
    dataset.ca_prbleed_wl_days = symp_to_ca_days(dataset.ca_prbleed_wl_date, dataset.prbleed_wl_date)

    dataset.ca_lowerGI_any_days = symp_to_ca_days(dataset.ca_lowerGI_any_date, dataset.lowerGI_any_symp_date)
    dataset.ca_lowerGI_2ww_days = symp_to_ca_days(dataset.ca_lowerGI_2ww_date, dataset.lowerGI_2ww_symp_date)

    def fit_symp_3months(symp_date):
        return clinical_events.where(clinical_events.snomedct_code.is_in(codelists.fit_codes)
        ).where(
            clinical_events.date.is_on_or_between(symp_date, symp_date + months(3))
        ).sort_by(
            clinical_events.date
        ).first_for_patient().date
        
    dataset.fit_ida_date = fit_symp_3months(dataset.ida_date)
    dataset.fit_cibh_date = fit_symp_3months(dataset.cibh_date)
    dataset.fit_prbleed_date = fit_symp_3months(dataset.prbleed_date)
    dataset.fit_wl_date = fit_symp_3months(dataset.wl_date)
    dataset.fit_abdomass_date = fit_symp_3months(dataset.abdomass_date)
    dataset.fit_abdopain_date = fit_symp_3months(dataset.abdopain_date)
    dataset.fit_anaemia_date = fit_symp_3months(dataset.anaemia_date)

    dataset.fit_prbleed_50_date = fit_symp_3months(dataset.prbleed_50_date)
    dataset.fit_wl_50_date = fit_symp_3months(dataset.wl_50_date)
    dataset.fit_abdopain_50_date = fit_symp_3months(dataset.abdopain_50_date)
    dataset.fit_anaemia_60_date = fit_symp_3months(dataset.anaemia_60_date)
    dataset.fit_wl_abdopain_40_date = fit_symp_3months(dataset.wl_abdopain_40_date)
    dataset.fit_prbleed_abdopain_date = fit_symp_3months(dataset.prbleed_abdopain_date)
    dataset.fit_prbleed_wl_date = fit_symp_3months(dataset.prbleed_wl_date)
    
    dataset.fit_lowerGI_any_date = fit_symp_3months(dataset.lowerGI_any_symp_date)
    dataset.fit_lowerGI_2ww_date = fit_symp_3months(dataset.lowerGI_2ww_symp_date)

    def fit_test_value(fit_date):
        return clinical_events_ranges.where(clinical_events_ranges.snomedct_code.is_in(codelists.fit_codes)
        ).where(
            clinical_events_ranges.date.is_on_or_after(fit_date)
        ).sort_by(
            clinical_events_ranges.date
        ).first_for_patient().numeric_value

    def fit_test_comparator(fit_date):
        return clinical_events_ranges.where(clinical_events_ranges.snomedct_code.is_in(codelists.fit_codes)
        ).where(
            clinical_events_ranges.date.is_on_or_after(fit_date)
        ).sort_by(
            clinical_events_ranges.date
        ).first_for_patient().comparator
    
    def fit_test_code(fit_date):
        return clinical_events.where(clinical_events.snomedct_code.is_in(codelists.fit_codes)
        ).where(
            clinical_events.date.is_on_or_after(fit_date)
        ).sort_by(
            clinical_events.date
        ).first_for_patient().snomedct_code

    def fit_test_positive(fit_date):
        return case(when((fit_test_value(fit_date)>=10) & (fit_test_comparator(fit_date)!="<")).then(True), 
                    when(fit_test_code(fit_date)=="389076003").then(True),
                    when(fit_test_code(fit_date)=="59614000").then(True),
                    otherwise=False)

    dataset.fit_ida_positive = fit_test_positive(dataset.fit_ida_date)
    dataset.fit_cibh_positive = fit_test_positive(dataset.fit_cibh_date)
    dataset.fit_prbleed_positive = fit_test_positive(dataset.fit_prbleed_date)
    dataset.fit_wl_positive = fit_test_positive(dataset.fit_wl_date)
    dataset.fit_abdomass_positive = fit_test_positive(dataset.fit_abdomass_date)
    dataset.fit_abdopain_positive = fit_test_positive(dataset.fit_abdopain_date)
    dataset.fit_anaemia_positive = fit_test_positive(dataset.fit_anaemia_date)

    dataset.fit_prbleed_50_positive = fit_test_positive(dataset.fit_prbleed_50_date)
    dataset.fit_wl_50_positive = fit_test_positive(dataset.fit_wl_50_date)
    dataset.fit_abdopain_50_positive = fit_test_positive(dataset.fit_abdopain_50_date)
    dataset.fit_anaemia_60_positive = fit_test_positive(dataset.fit_anaemia_60_date)
    dataset.fit_wl_abdopain_40_positive = fit_test_positive(dataset.fit_wl_abdopain_40_date)
    dataset.fit_prbleed_abdopain_positive = fit_test_positive(dataset.fit_prbleed_abdopain_date)
    dataset.fit_prbleed_wl_positive = fit_test_positive(dataset.fit_prbleed_wl_date)
    
    dataset.fit_lowerGI_any_positive = fit_test_positive(dataset.fit_lowerGI_any_date)
    dataset.fit_lowerGI_2ww_positive = fit_test_positive(dataset.fit_lowerGI_2ww_date)

    def symp_to_fit_days(fit_date, symp_date):
        return (fit_date - symp_date).days
    
    dataset.fit_ida_days = symp_to_fit_days(dataset.fit_ida_date, dataset.ida_date)
    dataset.fit_cibh_days = symp_to_fit_days(dataset.fit_cibh_date, dataset.cibh_date)
    dataset.fit_prbleed_days = symp_to_fit_days(dataset.fit_prbleed_date, dataset.prbleed_date)
    dataset.fit_wl_days = symp_to_fit_days(dataset.fit_wl_date, dataset.wl_date)
    dataset.fit_abdomass_days = symp_to_fit_days(dataset.fit_abdomass_date, dataset.abdomass_date)
    dataset.fit_abdopain_days = symp_to_fit_days(dataset.fit_abdopain_date, dataset.abdopain_date)
    dataset.fit_anaemia_days = symp_to_fit_days(dataset.fit_anaemia_date, dataset.anaemia_date)
    
    dataset.fit_prbleed_50_days = symp_to_fit_days(dataset.fit_prbleed_50_date, dataset.prbleed_50_date)
    dataset.fit_wl_50_days = symp_to_fit_days(dataset.fit_wl_50_date, dataset.wl_50_date)
    dataset.fit_abdopain_50_days = symp_to_fit_days(dataset.fit_abdopain_50_date, dataset.abdopain_50_date)
    dataset.fit_anaemia_60_days = symp_to_fit_days(dataset.fit_anaemia_60_date, dataset.anaemia_60_date)
    dataset.fit_wl_abdopain_40_days = symp_to_fit_days(dataset.fit_wl_abdopain_40_date, dataset.wl_abdopain_40_date)
    dataset.fit_prbleed_abdopain_days = symp_to_fit_days(dataset.fit_prbleed_abdopain_date, dataset.prbleed_abdopain_date)
    dataset.fit_prbleed_wl_days = symp_to_fit_days(dataset.fit_prbleed_wl_date, dataset.prbleed_wl_date)

    dataset.fit_lowerGI_any_days = symp_to_fit_days(dataset.fit_lowerGI_any_date, dataset.lowerGI_any_symp_date)
    dataset.fit_lowerGI_2ww_days = symp_to_fit_days(dataset.fit_lowerGI_2ww_date, dataset.lowerGI_2ww_symp_date)
    
    lowerGI_any_num_ca = clinical_events.where(clinical_events.snomedct_code.is_in(codelists.colorectal_symptom_codes)
        ).where(
            clinical_events.date.is_on_or_between(dataset.lowerGI_any_symp_date, dataset.ca_lowerGI_any_date)
        ).date.count_episodes_for_patient(days(42))
    
    dataset.lowerGI_any_num_ca = lowerGI_any_num_ca

    lowerGI_any_num_fit = clinical_events.where(clinical_events.snomedct_code.is_in(codelists.colorectal_symptom_codes)
        ).where(
            clinical_events.date.is_on_or_between(dataset.lowerGI_any_symp_date, dataset.fit_lowerGI_any_date)
        ).date.count_episodes_for_patient(days(42))
    
    dataset.lowerGI_any_num_fit = lowerGI_any_num_fit

    return dataset

