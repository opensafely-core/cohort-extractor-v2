import datetime

from databuilder.query_language import EventFrame, PatientFrame, Series, construct

from .constraints import (
    CategoricalConstraint,
    FirstOfMonthConstraint,
    NotNullConstraint,
)


@construct
class patient_demographics(PatientFrame):
    """Provides demographic information about patients."""

    date_of_birth = Series(
        datetime.date,
        description="Patient's year and month of birth, provided in format YYYY-MM-01.",
        constraints=[NotNullConstraint(), FirstOfMonthConstraint()],
    )
    sex = Series(
        str,
        description="Patient's sex.",
        constraints=[
            NotNullConstraint(),
            CategoricalConstraint("female", "male", "intersex", "unknown"),
        ],
    )
    date_of_death = Series(
        datetime.date,
        description="Patient's year and month of death, provided in format YYYY-MM-01.",
        constraints=[FirstOfMonthConstraint()],
    )


###
# The following contracts have not been through any kind of assurance process!
###


@construct
class clinical_events(EventFrame):
    """TODO."""

    code = Series(str)
    system = Series(str)
    date = Series(datetime.date)
    numeric_value = Series(float)


@construct
class hospital_admissions(EventFrame):
    """TODO."""

    admission_date = Series(datetime.date)
    primary_diagnosis = Series(str)
    admission_method = Series(int)
    episode_is_finished = Series(bool)
    spell_id = Series(int)


@construct
class hospitalizations(EventFrame):
    """TODO."""

    date = Series(datetime.date)
    code = Series(str)
    system = Series(str)


@construct
class hospitalizations_without_system(EventFrame):
    """TODO."""

    code = Series(str)


@construct
class patient_address(EventFrame):
    """TODO."""

    patientaddress_id = Series(int)
    date_start = Series(datetime.date)
    date_end = Series(datetime.date)
    index_of_multiple_deprivation_rounded = Series(int)
    has_postcode = Series(bool)


@construct
class practice_registrations(EventFrame):
    """TODO."""

    pseudo_id = Series(int)
    nuts1_region_name = Series(str)
    date_start = Series(datetime.date)
    date_end = Series(datetime.date)


@construct
class prescriptions(EventFrame):
    """TODO."""

    prescribed_dmd_code = Series(str)
    processing_date = Series(datetime.date)


@construct
class covid_test_results(EventFrame):
    """TODO."""

    date = Series(datetime.date)
    positive_result = Series(bool)


@construct
class patients(EventFrame):
    """TODO."""

    date_of_birth = Series(datetime.date)
