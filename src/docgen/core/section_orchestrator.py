"""Section orchestrator for documentation generation.

This module handles generating documentation sections (sequentially or in
parallel), including caching, filtering, and cross-reference preprocessing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from langchain_core.runnables import Runnable

from ..cache.content_cache import SectionContentCache
from ..config import GeneratorConfig
from ..exceptions.errors import LLMError
from ..models.file_analysis import FileAnalysis
from ..prompts.sections import get_section_prompt, select_sections
from ..utils.cost_tracker import CostTracker
from ..utils.usage_tracking import TokenUsageCallback

logger = logging.getLogger(__name__)


class SectionOrchestrator:
    """Orchestrates documentation section generation.

    Handles section filtering, caching, sequential/parallel generation,
    and cross-reference preprocessing.
    """

    def __init__(
        self,
        config: GeneratorConfig,
        *,
        model_name: str,
        parallel: bool = True,
        cost_tracker: CostTracker | None = None,
        section_cache: SectionContentCache | None = None,
        current_analyses: list[FileAnalysis] | None = None,
        selected_sections: list[str] | None = None,
        section_preprocessors: dict[
            str, Callable[[str, list[FileAnalysis] | None], str]
        ]
        | None = None,
        convert_markdown_to_html: Callable[[str], str] | None = None,
    ) -> None:
        self.config = config
        self.model_name = model_name
        self.parallel = parallel
        self.cost_tracker = cost_tracker
        self.section_cache = section_cache
        self.current_analyses = current_analyses
        self.selected_sections = selected_sections
        self._section_preprocessors = section_preprocessors or {}
        self._convert_markdown_to_html = convert_markdown_to_html or (lambda x: x)

    def generate_documentation_sections(
        self, rag_chain: Runnable
    ) -> tuple[dict[str, Any], list[tuple[str, str]]]:
        """Generate all documentation sections using the RAG chain.

        Args:
            rag_chain: LCEL RAG chain for content generation

        Returns:
            Tuple of (documentation dict, list of (section_name, error) pairs)
        """
        logger.debug("Generating documentation content...")

        sections_to_generate = select_sections(self.selected_sections)
        if self.selected_sections:
            logger.info(f"Generating selected sections: {sections_to_generate}")

        if self.parallel and len(sections_to_generate) > 1:
            sections, errors = self._generate_sections_parallel(
                rag_chain, sections_to_generate
            )
        else:
            sections, errors = self._generate_sections_sequential(
                rag_chain, sections_to_generate
            )

        if errors:
            logger.warning(
                f"Some sections failed to generate ({len(errors)} errors):\n"
                + "\n".join(f"  - {name}: {error}" for name, error in errors)
            )

        documentation = {
            "title": "Code Documentation",
            "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sections": sections,
        }

        return documentation, errors

    def _generate_sections_sequential(
        self,
        rag_chain: Runnable,
        section_names: list[str],
    ) -> tuple[list[dict], list[tuple[str, str]]]:
        """Generate sections sequentially."""
        sections = []
        errors: list[tuple[str, str]] = []

        for section_name in section_names:
            logger.info(f"Generating section: {section_name}")
            try:
                content = self._generate_section_with_cache(rag_chain, section_name)
                html_content = self._convert_markdown_to_html(content)
                sections.append({"title": section_name, "content": html_content})
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"Failed to generate section '{section_name}': {error_msg}"
                )
                errors.append((section_name, error_msg))
                sections.append(
                    {
                        "title": section_name,
                        "content": f"*Error generating this section: {error_msg}*",
                    }
                )

        return sections, errors

    def _generate_sections_parallel(
        self,
        rag_chain: Runnable,
        section_names: list[str],
    ) -> tuple[list[dict], list[tuple[str, str]]]:
        """Generate sections in parallel."""
        logger.info(f"Generating {len(section_names)} sections in parallel")

        sections_dict = {}
        errors: list[tuple[str, str]] = []

        max_workers = min(len(section_names), self.config.MAX_PARALLEL_WORKERS)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_section = {
                executor.submit(
                    self._generate_section_with_cache, rag_chain, section_name
                ): section_name
                for section_name in section_names
            }

            for future in as_completed(future_to_section):
                section_name = future_to_section[future]
                try:
                    content = future.result()
                    html_content = self._convert_markdown_to_html(content)
                    sections_dict[section_name] = {
                        "title": section_name,
                        "content": html_content,
                    }
                    logger.info(f"Completed section: {section_name}")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(
                        f"Failed to generate section '{section_name}': {error_msg}"
                    )
                    errors.append((section_name, error_msg))
                    sections_dict[section_name] = {
                        "title": section_name,
                        "content": f"*Error generating this section: {error_msg}*",
                    }

        sections = [sections_dict[name] for name in section_names]
        return sections, errors

    def _generate_section_with_cache(
        self,
        rag_chain: Runnable,
        section_name: str,
    ) -> str:
        """Generate a section with caching support."""
        if self.section_cache and self.current_analyses:
            cached_content = self.section_cache.get_cached_section(
                section_name, self.current_analyses
            )
            if cached_content is not None:
                if self.cost_tracker:
                    self.cost_tracker.record_llm_usage(
                        model=self.model_name,
                        input_tokens=0,
                        output_tokens=0,
                        cached=True,
                    )
                return cached_content

        content = self._generate_section(rag_chain, section_name)

        if self.section_cache and self.current_analyses:
            self.section_cache.cache_section(
                section_name, content, self.current_analyses
            )

        return content

    def _generate_section(self, rag_chain: Runnable, section_name: str) -> str:
        """Generate content for a documentation section.

        Args:
            rag_chain: LCEL RAG chain for content generation
            section_name: Name of the section to generate

        Returns:
            Generated section content as a string

        Raises:
            LLMError: If section generation fails
        """
        try:
            prompt = get_section_prompt(section_name)

            # Apply any registered preprocessors for this section
            for key, preprocessor in self._section_preprocessors.items():
                if key in section_name.lower():
                    prompt = preprocessor(prompt, self.current_analyses)

            usage = TokenUsageCallback()
            content = rag_chain.invoke(prompt, config={"callbacks": [usage]})
            if self.cost_tracker:
                self.cost_tracker.record_llm_usage(
                    model=self.model_name,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                )
            return content
        except Exception as e:
            raise LLMError(
                f"Failed to generate section '{section_name}': {str(e)}"
            ) from e
