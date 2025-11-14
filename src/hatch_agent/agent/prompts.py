"""LLM prompt templates used by the agent."""

from typing import Callable


def default_prompt(task_description: str) -> str:
    """Return a simple prompt template for a task."""
    return (
        "You are an automated assistant. Perform the following task precisely:\n"
        f"{task_description}\n"
        "If the task is ambiguous, ask clarifying questions."
    )


def system_prompt_factory(role_name: str) -> Callable[[str], str]:
    """Return a prompt constructor for the given system role."""

    def make_prompt(body: str) -> str:
        return f"System role: {role_name}\n{body}"

    return make_prompt

