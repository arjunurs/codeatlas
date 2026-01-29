"""Unit tests for cost tracking."""

from datetime import datetime

from docgen.utils.cost_tracker import PRICING, CostTracker, UsageStats


def test_usage_stats_estimate_cost():
    """Test cost estimation for usage stats."""
    stats = UsageStats(
        model="claude-sonnet-4-20250514",
        input_tokens=10_000,
        output_tokens=5_000,
    )

    # Calculate expected cost
    expected_input = (10_000 / 1_000_000) * 3.00  # $3.00 per 1M input tokens
    expected_output = (5_000 / 1_000_000) * 15.00  # $15.00 per 1M output tokens
    expected_total = expected_input + expected_output

    assert abs(stats.estimate_cost() - expected_total) < 0.0001


def test_usage_stats_to_dict():
    """Test UsageStats to_dict serialization."""
    stats = UsageStats(
        model="claude-haiku-4",
        input_tokens=1000,
        output_tokens=500,
        requests=5,
        cached_requests=2,
    )

    data = stats.to_dict()
    assert data['model'] == "claude-haiku-4"
    assert data['input_tokens'] == 1000
    assert data['output_tokens'] == 500
    assert data['requests'] == 5
    assert data['cached_requests'] == 2
    assert 'estimated_cost' in data
    assert 'timestamp' in data


def test_cost_tracker_record_llm_usage():
    """Test recording LLM API usage."""
    tracker = CostTracker()

    # Record usage
    tracker.record_llm_usage("claude-sonnet-4-20250514", 1000, 500)
    tracker.record_llm_usage("claude-sonnet-4-20250514", 2000, 1000)

    # Check stats
    assert "claude-sonnet-4-20250514" in tracker.usage_by_model
    stats = tracker.usage_by_model["claude-sonnet-4-20250514"]
    assert stats.input_tokens == 3000
    assert stats.output_tokens == 1500
    assert stats.requests == 2
    assert stats.cached_requests == 0


def test_cost_tracker_record_cached_usage():
    """Test recording cached requests."""
    tracker = CostTracker()

    # Record cached and uncached requests
    tracker.record_llm_usage("claude-sonnet-4-20250514", 1000, 500, cached=False)
    tracker.record_llm_usage("claude-sonnet-4-20250514", 0, 0, cached=True)
    tracker.record_llm_usage("claude-sonnet-4-20250514", 0, 0, cached=True)

    # Check stats
    stats = tracker.usage_by_model["claude-sonnet-4-20250514"]
    assert stats.requests == 3
    assert stats.cached_requests == 2


def test_cost_tracker_record_embedding_usage():
    """Test recording embedding API usage."""
    tracker = CostTracker()

    # Record embedding usage
    tracker.record_embedding_usage("text-embedding-3-small", 10000)
    tracker.record_embedding_usage("text-embedding-3-small", 5000, cached=True)

    # Check stats
    assert "text-embedding-3-small" in tracker.usage_by_model
    stats = tracker.usage_by_model["text-embedding-3-small"]
    assert stats.input_tokens == 15000
    assert stats.requests == 2
    assert stats.cached_requests == 1


def test_cost_tracker_get_total_cost():
    """Test calculating total cost across models."""
    tracker = CostTracker()

    # Record usage for multiple models
    tracker.record_llm_usage("claude-sonnet-4-20250514", 10_000, 5_000)
    tracker.record_embedding_usage("text-embedding-3-small", 100_000)

    # Calculate expected costs
    sonnet_cost = (10_000 / 1_000_000) * 3.00 + (5_000 / 1_000_000) * 15.00
    embedding_cost = (100_000 / 1_000_000) * 0.02
    expected_total = sonnet_cost + embedding_cost

    assert abs(tracker.get_total_cost() - expected_total) < 0.0001


def test_cost_tracker_get_total_requests():
    """Test counting total requests."""
    tracker = CostTracker()

    tracker.record_llm_usage("claude-sonnet-4-20250514", 1000, 500)
    tracker.record_llm_usage("claude-sonnet-4-20250514", 1000, 500)
    tracker.record_embedding_usage("text-embedding-3-small", 10000)

    assert tracker.get_total_requests() == 3


def test_cost_tracker_get_cache_hit_rate():
    """Test calculating cache hit rate."""
    tracker = CostTracker()

    # Record 10 requests, 3 cached
    for i in range(7):
        tracker.record_llm_usage("claude-sonnet-4-20250514", 1000, 500, cached=False)
    for i in range(3):
        tracker.record_llm_usage("claude-sonnet-4-20250514", 0, 0, cached=True)

    assert tracker.get_cache_hit_rate() == 30.0  # 3/10 = 30%


def test_cost_tracker_get_cache_hit_rate_zero_requests():
    """Test cache hit rate with no requests."""
    tracker = CostTracker()
    assert tracker.get_cache_hit_rate() == 0.0


def test_cost_tracker_finish():
    """Test finishing tracking."""
    tracker = CostTracker()
    assert tracker.end_time is None

    tracker.finish()
    assert tracker.end_time is not None
    assert isinstance(tracker.end_time, datetime)


def test_cost_tracker_get_summary():
    """Test getting usage summary."""
    tracker = CostTracker()

    # Record some usage
    tracker.record_llm_usage("claude-sonnet-4-20250514", 1000, 500)
    tracker.record_embedding_usage("text-embedding-3-small", 10000)
    tracker.finish()

    # Get summary
    summary = tracker.get_summary()
    assert 'start_time' in summary
    assert 'end_time' in summary
    assert 'duration_seconds' in summary
    assert 'total_cost_usd' in summary
    assert 'total_requests' in summary
    assert 'cache_hit_rate_percent' in summary
    assert 'usage_by_model' in summary

    # Check models are included
    assert "claude-sonnet-4-20250514" in summary['usage_by_model']
    assert "text-embedding-3-small" in summary['usage_by_model']


def test_cost_tracker_print_summary(capsys):
    """Test printing summary to console."""
    tracker = CostTracker()

    # Record usage
    tracker.record_llm_usage("claude-sonnet-4-20250514", 1000, 500)
    tracker.finish()

    # Print summary
    tracker.print_summary()

    # Check output
    captured = capsys.readouterr()
    assert "API Usage & Cost Summary" in captured.out
    assert "claude-sonnet-4-20250514" in captured.out
    assert "Estimated Cost" in captured.out


def test_pricing_includes_common_models():
    """Test that pricing includes commonly used models."""
    # Anthropic models
    assert "claude-sonnet-4-20250514" in PRICING
    assert "claude-haiku-4" in PRICING
    assert "claude-opus-4" in PRICING

    # OpenAI embeddings
    assert "text-embedding-3-small" in PRICING
    assert "text-embedding-3-large" in PRICING


def test_usage_stats_unknown_model():
    """Test cost estimation for unknown model."""
    stats = UsageStats(
        model="unknown-model",
        input_tokens=1000,
        output_tokens=500,
    )

    # Should return 0 for unknown models
    assert stats.estimate_cost() == 0.0
