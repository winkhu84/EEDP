# EEDP

Electrical Engineering Development Platform for PLC engineering automation.

## Features

- FC_IO Generator
- Siemens TIA Tag CSV Generator
- Siemens TIA Portal V20 XLSX Generator
- Generate Framework
- Generation Report
- Output Management

## Project Structure

```text
app/
docs/
library/
output/
resources/
scripts/
tests/
```

## Requirements

- Python 3.11+

Required packages:

- PySide6
- pandas
- openpyxl
- pyyaml

## Installation

```bash
git clone https://github.com/winkhu84/EEDP.git
cd EEDP
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Current Version

**Current Release:** v0.3

Generate Framework completed.
