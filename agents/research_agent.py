"""
Research agent - the first agent in the pipeline that actually uses
tool-calling rather than a single completion, so it's built on
smolagents directly instead of BaseAgent's plain litellm call.

This is deliberately the proof point for "does smolagents work in this
project": if this agent runs and calls web_search, the orchestration
layer is validated end to end.
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from smolagents import LiteLLMModel, ToolCallingAgent, tool

from agents.base import AgentResult, BaseAgent, register_agent
from config import settings
from models.schemas import ResearchBrief
from prompts.research_prompt import RESEARCH_SYSTEM_PROMPT
from tools.search import web_search as _web_search_impl
from utils.json_parsing import extract_json


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for a query and return the results.

    Args:
        query: the search query.
        max_results: maximum number of results to return.

    Returns:
        A formatted string of search results (title, url, snippet per result).
    """
    results = _web_search_impl(query, max_results=max_results)
    if not results:
        return "No results found."
    return "\n\n".join(f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}" for r in results)


@register_agent("research")
class ResearchAgent(BaseAgent):
    """
    Overrides run() entirely (rather than build_user_prompt only) because
    it delegates execution to a smolagents ToolCallingAgent instead of a
    single litellm.completion call.

    Provider failover mirrors BaseAgent: retry once on a different model
    when the smolagents run itself raises (provider/network), but not when
    the response fails ResearchBrief schema validation.
    """

    name = "research"
    system_prompt = RESEARCH_SYSTEM_PROMPT
    response_model = ResearchBrief

    def build_user_prompt(self, **kwargs: Any) -> str:
        persona = kwargs.get("persona")
        topic = kwargs.get("topic")
        if not topic:
            raise ValueError("ResearchAgent requires a 'topic' in context")

        prompt = f"Research this course topic: {topic}"
        if persona is not None:
            prompt += f"\n\nTarget audience: {persona.audience_level}"
        return prompt

    def run(self, **kwargs: Any) -> AgentResult:
        start = time.monotonic()

        try:
            user_prompt = self.build_user_prompt(**kwargs)
        except Exception as exc:  # noqa: BLE001 - bad/missing context, not a model problem
            elapsed = time.monotonic() - start
            logger.exception("{} failed building prompt after {:.2f}s: {}", self.name, elapsed, exc)
            return AgentResult(agent_name=self.name, success=False, error=str(exc), latency_seconds=elapsed)

        attempt_models = self._models_for_failover()
        last_exc: Exception | None = None

        for i, model_id in enumerate(attempt_models):
            try:
                llm = LiteLLMModel(model_id=model_id, max_tokens=settings.max_tokens)
                smol_agent = ToolCallingAgent(
                    tools=[web_search],
                    model=llm,
                    max_steps=6,
                    instructions=self.system_prompt,
                )

                raw_result = smol_agent.run(user_prompt)
            except Exception as exc:  # noqa: BLE001 - provider/network error, eligible for failover
                last_exc = exc
                is_last_attempt = i == len(attempt_models) - 1
                if is_last_attempt:
                    elapsed = time.monotonic() - start
                    logger.exception(
                        "{} failed after {:.2f}s - all models exhausted ({}): {}",
                        self.name,
                        elapsed,
                        attempt_models,
                        exc,
                    )
                    return AgentResult(
                        agent_name=self.name,
                        success=False,
                        error=str(exc),
                        model_used=model_id,
                        latency_seconds=elapsed,
                    )
                logger.warning(
                    "{}: {} failed ({}), failing over to {}",
                    self.name,
                    model_id,
                    exc,
                    attempt_models[i + 1],
                )
                continue

            # Got a response - parse/validate here; do not failover on schema errors.
            elapsed = time.monotonic() - start
            try:
                token_usage = smol_agent.monitor.get_total_token_counts()
                input_tokens = token_usage.input_tokens
                output_tokens = token_usage.output_tokens
            except AttributeError as monitor_exc:
                # smolagents is on a loose version pin (>=1.3) and has
                # changed its monitor API before - token/cost tracking
                # degrading gracefully to zero is far better than this
                # whole agent crashing over a cost-tracking nicety.
                logger.warning(
                    "{}: smolagents monitor API unavailable ({}) - token/cost tracking "
                    "degraded to 0 for this call, but the agent result itself is unaffected",
                    self.name,
                    monitor_exc,
                )
                input_tokens = 0
                output_tokens = 0

            # smolagents doesn't compute cost itself; estimate via litellm
            # using the same per-token pricing table the rest of the app uses.
            try:
                import litellm

                cost = litellm.cost_per_token(
                    model=model_id.split("/", 1)[-1],
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                )
                estimated_cost = sum(cost) if isinstance(cost, tuple) else 0.0
                cost_estimation_failed = False
            except Exception as cost_exc:  # noqa: BLE001 - cost calc itself shouldn't fail the agent
                estimated_cost = 0.0
                cost_estimation_failed = True
                logger.warning(
                    "{}: cost estimation failed for model {} ({}) - this call is being counted "
                    "as $0.00 toward the cost ceiling, which is NOT accurate.",
                    self.name,
                    model_id,
                    cost_exc,
                )

            try:
                parsed_dict = extract_json(str(raw_result))
                output = self.response_model.model_validate(parsed_dict)
            except Exception as parse_exc:  # noqa: BLE001
                logger.warning(
                    "{}: smolagents output failed schema validation: {}\nRaw: {}",
                    self.name,
                    parse_exc,
                    raw_result,
                )
                return AgentResult(
                    agent_name=self.name,
                    success=False,
                    error=f"Output failed ResearchBrief validation: {parse_exc}",
                    model_used=model_id,
                    latency_seconds=elapsed,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=estimated_cost,
                    metadata={
                        "raw_output": str(raw_result),
                        "failed_over": i > 0,
                        "cost_estimation_failed": cost_estimation_failed,
                    },
                )

            if i > 0:
                logger.info("{}: succeeded on fallback model {} after primary failed", self.name, model_id)

            logger.info(
                "{} completed in {:.2f}s (model={}, tokens={}+{}, cost=${:.4f})",
                self.name,
                elapsed,
                model_id,
                input_tokens,
                output_tokens,
                estimated_cost,
            )

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=output,
                model_used=model_id,
                latency_seconds=elapsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimated_cost,
                metadata={"failed_over": i > 0, "cost_estimation_failed": cost_estimation_failed},
            )

        elapsed = time.monotonic() - start
        return AgentResult(
            agent_name=self.name,
            success=False,
            error=str(last_exc) if last_exc else "No model attempts were made",
            latency_seconds=elapsed,
        )
