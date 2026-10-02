"""Unit tests for the LangChain usage tracking adapters."""

from langchain_core.output_parsers import StrOutputParser

from docgen.utils.cost_tracker import CostTracker
from docgen.utils.usage_tracking import TokenUsageCallback, UsageTrackingEmbeddings


def test_callback_reads_usage_through_chain_ending_in_str_parser(
    fake_chat_model_with_usage,
):
    """Usage is captured even though the chain returns a plain string."""
    chain = fake_chat_model_with_usage | StrOutputParser()
    usage = TokenUsageCallback()

    result = chain.invoke("prompt", config={"callbacks": [usage]})

    assert result == "generated text"
    assert (usage.input_tokens, usage.output_tokens) == (120, 30)


def test_embeddings_wrapper_records_estimated_tokens(fake_embeddings):
    """Each embed call records about one token per four characters, as an estimate."""
    tracker = CostTracker()
    embeddings = UsageTrackingEmbeddings(
        fake_embeddings, tracker, "text-embedding-3-small"
    )

    vectors = embeddings.embed_documents(["a" * 40, "b" * 80])
    embeddings.embed_query("c" * 8)

    assert len(vectors) == 2
    stats = tracker.usage_by_model["text-embedding-3-small"]
    assert stats.input_tokens == 10 + 20 + 2
    assert stats.requests == 2
    assert stats.estimated
