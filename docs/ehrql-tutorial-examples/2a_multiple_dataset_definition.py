from ehrql.ehrql import Dataset
from ehrql.tables.examples.tutorial import patients, prescriptions

dataset = Dataset()

year_of_birth = patients.date_of_birth.year
dataset.define_population(year_of_birth >= 2000)

dataset.sex = patients.sex
dataset.most_recent_dmd_code = (
    prescriptions.sort_by(prescriptions.processing_date)
    .last_for_patient()
    .prescribed_dmd_code
)
