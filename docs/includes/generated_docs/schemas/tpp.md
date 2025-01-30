# <strong>tpp</strong> schema

Available on backends: [**TPP**](../backends.md#tpp)

This schema defines the data (both primary care and externally linked) available in the
OpenSAFELY-TPP backend. For more information about this backend, see
"[SystmOne Primary Care](https://docs.opensafely.org/data-sources/systmone/)".

``` {.python .copy title='To use this schema in an ehrQL file:'}
from ehrql.tables.tpp import (
    addresses,
    apcs,
    apcs_cost,
    appointments,
    clinical_events,
    clinical_events_ranges,
    covid_therapeutics,
    decision_support_values,
    ec,
    ec_cost,
    emergency_care_attendances,
    ethnicity_from_sus,
    household_memberships_2020,
    medications,
    occupation_on_covid_vaccine_record,
    ons_deaths,
    opa,
    opa_cost,
    opa_diag,
    opa_proc,
    open_prompt,
    parents,
    patients,
    practice_registrations,
    sgss_covid_all_tests,
    ukrr,
    vaccinations,
    wl_clockstops,
    wl_openpathways,
)
```

<p class="dimension-indicator"><code>many rows per patient</code></p>
## addresses

Geographic characteristics of the home address a patient registers with a practice.
Each row in this table is one registration period per patient.
Occasionally, a patient has multiple active registrations on a given date.
The postcode from the address is mapped to an Output Area,
from which other larger geographic representations can be derived
(see various [ONS publications][addresses_ukgeographies] for more detail).

[addresses_ukgeographies]: https://www.ons.gov.uk/methodology/geography/ukgeographies

[Example ehrQL usage of addresses](../../../how-to/examples/#addresses)
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="addresses.address_id">
    <strong>address_id</strong>
    <a class="headerlink" href="#addresses.address_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique address identifier.

  </dd>
</div>

<div markdown="block">
  <dt id="addresses.start_date">
    <strong>start_date</strong>
    <a class="headerlink" href="#addresses.start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date patient moved to address.

  </dd>
</div>

<div markdown="block">
  <dt id="addresses.end_date">
    <strong>end_date</strong>
    <a class="headerlink" href="#addresses.end_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date patient moved out of address.

  </dd>
</div>

<div markdown="block">
  <dt id="addresses.address_type">
    <strong>address_type</strong>
    <a class="headerlink" href="#addresses.address_type" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Type of address:

* 0 - Permanent
* 1 - Temporary
* 3 - Correspondence only

 * Possible values: `0`, `1`, `3`
  </dd>
</div>

<div markdown="block">
  <dt id="addresses.rural_urban_classification">
    <strong>rural_urban_classification</strong>
    <a class="headerlink" href="#addresses.rural_urban_classification" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Rural urban classification:

* 1 - Urban major conurbation
* 2 - Urban minor conurbation
* 3 - Urban city and town
* 4 - Urban city and town in a sparse setting
* 5 - Rural town and fringe
* 6 - Rural town and fringe in a sparse setting
* 7 - Rural village and dispersed
* 8 - Rural village and dispersed in a sparse setting

 * Always >= 1 and <= 8
  </dd>
</div>

<div markdown="block">
  <dt id="addresses.imd_rounded">
    <strong>imd_rounded</strong>
    <a class="headerlink" href="#addresses.imd_rounded" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
[Index of Multiple Deprivation][addresses_imd] (IMD)
rank of each lower layer super output area (LSOA), rounded to the nearest 100, where
lower values represent more deprived areas. E.g. 1 is the most deprived LSOA in the country
and 32,844 is the least deprived (though in this field these are rounded to 0 and 32,800
respectively)

[addresses_imd]: https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019

 * Always >= 0, <= 32800, and a multiple of 100
  </dd>
</div>

<div markdown="block">
  <dt id="addresses.imd_quintile">
    <strong>imd_quintile</strong>
    <a class="headerlink" href="#addresses.imd_quintile" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
[Index of Multiple Deprivation][addresses_imd] (IMD) LSOA rank mapped to quintiles. NB this does not
return an integer 1-5, instead it is a string to make clear that 1 is the most, and 5 is the
least deprived. Possible values are:

* `1 (most deprived)`
* `2`
* `3`
* `4`
* `5 (least deprived)`
* `unknown`

The number of lower layer super output areas (LSOAs) in 2011 was 32,844. As this is not divisible
by 5 the number of LSOAs in each quintile is not the same. We have used the same boundaries as
provided in the data [available to download here][addresses_imd] with the first quintile containing
6,568 LSOAs, and the other 4 quintiles containing 6,569 LSOAs.

[addresses_imd]: https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019
  <details markdown="block">
  <summary>View definition</summary>
```py
imd = addresses.imd_rounded
return case(
    # Although the lowest IMD rank is 1, we need to check >= 0 because
    # we're using the imd_rounded field rather than the actual imd
    when((imd >= 0) & (imd <= int(32844 * 1 / 5))).then("1 (most deprived)"),
    when(imd <= int(32844 * 2 / 5)).then("2"),
    when(imd <= int(32844 * 3 / 5)).then("3"),
    when(imd <= int(32844 * 4 / 5)).then("4"),
    when(imd <= int(32844 * 5 / 5)).then("5 (least deprived)"),
    otherwise="unknown",
)

```
  </details>

  </dd>
</div>

<div markdown="block">
  <dt id="addresses.imd_decile">
    <strong>imd_decile</strong>
    <a class="headerlink" href="#addresses.imd_decile" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
[Index of Multiple Deprivation][addresses_imd] (IMD) LSOA rank mapped to deciles. NB this does not
return an integer 1-10, instead it is a string to make clear that 1 is the most, and 10 is the
least deprived. Possible values are:

* `1 (most deprived)`
* `2`
* ...
* `9`
* `10 (least deprived)`
* `unknown`

The number of lower layer super output areas (LSOAs) in 2011 was 32,844. As this is not divisible
by 10 the number of LSOAs in each decile is not the same. We have used the same boundaries as
provided in the data [available to download here][addresses_imd] with deciles 1, 2, 4, 6, 7 and 9
containing 3,284 LSOAs, and deciles 3, 5, 8 and 10 containing 3,285

[addresses_imd]: https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019
  <details markdown="block">
  <summary>View definition</summary>
```py
imd = addresses.imd_rounded
return case(
    # Although the lowest IMD rank is 1, we need to check >= 0 because
    # we're using the imd_rounded field rather than the actual imd
    when((imd >= 0) & (imd <= int(32844 * 1 / 10))).then("1 (most deprived)"),
    when(imd <= int(32844 * 2 / 10)).then("2"),
    when(imd <= int(32844 * 3 / 10)).then("3"),
    when(imd <= int(32844 * 4 / 10)).then("4"),
    when(imd <= int(32844 * 5 / 10)).then("5"),
    when(imd <= int(32844 * 6 / 10)).then("6"),
    when(imd <= int(32844 * 7 / 10)).then("7"),
    when(imd <= int(32844 * 8 / 10)).then("8"),
    when(imd <= int(32844 * 9 / 10)).then("9"),
    when(imd <= int(32844 * 10 / 10)).then("10 (least deprived)"),
    otherwise="unknown",
)

```
  </details>

  </dd>
</div>

<div markdown="block">
  <dt id="addresses.msoa_code">
    <strong>msoa_code</strong>
    <a class="headerlink" href="#addresses.msoa_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Middle Layer Super Output Areas (MSOA) code.

 * Matches regular expression: `E020[0-9]{5}`
  </dd>
</div>

<div markdown="block">
  <dt id="addresses.has_postcode">
    <strong>has_postcode</strong>
    <a class="headerlink" href="#addresses.has_postcode" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">
Indicating whether a valid postcode is recorded for the patient.

  </dd>
</div>

<div markdown="block">
  <dt id="addresses.care_home_is_potential_match">
    <strong>care_home_is_potential_match</strong>
    <a class="headerlink" href="#addresses.care_home_is_potential_match" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">
Indicating whether the patient's address matched with a care home, using TPP's algorithm.

  </dd>
</div>

<div markdown="block">
  <dt id="addresses.care_home_requires_nursing">
    <strong>care_home_requires_nursing</strong>
    <a class="headerlink" href="#addresses.care_home_requires_nursing" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">
Indicating whether the patient's address matched with a care home that required nursing.

  </dd>
</div>

<div markdown="block">
  <dt id="addresses.care_home_does_not_require_nursing">
    <strong>care_home_does_not_require_nursing</strong>
    <a class="headerlink" href="#addresses.care_home_does_not_require_nursing" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">
Indicating whether the patient's address matched with a care home that did not require nursing.

  </dd>
</div>

  </dl>
</div>
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Methods</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="addresses.for_patient_on">
    <strong>for_patient_on(</strong>date<strong>)</strong>
    <a class="headerlink" href="#addresses.for_patient_on" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Return each patient's registered address as it was on the supplied date.

Where there are multiple registered addresses we prefer any which have a known
postcode (though we never have access to this postcode) as this is used by TPP
to cross-reference other data associated with the address, such as the MSOA or
index of multiple deprevation.

Where there are multiple of these we prefer the most recently registered address
and then, if there are multiple of these, the one with the longest duration. If
there's stil an exact tie we choose arbitrarily based on the address ID.
    <details markdown="block">
    <summary>View method definition</summary>
```py
spanning_addrs = addresses.where(addresses.start_date <= date).except_where(
    addresses.end_date < date
)
ordered_addrs = spanning_addrs.sort_by(
    case(when(addresses.has_postcode).then(1), otherwise=0),
    addresses.start_date,
    addresses.end_date,
    addresses.address_id,
)
return ordered_addrs.last_for_patient()

```
    </details>
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## apcs

Admitted Patient Care Spells (APCS) data is provided via the NHS Secondary Uses Service.

This table gives core details of spells.

Each row is an in-hospital spell: a period of continuous care within a single trust.

Refer to the [OpenSAFELY documentation on the APCS data source][apcs_data_source_docs]
and the [GitHub issue discussing more of the background context][apcs_context_issue].

[apcs_data_source_docs]: https://docs.opensafely.org/data-sources/apc/
[apcs_context_issue]: https://github.com/opensafely-core/cohort-extractor/issues/186

[Example ehrQL usage of apcs](../../../how-to/examples/#admitted-patient-care-spells-apcs)
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="apcs.apcs_ident">
    <strong>apcs_ident</strong>
    <a class="headerlink" href="#apcs.apcs_ident" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the spell used across the APCS tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="apcs.admission_date">
    <strong>admission_date</strong>
    <a class="headerlink" href="#apcs.admission_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The admission date of the hospital provider spell.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.discharge_date">
    <strong>discharge_date</strong>
    <a class="headerlink" href="#apcs.discharge_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date of discharge from a hospital provider spell.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.discharge_destination">
    <strong>discharge_destination</strong>
    <a class="headerlink" href="#apcs.discharge_destination" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The destination of a patient on completion of a hospital provider spell, or that the patient died or was a stillbirth. The code is a 2 character string (e.g. 19 = usual place of residence, 54 = NHS run care home). Refer to [this documentation](https://docs.opensafely.org/data-sources/apc/#discharge-destination-reference-table) for a full list of codes.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.discharge_method">
    <strong>discharge_method</strong>
    <a class="headerlink" href="#apcs.discharge_method" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The method of discharge from a hospital provider spell. Currently the code is a 1 character string (e.g. 1 = discharged on clinical advice, 4 = died). Refer to [this documentation](https://www.datadictionary.nhs.uk/attributes/discharge_method.html) for a full list of codes.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.spell_core_hrg_sus">
    <strong>spell_core_hrg_sus</strong>
    <a class="headerlink" href="#apcs.spell_core_hrg_sus" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The core Healthcare Resource Group (HRG) code for the spell according to the derivations made by NHS Digital prior to import to the National Commissioning Data Repository (NCDR). HRGs are used to assign baseline tariff costs.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.admission_method">
    <strong>admission_method</strong>
    <a class="headerlink" href="#apcs.admission_method" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Code identifying admission method. Refer to [APCS data source documentation](https://docs.opensafely.org/data-sources/apc/) for details of codes.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.primary_diagnosis">
    <strong>primary_diagnosis</strong>
    <a class="headerlink" href="#apcs.primary_diagnosis" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Code indicating primary diagnosis. This is not necessarily the primary reason for admission, and could represent an escalation/complication of initial reason for admission.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.secondary_diagnosis">
    <strong>secondary_diagnosis</strong>
    <a class="headerlink" href="#apcs.secondary_diagnosis" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Code indicating secondary diagnosis. This is a single code giving the first listed secondary diagnosis, but there may other secondary diagnoses listed in the `all_diagnoses` field below.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.all_diagnoses">
    <strong>all_diagnoses</strong>
    <a class="headerlink" href="#apcs.all_diagnoses" title="Permanent link">🔗</a>
    <code>Multiple ICD-10 codes</code>
  </dt>
  <dd markdown="block">
List of all diagnoses as ICD-10 codes.

Note that the codes are not quite in the standard ICD-10 format in that they
omit the dot character e.g. instead of `I80.1` it will be written `I801`.

The codes are arranged in clusters separated by commas, with each cluster
separated by two pipe characters (`||`). These separators may or may not be
surrounded by spaces. For example:

    ||E119 ,J849 ,K869 ,M069 ,Z824 ,Z867 ||I801 ,I802 ,N179 ,N183

A hospital "spell" is made up of 1 or more "episodes". The `||` is the separator
between episodes. I.e. the example above is a spell of two episodes with 6
diagnosis codes recorded in the first episode, and 4 recorded in the second.

This field can be queried using the
[`contains`](../../reference/language.md#MultiCodeStringEventSeries.contains) method.
This uses simple substring matching to find a code anywhere inside the
field.  For example, to match the code `N17.1` (Acute renal failure with
acute cortical necrosis) you could use:
```python
apcs.where(apcs.all_diagnoses.contains("N171"))
```

You can take advantage of the hierarchical structure of ICD-10 by searching
the just the prefix of a code. For example to match all N17 (Acute renal
failure) codes you could use:
```python
apcs.where(apcs.all_diagnoses.contains("N17"))
```

Finally there is also
[`contains_any_of`](../../reference/language.md#MultiCodeStringEventSeries.contains_any_of).
So if you were looking for any of a list of ICD10 codes called `icd10_diagnosis_codes` you
could do:
```python
apcs.where(apcs.all_diagnoses.contains_any_of(icd10_diagnosis_list))
```

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.all_procedures">
    <strong>all_procedures</strong>
    <a class="headerlink" href="#apcs.all_procedures" title="Permanent link">🔗</a>
    <code>Multiple OPCS4 codes</code>
  </dt>
  <dd markdown="block">
List of all procedures as OPCS-4 codes.

Note that the codes are not quite in the standard OPCS-4 format in that they
omit the dot character e.g. instead of `W23.2` it will be written `W232`.

The codes are arranged in clusters separated by commas, with each cluster
separated by two pipe characters (`||`). These separators may or may not be
surrounded by spaces. For example:

    ||E851,T124,X403||Y532,Z921

A hospital "spell" is made up of 1 or more "episodes". The `||` is the separator
between episodes. I.e. the example above is a spell of two episodes with 3
procedure codes recorded in the first episode, and 2 recorded in the second.

This field can be queried using the
[`contains`](../../reference/language.md#MultiCodeStringEventSeries.contains) method.
This uses simple substring matching to find a code anywhere inside the
field.  For example, to match the code `W23.2` (Secondary open reduction of
fracture of bone and extramedullary fixation HFQ) you could use:
```python
apcs.where(apcs.all_procedures.contains("W232"))
```

You can take advantage of the hierarchical structure of OPCS-4 by searching
the just the prefix of a code. For example to match all X30 (Injection of therapeutic substance)
codes you could use:
```python
apcs.where(apcs.all_procedures.contains("X30"))
```

Finally there is also
[`contains_any_of`](../../reference/language.md#MultiCodeStringEventSeries.contains_any_of).
So if you were looking for any of a list of OPCS-4 codes called `opcs4_procedure_codes` you
could do:
```python
apcs.where(apcs.all_procedures.contains_any_of(opcs4_procedure_list))
```

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.days_in_critical_care">
    <strong>days_in_critical_care</strong>
    <a class="headerlink" href="#apcs.days_in_critical_care" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Number of days spent in critical care. This is counted in number of days (or part-days) not the number of nights as per normal "length of stay" calculations. Note the definition of critical care may vary between trusts.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs.patient_classification">
    <strong>patient_classification</strong>
    <a class="headerlink" href="#apcs.patient_classification" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Refer to [APCS data source documentation](https://docs.opensafely.org/data-sources/apc/) for details.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## apcs_cost

Admitted Patient Care Spells (APCS) data is provided via the NHS Secondary Uses Service.

This table gives details of spell cost.

Each row is an in-hospital spell: a period of continuous care within a single trust.

Note that data only goes back a couple of years.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="apcs_cost.apcs_ident">
    <strong>apcs_ident</strong>
    <a class="headerlink" href="#apcs_cost.apcs_ident" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the spell used across the APCS tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="apcs_cost.grand_total_payment_mff">
    <strong>grand_total_payment_mff</strong>
    <a class="headerlink" href="#apcs_cost.grand_total_payment_mff" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The grand total payment for the activity (`Net_SLA_Payment + Tariff_MFF_Payment`) where SLA = service level agreement, i.e. all contractual payments which is national tariff for the type of activity **plus** any additional payments **minus** any applicable deductions. MFF = Market Forces Factor, a geography-based cost adjustment).

  </dd>
</div>

<div markdown="block">
  <dt id="apcs_cost.tariff_initial_amount">
    <strong>tariff_initial_amount</strong>
    <a class="headerlink" href="#apcs_cost.tariff_initial_amount" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The base national tariff.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs_cost.tariff_total_payment">
    <strong>tariff_total_payment</strong>
    <a class="headerlink" href="#apcs_cost.tariff_total_payment" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The total payment according to the national tariff.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs_cost.admission_date">
    <strong>admission_date</strong>
    <a class="headerlink" href="#apcs_cost.admission_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The admission date of the hospital provider spell.

  </dd>
</div>

<div markdown="block">
  <dt id="apcs_cost.discharge_date">
    <strong>discharge_date</strong>
    <a class="headerlink" href="#apcs_cost.discharge_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date of discharge from a hospital provider spell.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## appointments

Appointments in primary care.

!!! warning
    In TPP this data comes from the "Appointment" table. This table has not yet been
    well characterised, so there are some issues around how to interpret findings
    from it. The data contains records created when an appointment is made with a GP
    practice, but may not capture absolutely all GP/patient interactions, for
    example it's uncertain whether an ad-hoc call to a patient would be included.
    There are also duplicate events in the table that we need to better understand.

    As a consequence, if you try to use the appointment table, you will see warnings
    when running your code locally, and failures when the GitHub action tests your
    code. If you need access to the appointments data, please speak to your
    OpenSAFELY co-pilot. We will be considering projects on a case by case basis
    until it can enter the normal stable pool of data.

    A **very important** caveat for this data: there are some circumstances where
    historical appointment records will be incomplete, for example when a patient
    moves from a practice using a different EHR provider, or when a practice changes
    EHR provider. If your study could be negatively affected by such missing data,
    it may be important to use the
    [`practice_registrations.spanning_with_systmone()`](#practice_registrations.spanning_with_systmone)
    method to identify patients which have a suitably continuous practice
    registration during the study period.

Some further investigation of the appointments data in TPP can be found in [this
King's fund report](https://www.kingsfund.org.uk/blog/2016/05/crisis-general-practice).

And you can find out more about [the associated database table][appointments_5] in the [short data report][appointments_1].
It shows:

* Date ranges for `booked_date`, `start_date`, and `seen_date`
* Row counts by month for `booked_date` and `start_date`
* The distribution of lead times (`start_date - booked_date`)
* Row counts for each value of `status`

To view it, you will need a login for OpenSAFELY Jobs and the Project Collaborator
or Project Developer role for the [project][appointments_4]. The
[workspace][appointments_2] shows when the code that comprises the report was run;
the code itself is in the [appointments-short-data-report][appointments_3]
repository on GitHub.

#### Appointments vs Consultations

"Consultation" is a very broad concept in SystmOne. It covers the things you might
expect, like a patient sitting down in front of a GP. But it also covers things like
some new pathology results arriving. There is no direct, explicit relationship
between an appointment and a consultation; but if an appointment results in any form
of recorded patient interaction then a corresponding consultation will be created.

The only way to link appointments and consultation is via the date they happened.
For instance, given some appointments you can find events which occurred on the same
day using:
```python
clinical_events.where(clinical_events.date.is_in(appointments.date))
```

!!! tip
    Querying this table is similar to using Cohort Extractor's
    `patients.with_gp_consultations` function. However, that function filters by
    the status of the appointment. To achieve a similar result with this table:

    ```py
    appointments.where(
        appointments.status.is_in([
            "Arrived",
            "In Progress",
            "Finished",
            "Visit",
            "Waiting",
            "Patient Walked Out",
        ])
    )
    ```

[appointments_1]: https://jobs.opensafely.org/curation-of-gp-appointments-data-short-data-report/appointments-short-data-report/outputs/latest/tpp/output/reports/report.html
[appointments_2]: https://jobs.opensafely.org/curation-of-gp-appointments-data-short-data-report/appointments-short-data-report/
[appointments_3]: https://github.com/opensafely/appointments-short-data-report
[appointments_4]: https://jobs.opensafely.org/curation-of-gp-appointments-data-short-data-report/
[appointments_5]: https://reports.opensafely.org/reports/opensafely-tpp-database-schema/#Appointment
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="appointments.booked_date">
    <strong>booked_date</strong>
    <a class="headerlink" href="#appointments.booked_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the appointment was booked

  </dd>
</div>

<div markdown="block">
  <dt id="appointments.start_date">
    <strong>start_date</strong>
    <a class="headerlink" href="#appointments.start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the appointment was due to start

  </dd>
</div>

<div markdown="block">
  <dt id="appointments.seen_date">
    <strong>seen_date</strong>
    <a class="headerlink" href="#appointments.seen_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the patient was seen

  </dd>
</div>

<div markdown="block">
  <dt id="appointments.status">
    <strong>status</strong>
    <a class="headerlink" href="#appointments.status" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The status of the appointment

 * Possible values: `Booked`, `Arrived`, `Did Not Attend`, `In Progress`, `Finished`, `Requested`, `Blocked`, `Visit`, `Waiting`, `Cancelled by Patient`, `Cancelled by Unit`, `Cancelled by Other Service`, `No Access Visit`, `Cancelled Due To Death`, `Patient Walked Out`
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## clinical_events

Each record corresponds to a single clinical or consultation event for a patient.

Each event is recorded twice: once with a CTv3 code, and again with the equivalent
SNOMED-CT code. Each record will have only one of the ctv3_code or snomedct_code
columns set and the other will be null. This allows you to query the table using
either a CTv3 codelist or SNOMED-CT codelist and all records using the other coding
system will be effectively ignored.

Note that event codes do not change in this table. If an event code in the coding
system becomes inactive, the event will still be coded to the inactive code.
As such, codelists should include all relevant inactive codes.

Detailed information on onward referrals is not currently available. A subset of
referrals are recorded in the clinical events table but this data will be incomplete.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="clinical_events.date">
    <strong>date</strong>
    <a class="headerlink" href="#clinical_events.date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events.snomedct_code">
    <strong>snomedct_code</strong>
    <a class="headerlink" href="#clinical_events.snomedct_code" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events.ctv3_code">
    <strong>ctv3_code</strong>
    <a class="headerlink" href="#clinical_events.ctv3_code" title="Permanent link">🔗</a>
    <code>CTV3 (Read v3) code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events.numeric_value">
    <strong>numeric_value</strong>
    <a class="headerlink" href="#clinical_events.numeric_value" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events.consultation_id">
    <strong>consultation_id</strong>
    <a class="headerlink" href="#clinical_events.consultation_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
ID of the [consultation](#appointments-vs-consultations) associated with this event

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## clinical_events_ranges

Each record corresponds to a single clinical or consultation event for a patient,
as presented in `clinical_events`, but with additional fields regarding the event's
`numeric_value`.

!!! warning
    Use of this table carries a severe performance penalty and should only be
    done so if the additional fields it provides are neccesary for a study.

These additional fields are:

* any comparators (if present) recorded with an event's `numeric_value` (e.g. '<9.5')
* the lower bound of the reference range associated with an event's `numeric_value`
* the upper bound of the reference range associated with an event's `numeric_value`
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="clinical_events_ranges.date">
    <strong>date</strong>
    <a class="headerlink" href="#clinical_events_ranges.date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events_ranges.snomedct_code">
    <strong>snomedct_code</strong>
    <a class="headerlink" href="#clinical_events_ranges.snomedct_code" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events_ranges.ctv3_code">
    <strong>ctv3_code</strong>
    <a class="headerlink" href="#clinical_events_ranges.ctv3_code" title="Permanent link">🔗</a>
    <code>CTV3 (Read v3) code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events_ranges.numeric_value">
    <strong>numeric_value</strong>
    <a class="headerlink" href="#clinical_events_ranges.numeric_value" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events_ranges.lower_bound">
    <strong>lower_bound</strong>
    <a class="headerlink" href="#clinical_events_ranges.lower_bound" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The lower bound of the reference range associated with an event's
numeric_value

  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events_ranges.upper_bound">
    <strong>upper_bound</strong>
    <a class="headerlink" href="#clinical_events_ranges.upper_bound" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The upper bound of the reference range associated with an event's
numeric_value

  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events_ranges.comparator">
    <strong>comparator</strong>
    <a class="headerlink" href="#clinical_events_ranges.comparator" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
If an event's numeric_value is returned with a comparator, e.g. as '<9.5',
then this column contains that comparator

 * Possible values: `~`, `=`, `>=`, `>`, `<`, `<=`
  </dd>
</div>

<div markdown="block">
  <dt id="clinical_events_ranges.consultation_id">
    <strong>consultation_id</strong>
    <a class="headerlink" href="#clinical_events_ranges.consultation_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
ID of the [consultation](#appointments-vs-consultations) associated with this event

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## covid_therapeutics

The COVID Therapeutics dataset contains information on COVID treatments used in inpatient
and outpatient settings.

**Metadata**

* **Data provider** NHS England
* **Participation / Coverage** Inpatients and outpatients treated with antivirals/nMABs for COVID-19 in England
* **Provenance** Data sourced largely from BlueTeq system (forms completed by clinicians)
* **Update frequency in OpenSAFELY** Approximately weekly
* **Delay between event occurring and event appearing in OpenSAFELY** Approximately 2-9 days
* **Collected information** Treatment start date; therapeutic intervention; COVID indication, current status, risk group, region


**Overview**

Antivirals and neutralising monoclonal antibodies (nMABs) for COVID-19 can be
administered in inpatient setting or, for outpatients, in COVID Medicine Delivery
Units (CMDUs) specifically set up for this purpose. For patients considered for
these treatments, clinicians submit completed forms to NHS England. Each row
represents one completed form for one course of treatment. Data received by
OpenSAFELY currently covers patients who were approved for treatment. The patient
may or may not have actually received the treatment or completed the course (but we
assume that they usually do). They may have another form completed for another
treatment, either because it was decided to give them a different treatment, or for
some other reason. They may in theory also have another form completed some months
later for another instance of infection.

Treatment dates may be in the past or future at the point when the form is
submitted.

Note that this dataset may contain **duplicate** rows – full duplicates are removed
but there may remain some partial duplicates.


**More Information**

* [Treatment guidelines](https://www.nice.org.uk/guidance/ta878)
* [Draft Data Report](https://docs.google.com/document/d/15o4x9sqHEO-sLm2dTqgm3PyAh72cdgOOmZC4AB3BTNk/) (currently only available to internal staff)
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="covid_therapeutics.covid_indication">
    <strong>covid_indication</strong>
    <a class="headerlink" href="#covid_therapeutics.covid_indication" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Treatment setting/indication.

 * Possible values: `non_hospitalised`, `hospitalised_with`, `hospital_onset`
  </dd>
</div>

<div markdown="block">
  <dt id="covid_therapeutics.current_status">
    <strong>current_status</strong>
    <a class="headerlink" href="#covid_therapeutics.current_status" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Status of form/application.

 * Possible values: `Approved`, `Treatment Complete`, `Treatment Not Started`, `Treatment Stopped`
  </dd>
</div>

<div markdown="block">
  <dt id="covid_therapeutics.intervention">
    <strong>intervention</strong>
    <a class="headerlink" href="#covid_therapeutics.intervention" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Intervention or therapeutic name. Expected to be one of:

 * Baricitinib
 * Casirivimab and imdevimab
 * Molnupiravir
 * Paxlovid
 * Remdesivir
 * sarilumab (sic)
 * Sotrovimab
 * Tocilizumab

  </dd>
</div>

<div markdown="block">
  <dt id="covid_therapeutics.received">
    <strong>received</strong>
    <a class="headerlink" href="#covid_therapeutics.received" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date form submitted.

  </dd>
</div>

<div markdown="block">
  <dt id="covid_therapeutics.region">
    <strong>region</strong>
    <a class="headerlink" href="#covid_therapeutics.region" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
NHS England region in which the CMDU submitting the form is located.

  </dd>
</div>

<div markdown="block">
  <dt id="covid_therapeutics.risk_cohort">
    <strong>risk_cohort</strong>
    <a class="headerlink" href="#covid_therapeutics.risk_cohort" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
High-risk group to which the patient was considered to belong. Derived from
tick-boxes. Multiple groups can be selected and will be comma separated,
e.g. `liver disease,rare neurological conditions`.

This series only contains data for events where the intervention was one of
Sotroviman, Molnupiravir, or Casirivimab & imdevimab.

The available groups as at the time of writing are listed below. However
note that the precise wording used has changed over time and so filtering by
a specific disease name may not be reliable.

 * `Downs syndrome`
 * `HIV or AIDS`
 * `IMID`
 * `haematologic malignancy`
 * `haematological diseases`
 * `immune deficiencies`
 * `liver disease`
 * `primary immune deficiencies`
 * `rare neurological conditions`
 * `rare neurological diseases`
 * `renal disease`
 * `sickle cell disease`
 * `solid cancer`
 * `solid organ recipients`
 * `stem cell transplant recipients`

  </dd>
</div>

<div markdown="block">
  <dt id="covid_therapeutics.treatment_start_date">
    <strong>treatment_start_date</strong>
    <a class="headerlink" href="#covid_therapeutics.treatment_start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Entered by the clinician and can represent either a future planned start
date or a past date at the time of form submission.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## decision_support_values

Returns values computed by decision support algorithms, for example the
[Electronic Frailty Index (EFI)][efi_ref]

[efi_ref]: https://www.england.nhs.uk/ourwork/clinical-policy/older-people/frailty/efi/
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="decision_support_values.calculation_date">
    <strong>calculation_date</strong>
    <a class="headerlink" href="#decision_support_values.calculation_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date of calculation for the decision support algorithm.

  </dd>
</div>

<div markdown="block">
  <dt id="decision_support_values.numeric_value">
    <strong>numeric_value</strong>
    <a class="headerlink" href="#decision_support_values.numeric_value" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The value computed by the decision support algorithm

  </dd>
</div>

<div markdown="block">
  <dt id="decision_support_values.algorithm_description">
    <strong>algorithm_description</strong>
    <a class="headerlink" href="#decision_support_values.algorithm_description" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The description of the decision support algorithm.

  </dd>
</div>

<div markdown="block">
  <dt id="decision_support_values.algorithm_version">
    <strong>algorithm_version</strong>
    <a class="headerlink" href="#decision_support_values.algorithm_version" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The version of the decision support algorithm.

  </dd>
</div>

  </dl>
</div>
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Methods</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="decision_support_values.electronic_frailty_index">
    <strong>electronic_frailty_index(</strong><strong>)</strong>
    <a class="headerlink" href="#decision_support_values.electronic_frailty_index" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Returns every calculated electronic frailty index v1 (EFI) for each patient.
    <details markdown="block">
    <summary>View method definition</summary>
```py
return decision_support_values.where(
    decision_support_values.algorithm_description == "UK Electronic Frailty Index (eFI)"
).where(decision_support_values.algorithm_version == "1.0")

```
    </details>
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## ec

Emergency care attendances data — the Emergency Care Data Set (ECDS) —
is provided via the NHS Secondary Uses Service.

This table gives core details of attendances.

Refer to the [OpenSAFELY documentation on the ECDS data source][ecds_data_source_docs]
and the GitHub issue that [discusses more of the background context][ecds_context_issue].

[ecds_data_source_docs]: https://docs.opensafely.org/data-sources/ecds/
[ecds_context_issue]: https://github.com/opensafely-core/cohort-extractor/issues/182
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="ec.ec_ident">
    <strong>ec_ident</strong>
    <a class="headerlink" href="#ec.ec_ident" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the attendance used across the EC tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="ec.arrival_date">
    <strong>arrival_date</strong>
    <a class="headerlink" href="#ec.arrival_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the patient self presented at the accident & emergency department, or arrived in an ambulance at the accident & emergency department.

  </dd>
</div>

<div markdown="block">
  <dt id="ec.sus_hrg_code">
    <strong>sus_hrg_code</strong>
    <a class="headerlink" href="#ec.sus_hrg_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The core Healthcare Resource Group (HRG) code derived by sus+, used for tariff application.

 * Matches regular expression: `[a-zA-Z]{2}[0-9]{2}[a-zA-Z]`
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## ec_cost

Emergency care attendances data is provided via the NHS Secondary Uses Service.

This table gives details of attendance costs.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="ec_cost.ec_ident">
    <strong>ec_ident</strong>
    <a class="headerlink" href="#ec_cost.ec_ident" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the attendance used across the EC tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="ec_cost.grand_total_payment_mff">
    <strong>grand_total_payment_mff</strong>
    <a class="headerlink" href="#ec_cost.grand_total_payment_mff" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The grand total payment for the activity (`Net_SLA_Payment + Tariff_MFF_Payment`) where SLA = service level agreement, i.e. all contractual payments which is national tariff for the type of activity **plus** any additional payments **minus** any applicable deductions. MFF = Market Forces Factor, a geography-based cost adjustment).

  </dd>
</div>

<div markdown="block">
  <dt id="ec_cost.tariff_total_payment">
    <strong>tariff_total_payment</strong>
    <a class="headerlink" href="#ec_cost.tariff_total_payment" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The total payment according to the national tariff.

  </dd>
</div>

<div markdown="block">
  <dt id="ec_cost.arrival_date">
    <strong>arrival_date</strong>
    <a class="headerlink" href="#ec_cost.arrival_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the patient self presented at the accident & emergency department, or arrived in an ambulance at the accident & emergency department.

  </dd>
</div>

<div markdown="block">
  <dt id="ec_cost.ec_decision_to_admit_date">
    <strong>ec_decision_to_admit_date</strong>
    <a class="headerlink" href="#ec_cost.ec_decision_to_admit_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date a decision to admit was made (if applicable).

  </dd>
</div>

<div markdown="block">
  <dt id="ec_cost.ec_injury_date">
    <strong>ec_injury_date</strong>
    <a class="headerlink" href="#ec_cost.ec_injury_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the patient was injured (if applicable).

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## emergency_care_attendances

Emergency care attendances data is provided via the NHS Secondary Uses Service.

This table gives details of attendances.

Note that there is a limited number of diagnoses allowed within this dataset,
and so will not match with the range of diagnoses allowed in other datasets
such as the primary care record.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="emergency_care_attendances.id">
    <strong>id</strong>
    <a class="headerlink" href="#emergency_care_attendances.id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the attendance used across the EC tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.arrival_date">
    <strong>arrival_date</strong>
    <a class="headerlink" href="#emergency_care_attendances.arrival_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the patient self presented at the accident & emergency department, or arrived in an ambulance at the accident & emergency department.

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.discharge_destination">
    <strong>discharge_destination</strong>
    <a class="headerlink" href="#emergency_care_attendances.discharge_destination" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the intended destination of the patient following discharge from the emergency care department.

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_01">
    <strong>diagnosis_01</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_01" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_02">
    <strong>diagnosis_02</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_02" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_03">
    <strong>diagnosis_03</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_03" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_04">
    <strong>diagnosis_04</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_04" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_05">
    <strong>diagnosis_05</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_05" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_06">
    <strong>diagnosis_06</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_06" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_07">
    <strong>diagnosis_07</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_07" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_08">
    <strong>diagnosis_08</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_08" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_09">
    <strong>diagnosis_09</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_09" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_10">
    <strong>diagnosis_10</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_10" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_11">
    <strong>diagnosis_11</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_11" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_12">
    <strong>diagnosis_12</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_12" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_13">
    <strong>diagnosis_13</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_13" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_14">
    <strong>diagnosis_14</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_14" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_15">
    <strong>diagnosis_15</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_15" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_16">
    <strong>diagnosis_16</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_16" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_17">
    <strong>diagnosis_17</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_17" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_18">
    <strong>diagnosis_18</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_18" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_19">
    <strong>diagnosis_19</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_19" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_20">
    <strong>diagnosis_20</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_20" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_21">
    <strong>diagnosis_21</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_21" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_22">
    <strong>diagnosis_22</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_22" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_23">
    <strong>diagnosis_23</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_23" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_24">
    <strong>diagnosis_24</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_24" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The SNOMED CT concept ID which is used to identify the patient diagnosis. Note that only a limited subset of SNOMED CT codes are used; see the [NHS Data Model and Dictionary entry for emergency care diagnosis](https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html).

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>one row per patient</code></p>
## ethnicity_from_sus

This finds the most frequently used national ethnicity code for each patient from
the various SUS (Secondary Uses Service) tables.

Specifically it uses ethnicity codes from the following tables:

    APCS (In-patient hospital admissions)
    EC (A&E attendances)
    OPA (Out-patient hospital appointments)

Codes are as defined by "Ethnic Category Code 2001" — the 16+1 ethnic data
categories used in the 2001 census:
https://www.datadictionary.nhs.uk/data_elements/ethnic_category.html

Codes beginning Z ("Not stated") and 99 ("Not known") are excluded.

Where there is a tie for the most common code the lexically greatest code is used.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="ethnicity_from_sus.code">
    <strong>code</strong>
    <a class="headerlink" href="#ethnicity_from_sus.code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
First character of recorded ethncity code (national code):
https://www.datadictionary.nhs.uk/data_elements/ethnic_category.html

 * Possible values: `A`, `B`, `C`, `D`, `E`, `F`, `G`, `H`, `J`, `K`, `L`, `M`, `N`, `P`, `R`, `S`
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>one row per patient</code></p>
## household_memberships_2020

Inferred household membership as of 2020-02-01, as determined by TPP using an as yet
undocumented algorithm.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="household_memberships_2020.household_pseudo_id">
    <strong>household_pseudo_id</strong>
    <a class="headerlink" href="#household_memberships_2020.household_pseudo_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="household_memberships_2020.household_size">
    <strong>household_size</strong>
    <a class="headerlink" href="#household_memberships_2020.household_size" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## medications

The medications table provides data about prescribed medications in primary care.

Prescribing data, including the contents of the medications table are standardised
across clinical information systems such as SystmOne (TPP). This is a requirement
for data transfer through the
[Electronic Prescription Service](https://digital.nhs.uk/services/electronic-prescription-service/)
in which data passes from the prescriber to the pharmacy for dispensing.

Medications are coded using
[dm+d codes](https://www.bennett.ox.ac.uk/blog/2019/08/what-is-the-dm-d-the-nhs-dictionary-of-medicines-and-devices/).
The medications table is structured similarly to the [clinical_events](#clinical_events)
table, and each row in the table is made up of a patient identifier, an event (dm+d)
code, and an event date. For this table, the event refers to the issue of a medication
(coded as a dm+d code), and the event date, the date the prescription was issued.

### Factors to consider when using medications data

Depending on the specific area of research, you may wish to exclude medications
in particular periods. For example, in order to ensure medication data is stable
following a change of practice, you may want to exclude patients for a period after
the start of their practice registration . You may also want to
exclude medications for patients for a period prior to their leaving a practice.
Alternatively, for research looking at a specific period of
interest, you may simply want to ensure that all included patients were registered
at a single practice for a minimum time prior to the study period, and were
registered at the same practice for the duration of the study period.

Examples of using ehrQL to calculation such periods can be found in the documentation
on how to
[use ehrQL to answer specific questions using the medications table](../../../how-to/examples/#clinical-events)
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="medications.date">
    <strong>date</strong>
    <a class="headerlink" href="#medications.date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="medications.dmd_code">
    <strong>dmd_code</strong>
    <a class="headerlink" href="#medications.dmd_code" title="Permanent link">🔗</a>
    <code>dm+d code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="medications.consultation_id">
    <strong>consultation_id</strong>
    <a class="headerlink" href="#medications.consultation_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
ID of the [consultation](#appointments-vs-consultations) associated with this event

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## occupation_on_covid_vaccine_record

This data is from the NHS England COVID-19 data store,
and reflects information collected at the point of vaccination
where recipients are asked by vaccination staff
whether they are in the category of health and care worker.

Refer to the [OpenSAFELY database build report][opensafely_database_build_report]
to see when this data was last updated.

See the GitHub issue that [discusses more of the background context][vaccine_record_issue].

[opensafely_database_build_report]: https://reports.opensafely.org/reports/opensafely-tpp-database-builds
[vaccine_record_issue]: https://github.com/opensafely-core/cohort-extractor/issues/544
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="occupation_on_covid_vaccine_record.is_healthcare_worker">
    <strong>is_healthcare_worker</strong>
    <a class="headerlink" href="#occupation_on_covid_vaccine_record.is_healthcare_worker" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>one row per patient</code></p>
## ons_deaths

Registered deaths

Date and cause of death based on information recorded when deaths are
certified and registered in England and Wales from February 2019 onwards.
The data provider is the Office for National Statistics (ONS).
This table is updated approximately weekly in OpenSAFELY.

This table includes the underlying cause of death and up to 15 medical conditions
mentioned on the death certificate.  These codes (`cause_of_death_01` to
`cause_of_death_15`) are not ordered meaningfully.

More information about this table can be found in following documents provided by the ONS:

- [Information collected at death registration](https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/deaths/methodologies/userguidetomortalitystatisticsjuly2017#information-collected-at-death-registration)
- [User guide to mortality statistics](https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/deaths/methodologies/userguidetomortalitystatisticsjuly2017)
- [How death registrations are recorded and stored by ONS](https://www.ons.gov.uk/aboutus/transparencyandgovernance/freedomofinformationfoi/howdeathregistrationsarerecordedandstoredbyons)

In the associated database table [ONS_Deaths](https://reports.opensafely.org/reports/opensafely-tpp-database-schema/#ONS_Deaths),
a small number of patients have multiple registered deaths.
This table contains the earliest registered death.
The `ehrql.tables.raw.core.ons_deaths` table contains all registered deaths.

!!! warning
    There is also a lag in ONS death recording caused amongst other things by things
    like autopsies and inquests delaying reporting on cause of death. This is
    evident in the [OpenSAFELY historical database coverage
    report](https://reports.opensafely.org/reports/opensafely-tpp-database-history/#ons_deaths)

[Example ehrQL usage of ons_deaths](../../../how-to/examples/#ons-deaths)

### TPP specific information

!!! tip
    Note that this version of the table, which includes a place of death field, is
    only available in the `tpp` schema and not the `core` schema.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="ons_deaths.date">
    <strong>date</strong>
    <a class="headerlink" href="#ons_deaths.date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Patient's date of death.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.underlying_cause_of_death">
    <strong>underlying_cause_of_death</strong>
    <a class="headerlink" href="#ons_deaths.underlying_cause_of_death" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Patient's underlying cause of death.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_01">
    <strong>cause_of_death_01</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_01" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_02">
    <strong>cause_of_death_02</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_02" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_03">
    <strong>cause_of_death_03</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_03" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_04">
    <strong>cause_of_death_04</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_04" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_05">
    <strong>cause_of_death_05</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_05" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_06">
    <strong>cause_of_death_06</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_06" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_07">
    <strong>cause_of_death_07</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_07" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_08">
    <strong>cause_of_death_08</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_08" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_09">
    <strong>cause_of_death_09</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_09" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_10">
    <strong>cause_of_death_10</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_10" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_11">
    <strong>cause_of_death_11</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_11" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_12">
    <strong>cause_of_death_12</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_12" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_13">
    <strong>cause_of_death_13</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_13" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_14">
    <strong>cause_of_death_14</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_14" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_15">
    <strong>cause_of_death_15</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_15" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
Medical condition mentioned on the death certificate.

  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.place">
    <strong>place</strong>
    <a class="headerlink" href="#ons_deaths.place" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Patient's place of death.

 * Possible values: `Care Home`, `Elsewhere`, `Home`, `Hospice`, `Hospital`, `Other communal establishment`
  </dd>
</div>

  </dl>
</div>
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Methods</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="ons_deaths.cause_of_death_is_in">
    <strong>cause_of_death_is_in(</strong>codelist<strong>)</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_is_in" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Match `codelist` against the `underlying_cause_of_death` field and all 15
separate `cause_of_death` fields.

This method evaluates as `True` if _any_ code in the codelist matches _any_ of
these fields.
    <details markdown="block">
    <summary>View method definition</summary>
```py
columns = [
    "underlying_cause_of_death",
    *[f"cause_of_death_{i:02d}" for i in range(1, 16)],
]
conditions = [getattr(ons_deaths, column).is_in(codelist) for column in columns]
return functools.reduce(operator.or_, conditions)

```
    </details>
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## opa

Outpatient appointments data (OPA) is provided via the NHS Secondary Uses Service.

This table gives core details of outpatient appointments.

Refer to the GitHub issue that [describes limitations
of the outpatient appointments data][opa_limitations_issue]
and the GitHub issue that [discusses more of the background context][opa_context_issue].

[opa_limitations_issue]: https://github.com/opensafely-core/cohort-extractor/issues/673
[opa_context_issue]: https://github.com/opensafely-core/cohort-extractor/issues/492
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="opa.opa_ident">
    <strong>opa_ident</strong>
    <a class="headerlink" href="#opa.opa_ident" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the appointment used across the OPA tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="opa.appointment_date">
    <strong>appointment_date</strong>
    <a class="headerlink" href="#opa.appointment_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date of an appointment.

  </dd>
</div>

<div markdown="block">
  <dt id="opa.attendance_status">
    <strong>attendance_status</strong>
    <a class="headerlink" href="#opa.attendance_status" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Indicates whether or not an appointment for a care contact took place. If the appointment did not take place it also indicates whether or not advanced warning was given. Refer to the [NHS Data Model and Dictionary entry for "attended or did not attend"](https://www.datadictionary.nhs.uk/data_elements/attended_or_did_not_attend_code.html) for details on code meanings.

 * Possible values: `5`, `6`, `7`, `2`, `3`, `4`, `0`
  </dd>
</div>

<div markdown="block">
  <dt id="opa.consultation_medium_used">
    <strong>consultation_medium_used</strong>
    <a class="headerlink" href="#opa.consultation_medium_used" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Identifies the communication mechanism used to relay information between the care professional and the person who is the subject of the consultation, during a care activity. Refer to the [NHS Data Model and Dictionary entry for "consultation mechanism"](https://www.datadictionary.nhs.uk/data_elements/consultation_mechanism.html) for details on code meanings. Note that the allowed codes as listed in TPP's data appear to be a subset of the codes listed in the NHS Data Model and Dictionary.

 * Possible values: `01`, `02`, `03`, `04`, `05`, `09`, `10`, `11`, `98`
  </dd>
</div>

<div markdown="block">
  <dt id="opa.first_attendance">
    <strong>first_attendance</strong>
    <a class="headerlink" href="#opa.first_attendance" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
An indication of whether a patient is making a first attendance or contact; or a follow-up attendance or contact and whether the consultation medium used national code was face to face communication or telephone or telemedicine web camera. Refer to the [NHS Data Model and Dictionary entry for "first attendance"](https://www.datadictionary.nhs.uk/attributes/first_attendance.html) for details on code meanings. Note that the allowed codes as listed in TPP's data contain an additional `9` code over the NHS Data Model and Dictionary entry.

 * Possible values: `1`, `2`, `3`, `4`, `5`, `9`
  </dd>
</div>

<div markdown="block">
  <dt id="opa.hrg_code">
    <strong>hrg_code</strong>
    <a class="headerlink" href="#opa.hrg_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The Healthcare Resource Group (HRG) code assigned to the activity, used to assign baseline tariff costs.

 * Matches regular expression: `[a-zA-Z]{2}[0-9]{2}[a-zA-Z]`
  </dd>
</div>

<div markdown="block">
  <dt id="opa.treatment_function_code">
    <strong>treatment_function_code</strong>
    <a class="headerlink" href="#opa.treatment_function_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The treatment function under which the patient is treated. It may be the same as the main specialty code or a different treatment function which will be the care professional's treatment interest.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## opa_cost

Outpatient appointments data is provided via the NHS Secondary Uses Service.

This table gives details of outpatient appointment costs.

Note that data only goes back a couple of years.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="opa_cost.opa_ident">
    <strong>opa_ident</strong>
    <a class="headerlink" href="#opa_cost.opa_ident" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the appointment used across the OPA tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="opa_cost.tariff_opp">
    <strong>tariff_opp</strong>
    <a class="headerlink" href="#opa_cost.tariff_opp" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The base national tariff where the procedure tariff is applicable.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_cost.grand_total_payment_mff">
    <strong>grand_total_payment_mff</strong>
    <a class="headerlink" href="#opa_cost.grand_total_payment_mff" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The grand total payment for the activity (`Net_SLA_Payment + Tariff_MFF_Payment`) where SLA = service level agreement, i.e. all contractual payments which is national tariff for the type of activity **plus** any additional payments **minus** any applicable deductions. MFF = Market Forces Factor, a geography-based cost adjustment).

  </dd>
</div>

<div markdown="block">
  <dt id="opa_cost.tariff_total_payment">
    <strong>tariff_total_payment</strong>
    <a class="headerlink" href="#opa_cost.tariff_total_payment" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The total payment according to the national tariff.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_cost.appointment_date">
    <strong>appointment_date</strong>
    <a class="headerlink" href="#opa_cost.appointment_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date of an appointment.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_cost.referral_request_received_date">
    <strong>referral_request_received_date</strong>
    <a class="headerlink" href="#opa_cost.referral_request_received_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the referral request was received by the health care provider.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## opa_diag

Outpatient appointments data is provided via the NHS Secondary Uses Service.

This table gives details of outpatient appointment diagnoses.

Note that diagnoses are often absent from outpatient records.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="opa_diag.opa_ident">
    <strong>opa_ident</strong>
    <a class="headerlink" href="#opa_diag.opa_ident" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the appointment used across the OPA tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="opa_diag.primary_diagnosis_code">
    <strong>primary_diagnosis_code</strong>
    <a class="headerlink" href="#opa_diag.primary_diagnosis_code" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
The international classification of diseases (ICD) code used to identify the primary patient diagnosis. Note that this will typically not be completed.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_diag.primary_diagnosis_code_read">
    <strong>primary_diagnosis_code_read</strong>
    <a class="headerlink" href="#opa_diag.primary_diagnosis_code_read" title="Permanent link">🔗</a>
    <code>CTV3 (Read v3) code</code>
  </dt>
  <dd markdown="block">
The Read coded clinical terms code to identify the primary patient diagnosis. Note that this will typically not be completed.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_diag.secondary_diagnosis_code_1">
    <strong>secondary_diagnosis_code_1</strong>
    <a class="headerlink" href="#opa_diag.secondary_diagnosis_code_1" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">
The international classification of diseases (ICD) code used to identify the secondary patient diagnosis. Note that this will typically not be completed.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_diag.secondary_diagnosis_code_1_read">
    <strong>secondary_diagnosis_code_1_read</strong>
    <a class="headerlink" href="#opa_diag.secondary_diagnosis_code_1_read" title="Permanent link">🔗</a>
    <code>CTV3 (Read v3) code</code>
  </dt>
  <dd markdown="block">
The Read coded clinical terms used to identify the secondary patient diagnosis. Note that this will typically not be completed.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_diag.appointment_date">
    <strong>appointment_date</strong>
    <a class="headerlink" href="#opa_diag.appointment_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date of an appointment.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_diag.referral_request_received_date">
    <strong>referral_request_received_date</strong>
    <a class="headerlink" href="#opa_diag.referral_request_received_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the referral request was received by the health care provider.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## opa_proc

Outpatient appointments data is provided via the NHS Secondary Uses Service.

This table gives details of outpatient procedures.
Typically, procedures will only be recorded where they attract a specified payment.
The majority of appointments will have no procedure recorded.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="opa_proc.opa_ident">
    <strong>opa_ident</strong>
    <a class="headerlink" href="#opa_proc.opa_ident" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Unique identifier for the appointment used across the OPA tables.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="opa_proc.primary_procedure_code">
    <strong>primary_procedure_code</strong>
    <a class="headerlink" href="#opa_proc.primary_procedure_code" title="Permanent link">🔗</a>
    <code>OPCS-4 code</code>
  </dt>
  <dd markdown="block">
The OPCS classification of interventions and procedures code which is used to identify the primary patient procedure carried out.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_proc.primary_procedure_code_read">
    <strong>primary_procedure_code_read</strong>
    <a class="headerlink" href="#opa_proc.primary_procedure_code_read" title="Permanent link">🔗</a>
    <code>CTV3 (Read v3) code</code>
  </dt>
  <dd markdown="block">
The Read coded clinical terms code which is used to identify the primary patient procedure carried out.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_proc.procedure_code_2">
    <strong>procedure_code_2</strong>
    <a class="headerlink" href="#opa_proc.procedure_code_2" title="Permanent link">🔗</a>
    <code>OPCS-4 code</code>
  </dt>
  <dd markdown="block">
TODO

  </dd>
</div>

<div markdown="block">
  <dt id="opa_proc.procedure_code_2_read">
    <strong>procedure_code_2_read</strong>
    <a class="headerlink" href="#opa_proc.procedure_code_2_read" title="Permanent link">🔗</a>
    <code>CTV3 (Read v3) code</code>
  </dt>
  <dd markdown="block">
The Read coded clinical terms for a procedure other than the primary procedure.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_proc.appointment_date">
    <strong>appointment_date</strong>
    <a class="headerlink" href="#opa_proc.appointment_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date of an appointment.

  </dd>
</div>

<div markdown="block">
  <dt id="opa_proc.referral_request_received_date">
    <strong>referral_request_received_date</strong>
    <a class="headerlink" href="#opa_proc.referral_request_received_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the referral request was received by the health care provider.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## open_prompt

This table contains responses to questions from the OpenPROMPT project.

You can find out more about this table in the associated short data report. To view
it, you will need a login for [Level 4][open_prompt_1]. The
[workspace][open_prompt_2] shows when the code that comprises the report was run;
the code itself is in the [airmid-short-data-report][open_prompt_3] repository on
GitHub.

[open_prompt_1]: https://docs.opensafely.org/security-levels/#level-4-nhs-england-are-data-controllers-of-the-data
[open_prompt_2]: https://jobs.opensafely.org/datalab/opensafely-internal/airmid-short-data-report/
[open_prompt_3]: https://github.com/opensafely/airmid-short-data-report
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="open_prompt.ctv3_code">
    <strong>ctv3_code</strong>
    <a class="headerlink" href="#open_prompt.ctv3_code" title="Permanent link">🔗</a>
    <code>CTV3 (Read v3) code</code>
  </dt>
  <dd markdown="block">
The response to the question, as a CTV3 code. Alternatively, if the question does not admit a CTV3 code as the response, then the question, as a CTV3 code.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="open_prompt.snomedct_code">
    <strong>snomedct_code</strong>
    <a class="headerlink" href="#open_prompt.snomedct_code" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">
The response to the question, as a SNOMED CT code. Alternatively, if the question does not admit a SNOMED CT code as the response, then the question, as a SNOMED CT code.

  </dd>
</div>

<div markdown="block">
  <dt id="open_prompt.creation_date">
    <strong>creation_date</strong>
    <a class="headerlink" href="#open_prompt.creation_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the survey was administered

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="open_prompt.consultation_date">
    <strong>consultation_date</strong>
    <a class="headerlink" href="#open_prompt.consultation_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The response to the question, as a date, if the question admits a date as the response. Alternatively, the date the survey was administered.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="open_prompt.consultation_id">
    <strong>consultation_id</strong>
    <a class="headerlink" href="#open_prompt.consultation_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
The ID of the survey

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="open_prompt.numeric_value">
    <strong>numeric_value</strong>
    <a class="headerlink" href="#open_prompt.numeric_value" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
The response to the question, as a number

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>one row per patient</code></p>
## parents

Provides the internal pseudonymous ID of the patient's mother, if this is recorded
in the SystmOne database.

We remove any records which have an "end date" specified: this is indicative of an
incorrect record having been amended in the database. We also remove any obviously
unsuitable records, specifically those where the mother is recorded as male (noting
that this is sex assigned at birth), or where the mother's date of birth is not
before the child's. Finally we remove any cases where more than one valid record
exists and we don't know which is correct.

It is not currently clear whether these records are intended to capture birth
mothers or those with parental responsibility.

At the time of writing (2024-09-23) the underlying `Relationship` table contains
approximately **3.8 million** rows, specifying **2.7 million** distinct
relationships (relations can be expressed as both parent-to-child and
child-to-parent, hence the high rate of duplicates).

 * Removing male parents discards about **120,000** of these.
 * Removing relationships with end dates discards a further **175,000**.
 * Removing those where the parent is younger than the child discards a futher
   **8,000**.
 * Finally, removing ambiguous records (i.e. multiple conflicting valid entries)
   discards another **4,000**.

This leaves a total of about **2.5 million** patients with a valid `mother_id`
record.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="parents.mother_id">
    <strong>mother_id</strong>
    <a class="headerlink" href="#parents.mother_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
The `patient_id` of the patient's mother

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>one row per patient</code></p>
## patients

Patients in primary care.

### Representativeness

You can find out more about the representativeness of these data in the
OpenSAFELY-TPP backend in:

> The OpenSAFELY Collaborative, Colm D. Andrews, Anna Schultze, Helen J. Curtis, William J. Hulme, John Tazare, Stephen J. W. Evans, _et al._ 2022.
> "OpenSAFELY: Representativeness of Electronic Health Record Platform OpenSAFELY-TPP Data Compared to the Population of England."
> Wellcome Open Res 2022, 7:191.
> <https://doi.org/10.12688/wellcomeopenres.18010.1>


### Orphan records

If a practice becomes aware that a patient has moved house,
then the practice _deducts_, or removes, the patient's records from their register.
If the patient doesn't register with a new practice within a given amount of time
(normally from four to eight weeks),
then the patient's records are permanently deducted and are _orphan records_.
There are roughly 1.6 million orphan records.

### Recording of death in primary care

In England, it is the statutory duty of the doctor who had attended in the last
illness to complete a medical certificate of cause of death (MCCD). ONS death data
are considered the gold standard for identifying patient deaths because they are
based on these MCCDs.

There is generally a lag between the death being recorded in ONS data and it
appearing in the primary care record, but the coverage or recorded death is almost
complete and the date of death is usually reliable when it appears. There is
also a lag in ONS death recording (see [`ons_deaths`](#ons_deaths) below
for more detail). You can find out more about the accuracy of date of death
recording in primary care in:

> Gallagher, A. M., Dedman, D., Padmanabhan, S., Leufkens, H. G. M. & de Vries, F 2019. The accuracy of date of death recording in the Clinical
> Practice Research Datalink GOLD database in England compared with the Office for National Statistics death registrations.
> Pharmacoepidemiol. Drug Saf. 28, 563–569.
> <https://doi.org/10.1002/pds.4747>

By contrast, cause of death is often not accurate in the primary care record so we
don't make it available to query here.

[Example ehrQL usage of patients](../../../how-to/examples/#patients)
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="patients.date_of_birth">
    <strong>date_of_birth</strong>
    <a class="headerlink" href="#patients.date_of_birth" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Patient's date of birth.

 * Always the first day of a month
 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="patients.sex">
    <strong>sex</strong>
    <a class="headerlink" href="#patients.sex" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Patient's sex.

 * Possible values: `female`, `male`, `intersex`, `unknown`
 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="patients.date_of_death">
    <strong>date_of_death</strong>
    <a class="headerlink" href="#patients.date_of_death" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Patient's date of death.

  </dd>
</div>

  </dl>
</div>
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Methods</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="patients.age_on">
    <strong>age_on(</strong>date<strong>)</strong>
    <a class="headerlink" href="#patients.age_on" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Patient's age as an integer, in whole elapsed calendar years, as it would be on
the given date.

This method takes no account of whether the patient is alive on the given date.
In particular, it may return negative values if the given date is before the
patient's date of birth.
    <details markdown="block">
    <summary>View method definition</summary>
```py
return (date - patients.date_of_birth).years

```
    </details>
  </dd>
</div>

<div markdown="block">
  <dt id="patients.is_alive_on">
    <strong>is_alive_on(</strong>date<strong>)</strong>
    <a class="headerlink" href="#patients.is_alive_on" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Whether a patient is alive on the given date, based on the date of death
recorded in their primary care record. **NB** this is only based on the primary
care record. Please see the section above about the accuracy of death data.

If the date provided is before a person was born, then this helper function will
actually return True, despite the person not being alive yet. For most research
this is likely the expected behaviour.
    <details markdown="block">
    <summary>View method definition</summary>
```py
return patients.date_of_death.is_after(date) | patients.date_of_death.is_null()

```
    </details>
  </dd>
</div>

<div markdown="block">
  <dt id="patients.is_dead_on">
    <strong>is_dead_on(</strong>date<strong>)</strong>
    <a class="headerlink" href="#patients.is_dead_on" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Whether a patient has a date of death in their primary care record before the given date.

A person is classed as dead if the date provided is after their death date.
    <details markdown="block">
    <summary>View method definition</summary>
```py
return patients.date_of_death.is_not_null() & patients.date_of_death.is_before(date)

```
    </details>
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## practice_registrations

Each record corresponds to a patient's registration with a practice.

[Example ehrQL usage of practice_registrations](../../../how-to/examples/#practice-registrations)

### TPP specific information

See the [TPP backend information](../backends.md#patients-included-in-the-tpp-backend)
for details of which patients are included.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="practice_registrations.start_date">
    <strong>start_date</strong>
    <a class="headerlink" href="#practice_registrations.start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date patient joined practice.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.end_date">
    <strong>end_date</strong>
    <a class="headerlink" href="#practice_registrations.end_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date patient left practice.

  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.practice_pseudo_id">
    <strong>practice_pseudo_id</strong>
    <a class="headerlink" href="#practice_registrations.practice_pseudo_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Pseudonymised practice identifier.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.practice_stp">
    <strong>practice_stp</strong>
    <a class="headerlink" href="#practice_registrations.practice_stp" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
ONS code of practice's STP (Sustainability and Transformation Partnership).
STPs have been replaced by ICBs (Integrated Care Boards), and ICB codes will be available soon.

 * Matches regular expression: `E540000[0-9]{2}`
  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.practice_nuts1_region_name">
    <strong>practice_nuts1_region_name</strong>
    <a class="headerlink" href="#practice_registrations.practice_nuts1_region_name" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Name of the NUTS level 1 region of England to which the practice belongs.
For more information see:
<https://www.ons.gov.uk/methodology/geography/ukgeographies/eurostat>

 * Possible values: `North East`, `North West`, `Yorkshire and The Humber`, `East Midlands`, `West Midlands`, `East`, `London`, `South East`, `South West`
  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.practice_systmone_go_live_date">
    <strong>practice_systmone_go_live_date</strong>
    <a class="headerlink" href="#practice_registrations.practice_systmone_go_live_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date on which the practice started using the SystmOne EHR platform.

Most patient records will have been transferred from the previous EHR
platform but records which are specific to SystmOne will not exist before
this date. In particular, the [appointments](#appointments) table should
only be considered accurate for a given practice _after_ this date.

  </dd>
</div>

  </dl>
</div>
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Methods</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="practice_registrations.for_patient_on">
    <strong>for_patient_on(</strong>date<strong>)</strong>
    <a class="headerlink" href="#practice_registrations.for_patient_on" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Return each patient's practice registration as it was on the supplied date.

Where a patient is registered with multiple practices we prefer the most recent
registration and then, if there are multiple of these, the one with the longest
duration. If there's still an exact tie we choose arbitrarily based on the
practice ID.
    <details markdown="block">
    <summary>View method definition</summary>
```py
spanning_regs = practice_registrations.where(practice_registrations.start_date <= date).except_where(
    practice_registrations.end_date < date
)
ordered_regs = spanning_regs.sort_by(
    practice_registrations.start_date,
    practice_registrations.end_date,
    practice_registrations.practice_pseudo_id,
)
return ordered_regs.last_for_patient()

```
    </details>
  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.exists_for_patient_on">
    <strong>exists_for_patient_on(</strong>date<strong>)</strong>
    <a class="headerlink" href="#practice_registrations.exists_for_patient_on" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Returns whether a person was registered with a practice on the supplied date.

NB. The implementation currently uses `spanning()`. It would also have been
valid to implement as
`practice_registrations.for_patient_on(date).exists_for_patient()`, but for
internal reasons that is less efficient.
    <details markdown="block">
    <summary>View method definition</summary>
```py
return practice_registrations.spanning(date, date).exists_for_patient()

```
    </details>
  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.spanning">
    <strong>spanning(</strong>start_date, end_date<strong>)</strong>
    <a class="headerlink" href="#practice_registrations.spanning" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Filter registrations to just those spanning the entire period between
`start_date` and `end_date`.
    <details markdown="block">
    <summary>View method definition</summary>
```py
return practice_registrations.where(
    practice_registrations.start_date.is_on_or_before(start_date)
    & (practice_registrations.end_date.is_after(end_date) | practice_registrations.end_date.is_null())
)

```
    </details>
  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.spanning_with_systmone">
    <strong>spanning_with_systmone(</strong>start_date, end_date<strong>)</strong>
    <a class="headerlink" href="#practice_registrations.spanning_with_systmone" title="Permanent link">🔗</a>
    <code></code>
  </dt>
  <dd markdown="block">
Filter registrations to just those spanning the entire period between
`start_date` and `end_date` _and_ where the practice has been using the SystmOne
EHR platform throughout that period (see
[`systmone_go_live_date`](#practice_registrations.practice_systmone_go_live_date)).
    <details markdown="block">
    <summary>View method definition</summary>
```py
return practice_registrations.spanning(start_date, end_date).where(
    practice_registrations.practice_systmone_go_live_date <= start_date
)

```
    </details>
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## sgss_covid_all_tests

COVID-19 tests results from SGSS (the Second Generation Surveillance System).

For background on this data see the NHS [DARS catalogue entry][DARS_SGSS].
And for more detail on SGSS in general see [UKHSA_Laboratory_Reporting_Guidelines.pdf][UKHSA_LRG].

[UKHSA_LRG]: https://assets.publishing.service.gov.uk/media/66e2e0ba0d913026165c3d77/UKHSA_Laboratory_reporting_guidelines_May_2023.pdf
[DARS_SGSS]: https://digital.nhs.uk/services/data-access-request-service-dars/dars-products-and-services/data-set-catalogue/covid-19-second-generation-surveillance-system-sgss
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="sgss_covid_all_tests.specimen_taken_date">
    <strong>specimen_taken_date</strong>
    <a class="headerlink" href="#sgss_covid_all_tests.specimen_taken_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date on which specimen was collected.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="sgss_covid_all_tests.is_positive">
    <strong>is_positive</strong>
    <a class="headerlink" href="#sgss_covid_all_tests.is_positive" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">
Whether the specimin tested positive for SARS-CoV-2.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="sgss_covid_all_tests.lab_report_date">
    <strong>lab_report_date</strong>
    <a class="headerlink" href="#sgss_covid_all_tests.lab_report_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date on which the labaratory reported the result.

 * Never `NULL`
  </dd>
</div>

<div markdown="block">
  <dt id="sgss_covid_all_tests.was_symptomatic">
    <strong>was_symptomatic</strong>
    <a class="headerlink" href="#sgss_covid_all_tests.was_symptomatic" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">
Whether the patient reported symptoms of COVID-19 at the time the specimen
was collected. May be NULL if unknown.

  </dd>
</div>

<div markdown="block">
  <dt id="sgss_covid_all_tests.sgtf_status">
    <strong>sgtf_status</strong>
    <a class="headerlink" href="#sgss_covid_all_tests.sgtf_status" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Provides information on whether a PCR test result exhibited "S-Gene Target
Failure" which can be used as a proxy for the presence of certain Variants
of Concern.

Results are provided as number between 0 and 9. We know the meaning of
_some_ of these numbers based on an email from PHE:

> 0: S gene detected<br>
> Detectable S gene (CH3>0)<br>
> Detectable y ORF1ab CT value (CH1) <=30 and >0<br>
> Detectable N gene CT value (CH2) <=30 and >0<br>
>
> 1: Isolate with confirmed SGTF<br>
> Undetectable S gene; CT value (CH3) =0<br>
> Detectable ORF1ab gene; CT value (CH2) <=30 and >0<br>
> Detectable N gene; CT value (CH1) <=30 and >0<br>
>
> 9: Cannot be classified
>
> Null are where the target is not S Gene. I think LFTs are currently
> also coming across as 9 so will need to review those to null as well as
> clearly this is a PCR only variable.

However the values 2, 4 and 8 also occur in this column and we don't
currently have documentation on their meaning.

 * Always >= 0 and <= 9
  </dd>
</div>

<div markdown="block">
  <dt id="sgss_covid_all_tests.variant">
    <strong>variant</strong>
    <a class="headerlink" href="#sgss_covid_all_tests.variant" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Where a specific SARS-CoV-2 variant was identified this column provides the details.

This appears to be effectively a free-text field with a large variety of
possible values. Some have an obvious meaning e.g. `B.1.617.2`,
`VOC-21JAN-02`, `VUI-21FEB-04`.

Others less so e.g. `VOC-22JAN-O1_probable:V-21OCT-01_low-qc`.

  </dd>
</div>

<div markdown="block">
  <dt id="sgss_covid_all_tests.variant_detection_method">
    <strong>variant_detection_method</strong>
    <a class="headerlink" href="#sgss_covid_all_tests.variant_detection_method" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Where a specific SARS-CoV-2 variant was identified this provides the method
used to do so.

 * Possible values: `Private Lab Sequencing`, `Reflex Assay`, `Sanger Provisional Result`
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## ukrr

The UK Renal Registry (UKRR) contains data on patients under secondary renal care
(advanced chronic kidney disease stages 4 and 5, dialysis, and kidney transplantation)
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="ukrr.dataset">
    <strong>dataset</strong>
    <a class="headerlink" href="#ukrr.dataset" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The cohort of patients.

Values are:

* '2019_prevalence' - a prevalence cohort of patients alive and on RRT in December 2019
* '2020_prevalence' - a prevalence cohort of patients alive and on RRT in December 2020
* '2021_prevalence' - a prevalence cohort of patients alive and on RRT in December 2021
* '2020_incidence' - an incidence cohort of patients who started RRT in 2020
* '2020_ckd' - a snapshot prevalence cohort of patient with Stage 4 or 5 CKD who were reported to the UKRR to be under renal care in December 2020.

 * Possible values: `2019_prevalence`, `2020_prevalence`, `2021_prevalence`, `2020_incidence`, `2020_ckd`
  </dd>
</div>

<div markdown="block">
  <dt id="ukrr.renal_centre">
    <strong>renal_centre</strong>
    <a class="headerlink" href="#ukrr.renal_centre" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The code of the main renal centre a patient is registered with

  </dd>
</div>

<div markdown="block">
  <dt id="ukrr.rrt_start_date">
    <strong>rrt_start_date</strong>
    <a class="headerlink" href="#ukrr.rrt_start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The latest start date for renal replacement therapy

  </dd>
</div>

<div markdown="block">
  <dt id="ukrr.latest_creatinine">
    <strong>latest_creatinine</strong>
    <a class="headerlink" href="#ukrr.latest_creatinine" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
Most recent creatinine held by UKRR

  </dd>
</div>

<div markdown="block">
  <dt id="ukrr.latest_egfr">
    <strong>latest_egfr</strong>
    <a class="headerlink" href="#ukrr.latest_egfr" title="Permanent link">🔗</a>
    <code>float</code>
  </dt>
  <dd markdown="block">
Most recent eGFR held by UKRR

  </dd>
</div>

<div markdown="block">
  <dt id="ukrr.treatment_modality_start">
    <strong>treatment_modality_start</strong>
    <a class="headerlink" href="#ukrr.treatment_modality_start" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The treatment modality at `rrt_start_date`.

Values such as ICHD, HHD, HD, PD, Tx.

  </dd>
</div>

<div markdown="block">
  <dt id="ukrr.treatment_modality_prevalence">
    <strong>treatment_modality_prevalence</strong>
    <a class="headerlink" href="#ukrr.treatment_modality_prevalence" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The treatment modality from the prevalence data

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## vaccinations

This table contains information on administered vaccinations,
identified using either the target disease (e.g., Influenza),
or the vaccine product name (e.g., Optaflu).
For more information about this table see the
"[Vaccinaton names in the OpenSAFELY-TPP database][vaccinations_1]" report.

Vaccinations that were administered at work or in a pharmacy might not be
included in this table.

[vaccinations_1]: https://reports.opensafely.org/reports/opensafely-tpp-vaccination-names/
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="vaccinations.vaccination_id">
    <strong>vaccination_id</strong>
    <a class="headerlink" href="#vaccinations.vaccination_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">
Vaccination identifier.

  </dd>
</div>

<div markdown="block">
  <dt id="vaccinations.date">
    <strong>date</strong>
    <a class="headerlink" href="#vaccinations.date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the vaccination was administered.

  </dd>
</div>

<div markdown="block">
  <dt id="vaccinations.target_disease">
    <strong>target_disease</strong>
    <a class="headerlink" href="#vaccinations.target_disease" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Vaccine's target disease.

  </dd>
</div>

<div markdown="block">
  <dt id="vaccinations.product_name">
    <strong>product_name</strong>
    <a class="headerlink" href="#vaccinations.product_name" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Vaccine's product name.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## wl_clockstops

National Waiting List Clock Stops

This dataset contains all completed referral-to-treatment (RTT) pathways with a "clock stop" date between May 2021 and May 2022.
Patients referred for non-emergency consultant-led treatment are on RTT pathways.
The "clock start" date is the date of the first referral that starts the pathway.
The "clock stop" date is when the patient either: receives treatment;
declines treatment;
enters a period of active monitoring;
no longer requires treatment;
or dies.
The time spent waiting is the difference in these two dates.

A patient may have multiple rows if they have multiple completed RTT pathways;
however, there is only one row per unique pathway.
Because referral identifiers aren't necessarily unique between hospitals,
unique RTT pathways can be identified using a combination of:

* `pseudo_organisation_code_patient_pathway_identifier_issuer`
* `pseudo_patient_pathway_identifier`
* `pseudo_referral_identifier`
* `referral_to_treatment_period_start_date`

For more information, see
"[Consultant-led Referral to Treatment Waiting Times Rules and Guidance][wl_clockstops_1]".

[wl_clockstops_1]: https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/rtt-guidance/
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="wl_clockstops.activity_treatment_function_code">
    <strong>activity_treatment_function_code</strong>
    <a class="headerlink" href="#wl_clockstops.activity_treatment_function_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The treatment function

 * Matches regular expression: `[a-zA-Z0-9]{3}`
  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.priority_type_code">
    <strong>priority_type_code</strong>
    <a class="headerlink" href="#wl_clockstops.priority_type_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The priority type.

Note that a small number of rows contain values which are not in the list
below. These are converted to NULL in this representation of the data. If
you need to access the original values, please see the corresponding [raw
table](raw.tpp.md#wl_clockstops).

 * Possible values: `routine`, `urgent`, `two week wait`
  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.pseudo_organisation_code_patient_pathway_identifier_issuer">
    <strong>pseudo_organisation_code_patient_pathway_identifier_issuer</strong>
    <a class="headerlink" href="#wl_clockstops.pseudo_organisation_code_patient_pathway_identifier_issuer" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.pseudo_patient_pathway_identifier">
    <strong>pseudo_patient_pathway_identifier</strong>
    <a class="headerlink" href="#wl_clockstops.pseudo_patient_pathway_identifier" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.pseudo_referral_identifier">
    <strong>pseudo_referral_identifier</strong>
    <a class="headerlink" href="#wl_clockstops.pseudo_referral_identifier" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.referral_request_received_date">
    <strong>referral_request_received_date</strong>
    <a class="headerlink" href="#wl_clockstops.referral_request_received_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the referral was received, for the referral that started the original pathway

  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.referral_to_treatment_period_end_date">
    <strong>referral_to_treatment_period_end_date</strong>
    <a class="headerlink" href="#wl_clockstops.referral_to_treatment_period_end_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Clock stop for the completed pathway

  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.referral_to_treatment_period_start_date">
    <strong>referral_to_treatment_period_start_date</strong>
    <a class="headerlink" href="#wl_clockstops.referral_to_treatment_period_start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Clock start for the completed pathway

  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.source_of_referral_for_outpatients">
    <strong>source_of_referral_for_outpatients</strong>
    <a class="headerlink" href="#wl_clockstops.source_of_referral_for_outpatients" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.waiting_list_type">
    <strong>waiting_list_type</strong>
    <a class="headerlink" href="#wl_clockstops.waiting_list_type" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The waiting list type on completion of the pathway.

Note that a small number of rows contain values which are not in the list
below. These are converted to NULL in this representation of the data. If
you need to access the original values, please see the corresponding [raw
table](raw.tpp.md#wl_clockstops).

 * Possible values: `ORTT`, `IRTT`, `PTLO`, `PTLI`, `RTTO`, `RTTI`
  </dd>
</div>

<div markdown="block">
  <dt id="wl_clockstops.week_ending_date">
    <strong>week_ending_date</strong>
    <a class="headerlink" href="#wl_clockstops.week_ending_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The Sunday of the week that the pathway relates to

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## wl_openpathways

National Waiting List Open Pathways

This dataset contains all people on open (incomplete) RTT or not current RTT (non-RTT) pathways as of May 2022.
It is a snapshot of everyone still awaiting treatment as of May 2022 (i.e., the clock hasn't stopped).
Patients referred for non-emergency consultant-led treatment are on RTT pathways,
while patients referred for non-consultant-led treatment are on non-RTT pathways.
For each pathway, there is one row for every week that the patient is still waiting.
Because referral identifiers aren't necessarily unique between hospitals,
unique RTT pathways can be identified using a combination of:

* `pseudo_organisation_code_patient_pathway_identifier_issuer`
* `pseudo_patient_pathway_identifier`
* `pseudo_referral_identifier`
* `referral_to_treatment_period_start_date`


For more information, see
"[Consultant-led Referral to Treatment Waiting Times Rules and Guidance][wl_openpathways_1]".

[wl_openpathways_1]: https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/rtt-guidance/
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="wl_openpathways.activity_treatment_function_code">
    <strong>activity_treatment_function_code</strong>
    <a class="headerlink" href="#wl_openpathways.activity_treatment_function_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The treatment function

 * Matches regular expression: `[a-zA-Z0-9]{3}`
  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.current_pathway_period_start_date">
    <strong>current_pathway_period_start_date</strong>
    <a class="headerlink" href="#wl_openpathways.current_pathway_period_start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Latest clock start for this pathway period

  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.priority_type_code">
    <strong>priority_type_code</strong>
    <a class="headerlink" href="#wl_openpathways.priority_type_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The priority type.

Note that a small number of rows contain values which are not in the list
below. These are converted to NULL in this representation of the data. If
you need to access the original values, please see the corresponding [raw
table](raw.tpp.md#wl_openpathways).

 * Possible values: `routine`, `urgent`, `two week wait`
  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.pseudo_organisation_code_patient_pathway_identifier_issuer">
    <strong>pseudo_organisation_code_patient_pathway_identifier_issuer</strong>
    <a class="headerlink" href="#wl_openpathways.pseudo_organisation_code_patient_pathway_identifier_issuer" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.pseudo_patient_pathway_identifier">
    <strong>pseudo_patient_pathway_identifier</strong>
    <a class="headerlink" href="#wl_openpathways.pseudo_patient_pathway_identifier" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.pseudo_referral_identifier">
    <strong>pseudo_referral_identifier</strong>
    <a class="headerlink" href="#wl_openpathways.pseudo_referral_identifier" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.referral_request_received_date">
    <strong>referral_request_received_date</strong>
    <a class="headerlink" href="#wl_openpathways.referral_request_received_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the referral was received, for the referral that started the original pathway

  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.referral_to_treatment_period_end_date">
    <strong>referral_to_treatment_period_end_date</strong>
    <a class="headerlink" href="#wl_openpathways.referral_to_treatment_period_end_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
If the pathway is open, then `NULL`

  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.referral_to_treatment_period_start_date">
    <strong>referral_to_treatment_period_start_date</strong>
    <a class="headerlink" href="#wl_openpathways.referral_to_treatment_period_start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Latest clock start for this pathway. If the pathway is not a current pathway, then `NULL`.

  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.source_of_referral">
    <strong>source_of_referral</strong>
    <a class="headerlink" href="#wl_openpathways.source_of_referral" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
National referral source code for the referral that created the original pathway

 * Matches regular expression: `[a-zA-Z0-9]{2}`
  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.waiting_list_type">
    <strong>waiting_list_type</strong>
    <a class="headerlink" href="#wl_openpathways.waiting_list_type" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
The waiting list type.

Note that a small number of rows contain values which are not in the list
below. These are converted to NULL in this representation of the data. If
you need to access the original values, please see the corresponding [raw
table](raw.tpp.md#wl_openpathways).

 * Possible values: `ORTT`, `IRTT`, `ONON`, `INON`, `PTLO`, `PTLI`, `RTTO`, `RTTI`
  </dd>
</div>

<div markdown="block">
  <dt id="wl_openpathways.week_ending_date">
    <strong>week_ending_date</strong>
    <a class="headerlink" href="#wl_openpathways.week_ending_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The Sunday of the week that the pathway relates to

  </dd>
</div>

  </dl>
</div>
