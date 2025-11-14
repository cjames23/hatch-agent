"""Multi-agent orchestration using strands-agents.

This module implements a multi-agent approach where:
- Two specialist agents generate different suggestions/solutions
- A judge agent evaluates and selects the best approach
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json

from strands_agents import Agent as StrandsAgent, AgentConfig


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

    def __init__(self, provider_name: str = "openai", provider_config: Optional[Dict[str, Any]] = None):
        """Initialize the multi-agent orchestrator.

        Args:
            provider_name: The LLM provider to use (openai, anthropic, bedrock, etc.)
            provider_config: Configuration for the LLM provider
        """
        self.provider_name = provider_name
        self.provider_config = provider_config or {}

    def _create_agent(self, name: str, role: str, instructions: str) -> StrandsAgent:
        """Create an agent with the given configuration."""
        config = AgentConfig(
            name=name,
            role=role,
            instructions=instructions,
            provider=self.provider_name,
            provider_config=self.provider_config
        )
        return StrandsAgent(config)

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the multi-agent system to solve a task.

        Args:
            task: The task description
            context: Optional context about the hatch project

        Returns:
            Dict with selected suggestion, reasoning, and all agent responses
        """
        context = context or {}

        # Create specialist agents with detailed instructions
        agent1 = self._create_agent(
            name="ConfigurationSpecialist",
            role="Hatch project configuration expert",
            instructions=self._get_configuration_specialist_prompt()
        )

        agent2 = self._create_agent(
            name="WorkflowSpecialist",
            role="Hatch workflow and automation expert",
            instructions=self._get_workflow_specialist_prompt()
        )

        judge_agent = self._create_agent(
            name="Judge",
            role="Solution evaluator and selector",
            instructions=self._get_judge_prompt()
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

    def _get_configuration_specialist_prompt(self) -> str:
        """Get the detailed prompt for the configuration specialist."""
        return """You are an expert in Hatch project configuration and dependency management.

Your expertise includes:
- pyproject.toml structure and PEP 621 compliance
- Build system configuration
- Dependency specification and version constraints
- Environment setup and management
- Hatch-specific configuration options

When providing solutions:
1. Focus on configuration accuracy and best practices
2. Ensure all TOML syntax is valid
3. Consider dependency compatibility
4. Follow semantic versioning guidelines
5. Explain the impact of changes on the project

Provide detailed, configuration-focused solutions that are immediately actionable."""

    def _get_workflow_specialist_prompt(self) -> str:
        """Get the detailed prompt for the workflow specialist."""
        return """You are an expert in Hatch workflows, automation, and development best practices.

Your expertise includes:
- Testing frameworks and test execution
- Code formatting and linting tools
- Type checking configuration
- CI/CD pipeline setup
- Development environment workflows
- Hatch scripts and automation

When providing solutions:
1. Focus on practical, workflow-oriented approaches
2. Consider developer experience and efficiency
3. Ensure commands are safe and reversible
4. Provide step-by-step execution plans
5. Include verification steps

Provide practical, workflow-oriented solutions that improve development processes."""

    def _get_judge_prompt(self) -> str:
        """Get the detailed prompt for the judge agent with consistency guidelines."""
        return """You are an impartial judge evaluating technical solutions.

Your role is to select the best solution based on consistent, objective criteria.

EVALUATION FRAMEWORK (use this exact scoring system):

1. CORRECTNESS (0-30 points):
   - Does the solution solve the stated problem?
   - Is the technical approach sound?
   - Are there any errors or oversights?

2. COMPLETENESS (0-25 points):
   - Does it address all aspects of the problem?
   - Are edge cases considered?
   - Is the solution actionable without additional information?

3. SAFETY (0-20 points):
   - Are there risks of breaking existing functionality?
   - Is the solution reversible if needed?
   - Are there proper safeguards?

4. BEST PRACTICES (0-15 points):
   - Does it follow industry standards?
   - Is it maintainable?
   - Does it align with Hatch conventions?

5. CLARITY (0-10 points):
   - Is the explanation clear?
   - Are instructions easy to follow?
   - Is the reasoning transparent?

DECISION PROCESS:
1. Score each suggestion using the framework above
2. Calculate total scores (max 100 points each)
3. Select the highest-scoring solution
4. If scores are within 5 points, prefer the safer approach
5. Document your scoring in the reasoning

OUTPUT FORMAT:
Always provide your response as valid JSON with:
- selected_agent: name of the winning agent
- suggestion: the selected (or improved) solution
- reasoning: detailed explanation including scores
- total_scores: object with scores for each agent

This framework ensures consistent judgments across similar inputs."""

    def _get_agent_response(self, agent: StrandsAgent, task: str, context: Dict[str, Any]) -> AgentResponse:
        """Get a response from a single agent."""
        prompt = self._build_prompt(task, context)
        result = agent.run(prompt)
        return self._parse_agent_response(agent.config.name, result)

    def _judge_suggestions(
        self,
        judge: StrandsAgent,
        task: str,
        suggestions: List[AgentResponse],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Have the judge agent evaluate and select the best suggestion."""
        judge_prompt = self._build_judge_prompt(task, suggestions, context)
        result = judge.run(judge_prompt)
        decision = self._parse_judge_decision(result, suggestions)
        return decision

    def _build_prompt(self, task: str, context: Dict[str, Any]) -> str:
        """Build a prompt for an agent."""
        context_str = ""
        if context:
            context_str = "\n\nContext:\n" + json.dumps(context, indent=2)

        return f"""Task: {task}{context_str}

INSTRUCTIONS:
1. Analyze the task carefully
2. Provide a detailed, actionable solution
3. Explain your reasoning
4. Rate your confidence (0.0 to 1.0)

RESPONSE FORMAT (JSON):
{{
    "suggestion": "Your detailed solution with specific steps/changes",
    "reasoning": "Why this approach is effective and appropriate",
    "confidence": 0.85
}}

Ensure your response is valid JSON."""

    def _build_judge_prompt(
        self,
        task: str,
        suggestions: List[AgentResponse],
        context: Dict[str, Any]
    ) -> str:
        """Build a prompt for the judge agent."""
        suggestions_str = "\n\n".join([
            f"=== Suggestion from {s.agent_name} ===\n"
            f"Suggestion: {s.suggestion}\n"
            f"Reasoning: {s.reasoning}\n"
            f"Confidence: {s.confidence}"
            for s in suggestions
        ])

        context_str = ""
        if context:
            context_str = "\n\nContext:\n" + json.dumps(context, indent=2)

        return f"""Task: {task}{context_str}

SUGGESTIONS TO EVALUATE:

{suggestions_str}

Using the evaluation framework in your instructions, analyze each suggestion and select the best one.

RESPONSE FORMAT (JSON):
{{
    "selected_agent": "name of the agent with best suggestion",
    "reasoning": "detailed scoring and rationale using the framework",
    "suggestion": "the selected suggestion (you may refine it)",
    "total_scores": {{
        "ConfigurationSpecialist": 85,
        "WorkflowSpecialist": 78
    }}
}}

Ensure your response is valid JSON."""

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

