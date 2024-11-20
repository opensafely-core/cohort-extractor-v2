# Quiz

Test your ehrQL knowledge by answering a quiz!

## Setup

You should already have a file called `quiz_answers.py` in your repo. This is the file you will use to answer the quiz.
(If it is not there, you can run `opensafely exec ehrql:v1 dump-quiz-file` to place it in your folder.)

To complete the quiz, you should modify the `answer = ...` line for each question. Your answer can span multiple lines (but take care of bracket placements)! If needed, you can even define your own intermediate variables (like the `latest_asthma_med` variable we defined in [Writing a dataset definition](../writing-a-dataset-definition/#select-each-patients-most-recent-asthma-medication)) to help you create the correct `answer`.

## Rendering the correct answer

The `example-data` folder in your repo contains dummy tables (that you can use with the `sandbox` and `debug` commands). For each question in the quiz, you can see what the answer would look like with the default example data to help you work towards the correct ehrQL syntax.

---8<-- 'includes/generated_docs/quiz_questions.md'
