# RePORTaLiN-Specialist - Clinical Data Pipeline

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Version: 0.0.1](https://img.shields.io/badge/version-0.0.1-green.svg)](./pyproject.toml)

A data processing pipeline for clinical research data: extraction, transformation, and de-identification.

## Overview

RePORTaLiN-Specialist provides a complete pipeline for processing sensitive clinical research data:

1. **Data Dictionary Loading** - Process Excel data dictionaries to JSONL
2. **Data Extraction** - Convert Excel datasets to JSONL format
3. **De-identification** - PHI/PII detection and pseudonymization

## Quick Start

```bash
# Create virtual environment (recommended)
make venv
source .venv/bin/activate

# Install dependencies
make install

# Run complete pipeline
make run

# Run with de-identification
make run-deidentify

# Or use Python directly
python main.py --enable-deidentification --countries IN US
```

## Project Structure

```
RePORTaLiN-Specialist/
├── main.py                    # Pipeline entry point
├── config.py                  # Configuration
├── pyproject.toml             # Project metadata and tool config
├── requirements.txt           # Dependencies
├── scripts/
│   ├── load_dictionary.py     # Data dictionary processor
│   ├── extract_data.py        # Excel to JSONL extraction
│   ├── deidentify.py          # De-identification engine
│   └── utils/
│       ├── country_regulations.py  # Privacy regulations (14 countries)
│       └── logging.py         # Logging utilities
└── data/
    ├── data_dictionary_and_mapping_specifications/
    └── dataset/               # Input Excel files
```

## Usage

### Make Commands

```bash
make help              # Show all commands
make run               # Run full pipeline
make run-verbose       # Run with debug logging
make run-dictionary    # Run dictionary loading only
make run-extract       # Run data extraction only
make run-deidentify    # Run with de-identification
make lint              # Run code linter
make format            # Format code
make test              # Run tests
make clean             # Clean cache files
```

### Command Line Options

```bash
python main.py --help

# Skip specific steps
python main.py --skip-dictionary
python main.py --skip-extraction

# Verbose logging
python main.py --verbose

# De-identification options
python main.py --enable-deidentification --countries ALL
python main.py --enable-deidentification --no-encryption
```

### Supported Countries

14 countries supported for de-identification compliance:

| Region | Countries |
|--------|-----------|
| Americas | US, CA, BR |
| Europe | EU, GB |
| Asia | IN, ID, PH |
| Africa | ZA, KE, NG, GH, UG |
| Oceania | AU |

Regulations: HIPAA, GDPR, LGPD, DPDPA, POPIA, and more.

## Development

### Setup Development Environment

```bash
make venv
source .venv/bin/activate
make install-dev
```

### Code Quality

```bash
make lint        # Check code style
make format      # Auto-format code
make typecheck   # Run type checker
make test-cov    # Run tests with coverage
```

## Requirements

- Python 3.10+
- See `requirements.txt` for dependencies

## Security

This project handles PHI/PII data. See `.github/copilot-instructions.md` for security guidelines.

**Never commit:**
- Actual patient data
- API keys or secrets
- Unencrypted mappings

## License

MIT License
