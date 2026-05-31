"""
LLM client for Ragebait Critic.

This module isolates LiteLLM calls from the rest of the application.

The rest of the system should not call LiteLLM directly. Keeping model access
behind this wrapper makes retries, timeouts, testing, and future provider-specific
handling much cleaner.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from litellm import acompletion

from ragebait_critic.config import RagebaitConfig
from ragebait_critic.exceptions import LLMClientError
from ragebait_critic.prompt_builder import BuiltPrompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    """
    Normalized LLM response.
    """

    content: str
    model: str
    raw_response: object | None = None


class LLMClient:
    """
    Thin async wrapper around LiteLLM chat completions.
    """

    def __init__(self, config: RagebaitConfig | None = None) -> None:
        self.config = config or RagebaitConfig.from_env()

    async def complete(
        self,
        prompt: BuiltPrompt,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        """
        Execute a chat completion request with retry handling.
        """
        selected_model = model or self.config.default_model
        attempts = self.config.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                logger.info(
                    "Calling LLM: model=%s attempt=%s/%s",
                    selected_model,
                    attempt,
                    attempts,
                )

                response = await acompletion(
                    model=selected_model,
                    messages=[
                        {"role": "system", "content": prompt.system_prompt},
                        {"role": "user", "content": prompt.user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.config.request_timeout_seconds,
                )

                content = self._extract_content(response)

                if not content.strip():
                    raise LLMClientError("LLM returned an empty response.")

                return LLMResponse(
                    content=content,
                    model=selected_model,
                    raw_response=response,
                )

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM call failed: model=%s attempt=%s/%s error=%s",
                    selected_model,
                    attempt,
                    attempts,
                    exc,
                )

                if attempt < attempts:
                    await asyncio.sleep(self._retry_delay(attempt))

        raise LLMClientError(
            f"LLM call failed after {attempts} attempt(s): {last_error}"
        ) from last_error

    def _extract_content(self, response: object) -> str:
        """
        Extract assistant message content from LiteLLM response.

        LiteLLM usually behaves like an OpenAI-compatible mapping, but this method
        stays defensive because provider responses can vary.
        """
        try:
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if not choices:
                    raise LLMClientError("LLM response has no choices.")

                message = choices[0].get("message", {})
                content = message.get("content", "")

                if isinstance(content, list):
                    return "\n".join(str(part) for part in content)

                return str(content)

            choices = getattr(response, "choices", None)
            if not choices:
                raise LLMClientError("LLM response has no choices.")

            first_choice = choices[0]
            message = getattr(first_choice, "message", None)

            if message is None:
                raise LLMClientError("LLM response choice has no message.")

            content = getattr(message, "content", "")

            if isinstance(content, list):
                return "\n".join(str(part) for part in content)

            return str(content)

        except LLMClientError:
            raise
        except Exception as exc:
            raise LLMClientError(f"Failed to extract LLM response content: {exc}") from exc

    def _retry_delay(self, attempt: int) -> float:
        """
        Small exponential backoff.

        Kept intentionally short because this is a CLI/dev tool, not a background worker.
        """
        return min(2.0, 0.5 * attempt)