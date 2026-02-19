---
title: "PicoClaw + Home Assistant: An AI Agent for Your Smart Home"
description: "PicoClaw is an ultra-lightweight AI agent written in Go that runs on $10 hardware. How it perfectly complements Home Assistant — no cloud, no overhead."
date: 2026-02-19 10:00
categories: [ai, smarthome]
tags: ["ai", "homeassistant", "picoclaw", "smarthome", "automation"]
---

![PicoClaw Home Assistant](/assets/img/picoclaw-ha.png "PicoClaw + Home Assistant")

---

# PicoClaw + Home Assistant: An AI Agent for Your Smart Home

I love Home Assistant. Genuinely. But let's be honest: the moment you start integrating AI into your smart home, things get complicated fast — resource-hungry, messy, and frankly — annoying. That's exactly where [PicoClaw](https://picoclaw.io) comes in.

## What is PicoClaw?

PicoClaw is an ultra-lightweight AI agent, developed by Sipeed, written entirely in Go. What makes it special: it runs on hardware you can buy for 10 dollars. Raspberry Pi Zero, LicheeRV-Nano, some forgotten SBC sitting in a drawer — all perfectly fine. The resource footprint is absurdly low: **under 10 MB RAM**, **boots in under a second**, and it runs on RISC-V, ARM, and x86_64.

Communication happens via Telegram or Discord. LLM requests are forwarded to external providers (OpenAI, Anthropic, etc.) via API key — you bring your own brain. The GitHub repo is at [sipeed/picoclaw](https://github.com/sipeed/picoclaw).

Inspired by the original nanobot project, but completely rewritten in Go. Clean, lean, and straight to the point.

## The Problem with AI in Home Assistant

Home Assistant has come a long way in recent years. There are integrations for OpenAI, local LLMs via Ollama, Assist pipelines — it's all there. But:

**The problem is complexity.** A cleanly running AI Assist pipeline requires:
- A local Whisper container for Speech-to-Text (RAM: easily 2–4 GB)
- Piper for Text-to-Speech
- Ollama for local inference (if you want to avoid the cloud) — another 4–8 GB
- Conversation agents that need to be correctly configured
- Intents that you have to define yourself

All of that is doable. But if all you want is for your smart home to message you on Telegram *"The basement temperature has been below 10°C for 3 hours"* or for you to type *"Turn off the living room lights"* — you don't need any of that.

And on a Raspberry Pi 4 that's already working hard running HA, you really don't want to throw an Ollama stack on top.

## PicoClaw as a Lean Solution

PicoClaw solves exactly this problem: grab a Raspberry Pi Zero 2W for 15 euros, put PicoClaw on it, and you've got an AI agent that:

1. Communicates with you via Telegram
2. Queries your Home Assistant REST API
3. Controls entities
4. Runs cron jobs
5. Processes webhooks from HA

The entire stack boots in one second, draws barely any power, and runs stably 24/7. The actual AI intelligence comes from an external LLM provider — you only pay for what you actually use.

### Setup in Five Minutes

Download PicoClaw as a binary and start it with a simple config file:

```yaml
# picoclaw.yaml
telegram:
  token: "YOUR_BOT_TOKEN"
  allowed_users: [12345678]

llm:
  provider: openai
  model: gpt-4o-mini
  api_key: "sk-..."

tools:
  - name: ha_rest
    base_url: "http://homeassistant.local:8123"
    token: "YOUR_HA_LONG_LIVED_TOKEN"
```

Done. That's all it takes.

## Practical Use Cases

### 1. Voice-Controlled Automations via Telegram

You message your bot on Telegram: *"Turn off the office heating and tell me how warm it is right now."*

PicoClaw asks the LLM, the LLM decides: call the REST API, read the thermostat entity, turn off the heating. Response back to Telegram. There's no magic here — it's simply an AI agent with tool calling that understands your HA API.

### 2. Smart Notifications

Classic use case: you don't want to build every automation yourself. Instead, you give the agent some context:

> "If the kitchen window has been open for more than 30 minutes and the outside temperature is below 5°C, send me a Telegram message."

PicoClaw can periodically check the state via cron and notify you intelligently — not on every event, but *when it's actually relevant*.

### 3. Querying the HA REST API and Controlling Entities

The Home Assistant REST API is straightforward. PicoClaw can interact with it directly:

```bash
# Query the state of an entity
curl -s \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  http://homeassistant.local:8123/api/states/sensor.living_room_temperature

# Result (simplified):
# {
#   "state": "21.5",
#   "attributes": { "unit_of_measurement": "°C" }
# }

# Call a service — turn on a light
curl -s -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room"}' \
  http://homeassistant.local:8123/api/services/light/turn_on
```

PicoClaw gets this API as a tool, and the LLM decides on its own when and with which parameters to call it. You don't have to write any intents.

### 4. Cron Jobs for Energy Reports

A daily summary of yesterday's power consumption delivered to Telegram at 7:30 AM — sounds like a lot of work. With PicoClaw, it's a one-liner:

```yaml
crons:
  - schedule: "30 7 * * *"
    prompt: >
      Query the electricity meter (sensor.power_meter_yesterday_kwh) and 
      the solar yield (sensor.solar_yesterday_kwh).
      Write a short summary in English of whether we produced more 
      or consumed more power.
```

The LLM formats the report, calculates the difference, and you get a meaningful morning message instead of raw sensor values.

### 5. Webhook Trigger: HA → PicoClaw → Action

Home Assistant can fire webhooks — and PicoClaw can receive them. Example: when the motion sensor triggers at 3 AM, instead of a dumb notification, the agent should *evaluate* whether this is suspicious (is nobody home according to Presence Detection?) and react accordingly.

```yaml
# In Home Assistant: Automation
trigger:
  - platform: state
    entity_id: binary_sensor.hallway_motion
    to: "on"
action:
  - service: rest_command.picoclaw_webhook
    data:
      event: "motion_detected"
      sensor: "binary_sensor.hallway_motion"
      presence: "{{ states('input_boolean.someone_home') }}"
      time: "{{ now().strftime('%H:%M') }}"
```

PicoClaw receives the webhook, sends the data to the LLM, and it decides: trigger an alarm, turn on the lights, or simply ignore it. Context-based. Not rule-based.

## Technical Integration: HA Long-Lived Token

To access the HA REST API, you need a Long-Lived Access Token. You get it in HA under:

**Profile → Security → Long-Lived Access Tokens → Create Token**

Put this token in the PicoClaw config (or as an environment variable) and the agent can query all entities and call services — including triggering automations, starting scripts, and activating scenes.

```bash
# List all entities — useful for debugging
curl -s \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://homeassistant.local:8123/api/states | \
  python3 -m json.tool | head -50
```

A practical tip: create a dedicated user in HA for PicoClaw with restricted permissions. Not everything needs admin access.

## What PicoClaw Does *Not* Replace

Quick reality check: PicoClaw is not a replacement for Home Assistant. HA remains the heart of it all — the automations, the dashboards, device integrations, presence detection, history. All of that stays in HA.

PicoClaw is the intelligent assistant *alongside* it. The one you can message on Telegram, that understands context, that proactively keeps you informed, and that handles more complex requests without pre-configured intents.

**The combination is stronger than either part on its own.**

HA does what automations do best: respond reliably, fast, and locally. PicoClaw does what LLMs do best: understand natural language, consider context, write summaries.

## Conclusion

If you use Home Assistant and sometimes wish you could just *ask* instead of configure — give PicoClaw a try. Grab a Raspberry Pi Zero, install the binary, plug in your HA token, and you've got an AI assistant for your smart home in 10 minutes.

No large local LLM, no GPU server, no complex stack. Just a tiny Go binary doing the work while HA quietly keeps doing its job in the background.

GitHub: [sipeed/picoclaw](https://github.com/sipeed/picoclaw) | Website: [picoclaw.io](https://picoclaw.io)
