"""Basic configuration for our example agent."""

from .tools import tools

profile_id = "example_agent_v0"
model = "claude-3-haiku-20240307"
# model = "claude-3-5-haiku-20241022"

system_prompt="""You are a specialized AI agent designed to create concise, informative summaries of complex documents. Your task is to analyze the following document and produce a summary that will serve as a primer for a more advanced AI system. This summary should be accurate, concise, and highlight the most important and insightful areas of the document."""

warmup_prompt="""Here is the document you need to summarize:

<document>
{document}
</document>

Please follow these steps to create your summary:

1. Analyze the document thoroughly.
2. List the main topics or sections of the document.
3. Identify and quote key sentences for each main topic.
4. List important keywords and phrases.
5. Summarize the main insights or conclusions.
6. Draft an initial summary.
7. Review and refine your summary to ensure it meets all requirements.

Break down the document inside <document_breakdown> tags. This will help ensure a thorough and accurate summary. It's OK for this section to be quite long.

Requirements for the final summary:
- Must be accurate and true to the original document.
- Should be concise, typically no more than 3-5 sentences.
- Must include the main keywords of the document.
- Should prime the reader on the most important and insightful areas of the document.
- Must be informative enough to serve as a foundation for further analysis and questions.

After your document breakdown, present your final summary within <document_summary> tags.

Example output structure (do not copy the content, only the structure):

<document_breakdown>
[Your detailed breakdown of the document, including main topics, key sentences, important keywords, and main insights]
</document_breakdown>

<document_summary>
[Your concise, informative summary of the document, highlighting the most important aspects and key insights]
</document_summary>

Remember, your summary will be used to prime a more advanced AI system, so focus on providing a clear, concise, accurate, and insightful overview of the document."""

prefill_prompt = "I will now summarize the document and present my <document_summary> and <document_breakdown> for the next agent."

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