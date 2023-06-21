# <strong>beta.tpp</strong> schema

Available on backends: [**TPP**](../../backends#tpp)

This defines all the data (both primary care and externally linked) available in the TPP
backend.

``` {.python .copy title='To use this schema in an ehrQL file:'}
from ehrql.tables.beta.tpp import (
    addresses,
    appointments,
    clinical_events,
    emergency_care_attendances,
    hospital_admissions,
    household_memberships_2020,
    isaric_raw,
    medications,
    occupation_on_covid_vaccine_record,
    ons_cis,
    ons_deaths,
    open_prompt,
    patients,
    practice_registrations,
    sgss_covid_all_tests,
    vaccinations,
)
```

<p class="dimension-indicator"><code>many rows per patient</code></p>
## addresses


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


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.start_date">
    <strong>start_date</strong>
    <a class="headerlink" href="#addresses.start_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.end_date">
    <strong>end_date</strong>
    <a class="headerlink" href="#addresses.end_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.address_type">
    <strong>address_type</strong>
    <a class="headerlink" href="#addresses.address_type" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.rural_urban_classification">
    <strong>rural_urban_classification</strong>
    <a class="headerlink" href="#addresses.rural_urban_classification" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.imd_rounded">
    <strong>imd_rounded</strong>
    <a class="headerlink" href="#addresses.imd_rounded" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.msoa_code">
    <strong>msoa_code</strong>
    <a class="headerlink" href="#addresses.msoa_code" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


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


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.care_home_is_potential_match">
    <strong>care_home_is_potential_match</strong>
    <a class="headerlink" href="#addresses.care_home_is_potential_match" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.care_home_requires_nursing">
    <strong>care_home_requires_nursing</strong>
    <a class="headerlink" href="#addresses.care_home_requires_nursing" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="addresses.care_home_does_not_require_nursing">
    <strong>care_home_does_not_require_nursing</strong>
    <a class="headerlink" href="#addresses.care_home_does_not_require_nursing" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">


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
    case(when(addresses.has_postcode).then(1), default=0),
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
## appointments

You can find out more about this table in the associated short data report:
<https://github.com/opensafely/appointments-short-data-report>.
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

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## clinical_events


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

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## emergency_care_attendances


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


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.arrival_date">
    <strong>arrival_date</strong>
    <a class="headerlink" href="#emergency_care_attendances.arrival_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.discharge_destination">
    <strong>discharge_destination</strong>
    <a class="headerlink" href="#emergency_care_attendances.discharge_destination" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_01">
    <strong>diagnosis_01</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_01" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_02">
    <strong>diagnosis_02</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_02" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_03">
    <strong>diagnosis_03</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_03" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_04">
    <strong>diagnosis_04</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_04" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_05">
    <strong>diagnosis_05</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_05" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_06">
    <strong>diagnosis_06</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_06" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_07">
    <strong>diagnosis_07</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_07" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_08">
    <strong>diagnosis_08</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_08" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_09">
    <strong>diagnosis_09</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_09" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_10">
    <strong>diagnosis_10</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_10" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_11">
    <strong>diagnosis_11</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_11" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_12">
    <strong>diagnosis_12</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_12" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_13">
    <strong>diagnosis_13</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_13" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_14">
    <strong>diagnosis_14</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_14" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_15">
    <strong>diagnosis_15</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_15" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_16">
    <strong>diagnosis_16</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_16" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_17">
    <strong>diagnosis_17</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_17" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_18">
    <strong>diagnosis_18</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_18" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_19">
    <strong>diagnosis_19</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_19" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_20">
    <strong>diagnosis_20</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_20" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_21">
    <strong>diagnosis_21</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_21" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_22">
    <strong>diagnosis_22</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_22" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_23">
    <strong>diagnosis_23</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_23" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="emergency_care_attendances.diagnosis_24">
    <strong>diagnosis_24</strong>
    <a class="headerlink" href="#emergency_care_attendances.diagnosis_24" title="Permanent link">🔗</a>
    <code>SNOMED-CT code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## hospital_admissions


<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="hospital_admissions.id">
    <strong>id</strong>
    <a class="headerlink" href="#hospital_admissions.id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="hospital_admissions.admission_date">
    <strong>admission_date</strong>
    <a class="headerlink" href="#hospital_admissions.admission_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="hospital_admissions.discharge_date">
    <strong>discharge_date</strong>
    <a class="headerlink" href="#hospital_admissions.discharge_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="hospital_admissions.admission_method">
    <strong>admission_method</strong>
    <a class="headerlink" href="#hospital_admissions.admission_method" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="hospital_admissions.all_diagnoses">
    <strong>all_diagnoses</strong>
    <a class="headerlink" href="#hospital_admissions.all_diagnoses" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="hospital_admissions.patient_classification">
    <strong>patient_classification</strong>
    <a class="headerlink" href="#hospital_admissions.patient_classification" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="hospital_admissions.days_in_critical_care">
    <strong>days_in_critical_care</strong>
    <a class="headerlink" href="#hospital_admissions.days_in_critical_care" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="hospital_admissions.primary_diagnoses">
    <strong>primary_diagnoses</strong>
    <a class="headerlink" href="#hospital_admissions.primary_diagnoses" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


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
## isaric_raw

A subset of the ISARIC data.

These columns are deliberately all taken as strings while in a preliminary phase.
They will later change to more appropriate data types.

Descriptions taken from: [CCP_REDCap_ISARIC_data_dictionary_codebook.pdf][isaric_ddc_pdf]

[isaric_ddc_pdf]: https://github.com/isaric4c/wiki/blob/d6b87d59a277cf2f6deedeb5e8c1a970dbb970a3/ISARIC/CCP_REDCap_ISARIC_data_dictionary_codebook.pdf
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="isaric_raw.age">
    <strong>age</strong>
    <a class="headerlink" href="#isaric_raw.age" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Age

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.age_factor">
    <strong>age_factor</strong>
    <a class="headerlink" href="#isaric_raw.age_factor" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
TODO

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.calc_age">
    <strong>calc_age</strong>
    <a class="headerlink" href="#isaric_raw.calc_age" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Calculated age (comparing date of birth with date of enrolment). May be inaccurate if a date of February 29 is used.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.sex">
    <strong>sex</strong>
    <a class="headerlink" href="#isaric_raw.sex" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Sex at birth.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___1">
    <strong>ethnic___1</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___1" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: Arab.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___2">
    <strong>ethnic___2</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___2" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: Black.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___3">
    <strong>ethnic___3</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___3" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: East Asian.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___4">
    <strong>ethnic___4</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___4" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: South Asian.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___5">
    <strong>ethnic___5</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___5" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: West Asian.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___6">
    <strong>ethnic___6</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___6" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: Latin American.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___7">
    <strong>ethnic___7</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___7" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: White.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___8">
    <strong>ethnic___8</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___8" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: Aboriginal/First Nations.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___9">
    <strong>ethnic___9</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___9" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: Other.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.ethnic___10">
    <strong>ethnic___10</strong>
    <a class="headerlink" href="#isaric_raw.ethnic___10" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Ethnic group: N/A.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.covid19_vaccine">
    <strong>covid19_vaccine</strong>
    <a class="headerlink" href="#isaric_raw.covid19_vaccine" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Has the patient received a Covid-19 vaccine (open label licenced product)?

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.covid19_vaccined">
    <strong>covid19_vaccined</strong>
    <a class="headerlink" href="#isaric_raw.covid19_vaccined" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date first vaccine given (Covid-19) if known.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.covid19_vaccine2d">
    <strong>covid19_vaccine2d</strong>
    <a class="headerlink" href="#isaric_raw.covid19_vaccine2d" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date second vaccine given (Covid-19) if known.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.covid19_vaccined_nk">
    <strong>covid19_vaccined_nk</strong>
    <a class="headerlink" href="#isaric_raw.covid19_vaccined_nk" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
First vaccine given (Covid-19) but date not known.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.corona_ieorres">
    <strong>corona_ieorres</strong>
    <a class="headerlink" href="#isaric_raw.corona_ieorres" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Suspected or proven infection with pathogen of public health interest.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.coriona_ieorres2">
    <strong>coriona_ieorres2</strong>
    <a class="headerlink" href="#isaric_raw.coriona_ieorres2" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Proven or high likelihood of infection with pathogen of public health interest.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.coriona_ieorres3">
    <strong>coriona_ieorres3</strong>
    <a class="headerlink" href="#isaric_raw.coriona_ieorres3" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Proven infection with pathogen of public health interest.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.inflammatory_mss">
    <strong>inflammatory_mss</strong>
    <a class="headerlink" href="#isaric_raw.inflammatory_mss" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Adult or child who meets case definition for inflammatory multi-system syndrome (MIS-C/MIS-A).

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.cestdat">
    <strong>cestdat</strong>
    <a class="headerlink" href="#isaric_raw.cestdat" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Onset date of first/earliest symptom.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.chrincard">
    <strong>chrincard</strong>
    <a class="headerlink" href="#isaric_raw.chrincard" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Chronic cardiac disease, including congenital heart disease (not hypertension).

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.hypertension_mhyn">
    <strong>hypertension_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.hypertension_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Hypertension (physician diagnosed).

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.chronicpul_mhyn">
    <strong>chronicpul_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.chronicpul_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Chronic pulmonary disease (not asthma).

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.asthma_mhyn">
    <strong>asthma_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.asthma_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Asthma (physician diagnosed).

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.renal_mhyn">
    <strong>renal_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.renal_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Chronic kidney disease.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.mildliver">
    <strong>mildliver</strong>
    <a class="headerlink" href="#isaric_raw.mildliver" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Mild liver disease.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.modliv">
    <strong>modliv</strong>
    <a class="headerlink" href="#isaric_raw.modliv" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Moderate or severe liver disease

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.chronicneu_mhyn">
    <strong>chronicneu_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.chronicneu_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Chronic neurological disorder.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.malignantneo_mhyn">
    <strong>malignantneo_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.malignantneo_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Malignant neoplasm.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.chronichaemo_mhyn">
    <strong>chronichaemo_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.chronichaemo_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Chronic haematologic disease.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.aidshiv_mhyn">
    <strong>aidshiv_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.aidshiv_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
AIDS/HIV.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.obesity_mhyn">
    <strong>obesity_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.obesity_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Obesity (as defined by clinical staff).

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.diabetes_type_mhyn">
    <strong>diabetes_type_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.diabetes_type_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Diabetes and type.

 * Possible values: `NO`, `1`, `2`, `N/K`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.diabetescom_mhyn">
    <strong>diabetescom_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.diabetescom_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Diabetes with complications.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.diabetes_mhyn">
    <strong>diabetes_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.diabetes_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Diabetes without complications.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.rheumatologic_mhyn">
    <strong>rheumatologic_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.rheumatologic_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Rheumatologic disorder.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.dementia_mhyn">
    <strong>dementia_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.dementia_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Dementia.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.malnutrition_mhyn">
    <strong>malnutrition_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.malnutrition_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Malnutrition.

 * Possible values: `YES`, `NO`, `Unknown`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.smoking_mhyn">
    <strong>smoking_mhyn</strong>
    <a class="headerlink" href="#isaric_raw.smoking_mhyn" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Smoking.

 * Possible values: `Yes`, `Never Smoked`, `Former Smoker`, `N/K`
  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.hostdat">
    <strong>hostdat</strong>
    <a class="headerlink" href="#isaric_raw.hostdat" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Admission date at this facility.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.hooccur">
    <strong>hooccur</strong>
    <a class="headerlink" href="#isaric_raw.hooccur" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Transfer from other facility?

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.hostdat_transfer">
    <strong>hostdat_transfer</strong>
    <a class="headerlink" href="#isaric_raw.hostdat_transfer" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Admission date at previous facility.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.hostdat_transfernk">
    <strong>hostdat_transfernk</strong>
    <a class="headerlink" href="#isaric_raw.hostdat_transfernk" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Admission date at previous facility not known.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.readm_cov19">
    <strong>readm_cov19</strong>
    <a class="headerlink" href="#isaric_raw.readm_cov19" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">
Is the patient being readmitted with Covid-19?

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.dsstdat">
    <strong>dsstdat</strong>
    <a class="headerlink" href="#isaric_raw.dsstdat" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Date of enrolment.

  </dd>
</div>

<div markdown="block">
  <dt id="isaric_raw.dsstdtc">
    <strong>dsstdtc</strong>
    <a class="headerlink" href="#isaric_raw.dsstdtc" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
Outcome date.

  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## medications


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

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## occupation_on_covid_vaccine_record


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


<p class="dimension-indicator"><code>many rows per patient</code></p>
## ons_cis

Data from the ONS Covid Infection Survey.
<div markdown="block" class="definition-list-wrapper">
  <div class="title">Columns</div>
  <dl markdown="block">
<div markdown="block">
  <dt id="ons_cis.visit_date">
    <strong>visit_date</strong>
    <a class="headerlink" href="#ons_cis.visit_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_cis.visit_num">
    <strong>visit_num</strong>
    <a class="headerlink" href="#ons_cis.visit_num" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_cis.is_opted_out_of_nhs_data_share">
    <strong>is_opted_out_of_nhs_data_share</strong>
    <a class="headerlink" href="#ons_cis.is_opted_out_of_nhs_data_share" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_cis.last_linkage_dt">
    <strong>last_linkage_dt</strong>
    <a class="headerlink" href="#ons_cis.last_linkage_dt" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_cis.imd_decile_e">
    <strong>imd_decile_e</strong>
    <a class="headerlink" href="#ons_cis.imd_decile_e" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_cis.imd_quartile_e">
    <strong>imd_quartile_e</strong>
    <a class="headerlink" href="#ons_cis.imd_quartile_e" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_cis.rural_urban">
    <strong>rural_urban</strong>
    <a class="headerlink" href="#ons_cis.rural_urban" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## ons_deaths


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


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.place">
    <strong>place</strong>
    <a class="headerlink" href="#ons_deaths.place" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


 * Possible values: `Care Home`, `Elsewhere`, `Home`, `Hospice`, `Hospital`, `Other communal establishment`
  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_01">
    <strong>cause_of_death_01</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_01" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_02">
    <strong>cause_of_death_02</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_02" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_03">
    <strong>cause_of_death_03</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_03" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_04">
    <strong>cause_of_death_04</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_04" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_05">
    <strong>cause_of_death_05</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_05" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_06">
    <strong>cause_of_death_06</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_06" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_07">
    <strong>cause_of_death_07</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_07" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_08">
    <strong>cause_of_death_08</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_08" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_09">
    <strong>cause_of_death_09</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_09" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_10">
    <strong>cause_of_death_10</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_10" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_11">
    <strong>cause_of_death_11</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_11" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_12">
    <strong>cause_of_death_12</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_12" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_13">
    <strong>cause_of_death_13</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_13" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_14">
    <strong>cause_of_death_14</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_14" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="ons_deaths.cause_of_death_15">
    <strong>cause_of_death_15</strong>
    <a class="headerlink" href="#ons_deaths.cause_of_death_15" title="Permanent link">🔗</a>
    <code>ICD-10 code</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## open_prompt

This table contains responses to questions from the OpenPROMPT project.

You can find out more about this table in the associated short data report:
<https://github.com/opensafely/airmid-short-data-report>.
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
The response to the question, as a CTV3 code. Alternatively, if the question admits a number as the response, then the question, as a CTV3 code.

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
The response to the question, as a SNOMED CT code, for responses where the CTV3 code has a corresponding SNOMED CT code. Alternatively, if the question admits a number as the response, then the question, as a SNOMED CT code, for questions where the CTV3 code has a corresponding SNOMED CT code.

  </dd>
</div>

<div markdown="block">
  <dt id="open_prompt.consultation_date">
    <strong>consultation_date</strong>
    <a class="headerlink" href="#open_prompt.consultation_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">
The date the survey was administered

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
The response to the question, as a number. Alternatively, if the question admits a code as the response, then zero.

 * Never `NULL`
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>one row per patient</code></p>
## patients


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
Patient's date of birth, rounded to first of month.

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
the supplied date.

Note that this takes no account of whether the patient is alive at the given
date. In particular, it may return negative values if the date is before the
patient's date of birth.
    <details markdown="block">
    <summary>View method definition</summary>
```py
return (date - patients.date_of_birth).years

```
    </details>
  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## practice_registrations


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


  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.end_date">
    <strong>end_date</strong>
    <a class="headerlink" href="#practice_registrations.end_date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.practice_pseudo_id">
    <strong>practice_pseudo_id</strong>
    <a class="headerlink" href="#practice_registrations.practice_pseudo_id" title="Permanent link">🔗</a>
    <code>integer</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="practice_registrations.practice_stp">
    <strong>practice_stp</strong>
    <a class="headerlink" href="#practice_registrations.practice_stp" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


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
duration. If there's stil an exact tie we choose arbitrarily based on the
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

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## sgss_covid_all_tests


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


  </dd>
</div>

<div markdown="block">
  <dt id="sgss_covid_all_tests.is_positive">
    <strong>is_positive</strong>
    <a class="headerlink" href="#sgss_covid_all_tests.is_positive" title="Permanent link">🔗</a>
    <code>boolean</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

  </dl>
</div>


<p class="dimension-indicator"><code>many rows per patient</code></p>
## vaccinations


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


  </dd>
</div>

<div markdown="block">
  <dt id="vaccinations.date">
    <strong>date</strong>
    <a class="headerlink" href="#vaccinations.date" title="Permanent link">🔗</a>
    <code>date</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="vaccinations.target_disease">
    <strong>target_disease</strong>
    <a class="headerlink" href="#vaccinations.target_disease" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

<div markdown="block">
  <dt id="vaccinations.product_name">
    <strong>product_name</strong>
    <a class="headerlink" href="#vaccinations.product_name" title="Permanent link">🔗</a>
    <code>string</code>
  </dt>
  <dd markdown="block">


  </dd>
</div>

  </dl>
</div>
