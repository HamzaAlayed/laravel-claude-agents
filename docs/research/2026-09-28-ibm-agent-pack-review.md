# IBM AI agents guide against Laravel Guild — 2026-09-28

This review uses the [13 source-linked notes](ibm-ai-agents/README.md) as an idea inventory. IBM's articles and case studies are inputs, not authority over the pack. A proposed change needs a current-state gap and a measurable outcome.

## Coverage and disposition

| IBM item | Pack evidence | Disposition |
| --- | --- | --- |
| [AI agents](ibm-ai-agents/ai-agents.md) | [Agent harness](../agent-harness.md), [loop policy](../loop-policy.md), [recovery policy](../recovery-policy.md) | Planning, bounded tools, retries, and interruption are covered. No new agent loop. |
| [Components](ibm-ai-agents/components-of-ai-agents.md) | [Context](../context-engineering.md), [memory](../memory-engineering.md), [feedback](../feedback-routing.md) | Input, memory, action, and feedback boundaries are explicit. No general component rewrite. |
| [Architecture](ibm-ai-agents/agentic-architecture.md) | [Orchestration contract](../orchestration-contract.md), [coordination](../multi-agent-coordination.md) | Single-agent and delegated paths exist. Keep topology evidence-based. |
| [Multiagent systems](ibm-ai-agents/multiagent-systems.md) | [Coordination harness](../multi-agent-coordination.md) | Typed handoffs, conflicts, and measured comparison exist. No extra agents by default. |
| [Frameworks](ibm-ai-agents/ai-agent-frameworks.md) | [Harness](../agent-harness.md), [enforcement map](../enforcement-map.md) | Framework adoption has no demonstrated gap or gain. Defer. |
| [Governance](ibm-ai-agents/ai-agent-governance.md) | [Security](../agent-security-governance.md), [observability](../observability.md), [reliability](../agent-reliability-operations.md) | Approval, incident, trace, and recovery controls exist. Recheck with evals before expanding. |
| [Agentic RAG](ibm-ai-agents/agentic-rag.md) | [Context packets](../context-engineering.md), [evaluation](../evaluation-engineering.md) | Source selection is bounded and hash-checked. Adaptive retrieval has no repository-question quality baseline; evaluate before building it. |
| [Use cases](ibm-ai-agents/ai-agent-use-cases.md) | [Eval cases](../../config/evaluation-cases.json), [economics](../agent-economics.md) | Software delivery cases exist. New industry examples need a Laravel-specific scenario and outcome. |
| [Riyadh Air](ibm-ai-agents/riyadh-air.md) | [Orchestration](../orchestration-contract.md) | Contextual case study; scale and results are not transferable benchmarks. |
| [Enterprise in 2030](ibm-ai-agents/enterprise-in-2030.md) | Public report landing page only | No implementation claim without the report's methods and findings. |
| [AI projects to profits](ibm-ai-agents/ai-projects-to-profits.md) | [Economics](../agent-economics.md); public report landing page only | Use project cost-per-success receipts, not a report headline, for thresholds. |
| [Agentic enterprise](ibm-ai-agents/agentic-enterprise.md) | [Harness](../agent-harness.md), [observability](../observability.md) | Product announcement is a capability checklist, not evidence to adopt its platform. |
| [Comparus](ibm-ai-agents/comparus.md) | [Outcome benchmark](../outcome-benchmark.md) | Measure the workflow before and after; do not generalize one customer's numbers. |

## First enhancement: evidence-based research intake

The initial hub collection omitted five readable destinations because the eight top-level guide cards were mistaken for the whole reading set. That is an observed failure in this project. [Technical writer](../../agents/technical-writer.md) already requires source citations and documentation drift checks, but did not require a link inventory or distinguish a report landing page from its downloadable contents. The new research-intake instructions make both checks explicit.

[Solution architect](../../agents/solution-architect.md) already compares technology options and cites version-sensitive claims. The new instruction makes the source-to-existing-control comparison explicit before a research idea becomes a proposal. This prevents an IBM topic already covered by the harness from turning into duplicate machinery.

## Next measured question

The [agentic RAG note](ibm-ai-agents/agentic-rag.md) suggests testing adaptive retrieval. First assemble repository questions with known source locations and answer criteria. Compare the current bounded context selection with an adaptive candidate on answer correctness, source relevance, stale-source failures, latency, and cost. Do not change the runtime retrieval path until that baseline exists.
