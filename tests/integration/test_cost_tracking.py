"""Integration test: the cost summary reflects the calls a run makes."""

from unittest.mock import MagicMock

from docgen.config import CacheConfig, GenerationOptions
from docgen.core.generator import CodeDocumentationGenerator


def test_run_records_llm_and_embedding_usage(
    temp_source_dir, tmp_path, fake_chat_model_with_usage, fake_embeddings
):
    """A real run records reported LLM tokens and estimated embedding tokens."""
    llm_provider = MagicMock()
    llm_provider.model_name = "claude-sonnet-5"
    llm_provider.get_langchain_llm.return_value = fake_chat_model_with_usage
    embedding_provider = MagicMock()
    embedding_provider.model_name = "text-embedding-3-small"
    embedding_provider.get_langchain_embeddings.return_value = fake_embeddings

    generator = CodeDocumentationGenerator(
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        generation_options=GenerationOptions(
            skip_diagrams=True, selected_sections=["overview"]
        ),
        cache_config=CacheConfig(enabled=False),
    )
    generator.generate_documentation(str(temp_source_dir), str(tmp_path / "docs"))

    assert generator.cost_tracker is not None
    usage = generator.cost_tracker.usage_by_model
    llm = usage["claude-sonnet-5"]
    assert (llm.input_tokens, llm.output_tokens, llm.requests) == (120, 30, 1)
    embedding = usage["text-embedding-3-small"]
    assert embedding.estimated
    assert embedding.input_tokens > 0
    # One call to embed the code chunks, one to embed the retrieval query
    assert embedding.requests == 2
