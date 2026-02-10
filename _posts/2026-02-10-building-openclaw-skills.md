---
title: Building Custom OpenClaw Skills - Extend Your AI Assistant
description: Learn how to create custom skills for OpenClaw. From simple scripts to complex integrations - teach your AI assistant new tricks with the AgentSkills format.
date: 2026-02-10 16:00
categories: [ai, devops]
tags: [openclaw, ai, skills, automation, python, bash, tutorial]
---

![Building OpenClaw Skills](/assets/img/openclaw-skills.png "OpenClaw Skills Development")

---

# Building Custom OpenClaw Skills: Extend Your AI Assistant

OpenClaw is powerful out of the box, but its real strength lies in extensibility. With custom skills, you can teach your AI assistant to interact with any tool, API, or workflow you use. In this guide, we'll build practical skills from scratch and publish them to ClawHub.

## What Are OpenClaw Skills?

Skills are self-contained instruction sets that teach the AI agent how to use specific tools. Each skill is a folder containing a `SKILL.md` file with YAML frontmatter and natural language instructions. The agent reads these at runtime and learns to invoke the associated tools.

**Key concepts:**
- **AgentSkills format**: OpenClaw follows the [AgentSkills](https://agentskills.io) specification
- **Zero code required**: Many skills are pure Markdown instructions
- **Binary integration**: Skills can wrap CLI tools, scripts, or APIs
- **Gating**: Skills auto-enable based on available binaries, env vars, or config

## Skill Anatomy

A minimal skill looks like this:

```
my-skill/
└── SKILL.md
```

With `SKILL.md` containing:

```markdown
---
name: my-skill
description: Does something useful
---

# My Skill

Instructions for the agent on how to use this skill.

## Usage

When the user asks to [do something], run:

\`\`\`bash
my-command --flag value
\`\`\`
```

That's it. The agent reads this, understands it, and uses it when appropriate.

## Skill Locations and Precedence

Skills load from three places (highest to lowest precedence):

1. **Workspace skills**: `<workspace>/skills/` — per-agent, highest priority
2. **Managed skills**: `~/.openclaw/skills/` — shared across agents
3. **Bundled skills**: shipped with OpenClaw

You can add extra directories via `skills.load.extraDirs` in config.

## Building Your First Skill: GitHub Issue Creator

Let's build a skill that creates GitHub issues directly from chat. We'll use the `gh` CLI.

### Step 1: Create the Skill Folder

```bash
mkdir -p ~/.openclaw/skills/github-issues
cd ~/.openclaw/skills/github-issues
```

### Step 2: Write SKILL.md

```markdown
---
name: github-issues
description: Create and manage GitHub issues from chat
metadata: { "openclaw": { "requires": { "bins": ["gh"] }, "emoji": "🐛" } }
---

# GitHub Issues

Create and manage GitHub issues using the GitHub CLI.

## Prerequisites

The `gh` CLI must be installed and authenticated:
\`\`\`bash
gh auth status
\`\`\`

## Creating Issues

To create an issue, use:

\`\`\`bash
gh issue create --repo OWNER/REPO --title "TITLE" --body "BODY"
\`\`\`

If the user doesn't specify a repo, ask them or check if we're in a git repo:
\`\`\`bash
gh repo view --json nameWithOwner -q .nameWithOwner
\`\`\`

## Listing Issues

\`\`\`bash
gh issue list --repo OWNER/REPO --limit 10
\`\`\`

## Viewing an Issue

\`\`\`bash
gh issue view ISSUE_NUMBER --repo OWNER/REPO
\`\`\`

## Closing Issues

\`\`\`bash
gh issue close ISSUE_NUMBER --repo OWNER/REPO --reason "completed"
\`\`\`

## Labels

Add labels when creating:
\`\`\`bash
gh issue create --repo OWNER/REPO --title "TITLE" --body "BODY" --label "bug,priority:high"
\`\`\`

## Best Practices

- Always confirm the repo with the user before creating issues
- Format issue bodies with proper Markdown
- Suggest appropriate labels based on the issue content
- Include reproduction steps for bugs
```

### Step 3: Test It

Restart OpenClaw or start a new session. Ask:

> "Create a GitHub issue in my terraform-hcloud-talos repo about adding Cilium CNI documentation"

The agent will use your skill instructions to run the appropriate `gh` commands.

## Advanced Skill: Kubernetes Namespace Cleaner

Let's build something more complex — a skill that safely cleans up old Kubernetes namespaces.

```markdown
---
name: k8s-namespace-cleaner
description: Safely clean up old or unused Kubernetes namespaces
metadata: { "openclaw": { "requires": { "bins": ["kubectl"] }, "emoji": "🧹" } }
---

# Kubernetes Namespace Cleaner

Identify and clean up unused Kubernetes namespaces safely.

## Safety First

**NEVER delete these namespaces:**
- kube-system
- kube-public
- kube-node-lease
- default
- Any namespace containing "prod" or "production"

Always ask for confirmation before deleting.

## List Candidates for Cleanup

Find namespaces older than 7 days with no recent pod activity:

\`\`\`bash
# List all namespaces with creation time
kubectl get namespaces -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.creationTimestamp}{"\n"}{end}'
\`\`\`

Check if namespace has running pods:
\`\`\`bash
kubectl get pods -n NAMESPACE --no-headers 2>/dev/null | wc -l
\`\`\`

## Analyze Namespace

Before deletion, show:
\`\`\`bash
# Resources in namespace
kubectl api-resources --verbs=list --namespaced -o name | xargs -n 1 kubectl get -n NAMESPACE --ignore-not-found --no-headers 2>/dev/null
\`\`\`

## Delete Namespace

Only after user confirmation:
\`\`\`bash
kubectl delete namespace NAMESPACE --wait=false
\`\`\`

## Dry Run Report

When asked to "analyze" or "report", generate a cleanup report WITHOUT deleting anything:

1. List all non-system namespaces
2. For each, show: age, pod count, resource count
3. Flag candidates older than 7 days with 0 pods
4. Calculate potential resource savings
```

## Skill Gating: Smart Auto-Enable

The `metadata` field controls when skills load:

```yaml
metadata: {
  "openclaw": {
    "requires": {
      "bins": ["terraform", "hcloud"],      # All must exist
      "anyBins": ["docker", "podman"],      # At least one
      "env": ["HCLOUD_TOKEN"],              # Env vars required
      "config": ["browser.enabled"]          # Config paths
    },
    "os": ["linux", "darwin"],              # OS filter
    "primaryEnv": "HCLOUD_TOKEN"            # For API key injection
  }
}
```

This skill only loads when Terraform, hcloud CLI, and the token are available — on Linux or macOS.

## Skills with Scripts

For complex logic, include scripts in your skill folder:

```
hetzner-snapshot/
├── SKILL.md
├── create-snapshot.sh
└── rotate-snapshots.py
```

Reference them in SKILL.md using `{baseDir}`:

```markdown
## Create Snapshot

\`\`\`bash
{baseDir}/create-snapshot.sh --server-name NAME
\`\`\`

## Rotate Old Snapshots

\`\`\`bash
python3 {baseDir}/rotate-snapshots.py --keep 5
\`\`\`
```

## Injecting Secrets

For skills that need API keys, configure them in `openclaw.json`:

```json
{
  "skills": {
    "entries": {
      "hetzner-snapshot": {
        "apiKey": "YOUR_HCLOUD_TOKEN"
      }
    }
  }
}
```

The key is injected as the environment variable specified in `primaryEnv`.

## Publishing to ClawHub

Share your skills with the community:

```bash
# Install clawhub CLI
npm install -g clawhub

# Login
clawhub login

# Publish from skill directory
cd ~/.openclaw/skills/github-issues
clawhub publish
```

Update existing skills:
```bash
clawhub sync --all
```

## Real-World Skill Ideas

Here are skills worth building:

| Skill | Description | Required Tools |
|-------|-------------|----------------|
| `prometheus-silence` | Create/manage Alertmanager silences | `amtool` |
| `terraform-cost` | Estimate infrastructure costs | `infracost` |
| `docker-cleanup` | Prune unused images/volumes | `docker` |
| `ssl-checker` | Check certificate expiry | `openssl` |
| `dns-lookup` | Comprehensive DNS diagnostics | `dig`, `host` |
| `log-analyzer` | Parse and summarize logs | `jq`, `grep` |

## Debugging Skills

Check if your skill loaded:

```bash
openclaw skills list
```

View skill details:

```bash
openclaw skills show github-issues
```

Test in isolation:

```bash
openclaw agent --message "Use the github-issues skill to list my open issues"
```

## Security Considerations

1. **Validate inputs**: Don't blindly pass user input to shell commands
2. **Least privilege**: Request only necessary permissions
3. **Secrets management**: Use `apiKey` config, not hardcoded values
4. **Sandboxing**: For risky operations, recommend sandboxed execution

## Conclusion

OpenClaw skills are the key to making your AI assistant truly personal. They bridge the gap between natural language and your specific toolchain. Start simple — wrap a CLI tool you use daily. Then expand to complex workflows.

The AgentSkills format means your skills can potentially work with other compatible agents too. Build once, use everywhere.

**Next steps:**
- Browse [ClawHub](https://clawhub.ai) for inspiration
- Check bundled skills in your OpenClaw installation
- Join the [Discord](https://discord.gg/clawd) to share what you build

Happy skill building! 🦞

---

*Questions or improvements? Open a PR on this blog's [repository](https://github.com/d4sw4r/d4sw4r.github.io).*
