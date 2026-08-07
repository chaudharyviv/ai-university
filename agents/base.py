"""
Base agent class.

Every specialized agent (Persona, Research, Curriculum, ... added in
later phases) inherits from `BaseAgent`. This class owns:
  - which model the agent calls (with primary -> fallback routing via LiteLLM)
  - a consistent `run()` entrypoint and return shape
  - basic cost/token logging per call
  - a plugin-style registry so the Orchestrator can discover agents by
    name without importing every module by hand

Concrete agents implement `system_prompt` and `build_user_prompt()`;
everything else is inherited.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import litellm
from loguru import logger
from pydantic import BaseModel, ValidationError

from config import settings
from utils.json_parsing import extract_json

# --- Plugin-style registry -------------------------------------------------

_AGENT_REGISTRY: dict[str, type["BaseAgent"]] = {}


def register_agent(name: str):
    """
    Class decorator: registers an agent under `name` so the Orchestrator
    can look it up without a hardcoded import list.

        @register_agent("research")
        class ResearchAgent(BaseAgent):
            ...
    """

    def _wrap(cls: type["BaseAgent"]) -> type["BaseAgent"]:
        if name in _AGENT_REGISTRY:
            raise ValueError(f"Agent name {name!r} already registered by {_AGENT_REGISTRY[name]!r}")
        _AGENT_REGISTRY[name] = cls
        return cls

    return _wrap


def get_agent_class(name: str) -> type["BaseAgent"]:
    if name not in _AGENT_REGISTRY:
        raise KeyError(f"No agent registered under {name!r}. Registered: {list(_AGENT_REGISTRY)}")
    return _AGENT_REGISTRY[name]


def list_registered_agents() -> list[str]:
    return sorted(_AGENT_REGISTRY)


# --- Result shape ------------------------------------------------------------


@dataclass
class AgentResult:
    """Uniform return type for every agent run, so the Orchestrator and
    the Streamlit UI can handle any agent's output the same way."""

    agent_name: str
    success: bool
    output: Any = None
    error: str | None = None
    model_used: str = ""
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Base agent ---------------------------------------------------------------


class BaseAgent(ABC):
    """
    Common functionality for all agents.

    Subclasses must set:
        name: short identifier, e.g. "research"
        system_prompt: the agent's role/instructions

    and implement:
        build_user_prompt(**kwargs) -> str
    """

    name: ClassVar[str] = "base"
    system_prompt: ClassVar[str] = "You are a helpful assistant."

    # Override per-agent if a specific agent should prefer a different
    # model than the app-wide default (e.g. a cheap agent forced to
    # fallback_model even when primary is available).
    preferred_model: str | None = None

    # If set, `run()` parses the model's text output as JSON and validates
    # it against this schema. On success, `AgentResult.output` is the
    # validated Pydantic instance (not a string). On failure to parse or
    # validate, the result is marked unsuccessful with a clear error -
    # this turns "the model didn't follow instructions" into a normal,
    # visible agent failure rather than a downstream KeyError somewhere else.
    response_model: ClassVar[type[BaseModel] | None] = None

    def __init__(self) -> None:
        settings.validate_at_least_one_provider()

    def _provider_available(self, model: str) -> bool:
        """True if we have credentials for the provider prefix of a LiteLLM model id."""
        provider = model.split("/", 1)[0]
        if provider == "anthropic":
            return settings.has_anthropic
        if provider == "openai":
            return settings.has_openai
        return True

    def _resolve_model(self) -> str:
        """Pick which model this agent should call, given configured keys."""
        model = self.preferred_model or settings.primary_model

        provider = model.split("/", 1)[0]
        if provider == "anthropic" and not settings.has_anthropic:
            logger.warning(
                "{}: anthropic key missing, falling back to {}",
                self.name,
                settings.fallback_model,
            )
            model = settings.fallback_model
        elif provider == "openai" and not settings.has_openai:
            logger.warning(
                "{}: openai key missing, falling back to {}",
                self.name,
                settings.fallback_model,
            )
            model = settings.fallback_model

        return model

    def _models_for_failover(self) -> list[str]:
        """
        Ordered models to try: resolved primary, then fallback if it differs
        and we actually have credentials for that provider.
        """
        primary_model = self._resolve_model()
        attempt_models = [primary_model]
        fallback = settings.fallback_model
        if fallback != primary_model and self._provider_available(fallback):
            attempt_models.append(fallback)
        elif fallback != primary_model:
            logger.warning(
                "{}: skipping failover to {} - provider credentials not configured",
                self.name,
                fallback,
            )
        return attempt_models

    @abstractmethod
    def build_user_prompt(self, **kwargs: Any) -> str:
        """Construct the user-turn prompt from whatever inputs this agent needs."""
        raise NotImplementedError

    def run(self, **kwargs: Any) -> AgentResult:
        """
        Execute this agent: build the prompt, call the model via LiteLLM,
        and return a uniform AgentResult. Never raises - errors are
        captured in the result so the Orchestrator can decide how to react.

        Provider failover (Phase 6): if the call to the primary model
        itself fails (rate limit, timeout, auth error, provider outage -
        anything litellm.completion raises), this automatically retries
        once against settings.fallback_model before giving up. This is
        separate from response_model validation failures (bad JSON from
        a model that DID respond) - those are not retried against a
        different model, since a formatting mistake isn't a provider
        problem and retrying it against a second model just doubles cost
        for the same likely outcome.
        """
        start = time.monotonic()

        try:
            user_prompt = self.build_user_prompt(**kwargs)
        except Exception as exc:  # noqa: BLE001 - bad/missing context, not a model problem
            elapsed = time.monotonic() - start
            logger.exception("{} failed building prompt after {:.2f}s: {}", self.name, elapsed, exc)
            return AgentResult(agent_name=self.name, success=False, error=str(exc), latency_seconds=elapsed)

        attempt_models = self._models_for_failover()

        last_exc: Exception | None = None
        for i, model in enumerate(attempt_models):
            try:
                response = litellm.completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=settings.max_tokens,
                )
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
                        agent_name=self.name, success=False, error=str(exc), model_used=model, latency_seconds=elapsed
                    )
                logger.warning(
                    "{}: {} failed ({}), failing over to {}", self.name, model, exc, attempt_models[i + 1]
                )
                continue

            # Got a response - handle success/parsing here rather than
            # retrying against another model. A response that fails schema
            # validation is a formatting problem, not a provider problem.
            elapsed = time.monotonic() - start
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0

            try:
                cost = litellm.completion_cost(completion_response=response)
                cost_estimation_failed = False
            except Exception as cost_exc:  # noqa: BLE001 - cost calc itself shouldn't fail the agent
                cost = 0.0
                cost_estimation_failed = True
                logger.warning(
                    "{}: cost estimation failed for model {} ({}) - this call is being counted as "
                    "$0.00 toward the cost ceiling, which is NOT accurate. If this happens "
                    "repeatedly, the cost ceiling is silently not being enforced for this model.",
                    self.name,
                    model,
                    cost_exc,
                )

            content = response.choices[0].message.content

            output: Any = content
            if self.response_model is not None:
                try:
                    parsed_dict = extract_json(content)
                    output = self.response_model.model_validate(parsed_dict)
                except (ValueError, ValidationError) as parse_exc:
                    elapsed = time.monotonic() - start
                    logger.warning(
                        "{}: model output failed schema validation: {}\nRaw output: {}",
                        self.name,
                        parse_exc,
                        content,
                    )
                    return AgentResult(
                        agent_name=self.name,
                        success=False,
                        error=f"Output failed {self.response_model.__name__} validation: {parse_exc}",
                        model_used=model,
                        latency_seconds=elapsed,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost_usd=cost,
                        metadata={"raw_output": content, "cost_estimation_failed": cost_estimation_failed},
                    )

            if i > 0:
                logger.info("{}: succeeded on fallback model {} after primary failed", self.name, model)

            logger.info(
                "{} completed in {:.2f}s (model={}, tokens={}+{}, cost=${:.4f})",
                self.name,
                elapsed,
                model,
                input_tokens,
                output_tokens,
                cost,
            )

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=output,
                model_used=model,
                latency_seconds=elapsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost,
                metadata={"failed_over": i > 0, "cost_estimation_failed": cost_estimation_failed},
            )

        # Unreachable in practice (the loop above always returns or raises
        # via the last-attempt branch), but keeps type checkers happy and
        # fails loudly instead of silently returning None if that ever changes.
        elapsed = time.monotonic() - start
        return AgentResult(
            agent_name=self.name,
            success=False,
            error=str(last_exc) if last_exc else "No model attempts were made",
            latency_seconds=elapsed,
        )
