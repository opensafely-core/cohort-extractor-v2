"""
This schema defines the data (both primary care and externally linked) available in the
OpenSAFELY-EMIS backend. For more information about this backend, see
"[EMIS Primary Care](https://docs.opensafely.org/data-sources/emis/)".
"""

import datetime

import ehrql.tables.core
from ehrql.codes import SNOMEDCTCode
from ehrql.patient_level_table_definitions.emis import Vaccinations
from ehrql.tables import Constraint, EventFrame, PatientFrame, Series, table
from ehrql.tables.core import clinical_events, medications, ons_deaths


__all__ = [
    "clinical_events",
    "medications",
    "ons_deaths",
    "patients",
    "practice_registrations",
    "vaccinations",
]


@table
class patients(PatientFrame):
    """
    Patients in primary care.

    In the EMIS backend, this table also includes information about the patient's
    current practice registration. Historical practice registration data is not
    currently available.

    ### Recording of death in primary care

    In England, it is the statutory duty of the doctor who had attended in the last
    illness to complete a medical certificate of cause of death (MCCD). ONS death data
    are considered the gold standard for identifying patient deaths because they are
    based on these MCCDs.

    There is generally a lag between the death being recorded in ONS data and it
    appearing in the primary care record, but the coverage or recorded death is almost
    complete and the date of death is usually reliable when it appears. There is
    also a lag in ONS death recording (see [`ons_deaths`](core.md#ons_deaths)
    for more detail). You can find out more about the accuracy of date of death
    recording in primary care in:

    > Gallagher, A. M., Dedman, D., Padmanabhan, S., Leufkens, H. G. M. & de Vries, F 2019. The accuracy of date of death recording in the Clinical
    > Practice Research Datalink GOLD database in England compared with the Office for National Statistics death registrations.
    > Pharmacoepidemiol. Drug Saf. 28, 563–569.
    > <https://doi.org/10.1002/pds.4747>
    """

    date_of_birth = Series(
        datetime.date,
        description="Patient's date of birth.",
        constraints=[Constraint.FirstOfMonth(), Constraint.NotNull()],
    )
    sex = Series(
        str,
        description="Patient's sex.",
        constraints=[
            Constraint.Categorical(["female", "male", "unknown"]),
            Constraint.NotNull(),
        ],
    )
    date_of_death = Series(
        datetime.date,
        description="Patient's date of death.",
    )
    registration_start_date = Series(
        datetime.date,
        constraints=[Constraint.NotNull()],
        description="Date patient joined practice.",
    )
    registration_end_date = Series(
        datetime.date,
        description="Date patient left practice.",
    )
    practice_pseudo_id = Series(
        str,
        constraints=[Constraint.NotNull()],
        description="Pseudonymised practice identifier.",
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
            rounded to the nearest 100, where lower values represent more deprived areas.

            [addresses_imd]: https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019
        """,
        constraints=[Constraint.ClosedRange(0, 32_800, 100)],
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

    def has_practice_registration_spanning(self, start_date, end_date):
        """
        Whether a patient's registration spans the entire period between
        `start_date` and `end_date`.
        """
        return self.registration_start_date.is_on_or_before(start_date) & (
            self.registration_end_date.is_after(end_date)
            | self.registration_end_date.is_null()
        )


@table
class practice_registrations(ehrql.tables.core.practice_registrations.__class__):
    """
    Each record corresponds to a patient's registration with a practice.

    [Example ehrQL usage of practice_registrations](../../../how-to/examples/#practice-registrations)

    !!! warning
        At present, the EMIS database contains only the patient's current practice
        registration and does not include their full registration history.
    """


@table
class vaccinations(EventFrame[Vaccinations]):
    """
    This table contains information on administered vaccinations,
    identified using SNOMED-CT codes for the vaccination procedure.

    Vaccinations may also be queried by product code using the
    [medications table](#medications).

    Vaccinations that were administered at work or in a pharmacy might not be
    included in this table.

    """

    date = Series(
        datetime.date,
        description="The date the vaccination was administered.",
    )
    procedure_code = Series(SNOMEDCTCode)
