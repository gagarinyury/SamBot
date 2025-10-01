"""DeepSeek API client for summarization."""

import structlog
from openai import AsyncOpenAI
from typing import Optional, AsyncGenerator

logger = structlog.get_logger()


class DeepSeekClient:
    """DeepSeek API client using OpenAI-compatible SDK."""

    def __init__(self, api_key: str):
        """Initialize DeepSeek client."""
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using DeepSeek.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        try:
            messages = []

            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            messages.append({
                "role": "user",
                "content": prompt
            })

            logger.info(
                "deepseek_request",
                model=self.model,
                prompt_length=len(prompt)
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 4096,
                stream=False
            )

            content = response.choices[0].message.content

            logger.info(
                "deepseek_response",
                response_length=len(content),
                tokens_used=response.usage.total_tokens,
                cost_estimate=f"${response.usage.total_tokens * 0.00000014:.6f}"
            )

            return content

        except Exception as e:
            logger.error("deepseek_error", error=str(e))
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate text using DeepSeek with streaming.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        try:
            messages = []

            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            messages.append({
                "role": "user",
                "content": prompt
            })

            logger.info(
                "deepseek_request_stream",
                model=self.model,
                prompt_length=len(prompt)
            )

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 4096,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

            logger.info("deepseek_stream_completed")

        except Exception as e:
            logger.error("deepseek_stream_error", error=str(e))
            raise


# Global instance (will be initialized in main.py)
deepseek_client: Optional[DeepSeekClient] = None
