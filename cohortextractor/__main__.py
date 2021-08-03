import os
from argparse import ArgumentParser
from pathlib import Path

from .main import main


def existing_python_file(value):
    path = Path(value)
    if not path.exists():
        raise ValueError(f"{value} does not exit")
    if not path.suffix == ".py":
        raise ValueError(f"{value} is not a Python file")
    return path


parser = ArgumentParser(description="Generate cohorts in OpenSAFELY")
parser.add_argument(
    "--cohort-definition",
    help="The path of the file where the cohort is defined",
    type=existing_python_file,
)
parser.add_argument(
    "--output-dir",
    help="Location to store output files",
    type=Path,
    default="output",
)
parser.add_argument(
    "--output-file",
    help="The name of the file where the output will be written",
    type=str,
)
parser.add_argument(
    "--dummy-data-file",
    help="Provide dummy data from a file to be validated and used as output",
    type=Path,
)

options = parser.parse_args()

if not (options.dummy_data_file or os.environ.get("DATABASE_URL")):
    parser.error(
        "error: either --dummy-data-file or DATABASE_URL environment variable is required"
    )

main(
    definition_path=options.cohort_definition,
    output_file=options.output_dir / options.output_file,
    db_url=os.environ.get("DATABASE_URL"),
    backend_id=os.environ.get("BACKEND"),
    dummy_data_file=options.dummy_data_file,
)
