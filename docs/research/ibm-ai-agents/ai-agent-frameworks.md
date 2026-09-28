# AI agent frameworks

- IBM source: [AI Agent Frameworks: Choosing the Right Foundation for Your Business](https://www.ibm.com/think/insights/top-ai-agent-frameworks)
- Hub section: Frameworks
- Reviewed: 2026-09-28

## Article notes

- Frameworks package common agent infrastructure: workflow structure, tool integration, communication, task management, and monitoring.
- IBM recommends evaluating a framework against task complexity, privacy and security, ease of use, integration needs, performance, and scale.
- The article surveys AutoGen, CrewAI, LangChain, LangChain4j, LangGraph, LlamaIndex, and Semantic Kernel. Its comparison is a starting inventory, not evidence that one library fits this repository.
- The selection question is operational: can a framework support the required controls and be maintained at an acceptable cost?

## Check against Laravel Guild

- Map the article's framework capabilities to the existing [agent harness](../../agent-harness.md) and [enforcement map](../../enforcement-map.md).
- Before introducing a dependency, define the missing capability and a small measured proof that it improves the current implementation.
- Test whether any candidate preserves current approval, source-bound evidence, and path containment rules.
