---
title: "OpenClaw Cron & Scheduling: Time-Based Automation for AI Agents"
description: How to schedule recurring tasks, set reminders, and build time-driven workflows with OpenClaw's cron system. From simple wake-ups to sophisticated multi-agent orchestration.
date: 2026-02-12 09:00
categories: [ai, devops]
tags: [openclaw, ai, cron, scheduling, automation, reminders]
---

![OpenClaw Cron Scheduling](/assets/img/openclaw-cron.png "Time-Based Automation in OpenClaw")

---

# OpenClaw Cron & Scheduling: Time-Based Automation for AI Agents

An AI assistant that only responds when you talk to it is useful. An AI assistant that proactively works on your behalf—even while you sleep—is transformative.

OpenClaw's cron system brings time-based automation to your AI agents. Schedule daily briefings, set reminders, run periodic checks, and orchestrate background workflows. This post covers everything from basic scheduling to advanced patterns.

## Why Time-Based Automation?

Traditional chatbots are reactive. You ask, they answer. But real assistants anticipate. They remind you about meetings, check your systems overnight, and prepare reports before you need them.

With OpenClaw cron, your agent can:
- Send daily news summaries at 7 AM
- Check CI pipelines every hour
- Remind you about expiring certificates
- Run security scans weekly
- Generate and publish blog posts (like this one!)

The agent becomes a proactive team member, not just a question-answering machine.

## Core Concepts

### Jobs, Schedules, and Payloads

Every cron job has three parts:

1. **Schedule**: When it runs (cron expression, interval, or one-shot)
2. **Payload**: What it does (system event or agent turn)
3. **Session Target**: Where it runs (main session or isolated)

### Two Execution Modes

**System Event (`main` session):**
- Injects a message into your existing chat
- Agent sees it as a system event, not a user message
- Good for reminders and notifications

**Agent Turn (`isolated` session):**
- Spawns a fresh isolated session
- Agent executes the task independently
- Results announced back to you
- Good for background work

## Quick Start: Natural Language

The easiest way to schedule is just asking:

```
Remind me to check the production logs in 2 hours
```

```
Every morning at 8 AM, give me a summary of my calendar
```

```
At 5 PM on Friday, remind me to submit the weekly report
```

OpenClaw translates these into proper cron job configurations. No YAML required.

## Schedule Types

### One-Shot (`at`)

Run once at a specific time:

```json
{
  "schedule": {
    "kind": "at",
    "at": "2026-02-12T14:30:00Z"
  }
}
```

Perfect for: reminders, delayed tasks, scheduled announcements.

### Recurring Interval (`every`)

Run at fixed intervals:

```json
{
  "schedule": {
    "kind": "every",
    "everyMs": 3600000
  }
}
```

That's every hour (3,600,000 milliseconds). Add `anchorMs` to control the starting point.

Perfect for: health checks, polling, periodic syncs.

### Cron Expression (`cron`)

Full cron syntax for complex schedules:

```json
{
  "schedule": {
    "kind": "cron",
    "expr": "0 9 * * 1-5",
    "tz": "Europe/Berlin"
  }
}
```

That's 9 AM on weekdays in Berlin time. Standard 5-field cron format.

Perfect for: daily briefings, weekly reports, business-hours tasks.

## Payload Types

### System Events

Inject text into the main session:

```json
{
  "payload": {
    "kind": "systemEvent",
    "text": "⏰ Reminder: Check production deployment status"
  }
}
```

The agent sees this and can respond naturally. Use for reminders and triggers.

**Constraint:** System events only work with `sessionTarget: "main"`.

### Agent Turns

Run a full agent task in isolation:

```json
{
  "payload": {
    "kind": "agentTurn",
    "message": "Check the CI pipeline status. If any builds failed in the last hour, report the failures.",
    "model": "anthropic/claude-sonnet-4",
    "thinking": "low",
    "timeoutSeconds": 300
  }
}
```

The agent spawns, executes the task, and announces results.

**Constraint:** Agent turns only work with `sessionTarget: "isolated"`.

## Full Job Examples

### Morning Briefing

Daily summary at 7 AM:

```json
{
  "name": "morning-briefing",
  "schedule": {
    "kind": "cron",
    "expr": "0 7 * * *",
    "tz": "Europe/Berlin"
  },
  "payload": {
    "kind": "agentTurn",
    "message": "Generate my morning briefing: 1) Weather forecast 2) Today's calendar events 3) Important emails 4) Any system alerts overnight"
  },
  "sessionTarget": "isolated",
  "delivery": {
    "mode": "announce"
  }
}
```

### Hourly Health Check

Monitor infrastructure every hour:

```json
{
  "name": "infra-health",
  "schedule": {
    "kind": "every",
    "everyMs": 3600000
  },
  "payload": {
    "kind": "agentTurn",
    "message": "Check: 1) Kubernetes pod status 2) Node resource usage 3) Certificate expiration. Only report if issues found."
  },
  "sessionTarget": "isolated",
  "delivery": {
    "mode": "announce"
  }
}
```

### Simple Reminder

One-shot notification:

```json
{
  "name": "standup-reminder",
  "schedule": {
    "kind": "at",
    "at": "2026-02-12T09:55:00+01:00"
  },
  "payload": {
    "kind": "systemEvent",
    "text": "⏰ Daily standup in 5 minutes!"
  },
  "sessionTarget": "main"
}
```

### Weekly Report

Generate and deliver every Friday:

```json
{
  "name": "weekly-report",
  "schedule": {
    "kind": "cron",
    "expr": "0 17 * * 5",
    "tz": "Europe/Berlin"
  },
  "payload": {
    "kind": "agentTurn",
    "message": "Generate the weekly infrastructure report: uptime stats, incident summary, cost analysis, and recommendations.",
    "timeoutSeconds": 600
  },
  "sessionTarget": "isolated",
  "delivery": {
    "mode": "announce",
    "channel": "slack"
  }
}
```

## Managing Jobs

### Using the cron Tool

The agent uses the `cron` tool internally:

```json
// List all jobs
{ "action": "list" }

// Add a new job
{ "action": "add", "job": { ... } }

// Update existing job
{ "action": "update", "jobId": "abc123", "patch": { "enabled": false } }

// Remove a job
{ "action": "remove", "jobId": "abc123" }

// Trigger immediately
{ "action": "run", "jobId": "abc123" }

// View run history
{ "action": "runs", "jobId": "abc123" }
```

### Slash Commands

For quick management:

```bash
/cron list                    # Show all scheduled jobs
/cron info daily-briefing     # Job details
/cron disable weekly-report   # Pause a job
/cron enable weekly-report    # Resume
/cron run daily-briefing      # Trigger now
/cron delete old-reminder     # Remove permanently
```

## Delivery Options

For isolated agent turns, control how results are delivered:

### Announce (Default)

Results posted to your chat:

```json
{
  "delivery": {
    "mode": "announce"
  }
}
```

### Channel-Specific

Route to a specific channel:

```json
{
  "delivery": {
    "mode": "announce",
    "channel": "discord",
    "to": "ops-channel"
  }
}
```

### Silent

No announcement (just logs):

```json
{
  "delivery": {
    "mode": "none"
  }
}
```

## Heartbeats vs. Cron: Choosing the Right Tool

OpenClaw has two periodic execution mechanisms. Use the right one:

### Use Heartbeats When:
- Multiple checks can batch together
- You need conversational context
- Timing can drift (every ~30 min is fine)
- You want to reduce API calls by combining checks

### Use Cron When:
- Exact timing matters ("9 AM sharp")
- Task needs isolation from main session
- You want a different model for the task
- One-shot reminders ("remind me in 20 minutes")
- Output should go to a specific channel

**Pro tip:** Batch similar periodic checks into your `HEARTBEAT.md` file. Use cron for precise schedules and standalone tasks.

## Advanced Patterns

### Pattern 1: Chained Jobs

Use one job's output to trigger another:

```json
{
  "name": "daily-backup",
  "schedule": { "kind": "cron", "expr": "0 2 * * *" },
  "payload": {
    "kind": "agentTurn",
    "message": "Run database backup. If successful, schedule a verification job for 1 hour from now."
  },
  "sessionTarget": "isolated"
}
```

The agent can create follow-up cron jobs dynamically.

### Pattern 2: Conditional Execution

Only act if conditions are met:

```json
{
  "payload": {
    "kind": "agentTurn",
    "message": "Check disk usage. If any volume is above 80%, alert. If all are fine, respond with just 'OK' and don't announce."
  }
}
```

### Pattern 3: Time-Window Awareness

Include context about when the job runs:

```json
{
  "payload": {
    "kind": "agentTurn",
    "message": "It's Monday morning. Generate the weekend incident summary and prepare this week's priorities."
  }
}
```

### Pattern 4: Multi-Agent Orchestration

Schedule jobs that coordinate multiple agents:

```json
{
  "name": "daily-ops",
  "payload": {
    "kind": "agentTurn",
    "message": "Coordinate today's operations: 1) Ask the monitoring agent for overnight alerts 2) Ask the security agent for scan results 3) Compile into a morning report"
  }
}
```

## Real-World Example: Daily Blog Automation

This very blog post was created by a scheduled job:

```json
{
  "name": "daily-blog-post",
  "schedule": {
    "kind": "cron",
    "expr": "0 7 * * *",
    "tz": "UTC"
  },
  "payload": {
    "kind": "agentTurn",
    "message": "Create the daily blog post for d4sw4r.github.io. Research a topic, write the article, generate an image, create the PR.",
    "model": "anthropic/claude-opus-4-5",
    "timeoutSeconds": 900
  },
  "sessionTarget": "isolated",
  "delivery": {
    "mode": "announce"
  }
}
```

Every morning at 7 AM UTC:
1. Agent spawns in isolation
2. Researches a topic (OpenClaw, Kubernetes, DevOps)
3. Writes a 1000-2000 word article
4. Generates a DALL-E image
5. Creates a PR on GitHub
6. Announces completion

By 9 AM, a fresh blog post is ready for review. Fully automated.

## Timezone Handling

All times without explicit timezone are UTC. For local time:

```json
{
  "schedule": {
    "kind": "cron",
    "expr": "0 9 * * *",
    "tz": "Europe/Berlin"
  }
}
```

Common timezone values:
- `UTC` — Default
- `Europe/Berlin` — CET/CEST
- `America/New_York` — EST/EDT
- `Asia/Tokyo` — JST

## Error Handling

### Timeouts

Jobs can specify execution limits:

```json
{
  "payload": {
    "kind": "agentTurn",
    "timeoutSeconds": 300
  }
}
```

If exceeded, the job is terminated and marked as timed out.

### Failed Runs

Check history with:

```json
{ "action": "runs", "jobId": "daily-briefing" }
```

Returns execution history with status, duration, and any errors.

### Retry Logic

Currently, OpenClaw doesn't auto-retry failed jobs. Design your tasks to be idempotent, or build retry logic into the task itself:

```
Check deployment status. If the check fails due to network issues, wait 30 seconds and try once more before reporting failure.
```

## Security Considerations

Cron jobs run with the permissions of their session target:

- **Main session:** Full access to your context and tools
- **Isolated session:** Restricted by subagent tool policies

For sensitive scheduled tasks, consider:

```json
{
  "tools": {
    "subagents": {
      "tools": {
        "deny": ["exec", "browser"]
      }
    }
  }
}
```

This prevents scheduled isolated tasks from executing shell commands or controlling browsers.

## Debugging

### Check Status

```json
{ "action": "status" }
```

Returns scheduler health and next scheduled runs.

### View Job Details

```json
{ "action": "list" }
```

Shows all jobs with their schedules and next run times.

### Force Execution

Test a job immediately:

```json
{ "action": "run", "jobId": "morning-briefing" }
```

### Wake Events

For heartbeat-style polling, use wake events:

```json
{ "action": "wake", "text": "Check for updates", "mode": "now" }
```

This triggers an immediate agent turn without creating a persistent job.

## Configuration Reference

### Job Schema

```json
{
  "name": "string (optional)",
  "schedule": {
    "kind": "at" | "every" | "cron",
    // ... schedule-specific fields
  },
  "payload": {
    "kind": "systemEvent" | "agentTurn",
    // ... payload-specific fields
  },
  "sessionTarget": "main" | "isolated",
  "delivery": {
    "mode": "none" | "announce",
    "channel": "string (optional)",
    "to": "string (optional)"
  },
  "enabled": true | false
}
```

### Constraints

| sessionTarget | payload.kind | Notes |
|---------------|--------------|-------|
| main | systemEvent | ✅ Required combination |
| main | agentTurn | ❌ Invalid |
| isolated | agentTurn | ✅ Required combination |
| isolated | systemEvent | ❌ Invalid |

## Conclusion

Time-based automation is the difference between a chatbot and an autonomous assistant. With OpenClaw cron, your agent works around the clock:

- Morning briefings prepared before you wake
- Infrastructure monitored while you sleep
- Reports generated on schedule
- Reminders delivered precisely when needed

Start with simple reminders. Graduate to daily briefings. Eventually, orchestrate complex multi-agent workflows running on sophisticated schedules.

Your AI assistant isn't just waiting for you anymore. It's working for you, 24/7.

---

*Scheduled, generated, and submitted automatically by OpenClaw. The future writes itself.* ⏰
