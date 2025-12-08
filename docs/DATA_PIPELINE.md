# Data Pipeline Architecture

## Overview

The RePORTaLiN-Agent implements a complete data pipeline for querying RePORT India clinical study data:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA PIPELINE FLOW                                  │
│                                                                             │
│    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────┐ │
│    │ EXTRACTION  │ ──► │ DE-IDENTIFY │ ──► │   RESULTS   │ ──► │   MCP   │ │
│    │             │     │             │     │             │     │  ACCESS │ │
│    │ Excel→JSONL │     │ PHI Removal │     │ Clean Data  │     │  Tools  │ │
│    └─────────────┘     └─────────────┘     └─────────────┘     └─────────┘ │
│                                                                             │
│    data/dataset/       scripts/            results/            server/     │
│    *.xlsx              deidentify.py       deidentified/       tools.py    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Pipeline Stages

### Stage 1: Extraction (`scripts/extract_data.py`)

Converts raw Excel files to JSONL format:

- **Input**: `data/dataset/Indo-vap_csv_files/*.xlsx`
- **Output**: `results/dataset/{name}/original/` and `results/dataset/{name}/cleaned/`
- **Features**:
  - Type conversion (dates, numbers, NaN handling)
  - Duplicate column removal
  - Progress tracking with integrity checks

```bash
# Run extraction only
python main.py --skip-dictionary
```

### Stage 2: De-identification (`scripts/deidentify.py`)

Removes PHI/PII per DPDPA 2023 requirements:

- **Input**: `results/dataset/{name}/`
- **Output**: `results/deidentified/{name}/`
- **Features**:
  - 18+ PHI types detected (names, Aadhaar, PAN, ABHA, dates, etc.)
  - Country-specific patterns (India, US, Indonesia, etc.)
  - Pseudonymization with deterministic hashing
  - Date shifting with interval preservation
  - Encrypted mapping storage (AES-256-GCM)

```bash
# Run full pipeline with de-identification
python main.py --enable-deidentification -c IN
```

### Stage 3: MCP Access (`server/data_pipeline.py`)

Connects MCP tools to de-identified results:

- **Input**: `results/deidentified/{name}/`
- **Output**: JSON responses via MCP tools
- **Features**:
  - K-anonymity protection (k ≥ 5)
  - Aggregate-only queries by default
  - Group suppression for small counts
  - Audit logging for compliance

## MCP Tools

| Tool | Purpose | Privacy |
|------|---------|---------|
| `get_pipeline_status` | Check if pipeline has been run | N/A |
| `list_datasets` | Discover available datasets | N/A |
| `describe_schema` | Get field definitions | N/A |
| `query_database` | Execute queries | K-anonymity protected |
| `search_dictionary` | Search data dictionary | N/A |
| `fetch_metrics` | Compute statistics | K-anonymity protected |
| `health_check` | Server status | N/A |

## Quick Start

```bash
# 1. Run the data pipeline
python main.py --enable-deidentification -c IN

# 2. Start the MCP server
uv run uvicorn server.main:app --host 127.0.0.1 --port 8000

# 3. Run the example client
uv run python client/examples/query_clinical_data.py
```

## Privacy Protection

All queries go through k-anonymity checks:

1. **Group Suppression**: Results with fewer than k=5 records are hidden
2. **Aggregate Only**: Individual records are never returned
3. **Audit Logging**: All access is logged for DPDPA compliance
4. **Encrypted Mappings**: De-identification keys stored with AES-256-GCM

## Directory Structure

```
RePORTaLiN-Agent/
├── data/
│   └── dataset/
│       └── Indo-vap_csv_files/     # Raw Excel files (INPUT)
│           ├── 1A_ICScreening.xlsx
│           ├── 2A_ICBaseline.xlsx
│           └── ...
├── results/
│   ├── dataset/
│   │   └── Indo-vap/               # Extracted JSONL
│   │       ├── original/
│   │       └── cleaned/
│   ├── deidentified/
│   │   └── Indo-vap/               # De-identified JSONL (MCP reads from here)
│   │       ├── original/
│   │       └── cleaned/
│   └── data_dictionary_mappings/   # Data dictionary JSONL
├── scripts/
│   ├── extract_data.py             # Stage 1: Extraction
│   ├── deidentify.py               # Stage 2: De-identification
│   └── load_dictionary.py          # Dictionary loader
├── server/
│   ├── data_pipeline.py            # Stage 3: MCP connector
│   ├── tools.py                    # MCP tool definitions
│   └── main.py                     # MCP server entry
└── main.py                         # Pipeline orchestrator
```

## Compliance

- **DPDPA 2023**: India's Digital Personal Data Protection Act
- **DPDP Rules 2025**: Implementation rules
- **ICMR Guidelines 2017**: National Ethical Guidelines for Biomedical Research
- **K-Anonymity**: Minimum k=5 for all query results
