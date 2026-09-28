# Agentic RAG

- IBM source: [What Is Agentic RAG?](https://www.ibm.com/think/topics/agentic-rag)
- Hub section: Agentic RAG
- Reviewed: 2026-09-28

## Article notes

- Retrieval augmented generation supplies a model with relevant external context. Agentic RAG lets an agent choose sources, plan several queries, call tools, and refine retrieval.
- IBM describes routing, query planning, iterative action, and plan-and-execute as roles an agent may take in a retrieval flow.
- This can help when questions span multiple changing sources. Extra model calls, latency, coordination, and imperfect grounding can outweigh the benefit on simple questions.
- Retrieval alone does not guarantee a correct answer; the result still needs source checks and evaluation.

## Check against Laravel Guild

- Start with the current [context engineering](../../context-engineering.md) rules for source selection, freshness, and trust.
- Evaluate a fixed set of repository questions with and without adaptive retrieval. Measure answer correctness, cited-source relevance, stale-source errors, latency, and cost.
- Promote a retrieval strategy only if it improves grounded answers while preserving the existing context and security boundaries.
