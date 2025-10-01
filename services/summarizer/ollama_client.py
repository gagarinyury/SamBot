"""Ollama API client for LLM inference."""

import httpx
from typing import Optional, Dict, Any
import structlog

from config import settings

logger = structlog.get_logger()


class OllamaClient:
    """Client for Ollama API."""

    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = settings.MODEL_NAME
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using Ollama.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        try:
            # Prepare messages
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

            # Call Ollama API
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                }
            }

            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            logger.info("ollama_request", model=self.model, prompt_length=len(prompt))

            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            generated_text = data["message"]["content"]

            logger.info(
                "ollama_response",
                response_length=len(generated_text),
                eval_count=data.get("eval_count"),
                eval_duration=data.get("eval_duration")
            )

            return generated_text

        except Exception as e:
            logger.error("ollama_error", error=str(e))
            raise

    async def check_health(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error("ollama_health_check_failed", error=str(e))
            return False

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global Ollama client
ollama = OllamaClient()
