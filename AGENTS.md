# AGENTS.md

<!-- versione 3.1 -->

## Project purpose

This repository contains a DSL manager application.

## Python version

Use Python 3.12.

The project requires:

```text
>=3.12,<3.13
```

## Repository layout

Use the `src/` layout:

```text
dsl_manager-v1/
  .codex/
    config.toml
  .kb/                         # project knowledge; intentionally ignored by Git
    documenti/
    projects/
      slicing/
        slice_01/
    prompt/
    template/
  pyproject.toml
  src/
    dsl_mngr/
      __init__.py
      __main__.py
      main.py
      cli/
        app.py
        commands/
      core/
      workers/
  tests/
    expected/
    fixtures/
    test_slice_01_*.py
    ...
    test_slice_19_*.py
```

The Python package is `dsl_mngr`.

`src` is not a Python package and must not be imported as one.

The `.kb` directory contains project documentation, prompts, templates, and
slicing material. Keep it outside Git until this policy is explicitly changed,
but treat its contents as project context when a task refers to them.

## File naming conventions

Use lowercase `snake_case` for new project-controlled files and directories.

Use an underscore followed by a two-digit, zero-padded number for ordered
sequences:

```text
slice_01/
dsl_manager_slice_01_prompt.md
dsl_manager_slice_01_report.md
test_slice_01_workspace_config_logging.py
design_document_v_01.md
```

Do not omit either the separator or the zero-padding in ordered names. When
renaming an ordered file, update all textual references to it in the same
change. Do not apply zero-padding to years, dates, schema versions, or runtime
identifiers whose format is defined by an external or existing application
contract.

## Import rules

Use absolute imports from the top-level package:

```python
from dsl_mngr.main import greet
```

Do not use imports such as:

```python
from src.dsl_mngr.main import greet
import main
```

## Canonical logical commands

These are the logical project commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m dsl_mngr
```

They must always be executed with the correct project interpreter for the current environment.

## Environment-specific interpreter rules

### Codex inside VS Code on Windows

Do not rely on plain `python`.

Before running any command that invokes Python, pip, pytest, or project tooling that depends on Python:

1. inspect `.codex/config.toml`;
2. read `PROJECT_PYTHON` from `[shell_environment_policy.set]`;
3. use that value as the only valid Python executable for this project.

If the user asks to run a command containing `python`, `pip`, `pytest`, or another Python entry point, rewrite the command so it uses `PROJECT_PYTHON`.

Examples:

```powershell
# User asks:
python --version

# Run instead:
.\.venv\Scripts\python.exe --version
```

```powershell
# User asks:
python -m pytest

# Run instead:
.\.venv\Scripts\python.exe -m pytest
```

```powershell
# User asks:
pip install -e ".[dev]"

# Run instead:
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Do not use the global `python` executable unless `.codex/config.toml` explicitly points to it.

Before modifying code or running tests, ensure the project is installed with the configured interpreter:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

After any code change, run tests with the configured interpreter:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

When reporting command results, mention which interpreter was used.

### Codex web / cloud

Use the Python runtime selected in the Codex cloud environment.

Rely on plain `python` in the cloud environment.

Ignore `.codex/config.toml` and ignore `PROJECT_PYTHON` under `[shell_environment_policy.set]`; those are local VS Code / Windows rules.

## VS Code rules

VS Code should use the project virtual environment:

```text
.venv
```

Do not rely on custom `PYTHONPATH` settings to make imports work.

Imports must work because the package is installed in editable mode.

## Codex rules

Before running tests or modifying code, make sure the project has been installed with the correct interpreter for the current environment:

```bash
python -m pip install -e ".[dev]"
```

After any code change, run tests with the correct interpreter for the current environment:

```bash
python -m pytest
```

Show the diff and the test result.
