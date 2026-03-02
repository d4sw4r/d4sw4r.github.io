---
layout: post
title: "Homelab Monitoring with Prometheus & Grafana"
date: 2026-03-02 22:00:00 +0100
categories: [homelab, monitoring, infrastructure]
tags: [prometheus, grafana, monitoring, docker]
image: /assets/img/homelab-monitoring-grafana.png
---

## Why Monitor Your Homelab?

Running a homelab without monitoring is like flying blind. You don't know when services go down, resources run low, or performance degrades until it's too late. This post covers setting up a robust monitoring stack using Prometheus and Grafana.

## The Stack

- **Prometheus**: Time-series database for metrics collection
- **Grafana**: Visualization and alerting platform
- **Node Exporter**: System-level metrics (CPU, memory, disk)
- **cAdvisor**: Container metrics

## Setup with Docker Compose

```yaml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  prometheus_data:
  grafana_data:
```

## Key Metrics to Watch

1. **CPU Usage**: Spikes indicate resource contention
2. **Memory Utilization**: OOM kills are silent killers
3. **Disk I/O**: Storage bottlenecks slow everything down
4. **Network Throughput**: Unexpected traffic patterns

## Dashboards Worth Importing

- Node Exporter Full (ID: 1860)
- Docker Monitoring (ID: 893)
- Prometheus Stats (ID: 3662)

## Alerting Rules

Don't just collect metrics—act on them:

```yaml
groups:
  - name: homelab-alerts
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        annotations:
          summary: "High CPU usage detected"
```

## Final Thoughts

Monitoring isn't optional for serious homelabs. Start with the basics, iterate based on what breaks, and gradually build comprehensive coverage. Your future self will thank you when troubleshooting at 2 AM.

---

*Cover image generated with DALL-E 3*
