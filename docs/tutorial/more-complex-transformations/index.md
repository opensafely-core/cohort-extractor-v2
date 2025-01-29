## Practice registrations

Our next task is to find the patients who were registered with a GP practice on the index date.
A patient can have multiple practice registrations – perhaps they've moved house and changed GPs, or perhaps they're a student living away from home and are registered with two GPs.

Data about practice registrations lives in the `practice_registrations` table.
Again, we have some dummy data, which we can see with the `show()` function.
 Replace the code in `dataset_definition.py` with the following:


```ehrql
from ehrql import show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

show(practice_registrations)
```

(Don't worry, we'll reinstate `aged_17_or_older` and `is_alive` soon!)

You can read more about `practice_registrations` in the [ehrQL schema documentation][1].

To find the patients who were registered with a GP practice on the index date, we want to find the registrations that started before the index date, and then exclude those that also ended before the index date.

Let's break this down.
First, we'll create a boolean series indicating whether each registration started before the index date:


```ehrql
from ehrql import show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

show(
    practice_registrations.start_date,
    practice_registrations.start_date <= index_date
)
```

Notice that we're showing the new boolean series alongside the `practice_registrations` table.

We can then use this boolean series to filter `practice_registrations` to create a new event frame containing only the rows where the boolean series is `True`:

```ehrql
from ehrql import show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

show(practice_registrations.where(practice_registrations.start_date <= index_date))
```

And now we can filter this event frame to create another new event frame containing only the rows where another boolean series is `False`:

```ehrql
from ehrql import show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

show(
    practice_registrations
    .where(practice_registrations.start_date <= index_date)
    .except_where(practice_registrations.end_date < index_date)
)
```

Notice that we're splitting a long expression over two lines.
This is optional.
See [this StackOverflow question][2] for more about how Python parses long lines.

Finally we want to ask whether a row in this new event frame exists for each patient:

```ehrql
from ehrql import show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

show(
    practice_registrations
    .where(practice_registrations.start_date <= index_date)
    .except_where(practice_registrations.end_date < index_date)
    .exists_for_patient()
)
```

Here, we have transformed an event frame into a patient series.

We can give this new patient series a name, and we can combine it with other series:

```ehrql
from ehrql import show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

aged_17_or_older = patients.age_on(index_date) >= 17
is_alive = patients.is_alive_on(index_date)
is_registered = (
    practice_registrations
    .where(practice_registrations.start_date <= index_date)
    .except_where(practice_registrations.end_date < index_date)
    .exists_for_patient()
)

show(
    aged_17_or_older,
    is_alive,
    is_registered,
    aged_17_or_older & is_alive & is_registered
)
```

## Clinical events

The diabetes QOF register needs to contain all patients who had an unresolved diabetes diagnosis on 31st March 2024.
To work out how to find these patients, we need to understand how things like diagnoses are recorded in a patient's health record.

Clinical events – things like observations, measurements, and diagnoses – are recorded in a table called `clinical_events`.
Again, we have some dummy data:


```
from ehrql import show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

show(clinical_events)
```

Clinical events are identified by SNOMED-CT code.
There are hundreds of thousands of SNOMED-CT codes, covering the full range of events that might be recorded on a patient's health record.
There might be tens or hundreds of codes that describe a condition such as diabetes, and researchers can use [codelists][3] to identify just the events that indicate a condition.

QOF rules come with codelists, and we'll use [this codelist][4], published by NHS Digital and hosted on OpenCodelists, to identify clinical events indicating a diagnosis of diabetes.
The codelist has already been downloaded into the tutorial Codespace, and is in a CSV file at `codelists/nhsd-primary-care-domain-refsets-dm_cod.csv`.
(The QOF rules use very short names for things, and `DM_COD` is short for "Diabetes Mellitus Codes".)

We can load the codelist from the CSV file, and use it to find just the events with a code in the codelist:

```ehrql
from ehrql import codelist_from_csv, show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

diabetes_codes = codelist_from_csv("codelists/nhsd-primary-care-domain-refsets-dm_cod.csv", column="code")

show(clinical_events.where(clinical_events.snomedct_code.is_in(diabetes_codes)))
```

Note that for the sake of this tutorial, all diabetes diagnosis events have the same SNOMED-CT code in the dummy data.

We can then ask which patients have a diabetes diagnosis code:

```ehrql
from ehrql import codelist_from_csv, show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

diabetes_codes = codelist_from_csv("codelists/nhsd-primary-care-domain-refsets-dm_cod.csv", column="code")

show(
    clinical_events
    .where(clinical_events.snomedct_code.is_in(diabetes_codes))
    .exists_for_patient()
)
```

But the QOF register should contain all patients with an _unresolved_ diabetes diagnosis.
There is another codelist, [`DMRES_COD`][5], that contains a single code indicating that a diabetes diagnosis has been resolved.

To find the patients with an unresolved diagnosis, we need to find the date of each patient's latest diabetes diagnosis event (if any) and the date of each patient's latest diabetes resolved event (if any), and take only patients where there is a diabetes diagnosis event and no subsequent diabetes resolved event.

We can find the latest event before the index date for each patient matching a codelists:

```ehrql
from ehrql import codelist_from_csv, show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

diabetes_codes = codelist_from_csv("codelists/nhsd-primary-care-domain-refsets-dm_cod.csv", column="code")
resolved_codes = codelist_from_csv("codelists/nhsd-primary-care-domain-refsets-dmres_cod.csv", column="code")

last_diagnosis_date = (
    clinical_events.where(clinical_events.snomedct_code.is_in(diabetes_codes))
    .sort_by(clinical_events.date)
    .where(clinical_events.date <= index_date)
    .last_for_patient()
    .date
)
last_resolved_date = (
    clinical_events.where(clinical_events.snomedct_code.is_in(resolved_codes))
    .sort_by(clinical_events.date)
    .where(clinical_events.date <= index_date)
    .last_for_patient()
    .date
)

show(last_diagnosis_date, last_resolved_date)
```

There are five cases we need to consider:

1. a patient has no diagnosis events and no resolved events
2. a patient has diagnosis events but no resolved events
3. a patient has resolved events but no diagnosis events (if you're wondering how this could happen… data is messy!)
4. a patient has diagnosis events and resolved events, and the last diagnosis event is after the last resolved event
5. a patient has diagnosis events and resolved events, and the last resolved event is after the last diagnosis event

A patient has an unresolved diagnosis in cases 2 and 4.
In other words, we want the patients where `last_diagnosis_date` is not null, and where either `last_resolved_date` is null (case 2), or `last_resolved_date` is before `last_diagnosis_date` (case 4):

```ehrql
from ehrql import codelist_from_csv, show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

diabetes_codes = codelist_from_csv("codelists/nhsd-primary-care-domain-refsets-dm_cod.csv", column="code")
resolved_codes = codelist_from_csv("codelists/nhsd-primary-care-domain-refsets-dmres_cod.csv", column="code")

last_diagnosis_date = (
    clinical_events.where(clinical_events.snomedct_code.is_in(diabetes_codes))
    .sort_by(clinical_events.date)
    .where(clinical_events.date <= index_date)
    .last_for_patient()
    .date
)
last_resolved_date = (
    clinical_events.where(clinical_events.snomedct_code.is_in(resolved_codes))
    .sort_by(clinical_events.date)
    .where(clinical_events.date <= index_date)
    .last_for_patient()
    .date
)

has_unresolved_diabetes = last_diagnosis_date.is_not_null() & (
    last_resolved_date.is_null() | (last_resolved_date < last_diagnosis_date)
)

show(last_diagnosis_date, last_resolved_date, has_unresolved_diabetes)
```

We've now done all the work required to find patients on the diabetes QOF register.
To recap, the register should contain all patients who, on 31st March 2024:

* were at least 17 years old,
* were alive,
* were registered with a GP practice, and
* had an unresolved diabetes diagnosis.

Here's the full code:

```ehrql
from ehrql import codelist_from_csv, show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications

index_date = "2024-03-31"

diabetes_codes = codelist_from_csv("codelists/nhsd-primary-care-domain-refsets-dm_cod.csv", column="code")
resolved_codes = codelist_from_csv("codelists/nhsd-primary-care-domain-refsets-dmres_cod.csv", column="code")

aged_17_or_older = patients.age_on(index_date) >= 17
is_alive = patients.is_alive_on(index_date)
is_registered = (
    practice_registrations.where(practice_registrations.start_date <= index_date)
    .except_where(practice_registrations.end_date < index_date)
    .exists_for_patient()
)

last_diagnosis_date = (
    clinical_events.where(clinical_events.snomedct_code.is_in(diabetes_codes))
    .sort_by(clinical_events.date)
    .where(clinical_events.date <= index_date)
    .last_for_patient()
    .date
)
last_resolved_date = (
    clinical_events.where(clinical_events.snomedct_code.is_in(resolved_codes))
    .sort_by(clinical_events.date)
    .where(clinical_events.date <= index_date)
    .last_for_patient()
    .date
)

has_unresolved_diabetes = last_diagnosis_date.is_not_null() & (
    last_resolved_date.is_null() | (last_resolved_date < last_diagnosis_date)
)

on_register = aged_17_or_older & is_alive & is_registered & has_unresolved_diabetes

show(
    aged_17_or_older,
    is_alive,
    is_registered,
    has_unresolved_diabetes,
    on_register
)
```

We're showing all the boolean series together so that you can see why different patients do or do not end up on the register.

Next: [Building a dataset](../building-a-dataset/index.md)

!!! abstract "Feedback"
    Had enough? That's not a problem, but if you could fill in this very short [feedback form][6]{:target="_blank"} we'd really appreciate it.

[1]: https://docs.opensafely.org/ehrql/reference/schemas/core/#practice_registrations
[2]: https://stackoverflow.com/questions/4172448/is-it-possible-to-break-a-long-line-to-multiple-lines-in-python
[3]: ../../how-to/codelists.md
[4]: https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/dm_cod/
[5]: https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/dmres_cod/
[6]: https://docs.google.com/forms/d/e/1FAIpQLSeouuTXPnwShAjBllyln4tl2Q52PMG_aUhpma4odpE2MmCngg/viewform
