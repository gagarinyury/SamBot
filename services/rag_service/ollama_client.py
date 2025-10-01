"""Ollama client for embeddings and LLM."""

import httpx
from typing import List, Optional
import structlog

from config import settings

logger = structlog.get_logger()


class OllamaClient:
    """Client for Ollama API."""

    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.embedding_model = settings.EMBEDDING_MODEL
        self.llm_model = settings.LLM_MODEL
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector (768-dim for nomic-embed-text)
        """
        try:
            url = f"{self.base_url}/api/embeddings"
            payload = {
                "model": self.embedding_model,
                "prompt": text
            }

            logger.info("embedding_request", text_length=len(text), model=self.embedding_model)

            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            embedding = data["embedding"]

            logger.info("embedding_generated", dimension=len(embedding))

            return embedding

        except Exception as e:
            logger.error("embedding_error", error=str(e))
            raise

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3
    ) -> str:
        """
        Generate text using LLM.

        Args:
            prompt: User prompt with RAG context
            system_prompt: System instructions
            temperature: Sampling temperature

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

            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.llm_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                }
            }

            logger.info("llm_request", model=self.llm_model, prompt_length=len(prompt))

            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            generated_text = data["message"]["content"]

            logger.info("llm_response", response_length=len(generated_text))

            return generated_text

        except Exception as e:
            logger.error("llm_error", error=str(e))
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
