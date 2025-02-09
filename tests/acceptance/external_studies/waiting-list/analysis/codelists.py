##################################################################
# Some covariates used in the study are created from codelists
# of clinical conditions or prescribed medications. 
# This script fetches the codelists identified in codelists.txt 
# from OpenCodelists
####################################################################


from ehrql import codelist_from_csv

 
### Opioid codelists

opioid_codes = codelist_from_csv(
    "codelists/user-anschaf-opioids-for-analgesia-dmd.csv",
    column = "code"
)

long_opioid_codes = codelist_from_csv(
    "codelists/user-anschaf-long-acting-opioids-dmd.csv",
    column = "code"
)

strong_opioid_codes1 = codelist_from_csv(
    "codelists/opensafely-strongopioidsCW-dmd.csv",
    column = "code"
)

strong_opioid_codes2 = codelist_from_csv(
    "codelists/user-anschaf-strong-opioids-exc-tramadol-and-tapentadol-dmd.csv",
    column = "code"
)

weak_opioid_codes = codelist_from_csv(
    "codelists/user-anschaf-weak-opioids-dmd.csv",
    column = "code"
)

moderate_opioid_codes = codelist_from_csv(
    "codelists/user-anschaf-tramadol-and-tapentadol-dmd.csv",
    column = "code"
)


short_opioid_codes = set(opioid_codes) - set(long_opioid_codes)


### Other medications

antidepressant_codes = codelist_from_csv(
    "codelists/user-anschaf-antidepressants-dmd.csv",
    column = "code"
)

gabapentinoid_codes = codelist_from_csv(
    "codelists/user-anschaf-gabapentinoids-dmd.csv",
    column = "code"
)

nsaid_codes = codelist_from_csv(
    "codelists/user-speed-vm-nsaids-dmd.csv",
    column = "code"
)

tca_codes = codelist_from_csv(
    "codelists/user-speed-vm-antidepressants-for-pain-indication-dmd.csv",
    column = "code"
)

### Ethnicity

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

### Comorbidities

oth_ca_codes = codelist_from_csv(
  "codelists/opensafely-cancer-excluding-lung-and-haematological-snomed.csv",
  column = "id"
)

lung_ca_codes = codelist_from_csv(
  "codelists/opensafely-lung-cancer-snomed.csv",
  column = "id"
)

haem_ca_codes = codelist_from_csv(
  "codelists/opensafely-haematological-cancer-snomed.csv",
  column = "id"
)

cancer_codes = (
  oth_ca_codes +
  lung_ca_codes +
  haem_ca_codes
)

osteoarthritis_codes = codelist_from_csv(
    "codelists/user-speed-vm-osteoarthritis-snomed-ct.csv",
    column = "code"
)

depression_codes = codelist_from_csv(
    "codelists/opensafely-symptoms-depression.csv",
    column = "code"
)

anxiety_codes = codelist_from_csv(
    "codelists/opensafely-symptoms-anxiety.csv",
    column = "code"
)

smi_codes = codelist_from_csv(
    "codelists/primis-covid19-vacc-uptake-old-sev_mental_cod.csv",
    column = "code"
)

cardiac_codes = codelist_from_csv(
  "codelists/primis-covid19-vacc-uptake-chd_cov.csv",
  column = "code"
)

ckd_codes = codelist_from_csv(
  "codelists/primis-covid19-vacc-uptake-ckd15.csv",
  column = "code"
)

liver_codes = codelist_from_csv(
  "codelists/primis-covid19-vacc-uptake-cld.csv",
  column = "code"
)

diabetes_codes = codelist_from_csv(
  "codelists/primis-covid19-vacc-uptake-diab.csv",
  column = "code"
)

copd_codes = codelist_from_csv(
  "codelists/primis-covid19-vacc-uptake-resp_cov.csv",
  column = "code"
)

ra_codes = codelist_from_csv(
  "codelists/user-markdrussell-new-rheumatoid-arthritis.csv",
  column = "code"
)

oud_codes = codelist_from_csv(
  "codelists/user-hjforbes-opioid-dependency-clinical-diagnosis.csv",
  column = "code"
)

### HRG codes
hip_codes = ["HN12A","HN12B","HN12C","HN12D","HN12E","HN12F","HN13A","HN13B","HN13C","HN13D","HN13E","HN13F","HN13G","HN13H",
              "HN14A","HN14B","HN14C","HN14D","HN14E","HN14F","HN14G","HN14H","HN15A","HN15B","HN16A","HN16B","HN16C"]

knee_codes = ["HN22A","HN22B","HN22C","HN22D","HN22E","HN23A","HN23B","HN23C","HN23D","HN23E",
              "HN24A","HN24B","HN24C","HN24D","HN24E","HN24F","HN25A","HN25B","HN26A","HN26B","HN26C"]

foot_codes = ["HN32A","HN32B","HN32C","HN33A","HN33B","HN33C","HN33D","HN34A","HN34B","HN34C","HN34D","HN35A","HN35B","HN36Z"]

hand_codes = ["HN42A","HN42B","HN43A","HN43B","HN43C","HN44A","HN44B","HN44C","HN44D","HN45A","HN45B","HN45C","HN46Z"]

shoulder_codes = ["HN52A","HN52B","HN52C","HN53A","HN53B","HN53C",
                 "HN54A","HN54B","HN54C","HN54D","HN55Z","HN56Z"]

elbow_codes = ["HN62A","HN62B","HN63A","HN63B","HN64A","HN64B","HN64C","HN64D","HN65Z","HN66Z"]

complex_codes = ["HN80A","HN80B","HN80C","HN80D","HN81A","HN81B","HN81C","HN81D","HN81E","HN85Z","HN86A","HN86B","HN93Z"]

pain_codes = ["AB11Z","AB12Z","AB13Z","AB14Z","AB15Z","AB16Z","AB17Z","AB18Z","AB19Z","AB20Z",
            "AB21Z","AB22Z","AB23Z","AB24Z","AB25Z","AB26Z","AB27Z","AB28Z"]

trauma_codes = ["HT12A","HT12B","HT12C","HT12D","HT12E","HT13A","HT13B","HT13C","HT13D","HT13E",
                "HT14A","HT14B","HT14C","HT15Z","HT22A","HT22B","HT22C","HT23A","HT23B","HT23C","HT23D","HT23E",
                "HT24A","HT24B","HT24C","HT24D","HT25Z","HT32A","HT32B","HT32C","HT33A","HT33B","HT33C","HT33D","HT33E",
                "HT34A","HT34B","HT34C","HT34D","HT34E","HT35Z","HT42A","HT42B","HT43A","HT43B","HT43C","HT43D","HT43E",
                "HT44A","HT44B","HT44C","HT44D","HT44E","HT45Z","HT52A","HT52B","HT52C","HT53A","HT53B","HT53C","HT53D","HT53E",
                "HT54A","HT54B","HT54C","HT54D","HT55Z","HT62A","HT62B","HT63A","HT63B","HT63C","HT63D","HT63E","HT63F",
                "HT64A","HT64B","HT64C","HT64D","HT65Z","HT81A","HT81B","HT81C","HT81D","HT86A","HT86B","HT86C"]