"""
Tools for the simple PDF agent.
"""
from pathlib import Path
from claudette.core import tool
from framework.embeddings import load_embeddings, load_models, matched_late_retrieval, EMBEDDING_MODEL_NAME, RAGEmbeds


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


@tool
def find_relevant_content(
    user_query: str, # augmented query for semantic similarity search with embedded document vectors
    ) -> str: # returns the relevant content with relevance scores
    """Use this tool to find relevant content in the user's document `chunks`. Directly plug in the `user_query` from your chat session into the semantic search."""
    print(f"Tool Execution: find_relevant_content() -> {user_query}")
    top_chunks, top_sims = matched_late_retrieval(
        user_query,
        RAGEmbeds.chunks,
        RAGEmbeds.embeddings,
        tokenizer,
        model)
    context = []
    for idx, (chunk, sim) in enumerate(zip(top_chunks, top_sims)):
        context.append(f"<context_{idx}>{chunk}</context_{idx}>\n<score_{idx}>{sim}</score_{idx}>")
    return "\n".join(context)

# group up the tools for easy import
tools = [think, find_relevant_content]
