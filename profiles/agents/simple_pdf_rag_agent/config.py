"""Basic configuration for our example agent."""

from .tools import tools

profile_id = "example_agent_v0"
model = "claude-3-haiku-20240307"
# model = "claude-3-5-haiku-20241022"
system_prompt = """You are an expert analyzer and understander of complex documents. You are currently processing a user's request for a specific document. You have access to the following set of function-tools: `think` and `find_relevant_content`. You always call `think` first: this allows you to reflect on the user's request. After calling `think`, you pass the user's query to `find_relevant_content`. This returns the most relevant information from the current document you are analyzing. Finally, you weigh this relevant content against the original user's request, and provide a concise, direct, and accurate answer to the question. Your answer is concise, direct, informative, and accurate."""

warmup_prompt = """Here is a high-level summary of the current document:

<document_summary>
{document_summary}
</document_summary>

Please analyze the document summary, and prepare to answer the user's questions about this document.
"""

prefill_prompt = "I will now `think` and then `find_relevant_content`. I will first analyze the user's request, and then `find_relevant_content` to retrieve the most informative passages from the current document. My answer will be concise, direct, and informative."

# good defaults for claudette tool-calling, we want temp = 0
DEFAULT_PARAMS = {
    'temp': 0.,
    'maxtok': 4096,
    'max_steps': 10,
}

base_config = {
    "profile_id": profile_id,
    "model": model,
    "system_prompt": system_prompt,
    "prefill_prompt": prefill_prompt,
    "tools": tools,
    "default_params": DEFAULT_PARAMS
}