# Agentic Architecture Design

> Design document for evolving the documentation generator from a fixed RAG pipeline
> to an agent-enhanced architecture.

## Current Architecture

### Pipeline Overview

The system follows a **fixed linear pipeline**:

```
Source Directory
    → CodeAnalyzer (AST parsing)
    → FileAnalysis[]
    → CodeDocumentationGenerator (orchestrator)
        ├── DiagramGenerator        → Mermaid diagrams (deterministic, no LLM)
        ├── RAGPipelineFactory      → single LCEL chain (retriever | prompt | llm | parser)
        │       └── SectionOrchestrator → invokes chain N times, once per section
        └── DocumentationRenderer   → Jinja2 HTML output
```

### Key Components

| Component | Role | LLM Involved? |
|---|---|---|
| `CodeAnalyzer` | AST parsing, entity extraction | No |
| `DiagramGenerator` | Mermaid diagram generation from AST data | No |
| `RAGPipelineFactory` | Builds ChromaDB vector store + LCEL chain | Yes (embeddings + LLM) |
| `SectionOrchestrator` | Runs sections sequentially or in parallel via ThreadPoolExecutor | Yes (invokes chain) |
| `DocumentationRenderer` | Jinja2 HTML rendering | No |
| `CrossReferenceAnalyzer` | Import/usage graph analysis | No |

### How Section Generation Works Today

1. All code is analyzed and embedded into ChromaDB once
2. A single LCEL RAG chain is constructed:
   ```
   {"context": retriever | format_docs, "question": passthrough} | prompt | llm | StrOutputParser
   ```
3. For each section, the chain is invoked with the section's static prompt as the "question"
4. The retriever returns the top-k documents by similarity to the section prompt
5. The LLM generates content from those documents + the prompt
6. No feedback loop — whatever comes back is the final output

### Limitations

| Limitation | Impact |
|---|---|
| **One-size-fits-all retrieval** | The same `k=10` similarity search serves "Overview" (needs breadth) and "Key Classes" (needs depth on specific entities). Results are often suboptimal for specialized sections. |
| **No inter-section awareness** | Overview might describe the architecture differently than Data Flow. Sections can contradict each other or repeat information because they share no context. |
| **Static section structure** | Always generates the same 5 core sections in the same format. A CLI tool, a library, and a web service all get identical documentation structure. |
| **No self-evaluation** | If the retriever returns poor context (e.g., irrelevant files), the section quality degrades silently. There is no mechanism to detect or recover from bad retrieval. |
| **Cross-reference is bolted on** | `_cross_reference_preprocessor` manually injects pre-analyzed data into the prompt string. This pattern doesn't scale to other sections that could benefit from structured analysis. |
| **No iterative depth** | The LLM gets one shot. If it mentions a class but lacks detail, it cannot go back and retrieve more about that specific class. |

---

## Proposed Architecture: Agent-Enhanced Pipeline

### Design Principles

1. **Keep what works** — AST analysis, diagram generation, caching, and HTML rendering stay as-is
2. **Add intelligence where it matters** — retrieval, section planning, and quality assurance
3. **Predictable cost** — bound agent loops to avoid runaway API costs
4. **Incremental adoption** — each phase is independently valuable and deployable

### Architecture Overview

```
Source Directory
    → CodeAnalyzer (unchanged)
    → FileAnalysis[]
    → CodeDocumentationGenerator (orchestrator)
        ├── DiagramGenerator (unchanged)
        ├── RAGPipelineFactory (unchanged — still builds vector store)
        │
        ├── NEW: PlanningAgent
        │       Input:  codebase summary, file list, entity list
        │       Output: DocumentationPlan (sections, emphasis, outline)
        │
        ├── ENHANCED: SectionAgent (per section)
        │       Input:  plan context, section assignment, tool access
        │       Tools:  vector_search, cross_ref_lookup, code_read, ast_query
        │       Output: section content (with self-evaluation)
        │
        ├── NEW: CoherenceAgent (optional)
        │       Input:  all generated sections
        │       Output: consistency report + suggested fixes
        │
        └── DocumentationRenderer (unchanged)
```

### Phase 1: Adaptive Retrieval

**Goal:** Let each section retrieve context tailored to its specific needs.

**Current state:** Every section uses the section title/prompt as the retrieval query, getting back the same `k` documents via cosine similarity.

**Proposed change:** Introduce a `RetrievalStrategy` per section that generates targeted queries.

#### Design

```python
@dataclass
class RetrievalStrategy:
    """Defines how a section should retrieve context from the vector store."""
    queries: list[str]           # Multiple retrieval queries
    k_per_query: int = 5         # Documents per query
    search_type: str = "similarity"  # or "mmr"
    deduplicate: bool = True     # Remove duplicate documents across queries


@dataclass
class SectionSpec:
    """Enhanced section definition with retrieval strategy."""
    name: str
    prompt: PromptTemplate
    retrieval_strategy: RetrievalStrategy
    tools: list[str] = field(default_factory=list)  # Tools this section can use
```

#### Retrieval Strategy Examples

```python
SECTION_RETRIEVAL_STRATEGIES = {
    "Overview": RetrievalStrategy(
        queries=[
            "main entry point and application purpose",
            "core classes and their responsibilities",
            "architectural patterns and design decisions",
        ],
        k_per_query=5,
        search_type="mmr",  # Diversity matters for overview
    ),
    "Key Classes and Functions": RetrievalStrategy(
        queries=[
            "class definitions with methods and inheritance",
            "public API functions and their signatures",
            "protocol and abstract base class definitions",
        ],
        k_per_query=7,
        search_type="similarity",  # Precision matters here
    ),
    "Data Flow": RetrievalStrategy(
        queries=[
            "data processing pipeline and transformations",
            "input parsing and validation",
            "output generation and serialization",
            "error handling and exception propagation",
        ],
        k_per_query=5,
        search_type="mmr",
    ),
    "Integration Points": RetrievalStrategy(
        queries=[
            "external API calls and HTTP clients",
            "authentication and API key handling",
            "configuration loading and environment variables",
        ],
        k_per_query=5,
        search_type="similarity",
    ),
    "Dependencies": RetrievalStrategy(
        queries=[
            "import statements and package dependencies",
            "requirements and version constraints",
            "third-party library usage patterns",
        ],
        k_per_query=5,
        search_type="similarity",
    ),
}
```

#### Implementation

New file: `src/docgen/core/adaptive_retriever.py`

```python
class AdaptiveRetriever:
    """Retrieves documents using section-specific strategies."""

    def __init__(self, vector_store: Chroma, default_k: int = 10):
        self.vector_store = vector_store
        self.default_k = default_k

    def retrieve(self, strategy: RetrievalStrategy) -> list[Document]:
        """Execute multiple targeted queries and merge results."""
        all_docs = []
        seen_contents = set()

        for query in strategy.queries:
            retriever = self.vector_store.as_retriever(
                search_type=strategy.search_type,
                search_kwargs={"k": strategy.k_per_query},
            )
            docs = retriever.invoke(query)

            for doc in docs:
                if strategy.deduplicate:
                    content_hash = hash(doc.page_content)
                    if content_hash in seen_contents:
                        continue
                    seen_contents.add(content_hash)
                all_docs.append(doc)

        return all_docs

    def retrieve_for_section(self, section_name: str) -> list[Document]:
        """Retrieve using the predefined strategy for a section."""
        strategy = SECTION_RETRIEVAL_STRATEGIES.get(section_name)
        if strategy is None:
            # Fallback: use section name as query with default k
            strategy = RetrievalStrategy(queries=[section_name], k_per_query=self.default_k)
        return self.retrieve(strategy)
```

#### Changes to Existing Code

- `RAGPipelineFactory.create_rag_chain` — expose the vector store and retriever separately instead of only returning the composed chain
- `SectionOrchestrator._generate_section` — use `AdaptiveRetriever` instead of invoking the fixed chain
- Section prompts remain unchanged; only retrieval changes

#### Files Modified

| File | Change |
|---|---|
| `src/docgen/core/adaptive_retriever.py` | New — adaptive retrieval logic |
| `src/docgen/core/rag_pipeline.py` | Expose vector store; add method to create retriever per strategy |
| `src/docgen/core/section_orchestrator.py` | Accept and use `AdaptiveRetriever` |
| `src/docgen/prompts/sections.py` | Add `RetrievalStrategy` definitions alongside prompts |
| `tests/unit/core/test_adaptive_retriever.py` | New — unit tests |

---

### Phase 2: Planning Agent

**Goal:** Dynamically decide what sections to generate and how to emphasize them based on the actual codebase.

**Current state:** Hardcoded list of 5 core sections, always generated in the same way regardless of codebase characteristics.

**Proposed change:** Add a planning step that analyzes the codebase summary and produces a `DocumentationPlan`.

#### Design

```python
@dataclass
class SectionPlan:
    """Plan for a single documentation section."""
    name: str
    emphasis: str          # "high", "medium", "low"
    key_topics: list[str]  # Specific topics to cover
    retrieval_hints: list[str]  # Additional retrieval queries based on codebase


@dataclass
class DocumentationPlan:
    """Output of the planning agent."""
    codebase_type: str         # "library", "cli", "service", "framework"
    sections: list[SectionPlan]
    shared_context: str        # Summary for cross-section coherence
    custom_sections: list[SectionPlan]  # Codebase-specific sections (e.g., "CLI Commands")
```

#### Planning Agent Implementation

```python
class PlanningAgent:
    """Analyzes a codebase and produces a documentation plan."""

    PLANNING_PROMPT = """You are a documentation architect. Given the following codebase summary,
    create a documentation plan.

    Codebase Summary:
    - {file_count} Python files
    - Key entities: {entity_summary}
    - Top imports: {import_summary}
    - Has CLI entry point: {has_cli}
    - Has web framework: {has_web}
    - Has test suite: {has_tests}

    Output a JSON documentation plan with:
    1. codebase_type: what kind of project is this?
    2. sections: for each standard section, set emphasis (high/medium/low) and key topics
    3. custom_sections: any additional sections specific to this codebase
    4. shared_context: a 2-3 sentence summary for cross-section coherence
    """

    def __init__(self, llm):
        self.llm = llm

    def create_plan(self, analyses: list[FileAnalysis]) -> DocumentationPlan:
        """Analyze the codebase and create a documentation plan."""
        summary = self._build_codebase_summary(analyses)
        # Single LLM call — structured output
        response = self.llm.invoke(self.PLANNING_PROMPT.format(**summary))
        return self._parse_plan(response)
```

#### How the Plan Feeds into Generation

```
PlanningAgent
    → DocumentationPlan
        → SectionOrchestrator uses plan.sections to:
            1. Skip low-emphasis sections or merge them
            2. Pass key_topics as additional retrieval queries
            3. Include plan.shared_context in every section prompt
            4. Generate plan.custom_sections with dynamically built prompts
```

#### Cost

- **1 additional LLM call** (the planning prompt)
- Structured JSON output, so it's a short response (~500 tokens)

#### Files Modified

| File | Change |
|---|---|
| `src/docgen/core/planning_agent.py` | New — planning agent |
| `src/docgen/models/documentation_plan.py` | New — plan dataclasses |
| `src/docgen/core/section_orchestrator.py` | Accept `DocumentationPlan`, use it for section filtering and context |
| `src/docgen/core/generator.py` | Call planning agent before section generation |
| `tests/unit/core/test_planning_agent.py` | New — unit tests |

---

### Phase 3: Section Agents with Tool Access

**Goal:** Give each section the ability to gather additional context on-demand rather than relying solely on pre-retrieved documents.

**Current state:** Each section gets one RAG chain invocation — the LLM cannot ask for more information.

**Proposed change:** Wrap section generation in a lightweight agent loop with tool access.

#### Tool Definitions

```python
class SectionTools:
    """Tools available to section generation agents."""

    def __init__(self, vector_store, analyses, cross_ref_analyzer):
        self.vector_store = vector_store
        self.analyses = analyses
        self.cross_ref = cross_ref_analyzer

    def vector_search(self, query: str, k: int = 5) -> str:
        """Search the code vector store for relevant context."""
        docs = self.vector_store.similarity_search(query, k=k)
        return "\n\n".join(doc.page_content for doc in docs)

    def get_class_details(self, class_name: str) -> str:
        """Get detailed information about a specific class."""
        for analysis in self.analyses:
            for entity in analysis.entities:
                if entity.name == class_name and entity.type == EntityType.CLASS:
                    return format_entity_document(entity)
        return f"Class '{class_name}' not found."

    def get_cross_references(self, component_name: str) -> str:
        """Get where a component is defined and used."""
        return self.cross_ref.get_component_report(component_name)

    def read_file_content(self, file_path: str) -> str:
        """Read the content of a specific source file."""
        for analysis in self.analyses:
            if analysis.file_path.endswith(file_path):
                return analysis.content[:2000]  # Truncate for context window
        return f"File '{file_path}' not found."

    def list_files(self) -> str:
        """List all analyzed files."""
        return "\n".join(a.file_path for a in self.analyses)
```

#### Agent Loop

```python
class SectionAgent:
    """Agent that generates a documentation section with tool access."""

    MAX_TOOL_CALLS = 3  # Bound the loop to control cost

    def __init__(self, llm, tools: SectionTools, plan_context: str = ""):
        self.llm = llm
        self.tools = tools
        self.plan_context = plan_context

    def generate(
        self,
        section_name: str,
        initial_context: str,
        prompt: str,
    ) -> str:
        """Generate a section with optional tool use.

        Flow:
        1. Generate initial draft from pre-retrieved context
        2. LLM evaluates: "Do I need more information?"
        3. If yes: call a tool (up to MAX_TOOL_CALLS times)
        4. Generate final output with enriched context
        """
        messages = [
            {"role": "system", "content": SECTION_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": self._build_initial_prompt(
                section_name, initial_context, prompt
            )},
        ]

        tool_calls_made = 0
        while tool_calls_made < self.MAX_TOOL_CALLS:
            response = self.llm.invoke(messages, tools=self._tool_schemas())

            if not response.tool_calls:
                # LLM is satisfied — return the content
                return response.content

            # Execute tool calls
            for tool_call in response.tool_calls:
                result = self._execute_tool(tool_call)
                messages.append({"role": "tool", "content": result})
                tool_calls_made += 1

        # Final generation after tool calls exhausted
        messages.append({
            "role": "user",
            "content": "Generate the final section content now with all gathered context.",
        })
        return self.llm.invoke(messages).content
```

#### Cost Controls

- `MAX_TOOL_CALLS = 3` per section — worst case is 4 LLM calls per section (1 initial + 3 tool iterations)
- Tools return truncated content (2000 chars max per file read)
- The agent can choose to skip tool use entirely if initial context is sufficient

#### Files Modified

| File | Change |
|---|---|
| `src/docgen/core/section_agent.py` | New — section agent with tool loop |
| `src/docgen/core/section_tools.py` | New — tool definitions |
| `src/docgen/core/section_orchestrator.py` | Use `SectionAgent` instead of direct chain invocation |
| `src/docgen/prompts/agent_prompts.py` | New — system prompts for agent behavior |
| `tests/unit/core/test_section_agent.py` | New — unit tests |

---

### Phase 4: Coherence Review Agent

**Goal:** Detect and fix contradictions or gaps across generated sections.

**Current state:** Sections are generated independently with no cross-validation.

**Proposed change:** After all sections are generated, run a review pass.

#### Design

```python
class CoherenceAgent:
    """Reviews generated sections for consistency and completeness."""

    REVIEW_PROMPT = """Review these documentation sections for a Python codebase.

    Sections:
    {sections}

    Check for:
    1. Contradictions between sections (e.g., Overview says X but Data Flow says Y)
    2. Key components mentioned but never explained
    3. Redundant content that should be consolidated
    4. Missing connections between sections

    Output a JSON report with:
    - issues: list of {section, issue_type, description, suggestion}
    - overall_quality: "good" | "needs_fixes" | "poor"
    """

    def review(self, sections: list[dict]) -> CoherenceReport:
        """Review sections and return a report."""
        ...

    def apply_fixes(self, sections: list[dict], report: CoherenceReport) -> list[dict]:
        """Apply suggested fixes to sections (one LLM call per fix)."""
        ...
```

#### Cost

- 1 LLM call for the review (all sections as input — uses the large context window)
- 0-N fix calls depending on issues found (typically 0-2)
- Can be disabled via `--skip-review` flag for cost-sensitive runs

#### Files Modified

| File | Change |
|---|---|
| `src/docgen/core/coherence_agent.py` | New — review agent |
| `src/docgen/models/coherence_report.py` | New — report dataclass |
| `src/docgen/core/generator.py` | Call coherence agent after section generation |
| `tests/unit/core/test_coherence_agent.py` | New — unit tests |

---

## Migration Strategy

### Incremental Rollout

Each phase is independently deployable and adds value on its own:

```
Phase 1 (Adaptive Retrieval)
    → Immediate quality improvement, no extra LLM calls
    → Gate: A/B test section quality on 5 sample codebases

Phase 2 (Planning Agent)
    → +1 LLM call, better section targeting
    → Gate: compare planned vs. static sections on diverse codebases

Phase 3 (Section Agents)
    → +0-3 LLM calls per section, significant quality jump
    → Gate: measure improvement vs. cost increase

Phase 4 (Coherence Review)
    → +1-3 LLM calls total, polish pass
    → Gate: manual review of contradiction detection accuracy
```

### Feature Flags

All agentic features are opt-in via CLI flags and config:

```python
@dataclass
class AgentConfig:
    """Configuration for agentic features."""
    adaptive_retrieval: bool = True       # Phase 1 (default on — no cost increase)
    enable_planning: bool = False         # Phase 2
    enable_section_agents: bool = False   # Phase 3
    max_tool_calls_per_section: int = 3   # Phase 3 cost bound
    enable_coherence_review: bool = False # Phase 4
```

CLI integration:

```bash
# Default: Phase 1 only (adaptive retrieval, no extra cost)
docgen --source ./my_project

# Enable planning
docgen --source ./my_project --agent-planning

# Full agentic mode
docgen --source ./my_project --agent-mode full

# Cost-conscious agentic mode
docgen --source ./my_project --agent-mode full --max-tool-calls 1
```

### Backward Compatibility

- All current CLI flags continue to work
- Default behavior (no flags) uses Phase 1 only — no cost increase
- `--dry-run` and `--diagrams-only` bypass all agentic features
- Existing tests pass without modification
- New features have their own test suites

---

## Cost Analysis

### LLM Calls Per Documentation Run

| Mode | Planning | Section Gen | Tool Calls | Review | Total (5 sections) |
|---|---|---|---|---|---|
| **Current** | 0 | 5 | 0 | 0 | **5** |
| **Phase 1** | 0 | 5 | 0 | 0 | **5** (same cost, better retrieval) |
| **Phase 2** | 1 | 5 | 0 | 0 | **6** |
| **Phase 3** | 1 | 5 | 0–15 | 0 | **6–21** (avg ~11) |
| **Phase 4** | 1 | 5 | 0–15 | 1–3 | **7–24** (avg ~13) |

### Estimated Token Usage Increase

| Phase | Input Tokens | Output Tokens | Cost Multiplier |
|---|---|---|---|
| Current baseline | ~50k | ~10k | 1.0x |
| + Phase 1 | ~60k (more docs retrieved) | ~10k | ~1.1x |
| + Phase 2 | +2k (planning) | +0.5k | ~1.15x |
| + Phase 3 | +30k (tool results) | +5k | ~1.8x |
| + Phase 4 | +15k (all sections as input) | +2k | ~2.1x |

---

## What Stays Unchanged

These components are correct by construction and benefit nothing from LLM involvement:

| Component | Reason to Keep |
|---|---|
| `CodeAnalyzer` | AST parsing is deterministic and precise — agents add latency for no accuracy gain |
| `DiagramGenerator` | Mermaid output from structured data is reliable; LLM-generated diagrams have syntax errors |
| `DiagramValidator` | Rule-based validation is complete and fast |
| `VectorStoreCache` | Caching logic is orthogonal to generation strategy |
| `DocumentationRenderer` | Jinja2 templating is deterministic |
| `CrossReferenceAnalyzer` | Graph analysis from AST is exact; LLMs hallucinate import relationships |

---

## Summary

The current pipeline is solid for deterministic work (analysis, diagrams, rendering) but leaves quality on the table in the LLM-driven parts (retrieval, section generation, coherence). The proposed hybrid approach adds intelligence where it matters — retrieval targeting, dynamic planning, tool-augmented generation, and cross-section review — while keeping the reliable deterministic components intact.

Phase 1 (adaptive retrieval) is the highest-ROI change: better output with zero additional LLM calls. Each subsequent phase trades cost for quality, with feature flags allowing users to choose their cost/quality tradeoff.
