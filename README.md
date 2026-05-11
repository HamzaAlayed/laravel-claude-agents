# The 15-Agent Claude Code Software Team

A production-grade, drop-in team of Claude Code subagents covering the full software lifecycle: discovery, prioritization, architecture, design, frontend, backend, database, mobile, QA, DevOps, security, technical writing, tech leadership, scrum, and end-to-end delivery coordination.

This is the original 14-role spec, re-engineered for Claude Code's actual primitives — tools, models, memory, MCP servers, worktree isolation, and the Agent-tool delegation model — so it runs, not just reads well.

---

## What's in here

```
.claude/agents/
├── business-analyst.md       # Discovery & requirements (Sonnet, project memory, read-only)
├── product-owner.md          # Backlog & prioritization (Sonnet, project memory)
├── ui-ux-designer.md         # Design system & accessibility (Sonnet, frontend-design skill)
├── frontend-developer.md     # Web UI implementation (Sonnet, worktree, frontend-design skill)
├── backend-developer.md      # APIs & services (Sonnet, worktree)
├── database-developer.md     # Schema, migrations, indexes (Sonnet, worktree, project memory)
├── qa-engineer.md            # Test strategy & release readiness (Sonnet)
├── devops-engineer.md        # CI/CD, IaC, observability (Sonnet)
├── scrum-master.md           # Delivery rhythm & blockers (Haiku, project memory)
├── solution-architect.md     # System design & ADRs (Opus, project memory)
├── security-engineer.md      # Threat models & vuln review (Sonnet, project memory, no Edit/Write)
├── technical-writer.md       # Docs, API ref, release notes (Sonnet)
├── tech-lead.md              # Code review & breakdown (Opus, project memory, no Edit/Write)
├── mobile-developer.md       # iOS, Android, React Native (Sonnet, worktree)
└── delivery-coordinator.md   # Orchestrator main-thread agent (Sonnet, project memory)
```

---

## Design choices, and why

These are the deliberate enhancements over the original spec to make the team perform well in Claude Code:

**Model selection is opinionated, not uniform.**
- **Opus** for `solution-architect` and `tech-lead` — these agents reason deeply about long-lived consequences and review work end-to-end. The extra cost is justified.
- **Haiku** for `scrum-master` — most of its work is aggregation, status, and orchestration. Faster + cheaper without quality loss.
- **Sonnet** for everyone else — the right default for builder and reviewer roles.

**Reviewers don't silently rewrite code.**
- `tech-lead` and `security-engineer` have `disallowedTools: Edit, Write`. They produce findings; the relevant builder applies them. This preserves the teaching/audit value of reviews and prevents "silent fixes" that the human and the original author never see.

**Builders get worktree isolation.**
- `frontend-developer`, `backend-developer`, `database-developer`, and `mobile-developer` set `isolation: worktree`. Their changes go into a temporary git worktree, so you can review the diff cleanly before merging into your working copy. The worktree is auto-cleaned if no changes are made.

**Persistent memory where institutional knowledge matters.**
- Project-scoped memory (`.claude/agent-memory/<agent>/`) is enabled for: `business-analyst`, `product-owner`, `ui-ux-designer`, `database-developer`, `solution-architect`, `security-engineer`, `tech-lead`, `scrum-master`, `delivery-coordinator`. These agents accumulate decisions, patterns, and lessons across sessions.

**Skills are preloaded where they earn their place.**
- `ui-ux-designer` and `frontend-developer` preload the `frontend-design` skill so they get design tokens, styling constraints, and component conventions injected from the start.

**A coordinator was added.**
- The original spec describes orchestration as a separate concern. In Claude Code, the cleanest implementation is a `delivery-coordinator` agent that runs as the **main thread** (`claude --agent delivery-coordinator`) and uses the Agent tool to spawn the specialists. Subagents can't spawn other subagents — the main thread can.

**Trigger phrases are tuned for auto-delegation.**
- Every `description` field uses phrases like "Use proactively after..." that Claude's delegation logic responds to. You can still @-mention any agent explicitly.

---

## Install

Drop the `.claude/agents/` folder into the root of any project. That's it.

```bash
# From the project root
cp -r path/to/this/.claude/agents .claude/agents
# (or just unzip into the project root)
```

The agents are now available in `/agents` and via `@agent-<name>` in that project. To make them available globally instead, copy to `~/.claude/agents/`.

Then either:

1. **Start a normal Claude Code session** — `claude` — and the agents auto-delegate based on your prompt, or
2. **Start as the coordinator** — `claude --agent delivery-coordinator` — for multi-stage delivery work.

---

## Driving the team — example prompts

**Single specialist, automatic delegation:**
```
Use the business-analyst to clarify what we actually need from
the new "customer health score" feature. Stakeholder ticket is INC-4421.
```

**Explicit @-mention to force a specific agent:**
```
@agent-tech-lead review the auth changes in PR #312
```

**Coordinated multi-stage work (start session with `claude --agent delivery-coordinator`):**
```
We need to ship a "team workspaces" feature. Take it from discovery
through to docs.
```
The coordinator will: brief the business-analyst, surface the human checkpoint on the problem statement, then sequence design → architecture → backend → frontend → review → test → docs.

**Parallel investigation:**
```
Investigate why the dashboard p95 latency doubled last week. Spawn
backend-developer to audit the API, database-developer to audit query
plans, and devops-engineer to audit infra changes — in parallel.
```

---

## Optional: connect MCP servers

Several agents become noticeably more capable when paired with MCP servers. The connectors below map to common workflows. If you have them connected in Claude Code (Settings → Connectors), the relevant agents will use them.

| Agent                | Useful MCP connectors                                          |
| -------------------- | -------------------------------------------------------------- |
| `business-analyst`   | Linear / Jira (Atlassian) / Notion — pull tickets & docs       |
| `product-owner`      | Linear / Jira / monday / HubSpot — backlog and revenue context |
| `scrum-master`       | Linear / Jira / Asana / monday — sprint state and activity     |
| `ui-ux-designer`     | Figma / Canva / Notion — design files and brand                |
| `frontend-developer` | Figma — pull design tokens and frames                          |
| `technical-writer`   | Notion — long-form docs surface                                |
| `tech-lead`          | Linear / Jira — link PRs to stories                            |

To scope an MCP server to a specific agent (so its tools don't clutter the main session), add to that agent's frontmatter:

```yaml
mcpServers:
  - linear   # references an already-configured server
  # or define inline:
  - playwright:
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
```

Names must match the server names registered in your Claude Code MCP config.

---

## Optional: shared project memory (`CLAUDE.md`)

A `CLAUDE.md` template is included in the bundle. Drop it at the project root (or `.claude/CLAUDE.md`) and fill in the sections. Every agent — main thread and subagent — sees it. Use it for the things that should be true *everywhere*: tech stack, conventions, what's in scope, what's not.

---

## Optional: a guardrail hook for the database agent

If you want to prevent the `database-developer` from running destructive SQL against production databases, add a `PreToolUse` hook to its frontmatter:

```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/block-prod-destructive-sql.sh"
```

The script reads the JSON tool input from stdin, checks for `DROP/TRUNCATE/DELETE` against a production hostname pattern, and exits 2 to block. A starter version is included in `scripts/`.

---

## Scaling the team down

You don't need all 15 agents on day one. Useful subsets:

- **Solo developer / weekend project:** `tech-lead`, `qa-engineer`, plus one of `frontend-developer` / `backend-developer` / `mobile-developer`.
- **Small product team:** add `business-analyst`, `product-owner`, `ui-ux-designer`, `solution-architect`.
- **Production system at scale:** add `database-developer`, `devops-engineer`, `security-engineer`, `technical-writer`.
- **Enterprise delivery:** add `scrum-master`, `delivery-coordinator`.

Each agent is one file. Add and remove as you go.

---

## Scaling the team up — Agent Teams (experimental)

The pattern above uses Claude Code subagents — one session, many specialists, delegated via the Agent tool. If you need teammates that **communicate directly with each other mid-task** (e.g. a backend and frontend agent negotiating an API contract live), enable Agent Teams:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

Subagent definitions in this folder are reusable as teammate types — when spawning a teammate, reference an agent name and the teammate inherits its tools, model, and system prompt. Costs ~3–4× tokens of a single session; only worth it for genuinely parallel work with live cross-talk.

---

## References

- Subagents documentation: https://code.claude.com/docs/en/sub-agents
- Agent Teams documentation: https://code.claude.com/docs/en/agent-teams
- Skills documentation: https://code.claude.com/docs/en/skills
- MCP documentation: https://code.claude.com/docs/en/mcp
