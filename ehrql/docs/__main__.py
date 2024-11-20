import sys
from pathlib import Path

from ehrql import quiz

from . import generate_docs, render


if __name__ == "__main__":
    output_dir = sys.argv[1]
    render(generate_docs(), Path(output_dir))
    quiz.write_docs(Path(output_dir) / "quiz_questions.md")
