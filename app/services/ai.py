from dataclasses import dataclass

from openai import APITimeoutError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.config import Settings


@dataclass(slots=True)
class AIResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class AIProviderError(Exception):
    pass


class OpenAIProvider:
    """Small provider boundary around OpenAI's async chat-completions API."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.openai_api_key.get_secret_value()
        if settings.openai_base_url:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.openai_base_url,
                timeout=settings.openai_timeout_seconds,
                max_retries=0,
            )
        else:
            self.client = AsyncOpenAI(
                api_key=api_key,
                timeout=settings.openai_timeout_seconds,
                max_retries=0,
            )
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_output_tokens

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=8),
        retry=retry_if_exception_type((APITimeoutError, RateLimitError)),
        reraise=True,
    )
    async def complete(self, messages: list[ChatCompletionMessageParam]) -> AIResult:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=self.max_tokens,
                temperature=0.7,
            )
        except (APITimeoutError, RateLimitError):
            raise
        except Exception as exc:
            raise AIProviderError("The AI provider rejected the request") from exc
        choice = response.choices[0].message.content or ""
        usage = response.usage
        return AIResult(
            content=choice.strip(),
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    async def close(self) -> None:
        await self.client.close()
