"""Multi-agent orchestration using strands-agents.

This module implements a multi-agent approach where:
- Two specialist agents generate different suggestions/solutions
- A judge agent evaluates and selects the best approach
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json

from strands import Agent as StrandsAgent


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
        system_prompt = f"You are a {role}.\n\n{instructions}"
        return StrandsAgent(system_prompt=system_prompt)

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the multi-agent system to solve a task.

        Args:
            task: The task description
            context: Optional context about the hatch project

        Returns:
            Dict with selected suggestion, reasoning, and all agent responses
        """
        context = context or {}

        # Check if this is a dependency update task
        is_update_task = "updating the dependency" in task.lower() or "update strategy" in task.lower()

        if is_update_task:
            # Use specialized agents for dependency updates
            return self._run_update_agents(task, context)

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

    def _run_update_agents(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run specialized agents for dependency updates.

        Uses different specialist agents focused on:
        - API compatibility analysis
        - Minimal code migration
        """
        # Create specialized update agents
        agent1 = self._create_agent(
            name="APIAnalysisSpecialist",
            role="API compatibility and breaking change analyst",
            instructions=self._get_api_analysis_prompt()
        )

        agent2 = self._create_agent(
            name="CodeMigrationSpecialist",
            role="Minimal code migration expert",
            instructions=self._get_code_migration_prompt()
        )

        judge_agent = self._create_agent(
            name="UpdateJudge",
            role="Update strategy evaluator",
            instructions=self._get_update_judge_prompt()
        )

        # Get suggestions from both specialist agents
        suggestions = []

        response1 = self._get_agent_response(agent1, task, context)
        suggestions.append(response1)

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

    def run_bulk_update_analysis(
        self,
        updates: List[Dict[str, str]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze multiple package updates efficiently.

        This method processes multiple dependency updates and aggregates the
        breaking changes and code modifications across all packages.

        Args:
            updates: List of dicts with keys: package, old_version, new_version
            context: Project context including source files

        Returns:
            Aggregated analysis with all breaking changes and code modifications
        """
        all_code_changes: List[Dict[str, Any]] = []
        all_breaking_changes: List[Dict[str, str]] = []
        failed_packages: List[str] = []

        for update in updates:
            package = update.get("package", "unknown")
            old_version = update.get("old_version", "unknown")
            new_version = update.get("new_version", "unknown")

            # Build task for this specific update
            task = self._build_bulk_update_task(update, updates)

            # Merge update-specific context
            update_context = {
                **context,
                "current_package": package,
                "current_update": update
            }

            # Run existing update agents
            try:
                result = self._run_update_agents(task, update_context)

                # Extract and aggregate results
                if result.get("success"):
                    plan = self._extract_update_plan(result.get("selected_suggestion", ""))
                    if plan:
                        # Add package info to each breaking change
                        for bc in plan.get("breaking_changes", []):
                            all_breaking_changes.append({
                                "package": package,
                                "old_version": old_version,
                                "new_version": new_version,
                                "change": bc
                            })

                        # Add package info to each code change
                        for cc in plan.get("code_changes", []):
                            cc["package"] = package
                            all_code_changes.append(cc)
                else:
                    failed_packages.append(package)
            except Exception:
                failed_packages.append(package)

        # Deduplicate code changes (same file/line might be suggested multiple times)
        unique_changes = self._deduplicate_code_changes(all_code_changes)

        return {
            "success": True,
            "breaking_changes": all_breaking_changes,
            "code_changes": unique_changes,
            "packages_analyzed": len(updates),
            "failed_packages": failed_packages
        }

    def _build_bulk_update_task(
        self,
        current_update: Dict[str, str],
        all_updates: List[Dict[str, str]]
    ) -> str:
        """Build a task description for bulk update analysis.

        Args:
            current_update: The specific package being analyzed
            all_updates: All packages being updated (for context)

        Returns:
            Task description string
        """
        package = current_update.get("package", "unknown")
        old_version = current_update.get("old_version", "unknown")
        new_version = current_update.get("new_version", "unknown")

        # Build context about other updates
        other_updates = [u for u in all_updates if u.get("package") != package]
        other_updates_str = ""
        if other_updates:
            other_list = ", ".join([
                f"{u.get('package')} ({u.get('old_version')} → {u.get('new_version')})"
                for u in other_updates[:5]  # Limit to 5 for context
            ])
            if len(other_updates) > 5:
                other_list += f" and {len(other_updates) - 5} more"
            other_updates_str = f"\n\nNote: Other packages being updated in this sync: {other_list}"

        return f"""You are analyzing the dependency '{package}' update from {old_version} to {new_version}.

Your task is to identify:

1. Any breaking API changes between these versions
2. ONLY the minimal code changes required for API compatibility
3. Specific file paths and change descriptions

CRITICAL REQUIREMENTS:
- Identify ONLY changes required for API compatibility
- Do NOT suggest refactoring or improvements
- Do NOT suggest adding new features
- Do NOT suggest style or formatting changes
- Be extremely conservative with suggestions
- Consider interactions with other packages being updated{other_updates_str}

RESPONSE FORMAT (required):

Your response MUST include this structured section at the END:

UPDATE_PLAN:
{{
    "version_spec": ">={new_version}",
    "breaking_changes": [
        "Description of breaking change 1",
        "Description of breaking change 2"
    ],
    "code_changes": [
        {{
            "file": "src/module/file.py",
            "line_range": "45-50",
            "description": "Replace deprecated method X with Y",
            "reason": "Method X was removed in version {new_version}"
        }}
    ]
}}

If NO breaking changes or code changes are needed, use empty arrays:
"breaking_changes": [], "code_changes": []

Provide this JSON block AFTER your explanation."""

    def _extract_update_plan(self, suggestion: str) -> Optional[Dict[str, Any]]:
        """Extract structured update plan from agent suggestion.

        Args:
            suggestion: The agent's suggestion text

        Returns:
            Parsed update plan dict or None if parsing fails
        """
        if "UPDATE_PLAN:" not in suggestion:
            return None

        try:
            plan_part = suggestion.split("UPDATE_PLAN:")[1].strip()

            # Find the JSON object
            start = plan_part.find("{")
            end = plan_part.rfind("}") + 1

            if start == -1 or end == 0:
                return None

            json_str = plan_part[start:end]
            plan_data = json.loads(json_str)

            return plan_data
        except (json.JSONDecodeError, IndexError):
            return None

    def _deduplicate_code_changes(
        self,
        code_changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Deduplicate code changes that affect the same file/lines.

        If multiple packages suggest changes to the same file and line range,
        we keep only one (preferring the one with more detail).

        Args:
            code_changes: List of code change dicts

        Returns:
            Deduplicated list of code changes
        """
        seen: Dict[str, Dict[str, Any]] = {}

        for change in code_changes:
            file_path = change.get("file", "")
            line_range = change.get("line_range", "")

            # Create a unique key based on file and line range
            key = f"{file_path}:{line_range}"

            if key not in seen:
                seen[key] = change
            else:
                # Keep the change with more detailed description
                existing = seen[key]
                existing_desc_len = len(existing.get("description", ""))
                new_desc_len = len(change.get("description", ""))

                if new_desc_len > existing_desc_len:
                    # Merge package info if different packages suggest same change
                    packages = set()
                    if "package" in existing:
                        packages.add(existing["package"])
                    if "package" in change:
                        packages.add(change["package"])
                    change["packages"] = list(packages) if len(packages) > 1 else None
                    seen[key] = change
                elif "package" in change and "package" in existing:
                    # Just add the package to the existing change
                    if "packages" not in existing:
                        existing["packages"] = [existing["package"]]
                    if change["package"] not in existing["packages"]:
                        existing["packages"].append(change["package"])

        return list(seen.values())

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

    def _get_api_analysis_prompt(self) -> str:
        """Get the prompt for API analysis specialist (dependency updates)."""
        return """You are an expert in analyzing API changes and breaking changes between library versions.

Your expertise includes:
- Changelog analysis and version comparison
- Breaking change identification
- API deprecation detection
- Migration path planning
- Semantic versioning interpretation

When analyzing dependency updates:
1. Research the specific version changes (if context provided)
2. Identify ALL breaking changes between versions
3. List deprecated APIs that are used
4. Determine minimum code changes required
5. Prioritize backward compatibility where possible

CRITICAL CONSTRAINTS FOR CODE CHANGES:
- Suggest ONLY changes required for API compatibility
- Do NOT suggest refactoring or improvements
- Do NOT add new features or abstractions
- Do NOT change existing code style or patterns
- Be extremely conservative and minimal

Your analysis should help determine if the update is safe and what minimal changes are needed."""

    def _get_code_migration_prompt(self) -> str:
        """Get the prompt for code migration specialist (dependency updates)."""
        return """You are an expert in minimal code migration for dependency updates.

Your expertise includes:
- Precise code modification for API compatibility
- Import statement updates
- Method signature changes
- Minimal refactoring for breaking changes
- Preserving existing code structure

STRICT CODE CHANGE RULES (CRITICAL):
1. Make ONLY changes required for the new API
2. Do NOT refactor or "improve" existing code
3. Do NOT add error handling unless API requires it
4. Do NOT change variable names or code structure
5. Do NOT add type hints, comments, or documentation
6. Do NOT change formatting or style
7. Preserve ALL existing logic and behavior
8. Make the SMALLEST possible change to work with new API

FORBIDDEN ACTIONS:
❌ Adding new features or functionality
❌ Refactoring for "better code quality"
❌ Changing code organization or structure
❌ Adding complexity beyond API requirements
❌ Updating unrelated code
❌ Style improvements or cleanup

ALLOWED ACTIONS:
✅ Changing import statements (if API moved)
✅ Updating method names (if renamed in API)
✅ Adjusting parameters (if signature changed)
✅ Replacing removed methods with equivalents
✅ Minimal syntax updates (if required by new API)

When suggesting code changes:
- Be extremely specific about file and line numbers
- Show only the exact lines that must change
- Explain why each change is absolutely required
- Verify no alternative approach exists that requires less change"""

    def _get_update_judge_prompt(self) -> str:
        """Get the prompt for update strategy judge."""
        return """You are an impartial judge evaluating dependency update strategies.

Your role is to select the safest, most minimal update approach.

EVALUATION FRAMEWORK (use this exact scoring system):

1. MINIMALISM (0-35 points):
   - Are code changes truly minimal?
   - Is any suggested change unnecessary?
   - Could fewer changes achieve the same result?
   - Deduct points for ANY unnecessary changes

2. CORRECTNESS (0-25 points):
   - Will the changes work with the new API?
   - Are all breaking changes addressed?
   - Is the migration path sound?

3. SAFETY (0-25 points):
   - Risk of breaking existing functionality?
   - Are changes reversible?
   - Is existing behavior preserved?

4. SPECIFICITY (0-15 points):
   - Are file paths and line numbers provided?
   - Are changes described precisely?
   - Can changes be applied unambiguously?

CRITICAL EVALUATION RULES:
- HEAVILY penalize suggestions that include refactoring
- HEAVILY penalize suggestions that add complexity
- PREFER the suggestion with FEWER code changes
- REJECT any "improvements" beyond API compatibility
- If both suggestions include unnecessary changes, reduce both scores

DECISION PROCESS:
1. Score each suggestion using the framework above
2. Calculate total scores (max 100 points each)
3. Identify and penalize any non-essential changes
4. Select the most minimal, safest approach
5. Document your scoring with specific examples

OUTPUT FORMAT:
Always provide your response as valid JSON with:
- selected_agent: name of the agent with most minimal approach
- suggestion: the selected suggestion (remove any non-essential changes)
- reasoning: detailed scoring with examples of what was penalized
- total_scores: object with scores for each agent

Prioritize MINIMALISM above all else. The best update makes the fewest changes."""

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
