# ingest_pdf.py
import sys
import argparse
import traceback
from pathlib import Path
from fastcore.xtras import *

from framework.embeddings import embed_docling_json
from framework.documents import parse_document, convert

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Ingest a PDF for RAG: Parse, Chunk, Embed, Store.")
    parser.add_argument("pdf_source", help="Path or URL to the PDF file.")
    parser.add_argument("-o", "--output-dir", default="./artifacts",
                        help="Directory to store ChromaDB database and chunk data. (Default: ./pdf_data_store)")
    args = parser.parse_args()

    pdf_source = Path(args.pdf_source)
    output_path = Path(args.output_dir)
    fid = pdf_source.stem

    output_path = output_path / fid
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"--- Starting PDF Ingestion Pipeline ---")
    print(f"Source PDF: {pdf_source.resolve()}")
    print(f"Output Directory: {output_path.resolve()}")

    # parse the document
    document = parse_document(pdf_source, output_path)

    # embed the document
    embed_docling_json(document, output_path / f"embeddings")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        sys.exit(1)
