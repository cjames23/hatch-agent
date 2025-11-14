"""Multi-agent orchestration using strands-agents.

This module implements a multi-agent approach where:
- Two specialist agents generate different suggestions/solutions
- A judge agent evaluates and selects the best approach
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json


@dataclass
class AgentResponse:
    """Response from an individual agent."""
    agent_name: str
    suggestion: str
    reasoning: str
    confidence: float


class MultiAgentOrchestrator:
    """Orchestrates multiple agents to generate and evaluate suggestions.

    Uses a consensus-based approach:
    1. Two specialist agents generate independent suggestions
    2. A judge agent evaluates all suggestions and picks the best one
    """

    def __init__(self, provider_name: str = "mock", provider_config: Optional[Dict[str, Any]] = None):
        """Initialize the multi-agent orchestrator.

        Args:
            provider_name: The LLM provider to use (openai, azure, aws, etc.)
            provider_config: Configuration for the LLM provider
        """
        self.provider_name = provider_name
        self.provider_config = provider_config or {}

        # Initialize agents using strands-agents
        try:
            from strands_agents import Agent as StrandsAgent, AgentConfig
            self._strands_available = True
            self.StrandsAgent = StrandsAgent
            self.AgentConfig = AgentConfig
        except ImportError:
            self._strands_available = False
            # Fallback to mock implementation
            self.StrandsAgent = None
            self.AgentConfig = None

    def _create_agent(self, name: str, role: str, instructions: str) -> Any:
        """Create an agent with the given configuration."""
        if self._strands_available and self.StrandsAgent:
            config = self.AgentConfig(
                name=name,
                role=role,
                instructions=instructions,
                provider=self.provider_name,
                provider_config=self.provider_config
            )
            return self.StrandsAgent(config)
        else:
            # Mock agent for testing
            return MockAgent(name, role, instructions)

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the multi-agent system to solve a task.

        Args:
            task: The task description
            context: Optional context about the hatch project

        Returns:
            Dict with selected suggestion, reasoning, and all agent responses
        """
        context = context or {}

        # Create specialist agents
        agent1 = self._create_agent(
            name="ConfigurationSpecialist",
            role="Hatch project configuration expert",
            instructions=(
                "You are an expert in Hatch project configuration and dependency management. "
                "Focus on pyproject.toml structure, build systems, and environment setup. "
                "Provide detailed, configuration-focused solutions."
            )
        )

        agent2 = self._create_agent(
            name="WorkflowSpecialist",
            role="Hatch workflow and automation expert",
            instructions=(
                "You are an expert in Hatch workflows, scripts, and automation. "
                "Focus on task automation, testing, and development workflows. "
                "Provide practical, workflow-oriented solutions."
            )
        )

        judge_agent = self._create_agent(
            name="Judge",
            role="Solution evaluator and selector",
            instructions=(
                "You are a judge that evaluates multiple solutions to select the best one. "
                "Consider accuracy, practicality, completeness, and appropriateness for the context. "
                "Provide clear reasoning for your selection."
            )
        )

        # Get suggestions from both specialist agents
        suggestions = []

        # Agent 1 suggestion
        response1 = self._get_agent_response(agent1, task, context)
        suggestions.append(response1)

        # Agent 2 suggestion
        response2 = self._get_agent_response(agent2, task, context)
        suggestions.append(response2)

        # Judge evaluates and selects
        selected = self._judge_suggestions(judge_agent, task, suggestions, context)

        return {
            "success": True,
            "selected_suggestion": selected["suggestion"],
            "selected_agent": selected["agent_name"],
            "reasoning": selected["reasoning"],
            "all_suggestions": [
                {
                    "agent": s.agent_name,
                    "suggestion": s.suggestion,
                    "reasoning": s.reasoning,
                    "confidence": s.confidence
                }
                for s in suggestions
            ]
        }

    def _get_agent_response(self, agent: Any, task: str, context: Dict[str, Any]) -> AgentResponse:
        """Get a response from a single agent."""
        prompt = self._build_prompt(task, context)

        if self._strands_available:
            # Use strands-agents
            result = agent.run(prompt)
            return self._parse_agent_response(agent.config.name, result)
        else:
            # Mock response
            response = agent.run(prompt)
            return AgentResponse(
                agent_name=agent.name,
                suggestion=response.get("suggestion", ""),
                reasoning=response.get("reasoning", ""),
                confidence=response.get("confidence", 0.5)
            )

    def _judge_suggestions(
        self,
        judge: Any,
        task: str,
        suggestions: List[AgentResponse],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Have the judge agent evaluate and select the best suggestion."""
        judge_prompt = self._build_judge_prompt(task, suggestions, context)

        if self._strands_available:
            result = judge.run(judge_prompt)
            # Parse judge's decision
            decision = self._parse_judge_decision(result, suggestions)
        else:
            # Mock judge decision
            result = judge.run(judge_prompt)
            decision = result

        return decision

    def _build_prompt(self, task: str, context: Dict[str, Any]) -> str:
        """Build a prompt for an agent."""
        context_str = ""
        if context:
            context_str = "\n\nContext:\n" + json.dumps(context, indent=2)

        return f"""Task: {task}{context_str}

Please provide:
1. A detailed suggestion/solution
2. Your reasoning for this approach
3. A confidence score (0.0 to 1.0)

Format your response as JSON:
{{
    "suggestion": "your detailed suggestion here",
    "reasoning": "why this is a good approach",
    "confidence": 0.85
}}"""

    def _build_judge_prompt(
        self,
        task: str,
        suggestions: List[AgentResponse],
        context: Dict[str, Any]
    ) -> str:
        """Build a prompt for the judge agent."""
        suggestions_str = "\n\n".join([
            f"**Suggestion from {s.agent_name}:**\n"
            f"Suggestion: {s.suggestion}\n"
            f"Reasoning: {s.reasoning}\n"
            f"Confidence: {s.confidence}"
            for s in suggestions
        ])

        context_str = ""
        if context:
            context_str = "\n\nContext:\n" + json.dumps(context, indent=2)

        return f"""Task: {task}{context_str}

Evaluate the following suggestions and select the best one:

{suggestions_str}

Provide your decision as JSON:
{{
    "selected_agent": "name of the agent with best suggestion",
    "reasoning": "why this suggestion is the best",
    "suggestion": "the selected suggestion (can be modified/combined)"
}}"""

    def _parse_agent_response(self, agent_name: str, result: Any) -> AgentResponse:
        """Parse an agent's response into structured format."""
        # Try to parse as JSON
        if isinstance(result, str):
            try:
                data = json.loads(result)
                return AgentResponse(
                    agent_name=agent_name,
                    suggestion=data.get("suggestion", result),
                    reasoning=data.get("reasoning", ""),
                    confidence=data.get("confidence", 0.7)
                )
            except json.JSONDecodeError:
                # Fallback: treat entire response as suggestion
                return AgentResponse(
                    agent_name=agent_name,
                    suggestion=result,
                    reasoning="",
                    confidence=0.5
                )
        elif isinstance(result, dict):
            return AgentResponse(
                agent_name=agent_name,
                suggestion=result.get("suggestion", str(result)),
                reasoning=result.get("reasoning", ""),
                confidence=result.get("confidence", 0.7)
            )
        else:
            return AgentResponse(
                agent_name=agent_name,
                suggestion=str(result),
                reasoning="",
                confidence=0.5
            )

    def _parse_judge_decision(self, result: Any, suggestions: List[AgentResponse]) -> Dict[str, Any]:
        """Parse the judge's decision."""
        if isinstance(result, str):
            try:
                data = json.loads(result)
                selected_agent = data.get("selected_agent", suggestions[0].agent_name)

                # Find the matching suggestion
                selected_suggestion = next(
                    (s for s in suggestions if s.agent_name == selected_agent),
                    suggestions[0]
                )

                return {
                    "agent_name": selected_agent,
                    "suggestion": data.get("suggestion", selected_suggestion.suggestion),
                    "reasoning": data.get("reasoning", "")
                }
            except json.JSONDecodeError:
                # Fallback: use first suggestion
                return {
                    "agent_name": suggestions[0].agent_name,
                    "suggestion": suggestions[0].suggestion,
                    "reasoning": result
                }
        elif isinstance(result, dict):
            selected_agent = result.get("selected_agent", suggestions[0].agent_name)
            selected_suggestion = next(
                (s for s in suggestions if s.agent_name == selected_agent),
                suggestions[0]
            )

            return {
                "agent_name": selected_agent,
                "suggestion": result.get("suggestion", selected_suggestion.suggestion),
                "reasoning": result.get("reasoning", "")
            }
        else:
            # Fallback
            return {
                "agent_name": suggestions[0].agent_name,
                "suggestion": suggestions[0].suggestion,
                "reasoning": str(result)
            }


class MockAgent:
    """Mock agent for testing when strands-agents is not available."""

    def __init__(self, name: str, role: str, instructions: str):
        self.name = name
        self.role = role
        self.instructions = instructions

    def run(self, prompt: str) -> Dict[str, Any]:
        """Generate a mock response."""
        if "judge" in self.name.lower() or "Judge" in self.name:
            # Judge response
            return {
                "selected_agent": "ConfigurationSpecialist",
                "suggestion": f"[Mock] Selected suggestion based on {self.role}",
                "reasoning": f"[Mock] This approach aligns best with {self.role}"
            }
        else:
            # Specialist response
            return {
                "suggestion": f"[Mock {self.name}] Suggestion based on {self.role}: {prompt[:100]}...",
                "reasoning": f"This suggestion leverages my expertise in {self.role}",
                "confidence": 0.75
            }

