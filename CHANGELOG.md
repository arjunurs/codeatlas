# Changelog

All notable changes to codeatlas are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-03

The first release.

### Added

- The `codeatlas` command (`docgen` is kept as an alias), which documents a Python codebase as
  a static HTML site.
- Analysis of each file's AST: classes, functions, imports, and calls, including calls on
  objects whose class is known from an annotation or an assignment, and methods inherited from
  the project's own classes.
- Five Mermaid diagrams drawn from the analysis, with no LLM involved: architecture, class,
  dependencies, call graph, and sequence (from the function that reaches the most of the
  project). Each is checked against 10 validation rules before it is written, and each is the
  same from run to run.
- Five sections written by Claude (Overview, Dependencies, Key Classes and Functions, Data Flow,
  Integration Points), and three more selected with `--sections` (Migration Guidance, Code
  Quality Insights, Cross-Reference Documentation).
- Code for each section chosen from the project's structure first: the entry point's call path,
  outlines of the exported classes, the classes an application plugs in, code that reads
  environment variables, and a map of third-party imports. Retrieval over a Chroma index of
  OpenAI embeddings, with MMR, fills the rest of the context, and each excerpt is labeled with
  its module.
- A Dependencies section that also reads `pyproject.toml`, `setup.cfg`, and `requirements*.txt`.
- `--diagrams-only` and `--dry-run`, which need no API keys and make no API calls.
- Quality modes `fast`, `balanced` (the default), and `best`, for Claude Haiku 4.5, Sonnet 5.5,
  and Opus 5.5, and `--anthropic-model` to name any model.
- Two cache levels: embeddings per file, updated incrementally, and sections, reused while their
  code, model, prompt, and retrieval settings are unchanged.
- A token usage and cost summary after each run, and warnings when a section reaches the output
  limit or refers to the code excerpts it was written from.
- Model output sanitized with nh3 before it reaches HTML, and Mermaid in strict mode.
- A file that does not parse, a failed diagram, or a failed section is reported, and the rest of
  the run goes on.
- Support for Python 3.10 to 3.13, tested in CI together with the oldest dependency versions
  `pyproject.toml` allows.

[Unreleased]: https://github.com/arjunurs/codeatlas/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/arjunurs/codeatlas/releases/tag/v0.1.0
