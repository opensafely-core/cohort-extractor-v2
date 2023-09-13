from ehrql import Dataset
from ehrql.tables.beta.tpp import practice_registrations

dataset = Dataset()
dataset.practice = practice_registrations.for_patient_on("2023-01-01").practice_pseudo_id
