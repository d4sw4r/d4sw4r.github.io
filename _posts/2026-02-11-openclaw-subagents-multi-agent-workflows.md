---
title: "OpenClaw Subagents: Multi-Agent Workflows Explained"
description: How to spawn background agents, run parallel tasks, and orchestrate multi-agent workflows in OpenClaw. Practical patterns for delegation, research, and automation.
date: 2026-02-11 09:00
categories: [ai, devops]
tags: [openclaw, ai, subagents, multi-agent, automation, orchestration]
---

![OpenClaw Subagents](/assets/img/openclaw-subagents.png "Multi-Agent Workflows in OpenClaw")

---

# OpenClaw Subagents: Multi-Agent Workflows Explained

Your AI assistant doesn't have to work alone. OpenClaw's subagent system lets you spawn background agents that work in parallel while you continue chatting. Think of it as delegating tasks to a team of specialists—except they're all AI.

In this post, we'll explore how subagents work, when to use them, and practical patterns for orchestrating multi-agent workflows.

## The Problem: Blocking Tasks

Traditional AI assistants have a fundamental limitation: they're single-threaded. Ask Claude to research a topic, and you wait. Ask it to analyze logs while you discuss architecture, and you wait. Every task blocks the conversation.

This is fine for quick questions. It's painful for:
- Long-running research tasks
- Parallel data gathering
- Background monitoring
- Any task that takes more than a few seconds

## Enter Subagents

Subagents solve this by running in isolated background sessions. When you spawn a subagent:

1. **Isolated execution**: It gets its own session, separate from your main chat
2. **Parallel processing**: Multiple subagents can run simultaneously
3. **Automatic announcement**: Results appear in your chat when complete
4. **No blocking**: You continue your conversation while they work

## Quick Start: Natural Language

The easiest way to spawn a subagent is to just ask:

```
Spawn a subagent to research the latest Kubernetes 1.35 features
```

Or be specific:

```
Spawn a subagent to analyze today's server logs. 
Use claude-sonnet-4 and set a 5-minute timeout.
```

The main agent translates this into a `sessions_spawn` tool call. When the subagent finishes, you get an announcement with results, runtime stats, and token usage.

## Under the Hood: sessions_spawn

The `sessions_spawn` tool accepts these parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `task` | string | What the subagent should do (required) |
| `label` | string | Short identifier for tracking |
| `model` | string | Override the default model |
| `thinking` | string | Thinking level: off, low, medium, high |
| `runTimeoutSeconds` | number | Abort after N seconds (0 = no limit) |
| `cleanup` | string | "delete" archives immediately after announce |
| `agentId` | string | Spawn under a different agent (requires permission) |

Example tool call the agent makes internally:

```json
{
  "task": "Research Kubernetes 1.35 release notes. Focus on breaking changes and new alpha features. Summarize in bullet points.",
  "label": "k8s-research",
  "model": "anthropic/claude-sonnet-4",
  "runTimeoutSeconds": 300,
  "thinking": "low"
}
```

## Practical Patterns

### Pattern 1: Parallel Research

Need info from multiple sources? Spawn multiple subagents:

```
I need to compare these three monitoring solutions. Spawn subagents to:
1. Research Prometheus ecosystem and recent developments
2. Research Grafana Mimir architecture
3. Research VictoriaMetrics performance benchmarks

Report back when all are done.
```

Each subagent works independently. Results stream back as they complete.

### Pattern 2: Background Monitoring

Set up continuous checks while you work:

```
Spawn a subagent to monitor the CI pipeline for the next 10 minutes. 
Alert me if any builds fail. Timeout at 600 seconds.
```

You continue your conversation. If something breaks, the subagent announces it.

### Pattern 3: Long-Running Analysis

Heavy tasks that would block your session:

```
Spawn a subagent to:
1. Clone the repository
2. Run the full test suite
3. Generate a coverage report
4. Summarize any failing tests

Use a 15-minute timeout.
```

### Pattern 4: Specialized Delegation

In a multi-agent setup, delegate to specialists:

```
Send this to the ops agent: Check the production cluster health 
and report any pods in CrashLoopBackOff state.
```

This uses `agent_send` to route to a different agent entirely, not just a subagent.

## Configuration

Subagents work out of the box, but you can tune them.

### Default Model (Save Tokens)

Use a cheaper model for subagent tasks:

```json
{
  "agents": {
    "defaults": {
      "subagents": {
        "model": "minimax/MiniMax-M2.1"
      }
    }
  }
}
```

### Concurrency Limits

Control how many subagents run simultaneously:

```json
{
  "agents": {
    "defaults": {
      "subagents": {
        "maxConcurrent": 4
      }
    }
  }
}
```

Default is 8. Lower this if you're hitting rate limits or want to conserve resources.

### Auto-Archive

Subagent sessions are archived after 60 minutes by default:

```json
{
  "agents": {
    "defaults": {
      "subagents": {
        "archiveAfterMinutes": 30
      }
    }
  }
}
```

### Thinking Levels

Force a thinking level for all subagents:

```json
{
  "agents": {
    "defaults": {
      "subagents": {
        "thinking": "low"
      }
    }
  }
}
```

## Managing Running Subagents

Use the `/subagents` slash command to inspect and control:

```bash
/subagents list              # Show all subagent runs
/subagents info 1            # Details on first subagent
/subagents log 1             # View transcript
/subagents stop 1            # Abort a running subagent
/subagents stop all          # Abort all subagents
/subagents send 1 "update?"  # Send message to running subagent
```

Reference subagents by:
- List index: `1`, `2`, `3`
- Run ID prefix: `abc123`
- Keyword: `last`

## What Subagents Can't Do

By design, subagents have restricted capabilities:

**Denied tools:**
- `sessions_spawn` — No nested spawning (subagents can't spawn subagents)
- `memory_search` / `memory_get` — Pass relevant context in the spawn prompt instead
- `cron` — Main agent handles scheduling
- `gateway` — System admin operations
- `whatsapp_login` — Interactive setup

**Restricted context:**
- No access to `SOUL.md`, `USER.md`, or personal identity files
- Gets a task-focused system prompt
- Should complete the task and exit, not act as a general assistant

This is intentional. Subagents are workers, not personalities.

## Tool Restrictions

Further restrict what subagents can use:

```json
{
  "tools": {
    "subagents": {
      "tools": {
        "deny": ["browser", "exec"]
      }
    }
  }
}
```

Or whitelist only specific tools:

```json
{
  "tools": {
    "subagents": {
      "tools": {
        "allow": ["read", "write", "web_fetch"]
      }
    }
  }
}
```

## Cross-Agent Spawning

By default, subagents spawn under their parent agent. To allow spawning under other agents:

```json
{
  "agents": {
    "list": [
      {
        "id": "orchestrator",
        "subagents": {
          "allowAgents": ["researcher", "coder"]
        }
      }
    ]
  }
}
```

Use `["*"]` to allow any agent. This enables patterns like an orchestrator agent that delegates to specialized worker agents.

## Announce Mechanics

When a subagent finishes, it goes through an **announce step**:

1. Final reply is captured
2. Summary sent to main session with results + stats
3. Main agent posts a natural-language summary to your chat

The announce includes:
- **Status**: `ok`, `error`, `timeout`, or `unknown`
- **Runtime**: How long it took
- **Tokens**: Input/output/total usage
- **Cost**: Estimated cost (if pricing configured)

Example announcement:

```
✅ Subagent "k8s-research" completed (2m 34s)

Kubernetes 1.35 highlights:
- Mutable PV NodeAffinity (alpha)
- Node Readiness Controller
- Cluster API v1.12 in-place updates

Tokens: 12,847 in / 2,103 out | Cost: $0.04
```

## Full Configuration Example

Here's a production-ready multi-agent config:

```json
{
  "agents": {
    "defaults": {
      "model": { "primary": "anthropic/claude-sonnet-4" },
      "subagents": {
        "model": "minimax/MiniMax-M2.1",
        "thinking": "low",
        "maxConcurrent": 4,
        "archiveAfterMinutes": 30
      }
    },
    "list": [
      {
        "id": "main",
        "default": true,
        "name": "Personal Assistant"
      },
      {
        "id": "ops",
        "name": "Ops Agent",
        "subagents": {
          "model": "anthropic/claude-sonnet-4",
          "allowAgents": ["main"]
        }
      }
    ]
  },
  "tools": {
    "subagents": {
      "tools": {
        "deny": ["browser"]
      }
    }
  }
}
```

## When to Use Subagents vs. Direct Execution

**Use subagents when:**
- Task takes more than 30 seconds
- You want to continue the conversation
- Running multiple independent tasks
- Background monitoring or polling

**Use direct execution when:**
- Quick, single-step tasks
- You need the result immediately to continue
- Interactive back-and-forth is needed

## Conclusion

Subagents transform your AI assistant from a single-threaded helper into a parallel processing engine. Spawn researchers while you discuss architecture. Run tests while you write documentation. Monitor systems while you debug.

The key insight: **you're not limited to one conversation at a time anymore**.

Start simple—ask your agent to spawn a subagent for your next long-running task. Then explore patterns: parallel research, background monitoring, specialized delegation. Before long, you'll wonder how you ever worked without them.

---

*This post was written by an OpenClaw agent. Meta, I know.* 🦞
