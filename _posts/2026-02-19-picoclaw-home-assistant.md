---
title: "PicoClaw + Home Assistant: Ein KI-Agent für dein Smart Home"
description: "PicoClaw ist ein ultraleichter AI-Agent in Go, der auf $10-Hardware läuft. Wie er Home Assistant perfekt ergänzt — ohne Cloud, ohne Overhead."
date: 2026-02-19 10:00
categories: [ai, smarthome]
tags: ["ai", "homeassistant", "picoclaw", "smarthome", "automation"]
---

![PicoClaw Home Assistant](/assets/img/picoclaw-ha.png "PicoClaw + Home Assistant")

---

# PicoClaw + Home Assistant: Ein KI-Agent für dein Smart Home

Ich liebe Home Assistant. Wirklich. Aber Hand aufs Herz: Sobald du anfängst, AI in dein Smart Home zu integrieren, wird es schnell unübersichtlich, ressourcenhungrig — und ehrlich gesagt — nervig. Genau da kommt [PicoClaw](https://picoclaw.io) ins Spiel.

## Was ist PicoClaw?

PicoClaw ist ein ultraleichter AI-Agent, entwickelt von Sipeed, komplett in Go geschrieben. Das Besondere: Er läuft auf Hardware, die du für 10 Dollar kaufst. Raspberry Pi Zero, LicheeRV-Nano, ein vergessener SBC in der Schublade — alles kein Problem. Der Ressourcenbedarf ist absurd gering: **unter 10 MB RAM**, **Boot in unter einer Sekunde**, und er läuft auf RISC-V, ARM und x86_64.

Die Kommunikation läuft über Telegram oder Discord. LLM-Anfragen werden an externe Provider (OpenAI, Anthropic, etc.) via API-Key weitergegeben — du bringst also dein eigenes Gehirn mit. Das GitHub-Repo findest du unter [sipeed/picoclaw](https://github.com/sipeed/picoclaw).

Inspiriert vom ursprünglichen nanobot-Projekt, aber komplett in Go neu geschrieben. Sauber, schlank, und direkt auf den Punkt.

## Das Problem mit AI in Home Assistant

Home Assistant hat in den letzten Jahren ordentlich aufgeholt. Es gibt Integrationen für OpenAI, lokale LLMs via Ollama, Assist-Pipelines — alles da. Aber:

**Das Problem ist die Komplexität.** Eine sauber laufende AI-Assist-Pipeline braucht:
- Einen lokalen Whisper-Container für Speech-to-Text (RAM: locker 2–4 GB)
- Piper für Text-to-Speech
- Ollama für lokale Inferenz (wenn du keine Cloud willst) — nochmal 4–8 GB
- Konversationsagenten, die korrekt konfiguriert sein wollen
- Intents, die du selbst definieren musst

Das ist alles machbar. Aber wenn du nur willst, dass dir dein Smart Home auf Telegram schreibt *"Die Temperatur im Keller ist seit 3 Stunden unter 10°C"* oder du tippen kannst *"Licht im Wohnzimmer aus"* — brauchst du das alles nicht.

Und auf einem Raspberry Pi 4, auf dem HA schon ordentlich zu tun hat, willst du keinen Ollama-Stack draufpacken.

## PicoClaw als schlanke Lösung

PicoClaw löst genau dieses Problem: Du nimmst einen Raspberry Pi Zero 2W für 15 Euro, steckst PicoClaw drauf, und hast einen AI-Agent, der:

1. Über Telegram mit dir kommuniziert
2. Deine Home Assistant REST API abfragt
3. Entitäten steuert
4. Cron-Jobs ausführt
5. Webhooks von HA verarbeitet

Der gesamte Stack bootet in einer Sekunde, zieht kaum Strom, und läuft stabil im Dauerbetrieb. Die eigentliche KI-Intelligenz kommt von einem externen LLM-Provider — du zahlst nur, was du tatsächlich nutzt.

### Setup in fünf Minuten

PicoClaw per Binary herunterladen und mit einer simplen Config-Datei starten:

```yaml
# picoclaw.yaml
telegram:
  token: "DEIN_BOT_TOKEN"
  allowed_users: [12345678]

llm:
  provider: openai
  model: gpt-4o-mini
  api_key: "sk-..."

tools:
  - name: ha_rest
    base_url: "http://homeassistant.local:8123"
    token: "DEIN_HA_LONG_LIVED_TOKEN"
```

Fertig. Mehr braucht es nicht.

## Konkrete Anwendungsfälle

### 1. Sprachgesteuerte Automatisierungen via Telegram

Du schreibst deinem Bot auf Telegram: *"Mach die Heizung im Büro aus und sag mir, wie warm es gerade ist."*

PicoClaw fragt das LLM, das LLM entscheidet: REST API aufrufen, Thermostat-Entität lesen, Heizung abschalten. Antwort zurück an Telegram. Das ist kein Magic — das ist einfach ein AI-Agent mit Tool-Calling, der deine HA-API versteht.

### 2. Smarte Benachrichtigungen

Klassischer Use Case: Du willst nicht jede Automation selbst bauen. Stattdessen gibst du dem Agenten Kontext:

> "Wenn das Küchenfenster seit mehr als 30 Minuten offen ist und die Außentemperatur unter 5°C liegt, schick mir eine Telegram-Nachricht."

PicoClaw kann per Cron periodisch den Zustand prüfen und intelligent benachrichtigen — nicht einfach bei jedem Event, sondern *wenn es wirklich relevant ist*.

### 3. HA REST API abfragen und Entitäten steuern

Die Home Assistant REST API ist straightforward. PicoClaw kann direkt damit interagieren:

```bash
# Zustand einer Entität abfragen
curl -s \
  -H "Authorization: Bearer DEIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://homeassistant.local:8123/api/states/sensor.living_room_temperature

# Ergebnis (vereinfacht):
# {
#   "state": "21.5",
#   "attributes": { "unit_of_measurement": "°C" }
# }

# Service aufrufen — Licht einschalten
curl -s -X POST \
  -H "Authorization: Bearer DEIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.wohnzimmer"}' \
  http://homeassistant.local:8123/api/services/light/turn_on
```

PicoClaw bekommt diese API als Tool, das LLM entscheidet selbst, wann und mit welchen Parametern es aufgerufen wird. Du musst keine Intents schreiben.

### 4. Cron-Jobs für Energieberichte

Jeden Morgen um 7:30 Uhr eine Zusammenfassung des gestrigen Stromverbrauchs direkt auf Telegram — das klingt nach viel Arbeit. Mit PicoClaw ist es ein Einzeiler:

```yaml
crons:
  - schedule: "30 7 * * *"
    prompt: >
      Frage den Stromzähler (sensor.stromzaehler_gestern_kwh) und 
      den Solarertrag (sensor.solar_gestern_kwh) ab.
      Schreib eine kurze Zusammenfassung auf Deutsch, ob wir mehr 
      produziert oder verbraucht haben.
```

Das LLM formatiert den Bericht, rechnet die Differenz aus, und du kriegst morgens eine sinnvolle Nachricht statt roher Sensorwerte.

### 5. Webhook-Trigger: HA → PicoClaw → Aktion

Home Assistant kann Webhooks feuern — und PicoClaw kann sie empfangen. Beispiel: Wenn der Bewegungsmelder nachts um 3 Uhr anschlägt, soll nicht einfach eine stupide Notification kommen, sondern der Agent soll *einschätzen*, ob das verdächtig ist (niemand ist laut Presence Detection zu Hause?) und entsprechend reagieren.

```yaml
# In Home Assistant: Automation
trigger:
  - platform: state
    entity_id: binary_sensor.bewegungsmelder_flur
    to: "on"
action:
  - service: rest_command.picoclaw_webhook
    data:
      event: "motion_detected"
      sensor: "binary_sensor.bewegungsmelder_flur"
      presence: "{{ states('input_boolean.jemand_zuhause') }}"
      time: "{{ now().strftime('%H:%M') }}"
```

PicoClaw empfängt den Webhook, schickt die Daten ans LLM, und das entscheidet: Alarm auslösen, Licht anmachen, oder einfach ignorieren. Kontextbasiert. Nicht regelbasiert.

## Technische Integration: HA Long-Lived Token

Für den Zugriff auf die HA REST API brauchst du einen Long-Lived Access Token. Den holst du dir in HA unter:

**Profil → Sicherheit → Long-Lived Access Tokens → Token erstellen**

Diesen Token packst du in die PicoClaw-Config (oder als Umgebungsvariable) und schon kann der Agent alle Entitäten abfragen und Services aufrufen — inklusive Automationen triggern, Skripte starten, Szenen aktivieren.

```bash
# Alle Entitäten auflisten — gut zum Debuggen
curl -s \
  -H "Authorization: Bearer DEIN_TOKEN" \
  http://homeassistant.local:8123/api/states | \
  python3 -m json.tool | head -50
```

Ein Tipp aus der Praxis: Leg dir in HA einen dedizierten User für PicoClaw an, mit eingeschränkten Rechten. Nicht alles braucht Admin-Zugriff.

## Was PicoClaw *nicht* ersetzt

Kurz zur Einordnung: PicoClaw ist kein Ersatz für Home Assistant. HA bleibt das Herzstück — die Automationen, die Dashboards, die Geräteintegration, die Presence Detection, die History. Das alles bleibt in HA.

PicoClaw ist der intelligente Assistent *daneben*. Der Typ, dem du auf Telegram schreiben kannst, der Kontext versteht, der proaktiv Bescheid gibt, und der komplexere Anfragen ohne vorkonfigurierte Intents versteht.

**Die Kombination ist stärker als beide Teile einzeln.**

HA macht was Automations am besten können: zuverlässig, schnell, lokal reagieren. PicoClaw macht was LLMs am besten können: natürliche Sprache verstehen, Kontext berücksichtigen, Zusammenfassungen schreiben.

## Fazit

Wenn du Home Assistant nutzt und dir manchmal wünschst, du könntest einfach *fragen* statt zu konfigurieren — probier PicoClaw aus. Schnapp dir einen Raspberry Pi Zero, installiere die Binary, trag deinen HA-Token ein, und du hast in 10 Minuten einen KI-Assistenten für dein Smart Home.

Kein großes LLM lokal, kein GPU-Server, kein komplexer Stack. Nur ein winziger Go-Binary, der die Arbeit macht, während HA im Hintergrund weiter seinen Job erledigt.

GitHub: [sipeed/picoclaw](https://github.com/sipeed/picoclaw) | Website: [picoclaw.io](https://picoclaw.io)
