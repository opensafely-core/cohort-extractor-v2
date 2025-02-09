from ehrql import codelist_from_csv

colorectal_symptom_codes = codelist_from_csv(
    "codelists/phc-symptoms-colorectal-cancer.csv", column="code"
)

colorectal_diagnosis_codes_snomed = codelist_from_csv(
    "codelists/phc-phc-colorectal-cancer-snomed.csv", column="code"
)

colorectal_referral_codes = codelist_from_csv(
    "codelists/phc-2ww-referral-colorectal.csv", column="code"
)

ida_codes = codelist_from_csv(
    "codelists/phc-symptom-colorectal-ida.csv", column="code"
)

cibh_codes = codelist_from_csv(
    "codelists/phc-symptom-colorectal-cibh.csv", column="code"
)

prbleeding_codes = codelist_from_csv(
    "codelists/phc-symptom-colorectal-pr-bleeding.csv", column="code"
)

wl_codes = codelist_from_csv(
    "codelists/phc-symptom-colorectal-wl.csv", column="code"
)

abdomass_codes = codelist_from_csv(
    "codelists/phc-symptom-lowergi-abdo-mass.csv", column="code"
)

abdopain_codes = codelist_from_csv(
    "codelists/phc-symptom-lowergi-abdo-pain.csv", column="code"
)

anaemia_codes = codelist_from_csv(
    "codelists/phc-symptom-lowergi-anaemia.csv", column="code"
)

fit_codes = codelist_from_csv(
    "codelists/phc-fit-test.csv", column="code"
)

ethnicity_codes_16 = codelist_from_csv(
    "codelists/opensafely-ethnicity-snomed-0removed.csv",
    column="snomedcode",
    category_column="Grouping_16",
)

ethnicity_codes_6 = codelist_from_csv(
    "codelists/opensafely-ethnicity-snomed-0removed.csv",
    column="snomedcode",
    category_column="Grouping_6",
)

lowerGI_diagnostic_codes = codelist_from_csv(
    "local_codelists/phc-lowergi-endoscopy-hrg.csv", column="code"
)