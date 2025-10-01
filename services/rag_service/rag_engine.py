"""RAG engine for question answering over video transcripts."""

import structlog
from typing import List, Dict, Any

from config import settings
from database import db
from ollama_client import ollama

logger = structlog.get_logger()


RAG_SYSTEM_PROMPT = """Ты — помощник для ответов на вопросы по видеоконтенту.

Твоя задача:
- Отвечать на вопросы используя ТОЛЬКО предоставленный контекст
- Если в контексте нет ответа, честно скажи "В предоставленном контексте нет информации по этому вопросу"
- Указывай источники (название видео, автор)
- Отвечай четко и по делу

Формат ответа:
1. Прямой ответ на вопрос
2. Краткое объяснение из контекста
3. Источник информации (если есть metadata)
"""


class RAGEngine:
    """RAG engine for semantic search and question answering."""

    async def generate_and_save_embedding(self, content_id: int) -> bool:
        """
        Generate and save embeddings for all chunks of content.

        Args:
            content_id: ID of content to embed

        Returns:
            True if successful
        """
        # Get chunks
        chunks = await db.get_chunks(content_id)

        if not chunks:
            logger.error("no_chunks_found", content_id=content_id)
            return False

        logger.info("embedding_chunks_started", content_id=content_id, chunks_count=len(chunks))

        # Generate embedding for each chunk
        successful = 0
        for chunk in chunks:
            try:
                # Generate embedding
                embedding = await ollama.generate_embedding(chunk['text'])

                # Save to database
                await db.save_chunk_embedding(
                    chunk_id=chunk['chunk_id'],
                    embedding=embedding,
                    model=settings.EMBEDDING_MODEL
                )

                successful += 1

                # Log progress every 10 chunks
                if (chunk['index'] + 1) % 10 == 0:
                    logger.info("embedding_progress", chunk=chunk['index'] + 1, total=len(chunks))

            except Exception as e:
                logger.error("chunk_embedding_failed", chunk_id=chunk['chunk_id'], error=str(e))

        logger.info(
            "embedding_chunks_completed",
            content_id=content_id,
            successful=successful,
            total=len(chunks)
        )

        return successful > 0

    async def search(
        self,
        query: str,
        top_k: int = None,
        min_similarity: float = None,
        content_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Search for content similar to query.

        Args:
            query: Search query
            top_k: Number of results (default from settings)
            min_similarity: Minimum similarity threshold
            content_id: Optional content ID to filter by specific video

        Returns:
            List of similar content with scores
        """
        top_k = top_k or settings.TOP_K_RESULTS
        min_similarity = min_similarity or settings.SIMILARITY_THRESHOLD

        # Generate query embedding
        query_embedding = await ollama.generate_embedding(query)

        # Search database
        results = await db.semantic_search(
            query_embedding=query_embedding,
            limit=top_k,
            min_similarity=min_similarity,
            content_id=content_id
        )

        logger.info("search_completed", query=query[:50], results=len(results), content_id=content_id)

        return results

    async def ask(
        self,
        question: str,
        top_k: int = None,
        min_similarity: float = None,
        content_id: int = None
    ) -> Dict[str, Any]:
        """
        Answer question using RAG.

        Process:
        1. Search for relevant content
        2. Build context from search results
        3. Generate answer using LLM

        Args:
            question: User question
            top_k: Number of context chunks
            min_similarity: Minimum similarity threshold
            content_id: Optional content ID to filter by specific video

        Returns:
            Answer with sources and metadata
        """
        # Search for relevant content
        search_results = await self.search(
            query=question,
            top_k=top_k,
            min_similarity=min_similarity,
            content_id=content_id
        )

        if not search_results:
            return {
                'answer': 'В базе знаний нет информации для ответа на этот вопрос.',
                'sources': [],
                'context_used': False
            }

        # Build context
        context_parts = []
        sources = []

        for i, result in enumerate(search_results, 1):
            metadata = result.get('metadata', {})
            # metadata might be JSON string, parse it
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            title = metadata.get('title', 'Unknown')
            channel = metadata.get('channel', 'Unknown')

            # Add source info
            sources.append({
                'content_id': result['content_id'],
                'chunk_id': result['chunk_id'],
                'chunk_index': result['chunk_index'],
                'title': title,
                'channel': channel,
                'url': result['url'],
                'similarity': result['similarity']
            })

            # Add context from chunk
            chunk_text = result['chunk_text']

            context_parts.append(f"""
[Источник {i}: {title} - {channel}, фрагмент #{result['chunk_index']}]
{chunk_text}
""")

        context = "\n\n".join(context_parts)

        # Build prompt
        prompt = f"""Контекст из видео:
{context}

Вопрос: {question}

Ответь на вопрос используя ТОЛЬКО информацию из контекста выше."""

        # Generate answer
        answer = await ollama.generate(
            prompt=prompt,
            system_prompt=RAG_SYSTEM_PROMPT,
            temperature=settings.TEMPERATURE
        )

        logger.info(
            "question_answered",
            question=question[:50],
            sources_used=len(sources),
            answer_length=len(answer)
        )

        return {
            'answer': answer,
            'sources': sources,
            'context_used': True,
            'num_sources': len(sources)
        }


# Global RAG engine
rag_engine = RAGEngine()
