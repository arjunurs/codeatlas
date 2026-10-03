"""Section orchestrator for documentation generation.

This module handles generating documentation sections (sequentially or in
parallel), including caching, filtering, and cross-reference preprocessing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.runnables import Runnable

from ..cache.content_cache import SectionContentCache
from ..config import GeneratorConfig
from ..models.file_analysis import FileAnalysis
from ..prompts.rag_prompt import EXCERPT_LABEL, RAG_PROMPT_TEMPLATE
from ..prompts.sections import get_section_prompt, select_sections
from ..utils.cost_tracker import CostTracker
from ..utils.error_classification import describe_error
from ..utils.excerpt_remarks import find_excerpt_remarks
from ..utils.usage_tracking import TokenUsageCallback
from .structural_context import RULES_VERSION

logger = logging.getLogger(__name__)

TRUNCATION_NOTE = "\n\n*This section was cut off at the model's output limit.*"


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
        force_refresh: bool = False,
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
        self.force_refresh = force_refresh
        self.current_analyses = current_analyses
        self.selected_sections = selected_sections
        self._section_preprocessors = section_preprocessors or {}
        self._convert_markdown_to_html = convert_markdown_to_html or (lambda x: x)

    def generate_documentation_sections(
        self, rag_chain: Runnable
    ) -> tuple[list[dict], list[tuple[str, str]]]:
        """Generate all documentation sections using the RAG chain.

        Args:
            rag_chain: LCEL RAG chain for content generation

        Returns:
            Tuple of (sections, each a dict with title and content, and a list
            of (section_name, error) pairs); the caller reports the errors
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

        return sections, errors

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
            # Per-section boundary: see _failed_section
            except Exception as e:  # noqa: BLE001
                sections.append(self._failed_section(section_name, e, errors))

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
                # Per-section boundary: see _failed_section
                except Exception as e:  # noqa: BLE001
                    sections_dict[section_name] = self._failed_section(
                        section_name, e, errors
                    )

        sections = [sections_dict[name] for name in section_names]
        return sections, errors

    def _failed_section(
        self, section_name: str, error: Exception, errors: list[tuple[str, str]]
    ) -> dict:
        """Record a section that failed and return the page that reports it.

        Sections are generated independently, so one that fails for any
        reason (a rate limit, a timeout, a bug) is reported and the others
        are still generated. The caller reports the failures together; the
        traceback is logged here, for --verbose.
        """
        logger.debug(f"Section '{section_name}' failed", exc_info=error)
        message = describe_error(error)
        errors.append((section_name, message))
        return {
            "title": section_name,
            "content": f"*Error generating this section: {message}*",
        }

    def _generate_section_with_cache(
        self,
        rag_chain: Runnable,
        section_name: str,
    ) -> str:
        """Generate a section, reusing cached content while it is still valid.

        The cache key covers the section's code dependencies, the model, the
        exact prompt, and the settings that shape the text. With
        force_refresh, cached content is ignored but the fresh result is still
        cached.
        """
        if not (self.section_cache and self.current_analyses):
            return self._generate_section(rag_chain, section_name)

        prompt = self._build_prompt(section_name)
        settings = self._generation_settings()
        if not self.force_refresh:
            cached_content = self.section_cache.get_cached_section(
                section_name,
                self.current_analyses,
                model=self.model_name,
                prompt=prompt,
                settings=settings,
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

        content, truncated = self._run_section(rag_chain, section_name, prompt)
        # A cut-off section is not cached, so the next run tries again
        if not truncated:
            self.section_cache.cache_section(
                section_name,
                content,
                self.current_analyses,
                model=self.model_name,
                prompt=prompt,
                settings=settings,
            )
        return content

    def _generation_settings(self) -> str:
        """The settings besides the model and prompt that shape a section's text.

        That is the template every section prompt is wrapped in, how code
        excerpts are labeled in it, what the retriever and the code structure
        put in it, and how long the answer may be.
        """
        config = self.config
        return "\n".join(
            [
                RAG_PROMPT_TEMPLATE,
                EXCERPT_LABEL,
                f"retriever k={config.RETRIEVER_K} "
                f"search={config.RETRIEVER_SEARCH_TYPE} "
                f"threshold={config.RETRIEVER_SCORE_THRESHOLD} "
                f"fetch_k={config.RETRIEVER_FETCH_K} "
                f"lambda={config.RETRIEVER_LAMBDA_MULT}",
                f"max_output_tokens={config.DEFAULT_MAX_OUTPUT_TOKENS}",
                f"structural share={config.STRUCTURAL_CONTEXT_SHARE} "
                f"rules={RULES_VERSION}",
            ]
        )

    def _build_prompt(self, section_name: str) -> str:
        """Build the prompt for a section, applying registered preprocessors."""
        prompt = get_section_prompt(section_name)
        for key, preprocessor in self._section_preprocessors.items():
            if key in section_name.lower():
                prompt = preprocessor(prompt, self.current_analyses)
        return prompt

    def _generate_section(
        self, rag_chain: Runnable, section_name: str, prompt: str | None = None
    ) -> str:
        """Generate content for a documentation section.

        Args:
            rag_chain: LCEL RAG chain for content generation
            section_name: Name of the section to generate
            prompt: Prebuilt prompt for the section (built here if omitted)

        Returns:
            Generated section content as a string
        """
        return self._run_section(rag_chain, section_name, prompt)[0]

    def _run_section(
        self, rag_chain: Runnable, section_name: str, prompt: str | None = None
    ) -> tuple[str, bool]:
        """Generate a section and report whether it hit the output limit.

        A section that stopped at the output token limit gets a visible note
        and a warning, since its text ends mid-sentence.

        Returns:
            Tuple of (content, whether the content was cut off)
        """
        if prompt is None:
            prompt = self._build_prompt(section_name)

        usage = TokenUsageCallback()
        # The chain chooses the section's code by its name (see create_rag_chain)
        content = rag_chain.invoke(
            prompt,
            config={"callbacks": [usage], "configurable": {"section": section_name}},
        )
        if self.cost_tracker:
            self.cost_tracker.record_llm_usage(
                model=self.model_name,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
        if usage.truncated:
            logger.warning(
                f"Section '{section_name}' was cut off at the model's output "
                "limit; it will be regenerated on the next run"
            )
            content += TRUNCATION_NOTE
        remarks = find_excerpt_remarks(content)
        if remarks:
            quoted = ", ".join(f'"{remark}"' for remark in remarks)
            logger.warning(
                f"Section '{section_name}' refers to the code excerpts it was "
                f"written from, which readers never see: {quoted}"
            )
        return content, usage.truncated
