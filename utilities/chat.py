import logging
from openai import RateLimitError

logger = logging.getLogger('dashboard')


async def format_agent_response(agent, messages, langfuse_handler, thread_id: str = "main_session"):
    """Stream response from agent and return the final content."""

    response_text = ""
    step = 0
    try:
        async for chunk in agent.astream(
            {"messages": messages},
            config={"configurable": {"thread_id": thread_id}, "callbacks": [langfuse_handler], "recursion_limit": 20},
            stream_mode="values"
        ):
            if 'messages' in chunk and chunk['messages']:
                latest = chunk['messages'][-1]
                step += 1
                msg_type = type(latest).__name__
                content_preview = str(getattr(latest, 'content', ''))[:200]
                tool_calls = getattr(latest, 'tool_calls', [])
                if tool_calls:
                    logger.info(f"[step {step}] {msg_type} tool_calls={[tc['name'] for tc in tool_calls]} args_preview={str(tool_calls[0].get('args',''))[:300]}")
                else:
                    logger.info(f"[step {step}] {msg_type} content={content_preview!r}")
                if hasattr(latest, 'content'):
                    response_text = latest.content
    except RateLimitError:
        return "I'm temporarily rate-limited by OpenAI. Please wait a few seconds and try again."

    return response_text
