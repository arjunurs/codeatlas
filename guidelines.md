First, focus on establishing the high-level architecture. Ask the LLM to explain the core components, their relationships, and the overall system design. For example, you might ask: "What are the main modules in this codebase and how do they interact?"
For complex systems, take an iterative approach:

Start with understanding the entry points and main execution flows
Gradually explore specific components in more detail
Use the LLM to explain unfamiliar patterns or complex logic

When analyzing specific parts of the code:

Provide necessary context by including relevant files and dependencies
Ask for explanations of non-obvious design decisions or implementation details
Have the LLM identify potential areas of technical debt or maintenance concerns

For documentation, ask the LLM to:

Generate architectural diagrams showing component relationships
Explain the business logic and domain concepts
Document key workflows and data flows
Highlight important configuration settings and their impact

To better understand changes and updates:

Share relevant git diffs and ask for explanations of the changes
Have the LLM identify potential impacts on other parts of the system
Request suggestions for testing strategies for the modified code