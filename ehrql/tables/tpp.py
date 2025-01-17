"""
This schema defines the data (both primary care and externally linked) available in the
OpenSAFELY-TPP backend. For more information about this backend, see
"[SystmOne Primary Care](https://docs.opensafely.org/data-sources/systmone/)".
"""

import datetime

import ehrql.tables.core
from ehrql import case, when
from ehrql.codes import (
    CTV3Code,
    ICD10Code,
    ICD10MultiCodeString,
    OPCS4Code,
    OPCS4MultiCodeString,
    SNOMEDCTCode,
)
from ehrql.tables import Constraint, EventFrame, PatientFrame, Series, table
from ehrql.tables.core import patients


__all__ = [
    "addresses",
    "apcs",
    "apcs_cost",
    "appointments",
    "clinical_events",
    "clinical_events_ranges",
    "covid_therapeutics",
    "decision_support_values",
    "ec",
    "ec_cost",
    "emergency_care_attendances",
    "ethnicity_from_sus",
    "household_memberships_2020",
    "medications",
    "occupation_on_covid_vaccine_record",
    "ons_deaths",
    "opa",
    "opa_cost",
    "opa_diag",
    "opa_proc",
    "open_prompt",
    "parents",
    "patients",
    "practice_registrations",
    "sgss_covid_all_tests",
    "ukrr",
    "vaccinations",
    "wl_clockstops",
    "wl_openpathways",
]


@table
class addresses(EventFrame):
    """
    Geographic characteristics of the home address a patient registers with a practice.
    Each row in this table is one registration period per patient.
    Occasionally, a patient has multiple active registrations on a given date.
    The postcode from the address is mapped to an Output Area,
    from which other larger geographic representations can be derived
    (see various [ONS publications][addresses_ukgeographies] for more detail).

    [addresses_ukgeographies]: https://www.ons.gov.uk/methodology/geography/ukgeographies

    [Example ehrQL usage of addresses](../../../how-to/examples/#addresses)
    """

    address_id = Series(
        int,
        description="Unique address identifier.",
    )
    start_date = Series(
        datetime.date,
        description="Date patient moved to address.",
    )
    end_date = Series(
        datetime.date,
        description="Date patient moved out of address.",
    )
    address_type = Series(
        int,
        description="""
            Type of address:

            * 0 - Permanent
            * 1 - Temporary
            * 3 - Correspondence only
        """,
        constraints=[Constraint.Categorical([0, 1, 3])],
    )
    rural_urban_classification = Series(
        int,
        description="""
            Rural urban classification:

            * 1 - Urban major conurbation
            * 2 - Urban minor conurbation
            * 3 - Urban city and town
            * 4 - Urban city and town in a sparse setting
            * 5 - Rural town and fringe
            * 6 - Rural town and fringe in a sparse setting
            * 7 - Rural village and dispersed
            * 8 - Rural village and dispersed in a sparse setting
        """,
        constraints=[Constraint.ClosedRange(1, 8)],
    )
    imd_rounded = Series(
        int,
        description="""
            [Index of Multiple Deprivation][addresses_imd] (IMD)
            rank of each lower layer super output area (LSOA), rounded to the nearest 100, where
            lower values represent more deprived areas. E.g. 1 is the most deprived LSOA in the country
            and 32,844 is the least deprived (though in this field these are rounded to 0 and 32,800
            respectively)

            [addresses_imd]: https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019
        """,
        constraints=[Constraint.ClosedRange(0, 32_800, 100)],
    )

    @property
    def imd_quintile(self) -> str:
        """
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
        """
        imd = self.imd_rounded
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

    @property
    def imd_decile(self) -> str:
        """
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
        """
        imd = self.imd_rounded
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

    msoa_code = Series(
        str,
        description="Middle Layer Super Output Areas (MSOA) code.",
        constraints=[Constraint.Regex("E020[0-9]{5}")],
    )
    has_postcode = Series(
        bool,
        description="Indicating whether a valid postcode is recorded for the patient.",
    )
    # Is the address potentially a match for a care home? (Using TPP's algorithm)
    care_home_is_potential_match = Series(
        bool,
        description="Indicating whether the patient's address matched with a care home, using TPP's algorithm.",
    )
    # These two fields look like they should be a single boolean, but this is how
    # they're represented in the data
    care_home_requires_nursing = Series(
        bool,
        description="Indicating whether the patient's address matched with a care home that required nursing.",
    )
    care_home_does_not_require_nursing = Series(
        bool,
        description="Indicating whether the patient's address matched with a care home that did not require nursing.",
    )

    def for_patient_on(self, date):
        """
        Return each patient's registered address as it was on the supplied date.

        Where there are multiple registered addresses we prefer any which have a known
        postcode (though we never have access to this postcode) as this is used by TPP
        to cross-reference other data associated with the address, such as the MSOA or
        index of multiple deprevation.

        Where there are multiple of these we prefer the most recently registered address
        and then, if there are multiple of these, the one with the longest duration. If
        there's stil an exact tie we choose arbitrarily based on the address ID.
        """
        spanning_addrs = self.where(self.start_date <= date).except_where(
            self.end_date < date
        )
        ordered_addrs = spanning_addrs.sort_by(
            case(when(self.has_postcode).then(1), otherwise=0),
            self.start_date,
            self.end_date,
            self.address_id,
        )
        return ordered_addrs.last_for_patient()


@table
class apcs(EventFrame):
    """
    Admitted Patient Care Spells (APCS) data is provided via the NHS Secondary Uses Service.

    This table gives core details of spells.

    Each row is an in-hospital spell: a period of continuous care within a single trust.

    Refer to the [OpenSAFELY documentation on the APCS data source][apcs_data_source_docs]
    and the [GitHub issue discussing more of the background context][apcs_context_issue].

    [apcs_data_source_docs]: https://docs.opensafely.org/data-sources/apc/
    [apcs_context_issue]: https://github.com/opensafely-core/cohort-extractor/issues/186

    [Example ehrQL usage of apcs](../../../how-to/examples/#admitted-patient-care-spells-apcs)
    """

    apcs_ident = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the spell used across the APCS tables.",
    )
    admission_date = Series(
        datetime.date,
        description="The admission date of the hospital provider spell.",
    )
    discharge_date = Series(
        datetime.date,
        description="The date of discharge from a hospital provider spell.",
    )
    spell_core_hrg_sus = Series(
        str,
        description=(
            "The core Healthcare Resource Group (HRG) code for the spell "
            "according to the derivations made by NHS Digital "
            "prior to import to the National Commissioning Data Repository (NCDR). "
            "HRGs are used to assign baseline tariff costs."
        ),
    )
    admission_method = Series(
        str,
        description=(
            "Code identifying admission method. "
            "Refer to [APCS data source documentation](https://docs.opensafely.org/data-sources/apc/) "
            "for details of codes."
        ),
    )
    primary_diagnosis = Series(
        ICD10Code,
        description=(
            "Code indicating primary diagnosis. "
            "This is not necessarily the primary reason for admission, "
            "and could represent an escalation/complication of initial reason for admission."
        ),
    )
    secondary_diagnosis = Series(
        ICD10Code,
        description=(
            "Code indicating secondary diagnosis. "
            "This is a single code giving the first listed secondary diagnosis, "
            "but there may other secondary diagnoses listed in the `all_diagnoses` "
            "field below."
        ),
    )
    all_diagnoses = Series(
        ICD10MultiCodeString,
        description="""
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
        """,
    )
    all_procedures = Series(
        OPCS4MultiCodeString,
        description="""
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
        """,
    )
    days_in_critical_care = Series(
        int,
        description=(
            "Number of days spent in critical care. "
            "This is counted in number of days (or part-days) "
            'not the number of nights as per normal "length of stay" calculations. '
            "Note the definition of critical care may vary between trusts. "
        ),
    )
    patient_classification = Series(
        str,
        description=(
            "Refer to [APCS data source documentation](https://docs.opensafely.org/data-sources/apc/) "
            "for details."
        ),
    )


@table
class apcs_cost(EventFrame):
    """
    Admitted Patient Care Spells (APCS) data is provided via the NHS Secondary Uses Service.

    This table gives details of spell cost.

    Each row is an in-hospital spell: a period of continuous care within a single trust.

    Note that data only goes back a couple of years.
    """

    apcs_ident = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the spell used across the APCS tables.",
    )
    grand_total_payment_mff = Series(
        float,
        description=(
            "The grand total payment for the activity (`Net_SLA_Payment + Tariff_MFF_Payment`) "
            "where SLA = service level agreement, "
            "i.e. all contractual payments which is national tariff for the type of activity "
            "**plus** any additional payments **minus** any applicable deductions. "
            "MFF = Market Forces Factor, a geography-based cost adjustment)."
        ),
    )
    tariff_initial_amount = Series(
        float,
        description="The base national tariff.",
    )
    tariff_total_payment = Series(
        float,
        description="The total payment according to the national tariff.",
    )
    admission_date = Series(
        datetime.date,
        description="The admission date of the hospital provider spell.",
    )
    discharge_date = Series(
        datetime.date,
        description="The date of discharge from a hospital provider spell.",
    )


@table
class appointments(EventFrame):
    """
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
    """

    booked_date = Series(
        datetime.date,
        description="The date the appointment was booked",
    )
    start_date = Series(
        datetime.date,
        description="The date the appointment was due to start",
    )
    seen_date = Series(
        datetime.date,
        description="The date the patient was seen",
    )
    status = Series(
        str,
        description="The status of the appointment",
        constraints=[
            Constraint.Categorical(
                [
                    "Booked",
                    "Arrived",
                    "Did Not Attend",
                    "In Progress",
                    "Finished",
                    "Requested",
                    "Blocked",
                    "Visit",
                    "Waiting",
                    "Cancelled by Patient",
                    "Cancelled by Unit",
                    "Cancelled by Other Service",
                    "No Access Visit",
                    "Cancelled Due To Death",
                    "Patient Walked Out",
                ]
            )
        ],
    )


@table
class clinical_events(EventFrame):
    """
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
    """

    date = Series(datetime.date)
    snomedct_code = Series(SNOMEDCTCode)
    ctv3_code = Series(CTV3Code)
    numeric_value = Series(float)
    consultation_id = Series(
        int,
        description=(
            "ID of the [consultation](#appointments-vs-consultations) associated with this event"
        ),
    )


@table
class clinical_events_ranges(EventFrame):
    """
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

    """

    date = Series(datetime.date)
    snomedct_code = Series(SNOMEDCTCode)
    ctv3_code = Series(CTV3Code)
    numeric_value = Series(float)
    lower_bound = Series(
        float,
        description="""
            The lower bound of the reference range associated with an event's
            numeric_value
        """,
    )
    upper_bound = Series(
        float,
        description="""
            The upper bound of the reference range associated with an event's
            numeric_value
        """,
    )
    comparator = Series(
        str,
        description="""
            If an event's numeric_value is returned with a comparator, e.g. as '<9.5',
            then this column contains that comparator
        """,
        constraints=[
            Constraint.Categorical(
                [
                    "~",
                    "=",
                    ">=",
                    ">",
                    "<",
                    "<=",
                ]
            )
        ],
    )
    consultation_id = Series(
        int,
        description=(
            "ID of the [consultation](#appointments-vs-consultations) associated with this event"
        ),
    )


@table
class covid_therapeutics(EventFrame):
    """
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
    """

    covid_indication = Series(
        str,
        description="Treatment setting/indication.",
        constraints=[
            Constraint.Categorical(
                ["non_hospitalised", "hospitalised_with", "hospital_onset"]
            )
        ],
    )
    current_status = Series(
        str,
        description="Status of form/application.",
        constraints=[
            Constraint.Categorical(
                [
                    "Approved",
                    "Treatment Complete",
                    "Treatment Not Started",
                    "Treatment Stopped",
                ]
            )
        ],
    )
    intervention = Series(
        str,
        description="""
            Intervention or therapeutic name. Expected to be one of:

             * Baricitinib
             * Casirivimab and imdevimab
             * Molnupiravir
             * Paxlovid
             * Remdesivir
             * sarilumab (sic)
             * Sotrovimab
             * Tocilizumab
        """,
    )
    received = Series(
        datetime.date,
        description="Date form submitted.",
    )
    region = Series(
        str,
        description="""
            NHS England region in which the CMDU submitting the form is located.
        """,
    )
    risk_cohort = Series(
        str,
        description="""
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
        """,
    )
    treatment_start_date = Series(
        datetime.date,
        description="""
            Entered by the clinician and can represent either a future planned start
            date or a past date at the time of form submission.
        """,
    )


@table
class decision_support_values(EventFrame):
    """
    Returns values computed by decision support algorithms, for example the
    [Electronic Frailty Index (EFI)][efi_ref]

    [efi_ref]: https://www.england.nhs.uk/ourwork/clinical-policy/older-people/frailty/efi/

    """

    calculation_date = Series(
        datetime.date,
        description="Date of calculation for the decision support algorithm.",
    )
    numeric_value = Series(
        float,
        description="The value computed by the decision support algorithm",
    )
    algorithm_description = Series(
        str, description="The description of the decision support algorithm."
    )
    algorithm_version = Series(
        str, description="The version of the decision support algorithm."
    )

    def electronic_frailty_index(self):
        """
        Returns every calculated electronic frailty index v1 (EFI) for each patient.
        """
        return self.where(
            self.algorithm_description == "UK Electronic Frailty Index (eFI)"
        ).where(self.algorithm_version == "1.0")


@table
class ec(EventFrame):
    """
    Emergency care attendances data — the Emergency Care Data Set (ECDS) —
    is provided via the NHS Secondary Uses Service.

    This table gives core details of attendances.

    Refer to the [OpenSAFELY documentation on the ECDS data source][ecds_data_source_docs]
    and the GitHub issue that [discusses more of the background context][ecds_context_issue].

    [ecds_data_source_docs]: https://docs.opensafely.org/data-sources/ecds/
    [ecds_context_issue]: https://github.com/opensafely-core/cohort-extractor/issues/182
    """

    ec_ident = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the attendance used across the EC tables.",
    )
    arrival_date = Series(
        datetime.date,
        description=(
            "The date the patient self presented at the accident & emergency department, "
            "or arrived in an ambulance at the accident & emergency department."
        ),
    )
    sus_hrg_code = Series(
        str,
        description=(
            "The core Healthcare Resource Group (HRG) code derived by sus+, "
            "used for tariff application."
        ),
        # For the format of an HRG code, see:
        # https://en.wikipedia.org/wiki/Healthcare_Resource_Group
        constraints=[Constraint.Regex(r"[a-zA-Z]{2}[0-9]{2}[a-zA-Z]")],
    )


@table
class ec_cost(EventFrame):
    """
    Emergency care attendances data is provided via the NHS Secondary Uses Service.

    This table gives details of attendance costs.
    """

    ec_ident = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the attendance used across the EC tables.",
    )
    grand_total_payment_mff = Series(
        float,
        description=(
            "The grand total payment for the activity (`Net_SLA_Payment + Tariff_MFF_Payment`) "
            "where SLA = service level agreement, "
            "i.e. all contractual payments which is national tariff for the type of activity "
            "**plus** any additional payments **minus** any applicable deductions. "
            "MFF = Market Forces Factor, a geography-based cost adjustment)."
        ),
    )
    tariff_total_payment = Series(
        float,
        description="The total payment according to the national tariff.",
    )
    arrival_date = Series(
        datetime.date,
        description=(
            "The date the patient self presented at the accident & emergency department, "
            "or arrived in an ambulance at the accident & emergency department."
        ),
    )
    ec_decision_to_admit_date = Series(
        datetime.date,
        description="The date a decision to admit was made (if applicable).",
    )
    ec_injury_date = Series(
        datetime.date,
        description="The date the patient was injured (if applicable).",
    )


eca_diagnosis_description = (
    "The SNOMED CT concept ID which is used to identify the patient diagnosis. "
    "Note that only a limited subset of SNOMED CT codes are used; "
    "see the [NHS Data Model and Dictionary entry for emergency care diagnosis]"
    "(https://www.datadictionary.nhs.uk/data_elements/emergency_care_diagnosis__snomed_ct_.html)."
)


@table
class emergency_care_attendances(EventFrame):
    """
    Emergency care attendances data is provided via the NHS Secondary Uses Service.

    This table gives details of attendances.

    Note that there is a limited number of diagnoses allowed within this dataset,
    and so will not match with the range of diagnoses allowed in other datasets
    such as the primary care record.
    """

    id = Series(  # noqa: A003
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the attendance used across the EC tables.",
    )
    arrival_date = Series(
        datetime.date,
        description=(
            "The date the patient self presented at the accident & emergency department, "
            "or arrived in an ambulance at the accident & emergency department."
        ),
    )
    discharge_destination = Series(
        SNOMEDCTCode,
        description=(
            "The SNOMED CT concept ID which is used to identify "
            "the intended destination of the patient following discharge "
            "from the emergency care department."
        ),
    )
    # TODO: Revisit this when we have support for multi-valued fields
    # The diagnosis columns are have identical descriptions
    # and there are many of them,
    # so set them programmatically instead of by hand
    # UPDATE: changed to by hand so that autocomplete works
    diagnosis_01 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_02 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_03 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_04 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_05 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_06 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_07 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_08 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_09 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_10 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_11 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_12 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_13 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_14 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_15 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_16 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_17 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_18 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_19 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_20 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_21 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_22 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_23 = Series(SNOMEDCTCode, description=eca_diagnosis_description)
    diagnosis_24 = Series(SNOMEDCTCode, description=eca_diagnosis_description)


@table
class household_memberships_2020(PatientFrame):
    """
    Inferred household membership as of 2020-02-01, as determined by TPP using an as yet
    undocumented algorithm.
    """

    household_pseudo_id = Series(int)
    household_size = Series(int)


@table
class medications(ehrql.tables.core.medications.__class__):
    """
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
    """

    consultation_id = Series(
        int,
        description=(
            "ID of the [consultation](#appointments-vs-consultations) associated with this event"
        ),
    )


@table
class occupation_on_covid_vaccine_record(EventFrame):
    """
    This data is from the NHS England COVID-19 data store,
    and reflects information collected at the point of vaccination
    where recipients are asked by vaccination staff
    whether they are in the category of health and care worker.

    Refer to the [OpenSAFELY database build report][opensafely_database_build_report]
    to see when this data was last updated.

    See the GitHub issue that [discusses more of the background context][vaccine_record_issue].

    [opensafely_database_build_report]: https://reports.opensafely.org/reports/opensafely-tpp-database-builds
    [vaccine_record_issue]: https://github.com/opensafely-core/cohort-extractor/issues/544
    """

    is_healthcare_worker = Series(bool)


@table
class ons_deaths(ehrql.tables.core.ons_deaths.__class__):
    """
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
    """

    place = Series(
        str,
        description="Patient's place of death.",
        constraints=[
            Constraint.Categorical(
                [
                    "Care Home",
                    "Elsewhere",
                    "Home",
                    "Hospice",
                    "Hospital",
                    "Other communal establishment",
                ]
            ),
        ],
    )


@table
class opa(EventFrame):
    """
    Outpatient appointments data (OPA) is provided via the NHS Secondary Uses Service.

    This table gives core details of outpatient appointments.

    Refer to the GitHub issue that [describes limitations
    of the outpatient appointments data][opa_limitations_issue]
    and the GitHub issue that [discusses more of the background context][opa_context_issue].

    [opa_limitations_issue]: https://github.com/opensafely-core/cohort-extractor/issues/673
    [opa_context_issue]: https://github.com/opensafely-core/cohort-extractor/issues/492
    """

    opa_ident = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the appointment used across the OPA tables.",
    )
    appointment_date = Series(
        datetime.date,
        description="The date of an appointment.",
    )
    attendance_status = Series(
        str,
        description=(
            "Indicates whether or not an appointment for a care contact took place. "
            "If the appointment did not take place it also indicates whether or not advanced warning was given. "
            'Refer to the [NHS Data Model and Dictionary entry for "attended or did not attend"]'
            "(https://www.datadictionary.nhs.uk/data_elements/attended_or_did_not_attend_code.html) "
            "for details on code meanings."
        ),
        # This non-ascending order follows the NHS Data Model and Dictionary.
        constraints=[Constraint.Categorical(["5", "6", "7", "2", "3", "4", "0"])],
    )
    consultation_medium_used = Series(
        str,
        description=(
            "Identifies the communication mechanism used to relay information "
            "between the care professional and the person who is the subject of the consultation, "
            "during a care activity. "
            'Refer to the [NHS Data Model and Dictionary entry for "consultation mechanism"]'
            "(https://www.datadictionary.nhs.uk/data_elements/consultation_mechanism.html) "
            "for details on code meanings. "
            "Note that the allowed codes as listed in TPP's data "
            "appear to be a subset of the codes listed in the NHS Data Model and Dictionary."
        ),
        constraints=[
            Constraint.Categorical(
                ["01", "02", "03", "04", "05", "09", "10", "11", "98"]
            )
        ],
    )
    first_attendance = Series(
        str,
        description=(
            "An indication of whether a patient is making a first attendance or contact; "
            "or a follow-up attendance or contact and whether the consultation medium used national code "
            "was face to face communication or telephone or telemedicine web camera. "
            'Refer to the [NHS Data Model and Dictionary entry for "first attendance"]'
            "(https://www.datadictionary.nhs.uk/attributes/first_attendance.html) "
            "for details on code meanings. "
            "Note that the allowed codes as listed in TPP's data "
            "contain an additional `9` code over the NHS Data Model and Dictionary entry."
        ),
        constraints=[Constraint.Categorical(["1", "2", "3", "4", "5", "9"])],
    )
    hrg_code = Series(
        str,
        description=(
            "The Healthcare Resource Group (HRG) code assigned to the activity, "
            "used to assign baseline tariff costs."
        ),
        # For the format of an HRG code, see:
        # https://en.wikipedia.org/wiki/Healthcare_Resource_Group
        constraints=[Constraint.Regex(r"[a-zA-Z]{2}[0-9]{2}[a-zA-Z]")],
    )
    treatment_function_code = Series(
        str,
        description=(
            "The treatment function under which the patient is treated. "
            "It may be the same as the main specialty code "
            "or a different treatment function which will be the care professional's treatment interest."
        ),
    )


@table
class opa_cost(EventFrame):
    """
    Outpatient appointments data is provided via the NHS Secondary Uses Service.

    This table gives details of outpatient appointment costs.

    Note that data only goes back a couple of years.
    """

    opa_ident = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the appointment used across the OPA tables.",
    )
    tariff_opp = Series(
        float,
        description="The base national tariff where the procedure tariff is applicable.",
    )
    grand_total_payment_mff = Series(
        float,
        description=(
            "The grand total payment for the activity (`Net_SLA_Payment + Tariff_MFF_Payment`) "
            "where SLA = service level agreement, "
            "i.e. all contractual payments which is national tariff for the type of activity "
            "**plus** any additional payments **minus** any applicable deductions. "
            "MFF = Market Forces Factor, a geography-based cost adjustment)."
        ),
    )
    tariff_total_payment = Series(
        float,
        description="The total payment according to the national tariff.",
    )
    appointment_date = Series(
        datetime.date,
        description="The date of an appointment.",
    )
    referral_request_received_date = Series(
        datetime.date,
        description="The date the referral request was received by the health care provider.",
    )


@table
class opa_diag(EventFrame):
    """
    Outpatient appointments data is provided via the NHS Secondary Uses Service.

    This table gives details of outpatient appointment diagnoses.

    Note that diagnoses are often absent from outpatient records.
    """

    opa_ident = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the appointment used across the OPA tables.",
    )
    primary_diagnosis_code = Series(
        ICD10Code,
        description=(
            "The international classification of diseases (ICD) code used to identify the primary patient diagnosis. "
            "Note that this will typically not be completed."
        ),
    )
    primary_diagnosis_code_read = Series(
        CTV3Code,
        description=(
            "The Read coded clinical terms code to identify the primary patient diagnosis. "
            "Note that this will typically not be completed."
        ),
    )
    secondary_diagnosis_code_1 = Series(
        ICD10Code,
        description=(
            "The international classification of diseases (ICD) code used to identify the secondary patient diagnosis. "
            "Note that this will typically not be completed."
        ),
    )
    secondary_diagnosis_code_1_read = Series(
        CTV3Code,
        description=(
            "The Read coded clinical terms used to identify the secondary patient diagnosis. "
            "Note that this will typically not be completed."
        ),
    )
    appointment_date = Series(
        datetime.date,
        description="The date of an appointment.",
    )
    referral_request_received_date = Series(
        datetime.date,
        description="The date the referral request was received by the health care provider.",
    )


@table
class opa_proc(EventFrame):
    """
    Outpatient appointments data is provided via the NHS Secondary Uses Service.

    This table gives details of outpatient procedures.
    Typically, procedures will only be recorded where they attract a specified payment.
    The majority of appointments will have no procedure recorded.
    """

    opa_ident = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Unique identifier for the appointment used across the OPA tables.",
    )
    primary_procedure_code = Series(
        OPCS4Code,
        description=(
            "The OPCS classification of interventions and procedures code "
            "which is used to identify the primary patient procedure carried out."
        ),
    )
    primary_procedure_code_read = Series(
        CTV3Code,
        description=(
            "The Read coded clinical terms code which is used "
            "to identify the primary patient procedure carried out."
        ),
    )
    procedure_code_2 = Series(
        OPCS4Code,
        description="TODO",
    )
    procedure_code_2_read = Series(
        CTV3Code,
        description="The Read coded clinical terms for a procedure other than the primary procedure.",
    )
    appointment_date = Series(
        datetime.date,
        description="The date of an appointment.",
    )
    referral_request_received_date = Series(
        datetime.date,
        description="The date the referral request was received by the health care provider.",
    )


@table
class open_prompt(EventFrame):
    """
    This table contains responses to questions from the OpenPROMPT project.

    You can find out more about this table in the associated short data report. To view
    it, you will need a login for [Level 4][open_prompt_1]. The
    [workspace][open_prompt_2] shows when the code that comprises the report was run;
    the code itself is in the [airmid-short-data-report][open_prompt_3] repository on
    GitHub.

    [open_prompt_1]: https://docs.opensafely.org/security-levels/#level-4-nhs-england-are-data-controllers-of-the-data
    [open_prompt_2]: https://jobs.opensafely.org/datalab/opensafely-internal/airmid-short-data-report/
    [open_prompt_3]: https://github.com/opensafely/airmid-short-data-report
    """

    ctv3_code = Series(
        CTV3Code,
        constraints=[Constraint.NotNull()],
        description=(
            "The response to the question, as a CTV3 code. "
            "Alternatively, if the question does not admit a CTV3 code as the response, "
            "then the question, as a CTV3 code."
        ),
    )
    snomedct_code = Series(
        SNOMEDCTCode,
        description=(
            "The response to the question, as a SNOMED CT code. "
            "Alternatively, if the question does not admit a SNOMED CT code as the response, "
            "then the question, as a SNOMED CT code."
        ),
    )
    creation_date = Series(
        datetime.date,
        constraints=[Constraint.NotNull()],
        description="The date the survey was administered",
    )
    consultation_date = Series(
        datetime.date,
        constraints=[Constraint.NotNull()],
        description=(
            "The response to the question, as a date, "
            "if the question admits a date as the response. "
            "Alternatively, the date the survey was administered."
        ),
    )
    consultation_id = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="The ID of the survey",
    )
    numeric_value = Series(
        float,
        description="The response to the question, as a number",
    )


@table
class parents(PatientFrame):
    """
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
    """

    mother_id = Series(
        int,
        description="The `patient_id` of the patient's mother",
    )


@table
class practice_registrations(ehrql.tables.core.practice_registrations.__class__):
    """
    Each record corresponds to a patient's registration with a practice.

    [Example ehrQL usage of practice_registrations](../../../how-to/examples/#practice-registrations)

    ### TPP specific information

    See the [TPP backend information](../backends.md#patients-included-in-the-tpp-backend)
    for details of which patients are included.
    """

    practice_stp = Series(
        str,
        constraints=[Constraint.Regex("E540000[0-9]{2}")],
        description="""
            ONS code of practice's STP (Sustainability and Transformation Partnership).
            STPs have been replaced by ICBs (Integrated Care Boards), and ICB codes will be available soon.
        """,
    )
    practice_nuts1_region_name = Series(
        str,
        constraints=[
            Constraint.Categorical(
                [
                    "North East",
                    "North West",
                    "Yorkshire and The Humber",
                    "East Midlands",
                    "West Midlands",
                    "East",
                    "London",
                    "South East",
                    "South West",
                ]
            ),
        ],
        description="""
            Name of the NUTS level 1 region of England to which the practice belongs.
            For more information see:
            <https://www.ons.gov.uk/methodology/geography/ukgeographies/eurostat>
        """,
    )
    practice_systmone_go_live_date = Series(
        datetime.date,
        description="""
            Date on which the practice started using the SystmOne EHR platform.

            Most patient records will have been transferred from the previous EHR
            platform but records which are specific to SystmOne will not exist before
            this date. In particular, the [appointments](#appointments) table should
            only be considered accurate for a given practice _after_ this date.
        """,
    )

    def spanning_with_systmone(self, start_date, end_date):
        """
        Filter registrations to just those spanning the entire period between
        `start_date` and `end_date` _and_ where the practice has been using the SystmOne
        EHR platform throughout that period (see
        [`systmone_go_live_date`](#practice_registrations.practice_systmone_go_live_date)).
        """
        return self.spanning(start_date, end_date).where(
            self.practice_systmone_go_live_date <= start_date
        )


@table
class sgss_covid_all_tests(EventFrame):
    """
    COVID-19 tests results from SGSS (the Second Generation Surveillance System).

    For background on this data see the NHS [DARS catalogue entry][DARS_SGSS].
    And for more detail on SGSS in general see [UKHSA_Laboratory_Reporting_Guidelines.pdf][UKHSA_LRG].

    [UKHSA_LRG]: https://assets.publishing.service.gov.uk/media/66e2e0ba0d913026165c3d77/UKHSA_Laboratory_reporting_guidelines_May_2023.pdf
    [DARS_SGSS]: https://digital.nhs.uk/services/data-access-request-service-dars/dars-products-and-services/data-set-catalogue/covid-19-second-generation-surveillance-system-sgss
    """

    specimen_taken_date = Series(
        datetime.date,
        constraints=[Constraint.NotNull()],
        description="""
            Date on which specimen was collected.
        """,
    )
    is_positive = Series(
        bool,
        constraints=[Constraint.NotNull()],
        description="""
            Whether the specimin tested positive for SARS-CoV-2.
        """,
    )
    lab_report_date = Series(
        datetime.date,
        constraints=[Constraint.NotNull()],
        description="""
            Date on which the labaratory reported the result.
        """,
    )
    was_symptomatic = Series(
        bool,
        description="""
            Whether the patient reported symptoms of COVID-19 at the time the specimen
            was collected. May be NULL if unknown.
        """,
    )
    sgtf_status = Series(
        int,
        constraints=[Constraint.ClosedRange(0, 9)],
        description="""
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
        """,
    )
    variant = Series(
        str,
        description="""
            Where a specific SARS-CoV-2 variant was identified this column provides the details.

            This appears to be effectively a free-text field with a large variety of
            possible values. Some have an obvious meaning e.g. `B.1.617.2`,
            `VOC-21JAN-02`, `VUI-21FEB-04`.

            Others less so e.g. `VOC-22JAN-O1_probable:V-21OCT-01_low-qc`.
        """,
    )
    variant_detection_method = Series(
        str,
        constraints=[
            Constraint.Categorical(
                [
                    "Private Lab Sequencing",
                    "Reflex Assay",
                    "Sanger Provisional Result",
                ]
            )
        ],
        description="""
            Where a specific SARS-CoV-2 variant was identified this provides the method
            used to do so.
        """,
    )


@table
class ukrr(EventFrame):
    """
    The UK Renal Registry (UKRR) contains data on patients under secondary renal care
    (advanced chronic kidney disease stages 4 and 5, dialysis, and kidney transplantation)
    """

    dataset = Series(
        str,
        description="""
            The cohort of patients.

            Values are:

            * '2019_prevalence' - a prevalence cohort of patients alive and on RRT in December 2019
            * '2020_prevalence' - a prevalence cohort of patients alive and on RRT in December 2020
            * '2021_prevalence' - a prevalence cohort of patients alive and on RRT in December 2021
            * '2020_incidence' - an incidence cohort of patients who started RRT in 2020
            * '2020_ckd' - a snapshot prevalence cohort of patient with Stage 4 or 5 CKD who were reported to the UKRR to be under renal care in December 2020.
        """,
        constraints=[
            Constraint.Categorical(
                [
                    "2019_prevalence",
                    "2020_prevalence",
                    "2021_prevalence",
                    "2020_incidence",
                    "2020_ckd",
                ]
            )
        ],
    )
    renal_centre = Series(
        str,
        description="The code of the main renal centre a patient is registered with",
    )
    rrt_start_date = Series(
        datetime.date, description="The latest start date for renal replacement therapy"
    )
    latest_creatinine = Series(float, description="Most recent creatinine held by UKRR")
    latest_egfr = Series(float, description="Most recent eGFR held by UKRR")
    treatment_modality_start = Series(
        str,
        description="""
            The treatment modality at `rrt_start_date`.

            Values such as ICHD, HHD, HD, PD, Tx.
        """,
    )
    treatment_modality_prevalence = Series(
        str, description="The treatment modality from the prevalence data"
    )


@table
class vaccinations(EventFrame):
    """
    This table contains information on administered vaccinations,
    identified using either the target disease (e.g., Influenza),
    or the vaccine product name (e.g., Optaflu).
    For more information about this table see the
    "[Vaccinaton names in the OpenSAFELY-TPP database][vaccinations_1]" report.

    Vaccinations that were administered at work or in a pharmacy might not be
    included in this table.

    [vaccinations_1]: https://reports.opensafely.org/reports/opensafely-tpp-vaccination-names/
    """

    vaccination_id = Series(
        int,
        description="Vaccination identifier.",
    )
    date = Series(
        datetime.date,
        description="The date the vaccination was administered.",
    )
    target_disease = Series(
        str,
        description="Vaccine's target disease.",
    )
    product_name = Series(
        str,
        description="Vaccine's product name.",
    )


@table
class wl_clockstops(EventFrame):
    """
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
    """

    activity_treatment_function_code = Series(
        str,
        description="The treatment function",
        constraints=[Constraint.Regex(r"[a-zA-Z0-9]{3}")],
    )
    priority_type_code = Series(
        str,
        description="""
            The priority type.

            Note that a small number of rows contain values which are not in the list
            below. These are converted to NULL in this representation of the data. If
            you need to access the original values, please see the corresponding [raw
            table](raw.tpp.md#wl_clockstops).
        """,
        constraints=[Constraint.Categorical(["routine", "urgent", "two week wait"])],
    )
    pseudo_organisation_code_patient_pathway_identifier_issuer = Series(str)
    pseudo_patient_pathway_identifier = Series(str)
    pseudo_referral_identifier = Series(str)
    referral_request_received_date = Series(
        datetime.date,
        description=(
            "The date the referral was received, "
            "for the referral that started the original pathway"
        ),
    )
    referral_to_treatment_period_end_date = Series(
        datetime.date,
        description="Clock stop for the completed pathway",
    )
    referral_to_treatment_period_start_date = Series(
        datetime.date,
        description="Clock start for the completed pathway",
    )
    source_of_referral_for_outpatients = Series(str)
    waiting_list_type = Series(
        str,
        description="""
            The waiting list type on completion of the pathway.

            Note that a small number of rows contain values which are not in the list
            below. These are converted to NULL in this representation of the data. If
            you need to access the original values, please see the corresponding [raw
            table](raw.tpp.md#wl_clockstops).
        """,
        constraints=[
            Constraint.Categorical(
                ["ORTT", "IRTT", "PTLO", "PTLI", "RTTO", "RTTI"],
            )
        ],
    )
    week_ending_date = Series(
        datetime.date,
        description="The Sunday of the week that the pathway relates to",
    )


@table
class wl_openpathways(EventFrame):
    """
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
    """

    activity_treatment_function_code = Series(
        str,
        description="The treatment function",
        constraints=[Constraint.Regex(r"[a-zA-Z0-9]{3}")],
    )
    current_pathway_period_start_date = Series(
        datetime.date,
        description="Latest clock start for this pathway period",
    )
    priority_type_code = Series(
        str,
        description="""
            The priority type.

            Note that a small number of rows contain values which are not in the list
            below. These are converted to NULL in this representation of the data. If
            you need to access the original values, please see the corresponding [raw
            table](raw.tpp.md#wl_openpathways).
        """,
        constraints=[Constraint.Categorical(["routine", "urgent", "two week wait"])],
    )
    pseudo_organisation_code_patient_pathway_identifier_issuer = Series(str)
    pseudo_patient_pathway_identifier = Series(str)
    pseudo_referral_identifier = Series(str)
    referral_request_received_date = Series(
        datetime.date,
        description=(
            "The date the referral was received, "
            "for the referral that started the original pathway"
        ),
    )
    referral_to_treatment_period_end_date = Series(
        datetime.date,
        description="If the pathway is open, then `NULL`",
    )
    referral_to_treatment_period_start_date = Series(
        datetime.date,
        description=(
            "Latest clock start for this pathway. "
            "If the pathway is not a current pathway, then `NULL`."
        ),
    )
    source_of_referral = Series(
        str,
        description=(
            "National referral source code "
            "for the referral that created the original pathway"
        ),
        constraints=[Constraint.Regex(r"[a-zA-Z0-9]{2}")],
    )
    waiting_list_type = Series(
        str,
        description="""
            The waiting list type.

            Note that a small number of rows contain values which are not in the list
            below. These are converted to NULL in this representation of the data. If
            you need to access the original values, please see the corresponding [raw
            table](raw.tpp.md#wl_openpathways).
        """,
        constraints=[
            Constraint.Categorical(
                ["ORTT", "IRTT", "ONON", "INON", "PTLO", "PTLI", "RTTO", "RTTI"]
            )
        ],
    )
    week_ending_date = Series(
        datetime.date,
        description="The Sunday of the week that the pathway relates to",
    )


@table
class ethnicity_from_sus(PatientFrame):
    """
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
    """

    code = Series(
        str,
        constraints=[
            Constraint.Categorical(list("ABCDEFGHJKLMNPRS")),
        ],
        description=(
            "First character of recorded ethncity code (national code):\n"
            "https://www.datadictionary.nhs.uk/data_elements/ethnic_category.html"
        ),
    )
