# AI agent governance

- IBM source: [AI Agent Governance: Big Challenges, Big Opportunities](https://www.ibm.com/think/insights/ai-agent-governance)
- Hub section: Governance
- Reviewed: 2026-09-28

## Article notes

- Autonomy raises the need to see and constrain decisions made without direct human review. Tool and API access can expose data or produce unauthorized effects.
- The article carries familiar governance practices into agent systems: risk assessment, transparent workflows, monitoring, and human approval for selected actions.
- It proposes simulation before deployment, observing interactions among agents, conflict rules, and a way to stop harmful behavior.
- Governance must cover a system across its lifecycle, including drift and new failure modes after deployment.

## Check against Laravel Guild

- Exercise a real pause, approval, interruption, and recovery path described in [security governance](../../agent-security-governance.md) and [reliability operations](../../agent-reliability-operations.md).
- Compare the existing adversarial cases with cross-agent conflicts and unsafe tool calls; add only a missing, reproducible scenario.
- Ensure [observability](../../observability.md) records enough derived evidence for investigation without logging sensitive payloads.
