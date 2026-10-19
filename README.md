# R&D Intelligence MVP

A small Python foundation for an R&D Intelligence workspace. The project will help organize research, explore evidence, and support informed R&D decisions. This initial version contains only a Streamlit home page; data ingestion, analytics, and integrations are future work.

## Setup

Use Python 3.12 or later. From the repository directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Run

```bash
python -m streamlit run app.py
```

## Test

```bash
python -m pytest -q
```

The test checks that the home page renders the project introduction.

## Data and secrets

Keep credentials, real business data, spreadsheets, and generated databases outside Git. The `.gitignore` excludes common local data formats and directories as a safeguard; review every staged change before committing. This foundation needs no API keys, external services, or business data.
