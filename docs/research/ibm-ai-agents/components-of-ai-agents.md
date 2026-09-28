# Components of AI agents

- IBM source: [What Are Components of AI Agents?](https://www.ibm.com/think/topics/components-of-ai-agents)
- Hub section: Components
- Reviewed: 2026-09-28

## Article notes

- IBM organizes agent behavior around input handling, planning, memory, reasoning, action through tools, communication, and learning from feedback.
- Input quality matters: an agent first needs to structure and prioritize what it sees. A misunderstood log, request, or API result can contaminate later decisions.
- Plans break complex work into ordered steps and dependencies. Memory preserves short-term context or longer-lived knowledge; these need different retention and trust rules.
- Tools turn decisions into effects in external systems. Communication coordinates people and agents. Feedback can improve later behavior, but it needs a reliable signal of success.

## Check against Laravel Guild

- Trace one delivery from user request to context packet, plan, stage claim, tool action, verification, and feedback receipt. Record any boundary where data could be mistaken for authority.
- Compare the article's memory role with [memory engineering](../../memory-engineering.md): freshness, approval, and deletion should stay explicit.
- Check whether [feedback routing](../../feedback-routing.md) captures failures in a form a later stage can act on.
