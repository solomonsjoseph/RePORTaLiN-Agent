"""
RePORT India Clinical Data Query Example - Three-T        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
        ) as client:

            # =========================================================
            # Step 0: Check Pipeline Status
            # =========================================================
            print("Step 0: Checking data pipeline status...")
            print("-" * 40)

            pipeline_status = await client.execute_tool("get_pipeline_status", {})

            if isinstance(pipeline_status, str):
                pipeline_status = json.loads(pipeline_status)

            if pipeline_status.get("pipeline_ready"):
                print(f"✓ Pipeline ready (data source: {pipeline_status.get('data_source')})")
                file_counts = pipeline_status.get("file_counts", {})
                print(f"  Raw files: {file_counts.get('raw_files', 0)}")
                print(f"  Extracted files: {file_counts.get('extracted_files', 0)}")
                print(f"  De-identified files: {file_counts.get('deidentified_files', 0)}")
            else:
                print("⚠ Pipeline not ready!")
                print(f"  Next action: {pipeline_status.get('next_action')}")
                print("\nRun the pipeline first:")
                print("  python main.py --enable-deidentification")
                return

            print()

            # =========================================================
            # Step 1: Discover RePORT India Datasets
            # =========================================================gn Pattern
=====================================================================

This example demonstrates how to use the MCP server to query
RePORT India (Regional Prospective Observational Research for Tuberculosis)
clinical study data using the recommended three-tool pattern:

1. list_datasets - Discover available CRFs/datasets
2. describe_schema - Understand dataset structure
3. query_database - Execute privacy-safe data queries

Study: RePORT India (Indo-VAP cohort)
Regulatory Framework: DPDPA 2023, ICMR Guidelines

Prerequisites:
    - MCP server running (uv run uvicorn server.main:app)
    - Valid auth token configured
    - Data files in data/dataset/Indo-vap_csv_files/

Usage:
    uv run python client/examples/query_clinical_data.py
"""

import asyncio
import json
import os

# Import the universal client adapter
from client.universal_client import (
    MCPAuthenticationError,
    MCPConnectionError,
    MCPToolExecutionError,
    UniversalMCPClient,
)


async def main() -> None:
    """Demonstrate the three-tool design pattern for RePORT India data queries."""

    # Configuration
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/sse")
    auth_token = os.getenv("MCP_AUTH_TOKEN", "dev-token-change-in-production")

    print("=" * 60)
    print("RePORT India MCP - Clinical Data Query Example")
    print("=" * 60)
    print("Study: Regional Prospective Observational Research for TB")
    print(f"Server: {server_url}")
    print("Regulatory: DPDPA 2023 + ICMR Guidelines")
    print()

    try:
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
        ) as client:

            # =========================================================
            # Step 1: Discover Available RePORT India Datasets
            # =========================================================
            print("Step 1: Discovering RePORT India datasets...")
            print("-" * 40)

            datasets_result = await client.execute_tool(
                "list_datasets",
                {"include_metadata": True}
            )

            # Parse the result
            if isinstance(datasets_result, str):
                datasets_result = json.loads(datasets_result)

            if datasets_result.get("success"):
                datasets = datasets_result.get("datasets", [])
                study_name = datasets_result.get("study_name", "Unknown")
                print(f"✓ Study: {study_name}")
                print(f"✓ Found {len(datasets)} CRF datasets\n")

                # Show datasets by domain
                print("Datasets by CDISC Domain:")
                domains = datasets_result.get("domains", [])
                for domain in domains[:8]:
                    domain_datasets = [ds for ds in datasets if ds.get("domain") == domain]
                    print(f"  {domain}: {len(domain_datasets)} forms")
                    for ds in domain_datasets[:2]:
                        print(f"    - {ds['name']}: {ds['description'][:50]}...")

                if len(domains) > 8:
                    print(f"  ... and {len(domains) - 8} more domains")
            else:
                print(f"✗ Failed to list datasets: {datasets_result.get('error')}")
                return

            print()

            # =========================================================
            # Step 2: Describe Schema for Index Case Baseline
            # =========================================================
            print("Step 2: Examining RePORT India CRF schema...")
            print("-" * 40)

            # Target the Index Case Baseline (demographics) dataset
            dm_datasets = [ds for ds in datasets if ds.get("domain") == "DM"]
            if dm_datasets:
                target_dataset = dm_datasets[0]["name"]
            else:
                target_dataset = "2A_ICBaseline"  # Default to IC Baseline

            print(f"Describing schema for: {target_dataset}")
            print("(Index Case Baseline - Demographics)")

            schema_result = await client.execute_tool(
                "describe_schema",
                {
                    "dataset_name": target_dataset,
                    "include_statistics": True,
                    "include_sample_values": True,
                }
            )

            if isinstance(schema_result, str):
                schema_result = json.loads(schema_result)

            if schema_result.get("success"):
                fields = schema_result.get("fields", [])
                row_count = schema_result.get("row_count", 0)

                print(f"✓ Schema retrieved: {len(fields)} fields, {row_count} rows\n")

                print("Field summary:")
                for field in fields[:10]:
                    name = field.get("name", "unknown")
                    dtype = field.get("type", "unknown")
                    nullable = "nullable" if field.get("nullable") else "required"
                    print(f"  - {name}: {dtype} ({nullable})")

                if len(fields) > 10:
                    print(f"  ... and {len(fields) - 10} more fields")
            else:
                print(f"✗ Failed to describe schema: {schema_result.get('error')}")

            print()

            # =========================================================
            # Step 3: Query TB Clinical Data (k-anonymity protected)
            # =========================================================
            print("Step 3: Querying RePORT India TB data...")
            print("-" * 40)
            print("Note: Results are k-anonymity protected (k≥5) per ICMR guidelines")
            print()

            # Example query - get aggregated data by group
            query = f"SELECT * FROM {target_dataset} GROUP BY sex"
            print(f"Query: {query}")
            print("(Results grouped by sex, groups with <5 subjects suppressed)\n")

            query_result = await client.execute_tool(
                "query_database",
                {
                    "query": query,
                    "limit": 100,
                    "include_metadata": True,
                }
            )

            if isinstance(query_result, str):
                query_result = json.loads(query_result)

            if query_result.get("success"):
                data = query_result.get("data", [])
                exec_time = query_result.get("execution_time_ms", 0)
                suppressed = query_result.get("suppressed_groups", 0)

                print(f"✓ Query returned {len(data)} rows in {exec_time:.1f}ms")
                if suppressed > 0:
                    print(f"  ⚠ {suppressed} groups suppressed for k-anonymity")

                if data:
                    print("\nResults:")
                    for row in data[:5]:
                        print(f"  {row}")
            else:
                print(f"✗ Query failed: {query_result.get('error')}")

            print()

            # =========================================================
            # Bonus: Search Data Dictionary
            # =========================================================
            print("Bonus: Searching data dictionary...")
            print("-" * 40)

            dict_result = await client.execute_tool(
                "search_dictionary",
                {"search_term": "age"}
            )

            if isinstance(dict_result, str):
                dict_result = json.loads(dict_result)

            if dict_result.get("success"):
                matches = dict_result.get("matches", [])
                print(f"✓ Found {len(matches)} matches for 'age'")
                for match in matches[:3]:
                    print(f"  - {match.get('field_name')}: {match.get('description', 'N/A')[:50]}")
            else:
                print(f"Dictionary search: {dict_result}")

            print()
            print("=" * 60)
            print("Pipeline: Extraction → De-identification → Results → MCP ✓")
            print("=" * 60)

    except MCPConnectionError as e:
        print(f"\n✗ Connection error: {e}")
        print("  Make sure the MCP server is running:")
        print("  uv run uvicorn server.main:app --host 127.0.0.1 --port 8000")

    except MCPAuthenticationError as e:
        print(f"\n✗ Authentication error: {e}")
        print("  Check your MCP_AUTH_TOKEN environment variable")

    except MCPToolExecutionError as e:
        print(f"\n✗ Tool execution error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
