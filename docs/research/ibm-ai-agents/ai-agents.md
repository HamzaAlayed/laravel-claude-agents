# AI agents

- IBM source: [What Are AI Agents?](https://www.ibm.com/think/topics/ai-agents)
- Hub section: Overview
- Reviewed: 2026-09-28

## Article notes

- An agent pursues a goal by deciding on steps and using available tools. Planning, tool use, feedback, and memory distinguish richer agents from a one-shot model response.
- The article compares iterative reasoning after each action with planning a sequence before execution. The choice affects flexibility, tool calls, and cost.
- It describes reflex, model-based, goal-based, utility-based, and learning agents as a range of capabilities. More autonomy is useful only when the task calls for it.
- Risks include repeated tool loops, multiagent dependencies, privacy exposure, and rising compute cost. The suggested controls include activity records, interruption, traceable identity, and human supervision for consequential actions.

## Check against Laravel Guild

- Confirm that each stage has a bounded goal, tool scope, budget, and clear completion evidence in the [agent harness](../../agent-harness.md).
- Exercise the [loop policy](../../loop-policy.md) and [recovery policy](../../recovery-policy.md) with an interrupted, repeating tool sequence.
- Compare plan-first and adaptive execution on one representative task using completion, cost, and error rates rather than assuming one approach always wins.
