# inquisitive-transformer

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Do not enter planning-only modes.** All thinking must produce files and commits. If scope is unclear, create a `planning/` directory and write `.md` files there instead of using an internal planning mode.
- **Keep this file up to date.** As the project takes shape, record architectural decisions, conventions, and anything needed to work effectively in this repo.
- **Update README.md regularly.** It should always reflect the current state of the project for human readers.

## Testing
- **Write unit tests early.** As soon as there is testable logic, create a test file. Use `pytest` for Python projects or the appropriate test framework for the language in use.
- **Set up CI as soon as tests exist.** Create a `.github/workflows/ci.yml` GitHub Actions workflow that runs the test suite on push and pull request. Keep the workflow simple — install dependencies and run tests.
- **Keep tests passing.** Do not commit code that breaks existing tests. If a change requires updating tests, update them in the same commit.

## Project Description

The Inquisitive Transformer introduces a **perceptiveness parameter (alpha)** into transformer
attention: `softmax(QK^T/sqrt(d) + alpha * S(K)) V`. This is an orthogonal behavioral control
axis to temperature -- it selectively amplifies or suppresses surprising/out-of-place keys rather
than uniformly scaling the distribution.

Target: GPT-2 (124M) as proof of concept, with a custom "Contextual Violation Detection" benchmark.

## Architecture and Conventions

- **Base model**: GPT-2 via HuggingFace Transformers (modify attention class directly)
- **Core code**: `src/` -- attention module, model wrapper, surprise functions
- **Experiments**: `experiments/` -- one script per ablation (E1-E4)
- **Benchmarks**: `src/benchmark/` -- CVD dataset and evaluation harness
- **Plans**: `planning/` -- project plan and technical spec (see these for full details)
- **Language**: Python, using `python` (not `python3`) on this Windows system
- **Testing**: pytest, CI via GitHub Actions

# currentDate
Today's date is 2026-03-30.
