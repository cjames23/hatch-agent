"""Multi-agent task execution command that uses the multi-agent orchestrator."""

from typing import Optional
from ..agent import Agent
from ..config import load_config


def run_multi_task(description: str, name: Optional[str] = None, config_path: Optional[str] = None) -> int:
    """Run a task using the multi-agent orchestrator.

    This command uses a multi-agent approach with:
    - 2 specialist agents that generate different suggestions
    - 1 judge agent that evaluates and selects the best suggestion

    The Agent will use the provider configuration from the config file,
    but route it through the multi-agent orchestrator.

    Returns an exit code (0 success, non-zero failure).
    """
    cfg = load_config(config_path)

    # Get provider configuration
    provider = cfg.get("provider", "mock")
    provider_cfg = cfg.get("providers", {}).get(provider, {})

    # Create agent with multi-agent orchestration enabled
    agent = Agent(
        name=name or "hatch-multi-agent",
        use_multi_agent=True,
        provider_name=provider,
        provider_config=provider_cfg
    )

    result = agent.run_task(description)

    if result.get("success"):
        # Format the multi-agent output nicely
        print("=" * 60)
        print("SELECTED SUGGESTION")
        print("=" * 60)
        print(result.get("selected_suggestion", result.get("output", "")))
        print()
        print(f"Selected Agent: {result.get('selected_agent', 'N/A')}")
        print(f"Reasoning: {result.get('reasoning', 'N/A')}")

        # Show all suggestions if available
        if "all_suggestions" in result:
            print("\n" + "=" * 60)
            print("ALL AGENT SUGGESTIONS")
            print("=" * 60)
            for i, suggestion in enumerate(result["all_suggestions"], 1):
                print(f"\n{i}. {suggestion['agent']} (confidence: {suggestion['confidence']:.2f})")
                print(f"   Suggestion: {suggestion['suggestion']}")
                print(f"   Reasoning: {suggestion['reasoning']}")

        return 0
    else:
        print("Task failed:", result.get("output", "Unknown error"))
        return 1


def main():
    """CLI entry point for multi-agent task execution."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Run a task using multi-agent orchestration")
    parser.add_argument("task", help="Task description")
    parser.add_argument("--name", help="Agent name", default=None)
    parser.add_argument("--config", help="Path to config file", default=None)

    args = parser.parse_args()

    exit_code = run_multi_task(args.task, args.name, args.config)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

