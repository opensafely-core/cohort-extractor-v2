"""
This schema defines the core tables and columns which should be available in any backend
providing primary care data, allowing dataset definitions written using this schema to
run across multiple backends.
"""

import datetime
import functools
import operator

from ehrql.codes import DMDCode, ICD10Code, SNOMEDCTCode
from ehrql.patient_level_table_definitions.core import (
    ClinicalEvents,
    Medications,
    PracticeRegistrations,
)
from ehrql.tables import Constraint, EventFrame, PatientFrame, Series, table


__all__ = [
    "clinical_events",
    "medications",
    "ons_deaths",
    "patients",
    "practice_registrations",
]


@table
class patients(PatientFrame):
    """
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
    """

    date_of_birth = Series(
        datetime.date,
        description="Patient's date of birth.",
        constraints=[Constraint.FirstOfMonth(), Constraint.NotNull()],
    )
    sex = Series(
        str,
        description="Patient's sex.",
        implementation_notes_to_add_to_description=(
            'Specify how this has been determined, e.g. "sex at birth", or "current sex".'
        ),
        constraints=[
            Constraint.Categorical(["female", "male", "intersex", "unknown"]),
            Constraint.NotNull(),
        ],
    )
    date_of_death = Series(
        datetime.date,
        description="Patient's date of death.",
    )

    def age_on(self, date):
        """
        Patient's age as an integer, in whole elapsed calendar years, as it would be on
        the given date.

        This method takes no account of whether the patient is alive on the given date.
        In particular, it may return negative values if the given date is before the
        patient's date of birth.
        """
        return (date - self.date_of_birth).years

    def is_alive_on(self, date):
        """
        Whether a patient is alive on the given date, based on the date of death
        recorded in their primary care record. **NB** this is only based on the primary
        care record. Please see the section above about the accuracy of death data.

        If the date provided is before a person was born, then this helper function will
        actually return True, despite the person not being alive yet. For most research
        this is likely the expected behaviour.
        """
        return self.date_of_death.is_after(date) | self.date_of_death.is_null()

    def is_dead_on(self, date):
        """
        Whether a patient has a date of death in their primary care record before the given date.

        A person is classed as dead if the date provided is after their death date.
        """
        return self.date_of_death.is_not_null() & self.date_of_death.is_before(date)


@table
class practice_registrations(EventFrame[PracticeRegistrations]):
    """
    Each record corresponds to a patient's registration with a practice.

    [Example ehrQL usage of practice_registrations](../../../how-to/examples/#practice-registrations)
    """

    start_date = Series(
        datetime.date,
        constraints=[Constraint.NotNull()],
        description="Date patient joined practice.",
    )
    end_date = Series(
        datetime.date,
        description="Date patient left practice.",
    )
    practice_pseudo_id = Series(
        int,
        constraints=[Constraint.NotNull()],
        description="Pseudonymised practice identifier.",
    )

    def for_patient_on(self, date):
        """
        Return each patient's practice registration as it was on the supplied date.

        Where a patient is registered with multiple practices we prefer the most recent
        registration and then, if there are multiple of these, the one with the longest
        duration. If there's still an exact tie we choose arbitrarily based on the
        practice ID.
        """
        spanning_regs = self.where(self.start_date <= date).except_where(
            self.end_date < date
        )
        ordered_regs = spanning_regs.sort_by(
            self.start_date,
            self.end_date,
            self.practice_pseudo_id,
        )
        return ordered_regs.last_for_patient()

    def exists_for_patient_on(self, date):
        """
        Returns whether a person was registered with a practice on the supplied date.

        NB. The implementation currently uses `spanning()`. It would also have been
        valid to implement as
        `practice_registrations.for_patient_on(date).exists_for_patient()`, but for
        internal reasons that is less efficient.

        """
        return self.spanning(date, date).exists_for_patient()

    def spanning(self, start_date, end_date):
        """
        Filter registrations to just those spanning the entire period between
        `start_date` and `end_date`.
        """
        return self.where(
            self.start_date.is_on_or_before(start_date)
            & (self.end_date.is_after(end_date) | self.end_date.is_null())
        )


@table
class ons_deaths(PatientFrame):
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
    """

    date = Series(
        datetime.date,
        description=("Patient's date of death."),
    )
    underlying_cause_of_death = Series(
        ICD10Code,
        description="Patient's underlying cause of death.",
    )
    # TODO: Revisit this when we have support for multi-valued fields
    cause_of_death_01 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_02 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_03 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_04 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_05 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_06 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_07 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_08 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_09 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_10 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_11 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_12 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_13 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_14 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )
    cause_of_death_15 = Series(
        ICD10Code,
        description="Medical condition mentioned on the death certificate.",
    )

    def cause_of_death_is_in(self, codelist):
        """
        Match `codelist` against the `underlying_cause_of_death` field and all 15
        separate `cause_of_death` fields.

        This method evaluates as `True` if _any_ code in the codelist matches _any_ of
        these fields.
        """
        columns = [
            "underlying_cause_of_death",
            *[f"cause_of_death_{i:02d}" for i in range(1, 16)],
        ]
        conditions = [getattr(self, column).is_in(codelist) for column in columns]
        return functools.reduce(operator.or_, conditions)


@table
class clinical_events(EventFrame[ClinicalEvents]):
    """
    Each record corresponds to a single clinical or consultation event for a patient.

    Note that event codes do not change in this table. If an event code in the coding
    system becomes inactive, the event will still be coded to the inactive code.
    As such, codelists should include all relevant inactive codes.

    [Example ehrQL usage of clinical_events](../../../how-to/examples/#clinical-events)
    """

    date = Series(datetime.date)
    snomedct_code = Series(SNOMEDCTCode)
    numeric_value = Series(float)


@table
class medications(EventFrame[Medications]):
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

    date = Series(datetime.date)
    dmd_code = Series(DMDCode)
