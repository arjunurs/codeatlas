"""Cost tracking for LLM API calls.

This module tracks API usage and estimated costs for documentation generation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# Pricing per 1M tokens (as of August 2026)
PRICING = {
    # Anthropic Claude models
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-4": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    # OpenAI embedding models
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
    "text-embedding-ada-002": {"input": 0.10, "output": 0.0},
}


@dataclass
class UsageStats:
    """Statistics for API usage.

    Attributes:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        requests: Number of API requests
        cached_requests: Number of requests served from cache
        timestamp: When these stats were recorded
    """

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    cached_requests: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def estimate_cost(self) -> float:
        """Estimate cost in USD based on pricing.

        Returns:
            Estimated cost in USD
        """
        if self.model not in PRICING:
            logger.warning(f"Unknown model for pricing: {self.model}")
            return 0.0

        pricing = PRICING[self.model]
        input_cost = (self.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "requests": self.requests,
            "cached_requests": self.cached_requests,
            "estimated_cost": self.estimate_cost(),
            "timestamp": self.timestamp.isoformat(),
        }


class CostTracker:
    """Tracks API usage and costs across documentation generation.

    This class accumulates usage statistics and provides cost estimates.
    """

    def __init__(self):
        """Initialize cost tracker."""
        self.usage_by_model: dict[str, UsageStats] = {}
        self.start_time = datetime.now()
        self.end_time: datetime | None = None

    def record_llm_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached: bool = False,
    ) -> None:
        """Record LLM API usage.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cached: Whether this was served from cache
        """
        if model not in self.usage_by_model:
            self.usage_by_model[model] = UsageStats(model=model)

        stats = self.usage_by_model[model]
        stats.input_tokens += input_tokens
        stats.output_tokens += output_tokens
        stats.requests += 1
        if cached:
            stats.cached_requests += 1

    def record_embedding_usage(
        self,
        model: str,
        tokens: int,
        cached: bool = False,
    ) -> None:
        """Record embedding API usage.

        Args:
            model: Model name
            tokens: Number of tokens embedded
            cached: Whether this was served from cache
        """
        if model not in self.usage_by_model:
            self.usage_by_model[model] = UsageStats(model=model)

        stats = self.usage_by_model[model]
        stats.input_tokens += tokens
        stats.requests += 1
        if cached:
            stats.cached_requests += 1

    def get_total_cost(self) -> float:
        """Get total estimated cost across all models.

        Returns:
            Total estimated cost in USD
        """
        return sum(stats.estimate_cost() for stats in self.usage_by_model.values())

    def get_total_requests(self) -> int:
        """Get total number of API requests.

        Returns:
            Total number of requests
        """
        return sum(stats.requests for stats in self.usage_by_model.values())

    def get_cache_hit_rate(self) -> float:
        """Get cache hit rate.

        Returns:
            Cache hit rate as a percentage (0-100)
        """
        total_requests = self.get_total_requests()
        if total_requests == 0:
            return 0.0

        cached_requests = sum(
            stats.cached_requests for stats in self.usage_by_model.values()
        )
        return (cached_requests / total_requests) * 100

    def finish(self) -> None:
        """Mark tracking as finished."""
        self.end_time = datetime.now()

    def get_summary(self) -> dict:
        """Get summary of all usage and costs.

        Returns:
            Dictionary with usage summary
        """
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "total_cost_usd": self.get_total_cost(),
            "total_requests": self.get_total_requests(),
            "cache_hit_rate_percent": self.get_cache_hit_rate(),
            "usage_by_model": {
                model: stats.to_dict() for model, stats in self.usage_by_model.items()
            },
        }

    def print_summary(self) -> None:
        """Print a formatted summary to console."""
        print(format_cost_summary(self.get_summary()))


def format_cost_summary(summary: dict) -> str:
    """Format a cost summary dict as a human-readable string.

    Args:
        summary: Summary dict as returned by CostTracker.get_summary()

    Returns:
        Formatted summary string
    """
    lines = [
        "",
        "=" * 60,
        "  API Usage & Cost Summary",
        "=" * 60,
    ]

    if summary["duration_seconds"]:
        lines.append(f"Duration: {summary['duration_seconds']:.1f}s")

    lines.append(f"Total Requests: {summary['total_requests']}")
    lines.append(f"Cache Hit Rate: {summary['cache_hit_rate_percent']:.1f}%")
    lines.append(f"Estimated Cost: ${summary['total_cost_usd']:.4f}")

    lines.append("\nBreakdown by Model:")
    lines.append("-" * 60)
    for model, stats in summary["usage_by_model"].items():
        lines.append(f"  {model}:")
        lines.append(
            f"    Requests: {stats['requests']} (cached: {stats['cached_requests']})"
        )
        if stats["input_tokens"] > 0:
            lines.append(f"    Input tokens: {stats['input_tokens']:,}")
        if stats["output_tokens"] > 0:
            lines.append(f"    Output tokens: {stats['output_tokens']:,}")
        lines.append(f"    Cost: ${stats['estimated_cost']:.4f}")

    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines)
