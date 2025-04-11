"""
Tools for the simple PDF agent.
"""
from pathlib import Path
from claudette.core import tool
from framework.embeddings import load_embeddings, load_models, matched_late_retrieval, EMBEDDING_MODEL_NAME

# load the precomputed embeddings
embeds_path = Path("/Users/cck/projects/cck-agents/artifacts/sample_doc/embeddings_sample_doc/late_chunks.npz")
embeds = load_embeddings(embeds_path)
chunks, embeddings = embeds['chunks'], embeds['embeddings']

# load the embedding models
tokenizer, model = load_models(EMBEDDING_MODEL_NAME)


@tool
def think(
    thought: str, # the thought or idea to think about to solve the user request
    ) -> str: # do not worry about returning anything, only think
    """Use this tool to think about the user's request. You will not obtain new information or change the user's input. It only helps you think about the task and problem to maximally, accurately, and completely solve the user's request."""
    print(f"Tool Execution: think() -> {thought}")
    return thought


# group up the tools for easy import
tools = [think]
