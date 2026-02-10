---
title: Deploying OpenClaw on Kubernetes - Your AI Assistant in the Cloud
description: Complete guide to deploying OpenClaw AI assistant on Kubernetes. Includes manifests for ConfigMaps, Secrets, PVCs, Deployments, and security best practices.
date: 2026-02-09 15:00
categories: [kubernetes, devops]
tags: [kubernetes, k8s, openclaw, ai, assistant, deployment, docker, helm]
---

![OpenClaw Kubernetes Deployment](/assets/img/openclaw-k8s.png "OpenClaw on Kubernetes")

---

# Deploying OpenClaw on Kubernetes: Your AI Assistant in the Cloud

In this guide, we'll explore how to deploy OpenClaw, a powerful personal AI assistant, on a Kubernetes cluster. While OpenClaw doesn't have an official Helm chart yet, we can deploy it using standard Kubernetes manifests with some smart configurations.

## What is OpenClaw?

OpenClaw is a personal AI assistant that you run on your own infrastructure. It connects to various messaging platforms (Discord, Telegram, WhatsApp, Slack) and provides a local-first approach to AI assistance. Think of it as your own ChatGPT that you control completely.

**Key features:**
- Multi-channel support (Discord, Telegram, WhatsApp, etc.)
- Browser control and automation
- Local file system access
- Voice integration
- Skills/plugins system
- Complete data privacy (runs on your infrastructure)

## Prerequisites

Before we start, make sure you have:

- A running Kubernetes cluster (k3s, k8s, or any managed service)
- `kubectl` configured and connected to your cluster
- Basic understanding of Kubernetes concepts
- OpenClaw configuration (we'll create this)

## Architecture Overview

Our Kubernetes deployment will consist of:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   ConfigMap     │    │   Deployment     │    │    Service      │
│  (Config Files) │    │  (OpenClaw Pod)  │    │ (Internal LB)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌──────────────────┐
                    │ PersistentVolume │
                    │   (Workspace)    │
                    └──────────────────┘
```

## Step 1: Create the Namespace

First, let's create a dedicated namespace for OpenClaw:

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: openclaw
  labels:
    name: openclaw
```

Apply it:
```bash
kubectl apply -f namespace.yaml
```

## Step 2: Configuration Management

OpenClaw needs configuration for models, channels, and authentication. We'll use ConfigMaps and Secrets:

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: openclaw-config
  namespace: openclaw
data:
  openclaw.json: |
    {
      "agents": {
        "defaults": {
          "workspace": "/home/openclaw/.openclaw/workspace",
          "model": {
            "primary": "anthropic/claude-sonnet-4-20250514"
          },
          "models": {
            "anthropic/claude-sonnet-4-20250514": {}
          }
        }
      },
      "gateway": {
        "mode": "local",
        "auth": {
          "mode": "token",
          "token": "YOUR_GATEWAY_TOKEN_HERE"
        },
        "port": 18789,
        "bind": "0.0.0.0"
      },
      "auth": {
        "profiles": {
          "anthropic:default": {
            "provider": "anthropic",
            "mode": "token"
          }
        }
      },
      "channels": {
        "discord": {
          "enabled": true,
          "token": "YOUR_DISCORD_BOT_TOKEN"
        }
      },
      "plugins": {
        "entries": {
          "discord": {
            "enabled": true
          }
        }
      }
    }
```

For sensitive data like API tokens, use Secrets:

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: openclaw-secrets
  namespace: openclaw
type: Opaque
stringData:
  anthropic-api-key: "YOUR_ANTHROPIC_API_KEY"
  discord-bot-token: "YOUR_DISCORD_BOT_TOKEN"
  gateway-token: "YOUR_GATEWAY_TOKEN"
```

## Step 3: Persistent Storage

OpenClaw needs persistent storage for its workspace and data:

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: openclaw-workspace
  namespace: openclaw
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: local-path  # Adjust for your cluster
```

## Step 4: Deployment Configuration

Now for the main deployment. OpenClaw runs as a single container with the gateway:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openclaw
  namespace: openclaw
  labels:
    app: openclaw
spec:
  replicas: 1  # OpenClaw is designed for single instance
  selector:
    matchLabels:
      app: openclaw
  template:
    metadata:
      labels:
        app: openclaw
    spec:
      containers:
      - name: openclaw
        image: ghcr.io/openclaw/openclaw:latest  # Use specific tag in production
        ports:
        - containerPort: 18789
          name: gateway
        env:
        - name: NODE_ENV
          value: "production"
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: openclaw-secrets
              key: anthropic-api-key
        - name: DISCORD_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: openclaw-secrets
              key: discord-bot-token
        volumeMounts:
        - name: config
          mountPath: /home/openclaw/.openclaw/openclaw.json
          subPath: openclaw.json
        - name: workspace
          mountPath: /home/openclaw/.openclaw/workspace
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 18789
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 18789
          initialDelaySeconds: 15
          periodSeconds: 5
      volumes:
      - name: config
        configMap:
          name: openclaw-config
      - name: workspace
        persistentVolumeClaim:
          claimName: openclaw-workspace
      securityContext:
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
```

## Step 5: Service Exposure

Create a service to expose OpenClaw internally:

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: openclaw-service
  namespace: openclaw
  labels:
    app: openclaw
spec:
  selector:
    app: openclaw
  ports:
  - name: gateway
    port: 18789
    targetPort: 18789
  type: ClusterIP
```

For external access (optional), create an Ingress:

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: openclaw-ingress
  namespace: openclaw
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    # Add TLS/SSL annotations as needed
spec:
  rules:
  - host: openclaw.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: openclaw-service
            port:
              number: 18789
```

## Step 6: Deployment

Deploy everything in order:

```bash
# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml
kubectl apply -f configmap.yaml
kubectl apply -f pvc.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml  # Optional
```

Check the deployment:

```bash
# Check pod status
kubectl get pods -n openclaw

# Check logs
kubectl logs -n openclaw deployment/openclaw -f

# Check services
kubectl get svc -n openclaw
```

## Step 7: Initial Setup

Once running, you'll need to complete the initial setup:

```bash
# Get a shell in the pod
kubectl exec -it -n openclaw deployment/openclaw -- /bin/bash

# Run the onboarding wizard
/app/openclaw.mjs onboard

# Or configure manually
/app/openclaw.mjs configure
```

## Security Considerations

1. **Network Policies**: Implement network policies to restrict pod communication
2. **RBAC**: Use proper service accounts with minimal permissions
3. **Secrets Management**: Use external secret management (e.g., Vault, Sealed Secrets)
4. **Pod Security Standards**: Apply pod security standards

Example Network Policy:

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: openclaw-network-policy
  namespace: openclaw
spec:
  podSelector:
    matchLabels:
      app: openclaw
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx  # Adjust for your ingress
    ports:
    - protocol: TCP
      port: 18789
  egress:
  - {}  # Allow all egress (OpenClaw needs to reach AI APIs)
```

## Monitoring and Observability

Add monitoring with Prometheus and Grafana:

```yaml
# servicemonitor.yaml (if using Prometheus Operator)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: openclaw
  namespace: openclaw
spec:
  selector:
    matchLabels:
      app: openclaw
  endpoints:
  - port: gateway
    path: /metrics
    interval: 30s
```

## Scaling Considerations

OpenClaw is designed as a single-user assistant, so scaling horizontally isn't typically needed. However, consider:

1. **Vertical Scaling**: Increase CPU/memory based on usage
2. **Storage**: Monitor workspace growth and adjust PVC size
3. **Multiple Instances**: Deploy separate instances for different users/teams

## Creating a Helm Chart (Future)

While we used raw manifests, you could package this as a Helm chart:

```
openclaw-chart/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   └── ingress.yaml
└── README.md
```

## Troubleshooting

Common issues and solutions:

1. **Pod not starting**: Check resource limits and node capacity
2. **Configuration errors**: Verify ConfigMap and Secret values
3. **Storage issues**: Ensure PVC is bound and accessible
4. **Network connectivity**: Check service and ingress configuration

```bash
# Debugging commands
kubectl describe pod -n openclaw
kubectl logs -n openclaw deployment/openclaw --previous
kubectl get events -n openclaw --sort-by=.metadata.creationTimestamp
```

## Conclusion

Deploying OpenClaw on Kubernetes gives you a scalable, production-ready AI assistant that you fully control. While the setup requires some Kubernetes knowledge, the benefits of having your own AI assistant running in your infrastructure are significant:

- **Complete data privacy**
- **Customizable and extensible**
- **Integration with your existing tools and workflows**
- **Cost control** (only pay for what you use)

The configuration shown here provides a solid foundation that you can customize based on your specific needs. As OpenClaw evolves, we might see official Helm charts and operators, but this manual approach gives you full control over the deployment.

## Next Steps

- Set up monitoring and alerting
- Configure additional channels (Telegram, Slack, etc.)
- Explore OpenClaw skills and plugins
- Implement backup strategies for the workspace
- Consider GitOps for configuration management

Happy deploying! 🦞

---

*Have questions or found improvements? Feel free to reach out or submit a PR to this blog's [repository](https://github.com/d4sw4r/d4sw4r.github.io).*