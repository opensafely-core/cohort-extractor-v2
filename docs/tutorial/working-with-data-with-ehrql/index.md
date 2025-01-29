You will use ehrQL to extract a _dataset_ from the tables of data in a secure OpenSAFELY backend.
A dataset is a new table containing one row per patient.
The patients in the dataset (your _population_) and the columns in the dataset are specified by your ehrQL _dataset definition_.

A dataset is the basis for further processing and analysis, which is covered in [the section of the main OpenSAFELY tutorial about scripted actions][1].

The tables in an OpenSAFELY backend contain data about patients, and about events that are linked to patients in an EHR system, such as observations, diagnoses, and prescriptions.

When you are developing your dataset definition, you do not have access to data in a secure OpenSAFELY backend.
Instead, you can run your ehrQL dataset definition against tables of fabricated dummy data.
You can use ehrQL to [generate your own tables of dummy data][2], but for now we will use the dummy tables in in the tutorial repository.

We have provided some dummy data for 100 fictional patients.
The data is in a directory called `dummy_tables`, and in your Codespace you can open the CSV files in that directory by clicking on the file in the _Explorer_ tab.

When developing your dataset definition, you can use ehrQL's [`show()` function][3] to see the data you're working with.
This is what the code in `dataset_definition.py` does.
Let's talk through the lines of code.

These lines make some ehrQL functions and objects available for you to use:

```ehrql
from ehrql import show
from ehrql.tables.core import patients, practice_registrations, clinical_events, medications
```

This line opens the new window and shows you the contents of the patients table:

```py
show(patients)
```

Notice that there is one row per patient, and each value in the `patient_id` column is unique.

> Question: What happens if you add `show(clinical_events)`?

Your task, when writing ehrQL, is to transform the data in these tables into a dataset.

## Terminology

When transforming data in tables into a dataset, you work data via various intermediate objects called _frames_ and _series_.

Frames are like tables, and some frames of data contain (at most) one row for each patient, while others contain multiple rows for each patient.
Whe call these _patient frames_ and _event frames_ respectively.

A frame consists of multiple series of data.
Each series has a label and, depending on which frame the series was derived from, will be a _patient series_ or an _event series_.
For instance, a patient series is a column of a patient frame.

All frames have a `patient_id` series, and for a patient frame the values in this column will be unique.

All the values in a series must be of the same type (or null).
We call a series containing boolean (true or false) values a _boolean series_.

In the next sections we will demonstrate how to work with these objects.

Next: [Simple transformations](../simple-transformations/index.md)

!!! abstract "Feedback"
    Had enough? That's not a problem, but if you could fill in this very short [feedback form][4]{:target="_blank"} we'd really appreciate it.

[1]: https://docs.opensafely.org/getting-started/tutorial/add-a-scripted-action-to-the-pipeline/
[2]: ../../how-to/dummy-data.md
[3]: ../../explanation/vscode-extension.md
[4]: https://docs.google.com/forms/d/e/1FAIpQLSeouuTXPnwShAjBllyln4tl2Q52PMG_aUhpma4odpE2MmCngg/viewform
