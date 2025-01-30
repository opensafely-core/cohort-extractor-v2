from urllib import parse

import sqlalchemy

import ehrql.tables.core
import ehrql.tables.raw.core
import ehrql.tables.raw.tpp
import ehrql.tables.smoketest
import ehrql.tables.tpp
from ehrql.backends.base import MappedTable, QueryTable, SQLBackend
from ehrql.codes import CTV3Code, DMDCode, SNOMEDCTCode
from ehrql.query_engines.mssql import MSSQLQueryEngine
from ehrql.query_model import nodes as qm


class TPPBackend(SQLBackend):
    """
    [TPP](https://tpp-uk.com/) are the developers and operators of the
    [SystmOne](https://tpp-uk.com/products/) EHR platform. The ehrQL TPP backend
    provides access to primary care data from SystmOne, plus data linked from other
    sources.

    ### Patients included in the TPP backend

    SystmOne is a primary care clinical information system
    used by roughly one third of GP practices in England,
    with records for approximately 44% of the English population.

    Only patients with a full GMS (General Medical Services) registration are included.

    We have registration history for:

    * all patients currently registered at a TPP practice
    * all patients registered at a TPP practice any time from 1 Jan 2009 onwards:
        * who have since de-registered
        * who have since died

    A patient can be registered with zero, one, or more than one practices at a given
    time. For instance, students are often registered with a practice at home and a
    practice at university.

    !!! warning
        Refer to the [discussion of selecting populations for studies](../explanation/selecting-populations-for-study.md).
    """

    display_name = "TPP"
    query_engine_class = MSSQLQueryEngine
    patient_join_column = "Patient_ID"
    implements = [
        ehrql.tables.core,
        ehrql.tables.raw.core,
        ehrql.tables.tpp,
        ehrql.tables.raw.tpp,
        ehrql.tables.smoketest,
    ]

    DEFAULT_COLLATION = "Latin1_General_CI_AS"

    include_t1oo = False

    def column_kwargs_for_type(self, type_):
        # For specific code types we need to set the collation to match what TPP use
        if type_ is CTV3Code:
            return {"type_": sqlalchemy.VARCHAR(50, collation="Latin1_General_BIN")}
        elif type_ is SNOMEDCTCode:
            return {"type_": sqlalchemy.VARCHAR(50, collation="Latin1_General_BIN")}
        elif type_ is DMDCode:
            return {"type_": sqlalchemy.VARCHAR(50, collation="Latin1_General_CI_AS")}
        else:
            kwargs = self.query_engine_class.column_kwargs_for_type(type_)
            # For all string types we set the collation to match TPP's default
            if isinstance(kwargs["type_"], sqlalchemy.String):
                assert kwargs["type_"].collation is None
                kwargs["type_"].collation = self.DEFAULT_COLLATION
            return kwargs

    def modify_dsn(self, dsn):
        """
        Removes the `opensafely_include_t1oo` parameter if present and uses it to set
        the `include_t1oo` attribute accordingly
        """
        parts = parse.urlparse(dsn)
        params = parse.parse_qs(parts.query, keep_blank_values=True)

        include_t1oo_values = params.pop("opensafely_include_t1oo", [])
        if len(include_t1oo_values) == 1:
            self.include_t1oo = include_t1oo_values[0].lower() == "true"
        elif len(include_t1oo_values) != 0:
            raise ValueError(
                "`opensafely_include_t1oo` parameter must not be supplied more than once"
            )

        new_query = parse.urlencode(params, doseq=True)
        new_parts = parts._replace(query=new_query)
        return parse.urlunparse(new_parts)

    def modify_dataset(self, dataset):
        # If this query has been explictly flagged as including T1OO patients then
        # return it unmodified
        if self.include_t1oo:
            return dataset

        # Otherwise we add an extra condition to the population definition which is that
        # the patient does not appear in the T1OO table.
        #
        # PLEASE NOTE: This logic is referenced in our public documentation, so if we
        # make any changes here we should ensure that the documentation is kept
        # up-to-date:
        # https://github.com/opensafely/documentation/blob/ea2e1645/docs/type-one-opt-outs.md
        #
        # From ehrQL's point of view, the construction of the T1OO table is opaque. For
        # discussion of the approach currently used to populate this see:
        # https://docs.google.com/document/d/1nBAwDucDCeoNeC5IF58lHk6LT-RJg6YZRp5RRkI7HI8/
        new_population = qm.Function.And(
            dataset.population,
            qm.Function.Not(
                qm.AggregateByPatient.Exists(
                    # We don't currently expose this table in the user-facing schema. If
                    # we did then we could avoid defining it inline like this.
                    qm.SelectPatientTable(
                        "t1oo",
                        # It doesn't need any columns: it's just a list of patient IDs
                        schema=qm.TableSchema(),
                    )
                )
            ),
        )
        return qm.Dataset(
            population=new_population,
            variables=dataset.variables,
        )

    def get_exit_status_for_exception(self, exception):
        is_database_error = False
        exception_messages = ""
        next_exception = exception
        # Walk up the chain of exceptions
        while next_exception is not None:
            # Checking for "DatabaseError" in the MRO means we can identify database
            # errors without referencing a specific driver.  Both pymssql and
            # presto/trino-python-client raise exceptions derived from a DatabaseError
            # parent class
            if "DatabaseError" in str(next_exception.__class__.mro()):
                is_database_error = True
            exception_messages += f"\n{next_exception}"
            next_exception = next_exception.__context__

        # Ignore errors which don't look like database errors
        if not is_database_error:
            return

        # Exit with specific exit codes to help identify known issues
        transient_errors = [
            "Unexpected EOF from the server",
            "DBPROCESS is dead or not enabled",
        ]
        if any(message in exception_messages for message in transient_errors):
            exception.add_note(f"\nIntermittent database error: {exception}")
            return 3

        if "Invalid object name 'CodedEvent_SNOMED'" in exception_messages:
            exception.add_note(
                "\nCodedEvent_SNOMED table is currently not available.\n"
                "This is likely due to regular database maintenance."
            )
            return 4

        exception.add_note(f"\nDatabase error: {exception}")
        return 5

    t1oo = MappedTable(
        source="PatientsWithTypeOneDissent",
        # The allowed patients table doesn't need any columns: it's just a list of
        # patient IDs
        columns={},
    )

    addresses = QueryTable(
        """
            SELECT
                addr.Patient_ID AS patient_id,
                addr.PatientAddress_ID AS address_id,
                CAST(NULLIF(addr.StartDate, '9999-12-31T00:00:00') AS date) AS start_date,
                CAST(NULLIF(addr.EndDate, '9999-12-31T00:00:00') AS date) AS end_date,
                addr.AddressType AS address_type,
                NULLIF(addr.RuralUrbanClassificationCode, -1) AS rural_urban_classification,
                NULLIF(addr.ImdRankRounded, -1) AS imd_rounded,
                CASE
                    WHEN addr.MSOACode NOT IN ('NPC', '') THEN addr.MSOACode
                END AS msoa_code,
                CASE
                    WHEN addr.MSOACode NOT IN ('NPC', '') THEN 1
                    ELSE 0
                END AS has_postcode,
                CASE
                    WHEN carehm.PatientAddress_ID IS NOT NULL THEN 1
                    ELSE 0
                END AS care_home_is_potential_match,
                CASE
                    WHEN carehm.LocationRequiresNursing = 'Y' THEN 1
                    WHEN carehm.LocationRequiresNursing = 'N' THEN 0
                 END AS care_home_requires_nursing,
                CASE
                    WHEN carehm.LocationDoesNotRequireNursing = 'Y' THEN 1
                    WHEN carehm.LocationDoesNotRequireNursing = 'N' THEN 0
                 END AS care_home_does_not_require_nursing
            FROM PatientAddress AS addr
            LEFT JOIN PotentialCareHomeAddress AS carehm
            ON addr.PatientAddress_ID = carehm.PatientAddress_ID
        """
    )

    @QueryTable.from_function
    def apcs(self):
        return self._union_over_hes_archive(
            # There is a 1-1 relationship between APCS and APCS_Der
            """
            SELECT
                apcs.Patient_ID AS patient_id,
                apcs.APCS_Ident AS apcs_ident,
                apcs.Admission_Date AS admission_date,
                apcs.Discharge_Date AS discharge_date,
                apcs.Discharge_Destination as discharge_destination,
                apcs.Discharge_Method as discharge_method,
                apcs.Spell_Core_HRG_SUS AS spell_core_hrg_sus,
                apcs.Admission_Method AS admission_method,
                apcs.Der_Diagnosis_All AS all_diagnoses,
                apcs.Der_Procedure_All AS all_procedures,
                apcs.Patient_Classification AS patient_classification,
                CAST(der.Spell_PbR_CC_Day AS INTEGER) AS days_in_critical_care,
                der.Spell_Primary_Diagnosis as primary_diagnosis,
                der.Spell_Secondary_Diagnosis as secondary_diagnosis
            FROM APCS{table_suffix} AS apcs
            LEFT JOIN APCS_Der{table_suffix} AS der
            ON apcs.APCS_Ident = der.APCS_Ident
            WHERE {date_condition}
            """
        )

    def _union_over_hes_archive(self, query_template):
        """
        Return SQL which is the UNION ALL over a pair of queries: one against the
        currently updated set of HES tables; and one against the static archive of
        historical data.

        As the tables are identical in structure apart from a suffix on the table name
        we use a template to generate the query pair. And as the current and archive
        tables contain overlapping data we need to apply a date filter to ensure that we
        don't return duplicate rows. The cutoff date needs to be somewhere in the
        overlapping period, but it doesn't matter exactly where.

        We filter on the `Der_Activity_Month` column as this adminstrative value is what
        actually determines the current/archive split rather than any of the patient
        activity dates.

        The filter will naturally exclude any rows where this column is NULL. This
        affects only a single-digit number of rows in one table, which contain largely
        NULL values in any case, and so I think is acceptable.
        """
        date_column = "Der_Activity_Month"
        cutoff_date = "202204"
        return "\nUNION ALL\n".join(
            [
                query_template.format(
                    table_suffix="",
                    date_condition=(f"{date_column} >= '{cutoff_date}'"),
                ),
                query_template.format(
                    table_suffix="_ARCHIVED",
                    date_condition=f"{date_column} < '{cutoff_date}'",
                ),
            ]
        )

    @QueryTable.from_function
    def apcs_cost(self):
        return self._union_over_hes_archive(
            """
            SELECT
                cost.Patient_ID AS patient_id,
                cost.APCS_Ident AS apcs_ident,
                cost.Grand_Total_Payment_MFF AS grand_total_payment_mff,
                cost.Tariff_Initial_Amount AS tariff_initial_amount,
                cost.Tariff_Total_Payment AS tariff_total_payment,
                apcs.Admission_Date AS admission_date,
                apcs.Discharge_Date AS discharge_date
            FROM APCS_Cost{table_suffix} AS cost
            LEFT JOIN APCS{table_suffix} AS apcs
            ON cost.APCS_Ident = apcs.APCS_Ident
            WHERE {date_condition}
            """
        )

    apcs_historical = MappedTable(
        source="APCS_JRC20231009_LastFilesToContainAllHistoricalCostData",
        columns={
            "apcs_ident": "APCS_Ident",
            "admission_date": "Admission_Date",
            "discharge_date": "Discharge_Date",
            "spell_core_hrg_sus": "Spell_Core_HRG_SUS",
        },
    )

    apcs_cost_historical = QueryTable(
        """
        SELECT
            cost.Patient_ID AS patient_id,
            cost.APCS_Ident AS apcs_ident,
            cost.Grand_Total_Payment_MFF AS grand_total_payment_mff,
            cost.Tariff_Initial_Amount AS tariff_initial_amount,
            cost.Tariff_Total_Payment AS tariff_total_payment,
            apcs.Admission_Date AS admission_date,
            apcs.Discharge_Date AS discharge_date
        FROM APCS_Cost_JRC20231009_LastFilesToContainAllHistoricalCostData AS cost
        LEFT JOIN APCS_JRC20231009_LastFilesToContainAllHistoricalCostData AS apcs
        ON cost.APCS_Ident = apcs.APCS_Ident
    """
    )

    appointments = QueryTable(
        # WARNING: There are duplicate rows in the Appointment table, so we add DISTINCT
        # to remove them from this query. When they are removed from the Appointment
        # table, then we will remove DISTINCT from this query.
        """
            SELECT DISTINCT
                Appointment_ID AS appointment_id,
                Patient_ID AS patient_id,
                CAST(BookedDate AS date) AS booked_date,
                CAST(StartDate AS date) AS start_date,
                CAST(NULLIF(SeenDate, '9999-12-31T00:00:00') AS date) AS seen_date,
                CASE Status
                    WHEN 0 THEN 'Booked' COLLATE Latin1_General_CI_AS
                    WHEN 1 THEN 'Arrived' COLLATE Latin1_General_CI_AS
                    WHEN 2 THEN 'Did Not Attend' COLLATE Latin1_General_CI_AS
                    WHEN 3 THEN 'In Progress' COLLATE Latin1_General_CI_AS
                    WHEN 4 THEN 'Finished' COLLATE Latin1_General_CI_AS
                    WHEN 5 THEN 'Requested' COLLATE Latin1_General_CI_AS
                    WHEN 6 THEN 'Blocked' COLLATE Latin1_General_CI_AS
                    WHEN 8 THEN 'Visit' COLLATE Latin1_General_CI_AS
                    WHEN 9 THEN 'Waiting' COLLATE Latin1_General_CI_AS
                    WHEN 10 THEN 'Cancelled by Patient' COLLATE Latin1_General_CI_AS
                    WHEN 11 THEN 'Cancelled by Unit' COLLATE Latin1_General_CI_AS
                    WHEN 12 THEN 'Cancelled by Other Service' COLLATE Latin1_General_CI_AS
                    WHEN 14 THEN 'No Access Visit' COLLATE Latin1_General_CI_AS
                    WHEN 15 THEN 'Cancelled Due To Death' COLLATE Latin1_General_CI_AS
                    WHEN 16 THEN 'Patient Walked Out' COLLATE Latin1_General_CI_AS
                END AS status
            FROM Appointment
        """
    )

    clinical_events = QueryTable(
        """
            SELECT
                Patient_ID AS patient_id,
                CAST(NULLIF(ConsultationDate, '9999-12-31T00:00:00') AS date) AS date,
                NULL AS snomedct_code,
                CTV3Code AS ctv3_code,
                NumericValue AS numeric_value,
                Consultation_ID AS consultation_id,
                CodedEvent_ID
            FROM CodedEvent
            UNION ALL
            SELECT
                Patient_ID AS patient_id,
                CAST(NULLIF(ConsultationDate, '9999-12-31T00:00:00') AS date) AS date,
                ConceptId AS snomedct_code,
                NULL AS ctv3_code,
                NumericValue AS numeric_value,
                Consultation_ID AS consultation_id,
                CodedEvent_ID
            FROM CodedEvent_SNOMED
        """
    )

    clinical_events_ranges = QueryTable(
        f"""
            SELECT
                ce.*,
                cer.LowerBound AS lower_bound,
                cer.UpperBound AS upper_bound,
                CASE cer.Comparator
                    WHEN 3 THEN '~'
                    WHEN 4 THEN '='
                    WHEN 5 THEN '>='
                    WHEN 6 THEN '>'
                    WHEN 7 THEN '<'
                    WHEN 8 THEN '<='
                END COLLATE Latin1_General_CI_AS AS comparator
            FROM ({clinical_events.query}) ce
            LEFT JOIN CodedEventRange cer
                ON ce.CodedEvent_ID = cer.CodedEvent_ID
        """
    )

    @QueryTable.from_function
    def covid_therapeutics(self):
        def _risk_cohort_format(risk_cohort):
            # First remove any "Patients with [a]" and replace " and " with ","
            # within individual risk group fields
            replaced = f"REPLACE(REPLACE(REPLACE({risk_cohort}, 'Patients with a ', ''),  'Patients with ', ''), ' and ', ',')"
            # coalesce with a leading ',' and replace nulls with empty strings
            coalesced = f"coalesce(',' + NULLIF({replaced}, ''), '')"
            # use STUFF() to remove the first ','
            return f"STUFF({coalesced}, 1, 1, '')"

        coalesced_parts = " + ".join(
            f"coalesce(',' + NULLIF({risk_group_column}, ''), '')"
            for risk_group_column in [
                _risk_cohort_format("CASIM05_risk_cohort"),
                _risk_cohort_format("MOL1_high_risk_cohort"),
                _risk_cohort_format("SOT02_risk_cohorts"),
            ]
        )
        covid_therapeutics_risk_cohort = f"STUFF({coalesced_parts}, 1, 1, '')"

        return f"""
            SELECT DISTINCT
                Patient_ID AS patient_id,
                COVID_indication AS covid_indication,
                Count AS count,
                CurrentStatus AS current_status,
                Diagnosis AS diagnosis,
                FormName AS form_name,
                Intervention AS intervention,
                CASIM05_date_of_symptom_onset,
                MOL1_onset_of_symptoms,
                SOT02_onset_of_symptoms,
                {covid_therapeutics_risk_cohort} as risk_cohort,
                CAST(Received AS date) AS received,
                CAST(TreatmentStartDate AS date) AS treatment_start_date,
                AgeAtReceivedDate AS age_at_received_date,
                Region AS region,
                CONVERT(DATE, Der_LoadDate, 23) AS load_date
            FROM Therapeutics
        """

    covid_therapeutics_raw = QueryTable(
        """
        SELECT
            Patient_ID AS patient_id,
            COVID_indication AS covid_indication,
            Count AS count,
            CurrentStatus AS current_status,
            Diagnosis AS diagnosis,
            FormName AS form_name,
            Intervention AS intervention,
            CASIM05_risk_cohort,
            MOL1_high_risk_cohort,
            SOT02_risk_cohorts,
            CAST(Received AS date) AS received,
            CAST(TreatmentStartDate AS date) AS treatment_start_date,
            AgeAtReceivedDate AS age_at_received_date,
            Region AS region,
            CONVERT(DATE, Der_LoadDate, 23) AS load_date
        FROM Therapeutics
        """
    )

    decision_support_values = QueryTable(
        """
            SELECT
                decval.Patient_ID AS patient_id,
                CAST(NULLIF(decval.CalculationDateTime, '9999-12-31T00:00:00') AS date) AS calculation_date,
                decval.NumericValue AS numeric_value,
                decvalref.AlgorithmDescription AS algorithm_description,
                decvalref.AlgorithmVersion AS algorithm_version
            FROM DecisionSupportValue AS decval
            LEFT JOIN DecisionSupportValueReference AS decvalref
            ON decval.AlgorithmType = decvalref.AlgorithmType
        """
    )

    @QueryTable.from_function
    def ec(self):
        return self._union_over_hes_archive(
            """
            SELECT
                Patient_ID AS patient_id,
                EC_Ident AS ec_ident,
                Arrival_Date AS arrival_date,
                SUS_HRG_Code AS sus_hrg_code
            FROM
                EC{table_suffix}
            WHERE {date_condition}
            """
        )

    @QueryTable.from_function
    def ec_cost(self):
        return self._union_over_hes_archive(
            """
            SELECT
                cost.Patient_ID AS patient_id,
                cost.EC_Ident AS ec_ident,
                cost.Grand_Total_Payment_MFF AS grand_total_payment_mff,
                cost.Tariff_Total_Payment AS tariff_total_payment,
                ec.Arrival_Date AS arrival_date,
                ec.EC_Decision_To_Admit_Date AS ec_decision_to_admit_date,
                ec.EC_Injury_Date AS ec_injury_date
            FROM EC_Cost{table_suffix} AS cost
            LEFT JOIN EC{table_suffix} AS ec
            ON cost.EC_Ident = ec.EC_Ident
            WHERE {date_condition}
            """
        )

    @QueryTable.from_function
    def emergency_care_attendances(self):
        return self._union_over_hes_archive(
            f"""
            SELECT
                ec.Patient_ID AS patient_id,
                ec.EC_Ident AS id,
                ec.Arrival_Date AS arrival_date,
                ec.Discharge_Destination_SNOMED_CT COLLATE Latin1_General_BIN AS discharge_destination,
                {
                ", ".join(
                    f"diag.EC_Diagnosis_{i:02d} COLLATE Latin1_General_BIN AS diagnosis_{i:02d}"
                    for i in range(1, 25)
                )
            }
            FROM EC{{table_suffix}} AS ec
            LEFT JOIN EC_Diagnosis{{table_suffix}} AS diag
            ON ec.EC_Ident = diag.EC_Ident
            WHERE {{date_condition}}
            """
        )

    @QueryTable.from_function
    def ethnicity_from_sus(self):
        # Each dataset we want to query over consists of both current and archived data
        # so, for each of these, we need to create the appropriate UNION query and then
        # UNION all the results together into a query that covers all the datasets.
        ethnicity_code_tables = "\nUNION ALL\n".join(
            [
                self._union_over_hes_archive(
                    """
                    SELECT
                        Patient_ID,
                        SUBSTRING(Ethnic_Group, 1, 1) AS code
                    FROM APCS{table_suffix}
                    WHERE {date_condition}
                    """
                ),
                self._union_over_hes_archive(
                    """
                    SELECT
                        Patient_ID,
                        Ethnic_Category AS code
                    FROM EC{table_suffix}
                    WHERE {date_condition}
                    """
                ),
                self._union_over_hes_archive(
                    """
                    SELECT
                        Patient_ID,
                        SUBSTRING(Ethnic_Category, 1, 1) AS code
                    FROM OPA{table_suffix}
                    WHERE {date_condition}
                    """
                ),
            ]
        )

        # For each patient, find the most commonly occuring code (subject to certain
        # exclusions) across all the source datasets
        return f"""
            SELECT
              Patient_ID AS patient_id,
              code
            FROM (
              SELECT
                Patient_ID,
                code,
                ROW_NUMBER() OVER (
                    PARTITION BY Patient_ID
                    ORDER BY COUNT(code) DESC, code DESC
                ) AS row_num
              FROM ({ethnicity_code_tables}) t
              WHERE
                code IS NOT NULL
                AND code != ''
                AND code != '9'
                AND code != 'Z'
              GROUP BY Patient_ID, code
            ) t
            WHERE row_num = 1
        """

    household_memberships_2020 = QueryTable(
        """
            SELECT
                mb.Patient_ID AS patient_id,
                NULLIF(hh.Household_ID, 0) AS household_pseudo_id,
                NULLIF(hh.HouseholdSize, 0) AS household_size
            FROM HouseholdMember AS mb
            LEFT JOIN Household AS hh
            ON mb.Household_ID = hh.Household_ID
        """
    )

    isaric_raw = QueryTable(
        """
            SELECT
                Patient_ID as patient_id,
                age,
                "age.factor" AS age_factor,
                calc_age,
                sex,
                ethnic___1,
                ethnic___2,
                ethnic___3,
                ethnic___4,
                ethnic___5,
                ethnic___6,
                ethnic___7,
                ethnic___8,
                ethnic___9,
                ethnic___10,
                covid19_vaccine,
                CASE
                    WHEN covid19_vaccined != 'NA' THEN CONVERT(DATE, covid19_vaccined, 23)
                END AS covid19_vaccined,
                CASE
                    WHEN covid19_vaccine2d != 'NA' THEN CONVERT(DATE, covid19_vaccine2d, 23)
                END AS covid19_vaccine2d,
                covid19_vaccined_nk,
                corona_ieorres,
                coriona_ieorres2,
                coriona_ieorres3,
                inflammatory_mss,
                CASE
                    WHEN cestdat != 'NA' THEN CONVERT(DATE, cestdat, 23)
                END AS cestdat,
                CASE
                    WHEN hostdat != 'NA' THEN CONVERT(DATE, hostdat, 23)
                END AS hostdat,
                CASE
                    WHEN chrincard IN ('YES', 'NO', 'Unknown') THEN chrincard
                    WHEN chrincard = 'NA' THEN 'NO'
                END AS chrincard,
                CASE
                    WHEN hypertension_mhyn IN ('YES', 'NO', 'Unknown') THEN hypertension_mhyn
                    WHEN hypertension_mhyn = 'NA' THEN 'NO'
                END AS hypertension_mhyn,
                CASE
                    WHEN chronicpul_mhyn IN ('YES', 'NO', 'Unknown') THEN chronicpul_mhyn
                    WHEN chronicpul_mhyn = 'NA' THEN 'NO'
                END AS chronicpul_mhyn,
                CASE
                    WHEN asthma_mhyn IN ('YES', 'NO', 'Unknown') THEN asthma_mhyn
                    WHEN asthma_mhyn = 'NA' THEN 'NO'
                END AS asthma_mhyn,
                CASE
                    WHEN renal_mhyn IN ('YES', 'NO', 'Unknown') THEN renal_mhyn
                    WHEN renal_mhyn = 'NA' THEN 'NO'
                END AS renal_mhyn,
                CASE
                    WHEN mildliver IN ('YES', 'NO', 'Unknown') THEN mildliver
                    WHEN mildliver = 'NA' THEN 'NO'
                END AS mildliver,
                CASE
                    WHEN modliv IN ('YES', 'NO', 'Unknown') THEN modliv
                    WHEN modliv = 'NA' THEN 'NO'
                END AS modliv,
                CASE
                    WHEN chronicneu_mhyn IN ('YES', 'NO', 'Unknown') THEN chronicneu_mhyn
                    WHEN chronicneu_mhyn = 'NA' THEN 'NO'
                END AS chronicneu_mhyn,
                CASE
                    WHEN malignantneo_mhyn IN ('YES', 'NO', 'Unknown') THEN malignantneo_mhyn
                    WHEN malignantneo_mhyn = 'NA' THEN 'NO'
                END AS malignantneo_mhyn,
                CASE
                    WHEN chronichaemo_mhyn IN ('YES', 'NO', 'Unknown') THEN chronichaemo_mhyn
                    WHEN chronichaemo_mhyn = 'NA' THEN 'NO'
                END AS chronichaemo_mhyn,
                CASE
                    WHEN aidshiv_mhyn IN ('YES', 'NO', 'Unknown') THEN aidshiv_mhyn
                    WHEN aidshiv_mhyn = 'NA' THEN 'NO'
                END AS aidshiv_mhyn,
                CASE
                    WHEN obesity_mhyn IN ('YES', 'NO', 'Unknown') THEN obesity_mhyn
                    WHEN obesity_mhyn = 'NA' THEN 'NO'
                END AS obesity_mhyn,
                diabetes_type_mhyn,
                CASE
                    WHEN diabetescom_mhyn IN ('YES', 'NO', 'Unknown') THEN diabetescom_mhyn
                    WHEN diabetescom_mhyn = 'NA' THEN 'NO'
                END AS diabetescom_mhyn,
                CASE
                    WHEN diabetes_mhyn IN ('YES', 'NO', 'Unknown') THEN diabetes_mhyn
                    WHEN diabetes_mhyn = 'NA' THEN 'NO'
                END AS diabetes_mhyn,
                CASE
                    WHEN rheumatologic_mhyn IN ('YES', 'NO', 'Unknown') THEN rheumatologic_mhyn
                    WHEN rheumatologic_mhyn = 'NA' THEN 'NO'
                END AS rheumatologic_mhyn,
                CASE
                    WHEN dementia_mhyn IN ('YES', 'NO', 'Unknown') THEN dementia_mhyn
                    WHEN dementia_mhyn = 'NA' THEN 'NO'
                END AS dementia_mhyn,
                CASE
                    WHEN malnutrition_mhyn IN ('YES', 'NO', 'Unknown') THEN malnutrition_mhyn
                    WHEN malnutrition_mhyn = 'NA' THEN 'NO'
                END AS malnutrition_mhyn,
                smoking_mhyn,
                hooccur,
                CASE
                    WHEN hostdat_transfer != 'NA' THEN CONVERT(DATE, hostdat_transfer, 23)
                END AS hostdat_transfer,
                hostdat_transfernk,
                readm_cov19,
                CASE
                    WHEN dsstdat != 'NA' THEN CONVERT(DATE, dsstdat, 23)
                END AS dsstdat,
                CASE
                    WHEN dsstdtc != 'NA' THEN CONVERT(DATE, dsstdtc, 23)
                END AS dsstdtc
            FROM ISARIC_New
        """
    )

    @QueryTable.from_function
    def medications(self):
        return f"""
            SELECT
                meds.Patient_ID AS patient_id,
                CAST(meds.ConsultationDate AS date) AS date,
                dict.DMD_ID AS dmd_code,
                Consultation_ID AS consultation_id
            FROM MedicationIssue AS meds
            LEFT JOIN ({self._medications_dictionary_query()}) AS dict
            ON meds.MultilexDrug_ID = dict.MultilexDrug_ID
        """

    @QueryTable.from_function
    def medications_raw(self):
        return f"""
            SELECT
                meds.Patient_ID AS patient_id,
                CAST(meds.ConsultationDate AS date) AS date,
                dict.DMD_ID AS dmd_code,
                Consultation_ID AS consultation_id,
                MedicationStatus AS medication_status
            FROM MedicationIssue AS meds
            LEFT JOIN ({self._medications_dictionary_query()}) AS dict
            ON meds.MultilexDrug_ID = dict.MultilexDrug_ID
        """

    def _medications_dictionary_query(self):
        temp_database_name = self.config.get(
            "TEMP_DATABASE_NAME", "PLACEHOLDER_FOR_TEMP_DATABASE_NAME"
        )

        # We construct a medication dictionary table which combines the table provided
        # by TPP (removing entries with no dm+d mapping and entries with multiple dm+d
        # mappings) with a custom dictionary we supply, taking care to remove any
        # entries in our custom dictionary which are already defined in the TPP
        # dictionary. If we didn't do this then duplicate entries would result in
        # duplicate MedicationIssue rows when we do the join later.
        #
        # This query looks a bit gnarly, but MSSQL is sensible enough to just execute it
        # once and it performs significantly better than other approaches we've tried.
        return f"""
            SELECT meds_dict.MultilexDrug_ID, meds_dict.DMD_ID
            FROM MedicationDictionary AS meds_dict
            WHERE meds_dict.DMD_ID NOT IN ('', 'MULTIPLE_DMD_MAPPING')

            UNION ALL

            SELECT cust_dict.MultilexDrug_ID, cust_dict.DMD_ID
            FROM {temp_database_name}..CustomMedicationDictionary AS cust_dict
            WHERE NOT EXISTS (
              SELECT 1 FROM MedicationDictionary AS meds_dict
              WHERE
                meds_dict.MultilexDrug_ID = cust_dict.MultilexDrug_ID
                AND meds_dict.DMD_ID NOT IN ('', 'MULTIPLE_DMD_MAPPING')
            )
        """

    occupation_on_covid_vaccine_record = QueryTable(
        """
            SELECT
                Patient_ID AS patient_id,
                1 AS is_healthcare_worker
            FROM HealthCareWorker
        """
    )

    ons_deaths_raw = MappedTable(
        source="ONS_Deaths",
        columns=dict(
            date="dod",
            place="Place_of_occurrence",
            underlying_cause_of_death="icd10u",
            **{f"cause_of_death_{i:02d}": f"ICD100{i:02d}" for i in range(1, 16)},
        ),
    )

    ons_deaths = QueryTable(
        """
        SELECT
            Patient_ID AS patient_id,
            dod AS date,
            Place_of_occurrence AS place,
            icd10u AS underlying_cause_of_death,
            ICD10001 AS cause_of_death_01,
            ICD10002 AS cause_of_death_02,
            ICD10003 AS cause_of_death_03,
            ICD10004 AS cause_of_death_04,
            ICD10005 AS cause_of_death_05,
            ICD10006 AS cause_of_death_06,
            ICD10007 AS cause_of_death_07,
            ICD10008 AS cause_of_death_08,
            ICD10009 AS cause_of_death_09,
            ICD10010 AS cause_of_death_10,
            ICD10011 AS cause_of_death_11,
            ICD10012 AS cause_of_death_12,
            ICD10013 AS cause_of_death_13,
            ICD10014 AS cause_of_death_14,
            ICD10015 AS cause_of_death_15
        FROM (
            SELECT
                Patient_ID,
                dod,
                Place_of_occurrence,
                icd10u,
                ICD10001,
                ICD10002,
                ICD10003,
                ICD10004,
                ICD10005,
                ICD10006,
                ICD10007,
                ICD10008,
                ICD10009,
                ICD10010,
                ICD10011,
                ICD10012,
                ICD10013,
                ICD10014,
                ICD10015,
                ROW_NUMBER() OVER (
                    PARTITION BY Patient_ID
                    ORDER BY dod ASC, icd10u ASC
                ) AS rownum
            FROM ONS_Deaths
        ) t
        WHERE t.rownum = 1
        """
    )

    @QueryTable.from_function
    def opa(self):
        return self._union_over_hes_archive(
            """
            SELECT
                Patient_ID AS patient_id,
                OPA_Ident AS opa_ident,
                Appointment_Date AS appointment_date,
                Attendance_Status AS attendance_status,
                Consultation_Medium_Used AS consultation_medium_used,
                First_Attendance AS first_attendance,
                HRG_Code AS hrg_code,
                Treatment_Function_Code AS treatment_function_code
            FROM OPA{table_suffix}
            WHERE {date_condition}
            """
        )

    @QueryTable.from_function
    def opa_cost(self):
        return self._union_over_hes_archive(
            """
            SELECT
                cost.Patient_ID AS patient_id,
                cost.OPA_Ident AS opa_ident,
                cost.Tariff_OPP AS tariff_opp,
                cost.Grand_Total_Payment_MFF AS grand_total_payment_mff,
                cost.Tariff_Total_Payment AS tariff_total_payment,
                opa.Appointment_Date AS appointment_date,
                opa.Referral_Request_Received_Date AS referral_request_received_date
            FROM OPA_Cost{table_suffix} AS cost
            LEFT JOIN OPA{table_suffix} AS opa
            ON cost.OPA_Ident = opa.OPA_Ident
            WHERE {date_condition}
            """
        )

    @QueryTable.from_function
    def opa_diag(self):
        return self._union_over_hes_archive(
            """
            SELECT
                diag.Patient_ID AS patient_id,
                diag.OPA_Ident AS opa_ident,
                diag.Primary_Diagnosis_Code COLLATE Latin1_General_CI_AS AS primary_diagnosis_code,
                diag.Primary_Diagnosis_Code_Read COLLATE Latin1_General_BIN AS primary_diagnosis_code_read,
                diag.Secondary_Diagnosis_Code_1 COLLATE Latin1_General_CI_AS AS secondary_diagnosis_code_1,
                diag.Secondary_Diagnosis_Code_1_Read COLLATE Latin1_General_BIN AS secondary_diagnosis_code_1_read,
                opa.Appointment_Date AS appointment_date,
                opa.Referral_Request_Received_Date AS referral_request_received_date
            FROM OPA_Diag{table_suffix} AS diag
            LEFT JOIN OPA{table_suffix} AS opa
            ON diag.OPA_Ident = opa.OPA_Ident
            WHERE {date_condition}
            """
        )

    @QueryTable.from_function
    def opa_proc(self):
        return self._union_over_hes_archive(
            # "PROC" is a reserved word in T-SQL, so we drop the "O"
            """
            SELECT
                prc.Patient_ID AS patient_id,
                prc.OPA_Ident AS opa_ident,
                prc.Primary_Procedure_Code COLLATE Latin1_General_CI_AS AS primary_procedure_code,
                prc.Primary_Procedure_Code_Read COLLATE Latin1_General_BIN AS primary_procedure_code_read,
                prc.Procedure_Code_2 COLLATE Latin1_General_CI_AS AS procedure_code_2,
                prc.Procedure_Code_2_Read COLLATE Latin1_General_BIN AS procedure_code_2_read,
                opa.Appointment_Date AS appointment_date,
                opa.Referral_Request_Received_Date AS referral_request_received_date
            FROM OPA_Proc{table_suffix} AS prc
            LEFT JOIN OPA{table_suffix} AS opa
            ON prc.OPA_Ident = opa.OPA_Ident
            WHERE {date_condition}
            """
        )

    open_prompt = QueryTable(
        """
        SELECT
            Patient_ID AS patient_id,
            CASE
                WHEN CodeSystemId = 0 THEN ConceptId
            END AS snomedct_code,
            CTV3Code AS ctv3_code,
            CAST(CreationDate AS date) AS creation_date,
            CAST(ConsultationDate AS date) AS consultation_date,
            Consultation_ID AS consultation_id,
            CASE
                WHEN NumericCode = 1 THEN NumericValue
            END AS numeric_value
        FROM OpenPROMPT
    """
    )

    # Present a consistent view on the mother-child linkage table by removing any
    # obviously invalid or ambiguous entries and normalising the direction of the
    # relationship as child->mother regardless of the direction it was recorded. For a
    # more detail explanation of what this query aims to include and exclude, see the
    # test cases in:
    #
    #   tests/integration/backends/test_tpp.py#test_parents
    #
    # NOTE: The algorithm implemented below is described in prose in the TPP schema
    # documentation. Any changes should be appropriately reflected in the documentation.
    parents = QueryTable(
        """
        SELECT
            patient_id,
            MAX(mother_id) AS mother_id
        FROM (
            SELECT
                child.Patient_ID AS patient_id,
                parent.Patient_ID AS mother_id
            FROM (
                SELECT
                    CASE Type_of_Relationship
                      WHEN 'Mother' THEN Patient_ID
                      ELSE Patient_ID_Relationship_With
                    END AS child_id,
                    CASE Type_of_Relationship
                      WHEN 'Mother' THEN Patient_ID_Relationship_With
                      ELSE Patient_ID
                    END AS parent_id
                FROM
                    Relationship
                WHERE
                    Type_of_Relationship IN ('Mother', 'Child', 'Son', 'Daughter')
                    AND RelationshipEndDate IS NULL
            ) AS relationships
            JOIN Patient AS child
            ON relationships.child_id = child.Patient_ID
            JOIN Patient AS parent
            ON relationships.parent_id = parent.Patient_ID
            WHERE
              child.DateOfBirth > parent.DateOfBirth
              AND parent.Sex != 'M'
        ) AS mothers
        GROUP BY patient_id
        HAVING COUNT(DISTINCT mother_id) = 1
        """
    )

    patients = QueryTable(
        """
            SELECT
                Patient_ID as patient_id,
                DateOfBirth as date_of_birth,
                CASE
                    WHEN Sex = 'M' THEN 'male' COLLATE Latin1_General_CI_AS
                    WHEN Sex = 'F' THEN 'female' COLLATE Latin1_General_CI_AS
                    WHEN Sex = 'I' THEN 'intersex' COLLATE Latin1_General_CI_AS
                    ELSE 'unknown' COLLATE Latin1_General_CI_AS
                END AS sex,
                NULLIF(DateOfDeath, '99991231') AS date_of_death
            FROM Patient
        """,
        implementation_notes=dict(
            sex="Sex assigned at birth.",
        ),
    )

    practice_registrations = QueryTable(
        """
            SELECT
                reg.Patient_ID AS patient_id,
                CAST(reg.StartDate AS date) AS start_date,
                CAST(NULLIF(reg.EndDate, '9999-12-31T00:00:00') AS date) AS end_date,
                org.Organisation_ID AS practice_pseudo_id,
                NULLIF(org.STPCode, '') AS practice_stp,
                NULLIF(org.Region, '') AS practice_nuts1_region_name,
                CAST(org.GoLiveDate AS date) AS practice_systmone_go_live_date
            FROM RegistrationHistory AS reg
            LEFT OUTER JOIN Organisation AS org
            ON reg.Organisation_ID = org.Organisation_ID
        """
    )

    sgss_covid_all_tests = QueryTable(
        # Note that the `Symptomatic` column takes values "Y"/"N" in the positive data
        # and "true"/"false" in the negative
        """
            SELECT
                Patient_ID AS patient_id,
                Specimen_Date AS specimen_taken_date,
                1 AS is_positive,
                Lab_Report_Date AS lab_report_date,
                CASE Symptomatic
                    WHEN 'Y' THEN 1
                    WHEN 'N' THEN 0
                END AS was_symptomatic,
                CAST(NULLIF(SGTF, '') AS int) AS sgtf_status,
                NULLIF(Variant, '') AS variant,
                NULLIF(VariantDetectionMethod, '') AS variant_detection_method
            FROM SGSS_AllTests_Positive

            UNION ALL

            SELECT
                Patient_ID AS patient_id,
                Specimen_Date AS specimen_taken_date,
                0 AS is_positive,
                Lab_Report_Date AS lab_report_date,
                CASE Symptomatic
                    WHEN 'true' THEN 1
                    WHEN 'false' THEN 0
                END AS was_symptomatic,
                NULL AS sgtf_status,
                NULL AS variant,
                NULL AS variant_detection_method
            FROM SGSS_AllTests_Negative
        """
    )

    ukrr = QueryTable(
        """
            SELECT
                Patient_ID AS patient_id,
                CASE dataset
                    WHEN '2019prev' THEN '2019_prevalence' COLLATE Latin1_General_CI_AS
                    WHEN '2020prev' THEN '2020_prevalence' COLLATE Latin1_General_CI_AS
                    WHEN '2021prev' THEN '2021_prevalence' COLLATE Latin1_General_CI_AS
                    WHEN '2020inc' THEN '2020_incidence' COLLATE Latin1_General_CI_AS
                    WHEN '2020ckd' THEN '2020_ckd' COLLATE Latin1_General_CI_AS
                END AS dataset,
                renal_centre AS renal_centre,
                creat AS latest_creatinine,
                eGFR_ckdepi AS latest_egfr,
                rrt_start AS rrt_start_date,
                mod_start AS treatment_modality_start,
                mod_prev AS treatment_modality_prevalence
            FROM UKRR
        """
    )

    vaccinations = QueryTable(
        """
            SELECT
                vax.Patient_ID AS patient_id,
                vax.Vaccination_ID AS vaccination_id,
                CAST(vax.VaccinationDate AS date) AS date,
                vax.VaccinationName AS product_name,
                ref.VaccinationContent AS target_disease
            FROM Vaccination AS vax
            LEFT JOIN VaccinationReference AS ref
            ON vax.VaccinationName_ID = ref.VaccinationName_ID
        """
    )

    wl_clockstops_raw = QueryTable(
        # columns passed to CONVERT are likely to contain sha256 hashes
        """
            SELECT
                Patient_ID AS patient_id,
                ACTIVITY_TREATMENT_FUNCTION_CODE AS activity_treatment_function_code,
                PRIORITY_TYPE_CODE AS priority_type_code,
                CONVERT(
                    varchar(max),
                    PSEUDO_ORGANISATION_CODE_PATIENT_PATHWAY_IDENTIFIER_ISSUER,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_organisation_code_patient_pathway_identifier_issuer,
                CONVERT(
                    varchar(max),
                    PSEUDO_PATIENT_PATHWAY_IDENTIFIER,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_patient_pathway_identifier,
                CONVERT(
                    varchar(max),
                    Pseudo_Referral_Identifier,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_referral_identifier,
                Referral_Request_Received_Date AS referral_request_received_date,
                REFERRAL_TO_TREATMENT_PERIOD_END_DATE AS referral_to_treatment_period_end_date,
                REFERRAL_TO_TREATMENT_PERIOD_START_DATE AS referral_to_treatment_period_start_date,
                SOURCE_OF_REFERRAL_FOR_OUTPATIENTS AS source_of_referral_for_outpatients,
                Waiting_List_Type AS waiting_list_type,
                Week_Ending_Date AS week_ending_date
            FROM WL_ClockStops
        """
    )

    wl_clockstops = QueryTable(
        f"""
            SELECT
                Patient_ID AS patient_id,
                ACTIVITY_TREATMENT_FUNCTION_CODE AS activity_treatment_function_code,
                CASE PRIORITY_TYPE_CODE
                    WHEN '1' THEN 'routine' COLLATE Latin1_General_CI_AS
                    WHEN '2' THEN 'urgent' COLLATE Latin1_General_CI_AS
                    WHEN '3' THEN 'two week wait' COLLATE Latin1_General_CI_AS
                END AS priority_type_code,
                CONVERT(
                    varchar(max),
                    PSEUDO_ORGANISATION_CODE_PATIENT_PATHWAY_IDENTIFIER_ISSUER,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_organisation_code_patient_pathway_identifier_issuer,
                CONVERT(
                    varchar(max),
                    PSEUDO_PATIENT_PATHWAY_IDENTIFIER,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_patient_pathway_identifier,
                CONVERT(
                    varchar(max),
                    Pseudo_Referral_Identifier,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_referral_identifier,
                CONVERT(DATE, Referral_Request_Received_Date, 23) AS referral_request_received_date,
                CONVERT(DATE, REFERRAL_TO_TREATMENT_PERIOD_END_DATE, 23) AS referral_to_treatment_period_end_date,
                CONVERT(DATE, REFERRAL_TO_TREATMENT_PERIOD_START_DATE, 23) AS referral_to_treatment_period_start_date,
                SOURCE_OF_REFERRAL_FOR_OUTPATIENTS AS source_of_referral_for_outpatients,
                CASE WHEN Waiting_List_Type IN
                    {ehrql.tables.tpp.wl_clockstops._qm_node.schema.get_column_categories("waiting_list_type")}
                    THEN Waiting_List_Type END AS waiting_list_type,
                CONVERT(DATE, Week_Ending_Date, 23) AS week_ending_date
            FROM WL_ClockStops
        """
    )

    wl_openpathways_raw = QueryTable(
        # columns passed to CONVERT are likely to contain sha256 hashes
        """
            SELECT
                Patient_ID AS patient_id,
                ACTIVITY_TREATMENT_FUNCTION_CODE AS activity_treatment_function_code,
                Current_Pathway_Period_Start_Date AS current_pathway_period_start_date,
                PRIORITY_TYPE_CODE AS priority_type_code,
                CONVERT(
                    varchar(max),
                    PSEUDO_ORGANISATION_CODE_PATIENT_PATHWAY_IDENTIFIER_ISSUER,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_organisation_code_patient_pathway_identifier_issuer,
                CONVERT(
                    varchar(max),
                    PSEUDO_PATIENT_PATHWAY_IDENTIFIER,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_patient_pathway_identifier,
                CONVERT(
                    varchar(max),
                    Pseudo_Referral_Identifier,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_referral_identifier,
                REFERRAL_REQUEST_RECEIVED_DATE AS referral_request_received_date,
                REFERRAL_TO_TREATMENT_PERIOD_END_DATE AS referral_to_treatment_period_end_date,
                REFERRAL_TO_TREATMENT_PERIOD_START_DATE AS referral_to_treatment_period_start_date,
                SOURCE_OF_REFERRAL AS source_of_referral,
                Waiting_List_Type AS waiting_list_type,
                Week_Ending_Date AS week_ending_date
            FROM WL_OpenPathways
        """
    )

    wl_openpathways = QueryTable(
        f"""
            SELECT
                Patient_ID AS patient_id,
                ACTIVITY_TREATMENT_FUNCTION_CODE AS activity_treatment_function_code,
                CONVERT(DATE, Current_Pathway_Period_Start_Date, 23) AS current_pathway_period_start_date,
                CASE PRIORITY_TYPE_CODE
                    WHEN '1' THEN 'routine' COLLATE Latin1_General_CI_AS
                    WHEN '2' THEN 'urgent' COLLATE Latin1_General_CI_AS
                    WHEN '3' THEN 'two week wait' COLLATE Latin1_General_CI_AS
                END AS priority_type_code,
                CONVERT(
                    varchar(max),
                    PSEUDO_ORGANISATION_CODE_PATIENT_PATHWAY_IDENTIFIER_ISSUER,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_organisation_code_patient_pathway_identifier_issuer,
                CONVERT(
                    varchar(max),
                    PSEUDO_PATIENT_PATHWAY_IDENTIFIER,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_patient_pathway_identifier,
                CONVERT(
                    varchar(max),
                    Pseudo_Referral_Identifier,
                    2
                ) COLLATE Latin1_General_CI_AS AS pseudo_referral_identifier,
                CONVERT(DATE, REFERRAL_REQUEST_RECEIVED_DATE, 23) AS referral_request_received_date,
                CONVERT(
                    DATE,
                    NULLIF(REFERRAL_TO_TREATMENT_PERIOD_END_DATE, '9999-12-31'),
                    23
                ) AS referral_to_treatment_period_end_date,
                CONVERT(DATE, REFERRAL_TO_TREATMENT_PERIOD_START_DATE, 23) AS referral_to_treatment_period_start_date,
                SOURCE_OF_REFERRAL AS source_of_referral,
                CASE WHEN Waiting_List_Type IN
                    {ehrql.tables.tpp.wl_openpathways._qm_node.schema.get_column_categories("waiting_list_type")}
                    THEN Waiting_List_Type END AS waiting_list_type,
                CONVERT(DATE, Week_Ending_Date, 23) AS week_ending_date
            FROM WL_OpenPathways
        """
    )
