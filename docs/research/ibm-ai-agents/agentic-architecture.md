# Agentic architecture

- IBM source: [What Is Agentic Architecture?](https://www.ibm.com/think/topics/agentic-architecture)
- Hub section: Architecture
- Reviewed: 2026-09-28

## Article notes

- Architecture determines how an agent can plan, act, react to new information, and reflect on outcomes. Tool and data interfaces are part of that design.
- The article contrasts a focused single agent with arrangements involving multiple agents. A single agent is simpler to debug and operate; multiple specialists may help when work can be divided safely.
- It also describes reactive, deliberative, and cognitive approaches. The required behavior should determine the architecture, rather than an ambition to maximize autonomy.
- Multiagent structures introduce communication and coordination overhead alongside their potential specialization benefit.

## Check against Laravel Guild

- For each proposed workflow, state why its topology is necessary and what a single-agent baseline would do.
- Use [multi-agent coordination](../../multi-agent-coordination.md) to reject unsafe graphs and measure the value of delegation.
- Check the [orchestration contract](../../orchestration-contract.md) for a clear source of authority when plans must change during execution.
