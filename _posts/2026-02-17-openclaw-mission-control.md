---
title: "Building an AI-Powered Kanban Board with OpenClaw"
date: 2026-02-17
tags: ["ai", "devops", "openclaw", "nodejs"]
description: "How I built a personal Kanban dashboard where an AI agent automatically processes tasks, researches topics, and moves cards to Done — without me lifting a finger."
---

![Kanban in OpenClaw](/assets/img/openclaw-cron.png "Kanban in OpenClaw")

---

## Building an AI-Powered Kanban Board with OpenClaw

What if your to-do list could complete itself?

That's not a thought experiment anymore. Here's how I built a personal Kanban board where an AI agent automatically picks up tasks, does the actual work, and moves cards to Done — on a schedule, without prompting.

## The Setup

The stack is simple:

- **Node.js + Express** — REST API + static file server
- **Vanilla JS + HTML5 Drag & Drop** — no React, no framework overhead
- **`todos.json`** — flat file storage, no database needed
- **OpenClaw cron** — the AI agent that does the actual work

The dashboard has four columns: Backlog, In Progress, Waiting, Done. Cards drag between columns, persist immediately via API, and live-update without page reloads.

## The API

Four endpoints, dead simple:

```js
GET    /api/todos          // all todos
POST   /api/todos          // create
PUT    /api/todos/:id      // update (status, title, description)
DELETE /api/todos/:id      // delete
```

Storage is a plain JSON file. For a personal tool running on a single machine, a database would be overkill.

```js
const TODOS_FILE = path.join(__dirname, '../todos.json');

function readTodos() {
  try {
    return JSON.parse(fs.readFileSync(TODOS_FILE, 'utf8'));
  } catch {
    return [];
  }
}
```

## Drag & Drop: The One Bug That Matters

HTML5 drag and drop has a well-known race condition. When you drop a card on a target column, the browser fires events in this order:

1. `dragstart` — sets `draggedId`
2. `dragover` — preventDefault to allow drop
3. `drop` — your handler fires, starts async fetch
4. `dragend` — fires on the source element

The problem: `dragend` fires *during* the async fetch, setting `draggedId = null`. Then the fetch resolves, tries to update `kanbanTodos` using `draggedId`... which is now null. The API call succeeds, but the local state doesn't update — the card visually snaps back to the original column.

The fix is one line:

```js
async function dropOnColumn(e, colId) {
  e.preventDefault();
  const id = draggedId; // capture before any await
  if (!id) return;
  // ... now use `id`, not `draggedId`
}
```

Always capture mutable globals into local variables before the first `await`.

## The AI Agent Part

Here's where it gets interesting. I set up an OpenClaw cron job that runs every hour:

```json
{
  "name": "Todo In-Progress Check",
  "schedule": { "kind": "every", "everyMs": 3600000 },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "Check todos.json for in-progress tasks. For each one: if you can complete it (research, code, analysis) — do it, set status to 'done', report results. If you need my input — give concrete next steps. Send summary to Discord."
  }
}
```

The agent runs in an isolated session, reads the JSON file directly, and:

- **Researches topics** — web searches, price checks, link aggregation
- **Writes content** — drafts, summaries, analysis
- **Updates status** — writes `done` directly into `todos.json`
- **Sends a Discord summary** — one message per run

Real example from today:

> 🔍 **Lichee RV Nano** — Found on AliExpress for ~$15 with 256MB RAM, RISC-V SBC. Link: [...]

Three tasks, zero manual work.

## What The Agent Can't Do (Yet)

The agent works well for lookup and research tasks. It struggles with:

- **Tasks requiring external accounts** (booking, ordering, posting)
- **Ambiguous tasks** — "Improve OpenClaw" is too vague; it'll mark it done without doing much
- **Long-running tasks** — the 60-second timeout means deep research gets cut off

For the ambiguous ones, the agent now sends concrete "what do you want me to do exactly?" questions to Discord instead of silently marking them done.

## The Result

A personal task manager where the AI is a genuine collaborator, not just a status display. I add tasks, the agent processes them, I see results in Discord.

Total setup time: about 2 hours. Dashboard code, API, drag-and-drop, cron job.

The interesting part isn't the technology — it's the workflow shift. Tasks become asynchronous. I add something to In Progress before bed, wake up to a Discord summary with results.

That's the actual promise of personal AI agents: not answering questions faster, but working while you're not.


*The dashboard source is not (yet) public, but all the OpenClaw cron and agent patterns are documented at [docs.openclaw.ai](https://docs.openclaw.ai).*