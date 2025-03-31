# AwaQ Agents

Minimal framework for tool-calling LLM agents using the claudette library from Answer.ai.

Setup your .env file with the `ANTHROPIC_API_KEY` variable.

## Talking to an agent.

```bash
python run_interactive.py
```

By default this runs the test agent here: `profiles/agents/example_agent/`.
This basic agent uses the cheapest Haiku model, and has a single tool that finds the current time. 

Your interaction should look something like:
![Sample interaction](image.png)

# TODO: 
- Eval framework.  
- Visualizations. 