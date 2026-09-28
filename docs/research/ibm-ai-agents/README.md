# IBM AI agents reading collection

Source hub: [The 2026 Guide to AI Agents](https://www.ibm.com/think/ai-agents)
Reviewed: 2026-09-28

Pack comparison and first enhancement: [IBM guide review](../2026-09-28-ibm-agent-pack-review.md).

The hub has eight **Get started** articles and fifteen links in **Resources**. This collection covers the eight guide articles plus five readable resource stories/report pages: **13 Markdown notes** in all. These are original, concise research notes linked to the IBM originals, not copies of the article text. The remaining resource destinations are catalogued below.

| Hub topic | Local note | Primary question for Laravel Guild |
| --- | --- | --- |
| Overview | [AI agents](ai-agents.md) | Where does autonomy need a stop or approval? |
| Components | [Components of AI agents](components-of-ai-agents.md) | Are the input, plan, action, feedback, and memory boundaries explicit? |
| Architecture | [Agentic architecture](agentic-architecture.md) | Is each topology justified by the task? |
| Multiagent systems | [Multiagent systems](multiagent-systems.md) | Does measured coordination beat a single agent? |
| Frameworks | [AI agent frameworks](ai-agent-frameworks.md) | Which framework capabilities belong in our own harness? |
| Governance | [AI agent governance](ai-agent-governance.md) | Can oversight and intervention be exercised and audited? |
| Agentic RAG | [Agentic RAG](agentic-rag.md) | Does retrieval improve grounded answers enough to justify its cost? |
| Applications | [AI agent use cases](ai-agent-use-cases.md) | Which workflows merit evaluation in a Laravel app? |

## Additional readable resources

| Hub resource | Local note | Format |
| --- | --- | --- |
| Designing an AI native airline at enterprise scale | [Riyadh Air](riyadh-air.md) | Case study |
| The enterprise in 2030 | [Enterprise in 2030](enterprise-in-2030.md) | Report landing page |
| From AI projects to profits | [AI projects to profits](ai-projects-to-profits.md) | Report landing page |
| Ushering in the agentic enterprise | [Agentic enterprise announcement](agentic-enterprise.md) | Announcement |
| How Comparus is using a banking assistant | [Comparus](comparus.md) | Case study |

The two report notes describe their public landing pages; their downloadable reports are separate material.

## Other linked destinations on the hub

| Resource | Destination type |
| --- | --- |
| [Start realizing ROI](https://www.ibm.com/forms/mkt-54067) | Guide CTA registration form |
| [Cost of a Data Breach Report 2026](https://www.ibm.com/reports/data-breach) | Report hub |
| [AI governance imperative](https://www.ibm.com/forms/mkt-54070) | Registration form |
| [Agentic AI explained](https://www.ibm.com/think/podcasts/techsplainers) | Podcast series |
| [Unlock AI ROI](https://www.ibm.com/forms/mkt-54227) | Registration form |
| [How AI agents and assistants can benefit your organization](https://www.ibm.com/forms/mkt-53811) | Registration form |
| [Reimagine business productivity](https://www.ibm.com/think/videos/ai-academy/reimagine-business-productivity-with-ai) | Video |
| [Try watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate/demos) | Demo |
| [Omdia report on empowered intelligence](https://www.ibm.com/forms/mkt-53501) | Registration form |
| [How AI agents will reinvent productivity](https://www.ibm.com/think/podcasts/ai-in-action/how-ai-agents-will-reinvent-productivity) | Podcast episode |
| [The future of agents](https://www.ibm.com/think/podcasts/mixture-of-experts/future-of-ai-agents-ai-energy-consumption-anthropic-computer-use-google-watermarking-ai) | Podcast episode |

## How to use these notes

Read the IBM source before treating a claim as design evidence. The notes paraphrase the articles and separate their themes from proposed checks for this repository. An upgrade should start with a current-state review, then a scoped spec and a measured eval. Existing controls are described in [agent harness](../../agent-harness.md), [multi-agent coordination](../../multi-agent-coordination.md), [security governance](../../agent-security-governance.md), and [agent economics](../../agent-economics.md).

## Candidate review order

1. Test retrieval quality and source freshness against the existing [context engineering](../../context-engineering.md) contract before considering agentic RAG.
2. Review intervention and recovery paths against [security governance](../../agent-security-governance.md) and [reliability operations](../../agent-reliability-operations.md).
3. Use the existing [coordination comparison](../../multi-agent-coordination.md) to measure when specialist delegation helps.
4. Add only changes that improve the [evaluation engineering](../../evaluation-engineering.md) evidence without weakening approval and path boundaries.
