Okay, let's lay out the concrete implementation for Phase 1: the simplest PDF RAG agent using `docling`, best-practice chunking, and the `awaq-agents` framework.

We'll separate this into two parts:

1.  **`ingest_pdf.py`:** An offline script for processing the PDF into embeddings and chunk data.
2.  **`awaq-agents` Setup:** The agent profile and tools for querying.

---

### 1. `ingest_pdf.py` (Offline Ingestion Workflow)

This script takes a PDF, converts it to Markdown using `docling`, chunks the Markdown, generates embeddings, and stores them in ChromaDB along with the chunk text data.

```python
# ingest_pdf.py
import argparse
import json
import logging
import uuid
from pathlib import Path
from typing import List, Dict, Any

# PDF Parsing
from docling.document_converter import DocumentConverter
# Assuming docling is installed: pip install docling

# Chunking (Using LangChain's splitter as a best-practice example)
# pip install langchain-text-splitters
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Embeddings (Using SentenceTransformers for local processing)
# pip install sentence-transformers
from sentence_transformers import SentenceTransformer

# Vector Storage (Using ChromaDB for local storage)
# pip install chromadb
import chromadb

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# Choose a local embedding model (adjust based on desired quality/speed)
# See https://www.sbert.net/docs/pretrained_models.html
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
# Chunking parameters
CHUNK_SIZE = 1000 # Characters
CHUNK_OVERLAP = 200 # Characters
MARKDOWN_SEPARATORS = ["\n\n", "\n", " ", ""] # For recursive splitting

# --- Helper Data Class ---
class Chunk:
    def __init__(self, chunk_id: str, text: str, document_source: str):
        self.chunk_id = chunk_id
        self.text = text
        self.document_source = document_source # e.g., the original PDF path/URL

    def to_dict(self) -> Dict[str, Any]:
        return {"chunk_id": self.chunk_id, "text": self.text, "document_source": self.document_source}

# --- Core Functions ---

def parse_pdf_to_markdown(pdf_source: str) -> str:
    """Uses docling to convert a PDF (path or URL) to Markdown."""
    logging.info(f"Starting PDF conversion for: {pdf_source}")
    try:
        # Using the simple docling interface for basic conversion
        converter = DocumentConverter()
        # For more control (OCR, tables etc.), use the complex setup shown previously
        result = converter.convert(pdf_source)
        markdown_content = result.document.export_to_markdown()
        logging.info(f"Successfully converted {pdf_source} to Markdown ({len(markdown_content)} chars).")
        return markdown_content
    except Exception as e:
        logging.error(f"Failed to convert PDF {pdf_source} using docling: {e}", exc_info=True)
        raise

def chunk_markdown(markdown_content: str, source_identifier: str) -> List[Chunk]:
    """Chunks Markdown content using RecursiveCharacterTextSplitter."""
    logging.info(f"Chunking Markdown content (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
        separators=MARKDOWN_SEPARATORS,
    )
    split_texts = text_splitter.split_text(markdown_content)

    chunks = []
    for i, text in enumerate(split_texts):
        chunk_id = f"{Path(source_identifier).stem}_chunk_{uuid.uuid4()}"
        chunks.append(Chunk(chunk_id=chunk_id, text=text, document_source=source_identifier))

    logging.info(f"Created {len(chunks)} chunks.")
    return chunks

def generate_and_store_embeddings(chunks: List[Chunk], output_dir: Path):
    """Generates embeddings and stores them in ChromaDB, saves chunk data."""
    if not chunks:
        logging.warning("No chunks provided, skipping embedding generation.")
        return

    db_path = output_dir / "chroma_db"
    chunks_json_path = output_dir / "chunks.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    logging.info(f"Initializing ChromaDB at: {db_path}")
    # Using PersistentClient for saving to disk
    chroma_client = chromadb.PersistentClient(path=str(db_path))

    # Create or get the collection (use pdf_source filename as collection name?)
    # Let's use a fixed name for simplicity now
    collection_name = "pdf_rag_collection"
    logging.info(f"Getting or creating ChromaDB collection: {collection_name}")
    collection = chroma_client.get_or_create_collection(name=collection_name)

    # Prepare data for ChromaDB
    chunk_texts = [chunk.text for chunk in chunks]
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    # Create metadata (could store page numbers here later if available)
    metadatas = [{"chunk_id": chunk.chunk_id, "source": chunk.document_source} for chunk in chunks]

    logging.info(f"Generating embeddings for {len(chunk_texts)} chunks...")
    embeddings = model.encode(chunk_texts, show_progress_bar=True).tolist()
    logging.info("Embedding generation complete.")

    # Add to ChromaDB collection in batches if necessary (for large docs)
    # For simplicity, adding all at once here
    logging.info("Adding embeddings and documents to ChromaDB...")
    try:
        collection.add(
            embeddings=embeddings,
            documents=chunk_texts, # Store text directly in ChromaDB documents
            metadatas=metadatas,
            ids=chunk_ids
        )
        logging.info(f"Successfully added {len(chunk_ids)} items to ChromaDB collection '{collection_name}'.")
    except Exception as e:
         logging.error(f"Failed to add items to ChromaDB: {e}", exc_info=True)
         # Decide how to handle partial failures if needed
         raise

    # Save the chunk details separately (optional, but useful for get_chunk_details tool)
    # Storing text in ChromaDB 'documents' makes this potentially redundant for Phase 1
    # but good practice if metadata grows or if we don't want to rely solely on Chroma retrieve
    chunk_data_for_json = [chunk.to_dict() for chunk in chunks]
    logging.info(f"Saving chunk details to {chunks_json_path}")
    try:
        with open(chunks_json_path, 'w', encoding='utf-8') as f:
            json.dump(chunk_data_for_json, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save chunks JSON: {e}")


# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Ingest a PDF for RAG: Parse, Chunk, Embed, Store.")
    parser.add_argument("pdf_source", help="Path or URL to the PDF file.")
    parser.add_argument("-o", "--output-dir", default="./pdf_data_store",
                        help="Directory to store ChromaDB database and chunk data.")
    args = parser.parse_args()

    output_path = Path(args.output_dir)

    try:
        # 1. Parse PDF to Markdown
        markdown = parse_pdf_to_markdown(args.pdf_source)

        # 2. Chunk Markdown
        chunks = chunk_markdown(markdown, args.pdf_source)

        # 3. Generate Embeddings and Store
        generate_and_store_embeddings(chunks, output_path)

        logging.info(f"Ingestion complete. Data stored in: {output_path.resolve()}")

    except Exception as e:
        logging.error(f"An error occurred during the ingestion pipeline: {e}", exc_info=True)
        # Exit with error code?
        exit(1)

if __name__ == "__main__":
    main()

```

**How to Run `ingest_pdf.py`:**

```bash
pip install docling langchain-text-splitters sentence-transformers chromadb
python ingest_pdf.py "path/to/your/document.pdf" --output-dir ./my_pdf_store
# or
python ingest_pdf.py "https://arxiv.org/pdf/some_paper.pdf" -o ./my_pdf_store
```

This will create a directory (`./my_pdf_store` in this example) containing:

*   `chroma_db/`: The ChromaDB vector store.
*   `chunks.json`: A JSON file listing all created chunks and their text (optional if relying on ChromaDB documents).

---

### 2. `awaq-agents` Setup (Phase 1: Simple Embedding Search Agent)

Now, we set up the `awaq-agents` profile and tools to query the data created by `ingest_pdf.py`.

**(Create directory structure: `profiles/agents/pdf_rag_agent_simple/`)**

**File: `profiles/agents/pdf_rag_agent_simple/config.py`**

```python
# profiles/agents/pdf_rag_agent_simple/config.py
from .tools import pdf_tools_simple # Tools defined in tools.py

profile_id = "pdf_rag_agent_simple_v1"
# Use a fast model for this simple phase
model = "claude-3-haiku-20240307"

# Focused system prompt for Phase 1
system_prompt = """You are an assistant designed to answer questions based on a PDF document that has been processed into text chunks. You have access to tools for searching these chunks semantically.

Your Process:
1.  **Analyze Query:** Understand what the user is asking for based on their query.
2.  **Search Chunks:** Use the `search_embeddings` tool to find the most relevant text chunks from the document based on the user's query meaning.
3.  **Get Details (Optional but Recommended):** Use the `get_chunk_details` tool with the IDs found by `search_embeddings` to retrieve the full text of the relevant chunks.
4.  **Synthesize Answer:** Use the `synthesize_basic` tool, providing the retrieved chunk information (ideally the full text from `get_chunk_details`). This tool will format the answer and cite the source chunk IDs. **You MUST call `synthesize_basic` as your final step.** Do not provide information without citing its source chunk ID via this tool.
"""

# Guide the LLM towards tool use
prefill_prompt = "Okay, I understand the request. I will use the search tool to find relevant document chunks and then synthesize the answer."

# Basic params for tool calling
DEFAULT_PARAMS = {
    'temp': 0.0, # Deterministic tool selection
    'maxtok': 4096,
    'max_steps': 5, # Simple flow: Search -> Details -> Synthesize
}

# Configuration dictionary used by AgentProfile
pdf_rag_config_simple = {
    "profile_id": profile_id,
    "model": model,
    "system_prompt": system_prompt,
    "prefill_prompt": prefill_prompt,
    "tools": pdf_tools_simple,
    "default_params": DEFAULT_PARAMS
}
```

**File: `profiles/agents/pdf_rag_agent_simple/agent.py`**

```python
# profiles/agents/pdf_rag_agent_simple/agent.py
from profiles.base_profile import AgentProfile
from .config import pdf_rag_config_simple

# Instantiate the AgentProfile for this agent
profile = AgentProfile(**pdf_rag_config_simple)

# You might add logic here later to load necessary resources
# like the path to the data store, if not handled by tools directly.
print(f"PDF RAG Agent Simple Profile Loaded: {profile.profile_id}")
```

**File: `profiles/agents/pdf_rag_agent_simple/tools.py`**

```python
# profiles/agents/pdf_rag_agent_simple/tools.py
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from claudette.core import tool # Assuming this is the decorator used in framework

# Import necessary libraries for tool implementation
# These should match the ones used in ingest_pdf.py
from sentence_transformers import SentenceTransformer
import chromadb

# --- Tool Configuration ---
# !! IMPORTANT: These paths must match the output of ingest_pdf.py !!
# In a real app, make these configurable (env vars, config file, passed at init)
DATA_STORE_DIR = Path("./my_pdf_store") # Default, same as ingest script
CHROMA_DB_PATH = str(DATA_STORE_DIR / "chroma_db")
CHUNKS_JSON_PATH = DATA_STORE_DIR / "chunks.json" # Needed for get_chunk_details if not using Chroma docs
COLLECTION_NAME = "pdf_rag_collection" # Must match ingest script
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' # Must match ingest script

# --- Tool Helper: Initialize clients (lazy loading) ---
# Avoid initializing heavy models/clients at module import time
# Initialize them the first time a tool needing them is called.
_chroma_client = None
_embedding_model = None
_chunk_data_cache = None

def get_chroma_collection():
    """Initializes and returns the ChromaDB collection."""
    global _chroma_client
    if _chroma_client is None:
        try:
            logging.info(f"Initializing ChromaDB client for path: {CHROMA_DB_PATH}")
            _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        except Exception as e:
            logging.error(f"Failed to initialize ChromaDB client: {e}")
            return None # Or raise error
    try:
        collection = _chroma_client.get_collection(name=COLLECTION_NAME)
        logging.info(f"Accessed ChromaDB collection: {COLLECTION_NAME}")
        return collection
    except Exception as e:
        # Handle case where collection might not exist yet
        logging.error(f"Failed to get ChromaDB collection '{COLLECTION_NAME}': {e}")
        return None # Or raise error

def get_embedding_model():
    """Initializes and returns the SentenceTransformer model."""
    global _embedding_model
    if _embedding_model is None:
        logging.info(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model

def get_chunk_data_from_json() -> Dict[str, Dict[str, Any]]:
    """Loads chunk data from the JSON file (cached)."""
    global _chunk_data_cache
    if _chunk_data_cache is None:
        logging.info(f"Loading chunk data from: {CHUNKS_JSON_PATH}")
        if not CHUNKS_JSON_PATH.exists():
            logging.error(f"Chunks JSON file not found at {CHUNKS_JSON_PATH}")
            return {}
        try:
            with open(CHUNKS_JSON_PATH, 'r', encoding='utf-8') as f:
                all_chunks = json.load(f)
            # Convert list to dict keyed by chunk_id for faster lookup
            _chunk_data_cache = {chunk['chunk_id']: chunk for chunk in all_chunks}
            logging.info(f"Loaded {_chunk_data_cache.__len__()} chunks into cache.")
        except Exception as e:
            logging.error(f"Failed to load or parse chunks JSON: {e}")
            return {} # Return empty on failure
    return _chunk_data_cache

# --- Agent Tools ---

@tool
def search_embeddings(query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Performs semantic search on the document's text chunks using embeddings.
    Returns a list of the top_k most relevant chunk IDs and their relevance scores (distances).
    Lower distance means more relevant.
    """
    logging.info(f"Tool Call: search_embeddings(query='{query_text[:50]}...', top_k={top_k})")
    collection = get_chroma_collection()
    model = get_embedding_model()
    if not collection or not model:
        return [{"error": "Failed to initialize backend services (ChromaDB/Model)."}]

    try:
        query_embedding = model.encode(query_text).tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=['distances', 'metadatas'] # Only need IDs and scores here
        )

        # Process results (Chroma returns lists of lists, handle potential errors)
        ids = results.get('ids', [[]])[0]
        distances = results.get('distances', [[]])[0]
        # metadatas = results.get('metadatas', [[]])[0] # Could use metadata if needed

        findings = []
        if ids:
            for i, chunk_id in enumerate(ids):
                 findings.append({
                     "chunk_id": chunk_id,
                     "distance": distances[i] if distances and i < len(distances) else None
                 })
            logging.info(f"Found {len(findings)} relevant chunks via embedding search.")
            return findings
        else:
            logging.warning("Embedding search returned no results.")
            return []

    except Exception as e:
        logging.error(f"Error during embedding search: {e}", exc_info=True)
        return [{"error": f"An error occurred during search: {e}"}]


@tool
def get_chunk_details(chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Retrieves the full text and any other stored metadata for a given list of chunk IDs.
    Use this *after* search_embeddings to get the content needed for the answer.
    """
    logging.info(f"Tool Call: get_chunk_details(ids_count={len(chunk_ids)})")

    # Option 1: Retrieve from ChromaDB 'documents' if stored there
    collection = get_chroma_collection()
    if not collection:
         return {"error": "Failed to initialize ChromaDB."}
    try:
        results = collection.get(ids=chunk_ids, include=['documents', 'metadatas'])
        details = {}
        docs = results.get('documents', [])
        metas = results.get('metadatas', [])
        retrieved_ids = results.get('ids', [])
        for i, chunk_id in enumerate(retrieved_ids):
            details[chunk_id] = {
                "id": chunk_id,
                "text": docs[i] if i < len(docs) else "[Text Not Found]",
                "metadata": metas[i] if i < len(metas) else {}
            }
        logging.info(f"Retrieved details for {len(details)} chunks from ChromaDB.")
        return details

    except Exception as e:
        logging.error(f"Error retrieving chunk details from Chroma: {e}", exc_info=True)
        # Fallback or alternative: Load from JSON (if Option 1 fails or isn't used)
        # chunk_data = get_chunk_data_from_json()
        # details = {}
        # for chunk_id in chunk_ids:
        #    if chunk_id in chunk_data:
        #        details[chunk_id] = chunk_data[chunk_id]
        #    else:
        #        details[chunk_id] = {"error": "Chunk ID not found."}
        # logging.info(f"Retrieved details for {len(details)} chunks from JSON.")
        # return details
        return {"error": f"Failed to retrieve details: {e}"}


@tool
def synthesize_basic(query: str, findings: Dict[str, Dict[str, Any]]) -> str:
    """
    Constructs a simple answer to the user's query based on the provided findings (output from get_chunk_details).
    Formats the answer and cites the source chunk IDs.
    **MUST be called as the final step.**
    """
    logging.info(f"Tool Call: synthesize_basic(query='{query[:50]}...', findings_count={len(findings)})")

    if not findings or all('error' in v for v in findings.values()):
        return "I couldn't retrieve the necessary information from the document to answer your query."

    response = f"Based on the document regarding your query '{query}':\n\n"
    found_content = False
    for chunk_id, details in findings.items():
        if 'text' in details and details['text'] != "[Text Not Found]":
            text_snippet = details['text'].strip()
            # Basic citation using chunk ID
            response += f"- Finding (Source Chunk ID: {chunk_id}):\n{text_snippet}\n\n"
            found_content = True
        # else: ignore chunks where text wasn't found

    if not found_content:
         response = "I found some potentially relevant chunks, but could not retrieve their content to synthesize an answer."

    return response.strip()

# List of tools for this profile
pdf_tools_simple = [search_embeddings, get_chunk_details, synthesize_basic]

```

**File: `run_pdf_agent.py` (Example Runner Script)**

```python
# run_pdf_agent.py (similar to run_interactive.py, but loads the PDF agent)
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure the framework and profiles are importable
# Adjust path as necessary based on your project structure
project_root = Path(__file__).parent.parent # Example: Adjust if needed
sys.path.insert(0, str(project_root))

# Attempt to import necessary components
try:
    # Import the specific agent profile we created
    from profiles.agents.pdf_rag_agent_simple.agent import profile as pdf_agent_profile
    from framework.agent_runner import AgentRunner
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure your project structure and PYTHONPATH are correct.")
    sys.exit(1)

# Load environment variables (e.g., ANTHROPIC_API_KEY)
load_dotenv()

def run_interactive_pdf_session():
    """Runs the main interactive command-line session for the PDF agent."""
    print("Initializing PDF RAG AgentRunner...")
    try:
        # Instantiate AgentRunner with the PDF RAG profile
        runner = AgentRunner(
            profile=pdf_agent_profile,
            log_dir="results_pdf_rag", # Separate log directory
            run_name_prefix="pdf_rag_simple"
        )
    except Exception as e:
        print(f"Failed to initialize AgentRunner: {e}")
        print("Check tool initialization (paths to data store?) and API keys.")
        print("Exiting.")
        return

    if runner.chat is None:
        print("AgentRunner could not start a chat session. Check previous errors. Exiting.")
        return

    print("\n--- Starting PDF RAG Interactive Session (Simple) ---")
    print(f"Agent Profile: {runner.profile.profile_id}")
    print(f"Model: {runner.profile.model}")
    print(f"Data Store (Expected): {DATA_STORE_DIR.resolve()}") # Show expected path from tools.py
    print(f"Logging to: {runner.log_path}")
    print("(Type 'quit' or 'exit' to end, 'reset' to clear history)")
    print("-" * 30)

    while True:
        try:
            user_input = input("You: ")
        except EOFError: # Handle Ctrl+D
            print("\nExiting.")
            break

        cleaned_input = user_input.strip().lower()
        if cleaned_input in ['quit', 'exit']:
            print("Exiting.")
            break
        if cleaned_input == 'reset':
            runner.reset_session()
            print("\n--- Session Reset --- \n")
            continue
        if not user_input.strip(): # Ignore empty input
            continue

        print("Agent: Thinking...") # Provide feedback
        try:
            # Use default parameters from the profile
            agent_response = runner.run_turn(user_input=user_input)
            print(f"Agent: {agent_response}")
        except Exception as e:
            print(f"\n--- ERROR DURING TURN --- ")
            print(f"{e}")
            print("Continuing session, but an error occurred.")
            print("-" * 30)

if __name__ == "__main__":
    # 1. Ensure you have run ingest_pdf.py first for the desired PDF!
    if not DATA_STORE_DIR.exists():
         print(f"ERROR: Data store directory not found at {DATA_STORE_DIR}")
         print(f"Please run 'python ingest_pdf.py <your_pdf> -o {DATA_STORE_DIR}' first.")
         sys.exit(1)

    print("Starting interactive PDF RAG agent runner...")
    try:
        run_interactive_pdf_session()
    except KeyboardInterrupt:
        print("\nCaught interrupt, exiting cleanly.")
    except Exception as e:
        print(f"\n--- UNEXPECTED ERROR IN MAIN LOOP --- ")
        print(f"{e}")

```

**Summary of Phase 1 Implementation:**

1.  Run `ingest_pdf.py <pdf_source>` to process your document.
2.  Run `python run_pdf_agent.py`.
3.  Ask questions related to the PDF content. The agent will use `search_embeddings` -> `get_chunk_details` -> `synthesize_basic` to answer, citing chunk IDs.

This provides the essential bedrock for the simple RAG system, ready for the incremental addition of graph capabilities and more sophisticated logic in later phases.