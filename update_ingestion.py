from __future__ import annotations
import subprocess
import sys

def run_smart_search(client: str, doc_type: str, export: str = "txt") -> None:
    """
    Helper to invoke smart_search_sa.py for a given client and document type.
    """
    subprocess.run(
        [
            sys.executable,
            "smart_search_sa.py",
            "--client",
            client,
            "--type",
            doc_type,
            "--export",
            export,
        ],
        check=True,
    )

def main() -> None:
    """
    Executes the ingestion pipeline for a specific client.

    It runs smart_search_sa.py for each document type defined in company_rules.json,
    exporting the results as plain text, and then ingests all exported text files
    into the Chroma DB collection using ingest_txt.py.
    Usage:
        python update_ingestion.py [client_name]
    If client_name is omitted, defaults to 'Start TI'.
    """
    client = sys.argv[1] if len(sys.argv) > 1 else "Start TI"
    # Types defined in company_rules.json
    doc_types = [
        "daily",
        "weekly",
        "checkin",
        "planejamento",
        "replanejamento",
        "benchmarking",
    ]
    for t in doc_types:
        run_smart_search(client, t)
    # After exporting, ingest all .txt files from data/raw into Chroma DB
    subprocess.run([sys.executable, "ingest_txt.py"], check=True)

if __name__ == "__main__":
    main()
