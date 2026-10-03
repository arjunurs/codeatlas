"""LangChain adapters that feed API usage into a CostTracker.

LLM token counts come from the usage each chat model call reports. LangChain's
embedding classes do not expose the usage the API reports, so embedding token
counts are estimated from text length and recorded as estimates.
"""

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.outputs import ChatGeneration, LLMResult

from .cost_tracker import CostTracker

# Rough average for English text and source code
CHARS_PER_TOKEN = 4

# Stop reasons meaning the model hit its output token limit: Anthropic reports
# stop_reason, OpenAI reports finish_reason
OUTPUT_LIMIT_STOP_REASONS = {("stop_reason", "max_tokens"), ("finish_reason", "length")}


def estimate_tokens(text: str) -> int:
    """Estimate the token count of a text from its length.

    Args:
        text: Text to estimate

    Returns:
        Estimated number of tokens
    """
    return len(text) // CHARS_PER_TOKEN


class TokenUsageCallback(BaseCallbackHandler):
    """Totals the token usage that chat models report for each call.

    Pass one instance per chain invocation, via ``config={"callbacks": [...]}``.
    It also sees model calls inside a chain that ends in a string parser.
    ``truncated`` is set when a response stopped at the output token limit.
    """

    def __init__(self) -> None:
        """Initialize with zero usage."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.truncated = False

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Add the usage reported by a finished model call."""
        for generations in response.generations:
            for generation in generations:
                if not isinstance(generation, ChatGeneration):
                    continue
                usage = getattr(generation.message, "usage_metadata", None)
                if usage:
                    self.input_tokens += usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("output_tokens", 0)
                metadata = {
                    **(generation.generation_info or {}),
                    **generation.message.response_metadata,
                }
                if any(
                    metadata.get(key) == value
                    for key, value in OUTPUT_LIMIT_STOP_REASONS
                ):
                    self.truncated = True


class UsageTrackingEmbeddings(Embeddings):
    """Wraps an embeddings model and records estimated usage for each call."""

    def __init__(
        self, embeddings: Embeddings, cost_tracker: CostTracker, model: str
    ) -> None:
        """Initialize the wrapper.

        Args:
            embeddings: Embeddings model to delegate to
            cost_tracker: Tracker that receives the usage
            model: Embedding model name, used for pricing
        """
        self._embeddings = embeddings
        self._cost_tracker = cost_tracker
        self._model = model

    def _record(self, texts: list[str]) -> None:
        self._cost_tracker.record_embedding_usage(
            model=self._model,
            tokens=sum(estimate_tokens(text) for text in texts),
            estimated=True,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents and record their estimated usage."""
        vectors = self._embeddings.embed_documents(texts)
        self._record(texts)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Embed a query and record its estimated usage."""
        vector = self._embeddings.embed_query(text)
        self._record([text])
        return vector
