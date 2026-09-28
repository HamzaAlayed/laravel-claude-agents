# Multiagent systems

- IBM source: [What Is a Multi-Agent System?](https://www.ibm.com/think/topics/multiagent-system)
- Hub section: Multiagent systems
- Reviewed: 2026-09-28

## Article notes

- A multiagent system coordinates agents with partly independent goals and state. The article distinguishes genuine cooperation from a primary agent simply invoking another agent as a tool.
- Centralized designs share oversight and knowledge but depend on a central coordinator. Decentralized designs can be resilient, while making alignment and conflict handling harder.
- Hierarchies, teams, and temporary coalitions are ways to organize work. Their value depends on task dependencies and how agents exchange results.
- Specialization and scale are potential benefits. Malfunction, shared model weaknesses, coordination cost, and unpredictable interaction are potential failure modes.

## Check against Laravel Guild

- Inspect [typed handoffs](../../multi-agent-coordination.md) for dependency evidence, ownership, budget, and stale-context detection.
- Add representative conflict and coordinator-failure cases to an eval only if the current registry lacks them.
- Keep the single-agent comparison as the decision gate; do not infer benefit from the number of participating agents.
