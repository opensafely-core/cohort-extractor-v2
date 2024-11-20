## Question 1
### Add column `age` to the dataset corresponding to the patient's age on January 1, 2024.
??? tip "Render correct answer"
    ```pycon
    patient_id        | age
    ------------------+------------------
    1                 | 50
    2                 | 75
    3                 | 20
    4                 | 16
    5                 | 85
    6                 | 29
    7                 | 70
    8                 | 31
    9                 | 92
    10                | 44

    ```

## Question 2
### Filter the clinical events table to only include records with SNOMED code `60621009`.
??? tip "Render correct answer"
    ```pycon
    patient_id        | row_id            | date              | snomedct_code     | numeric_value
    ------------------+-------------------+-------------------+-------------------+------------------
    1                 | 2                 | 2014-04-10        | 60621009          | 25.8
    2                 | 4                 | 2017-04-12        | 60621009          | 18.4
    2                 | 5                 | 2018-05-26        | 60621009          | 23.1
    3                 | 7                 | 2017-05-11        | 60621009          | 29.5
    4                 | 8                 | 2019-05-16        | 60621009          | 34.3
    5                 | 11                | 2017-05-23        | 60621009          | 22.3
    5                 | 12                | 2017-08-01        | 60621009          | 19.9
    6                 | 14                | 2018-08-16        | 60621009          | 22.8
    7                 | 16                | 2018-01-06        | 60621009          | 35.2
    8                 | 18                | 2022-10-25        | 60621009          | 16.3

    ```
