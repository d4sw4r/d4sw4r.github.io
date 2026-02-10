---
title: "Getting Started with Kubernetes Gateway API and kind"
date: 2026-02-10 19:00:00 +0000
categories: [Kubernetes, Networking]
tags: [kubernetes, gateway-api, kind, ingress, networking]
image:
  path: /assets/img/2026-02-10-gateway-api.png
  alt: Kubernetes Gateway API Architecture
---

## Introduction

The Kubernetes Gateway API represents a significant evolution in how we handle ingress traffic in Kubernetes clusters. While the traditional Ingress resource has served us well, the Gateway API offers a more expressive, extensible, and role-oriented approach to managing external traffic.

In this guide, we'll set up a local Kubernetes cluster using kind (Kubernetes IN Docker), install a Gateway API implementation, and walk through practical examples that demonstrate the power and flexibility of this new standard.

## Why Gateway API Over Ingress?

Before diving into the hands-on portion, let's understand why the Kubernetes community developed the Gateway API:

### Limitations of Ingress

The Ingress resource was designed to be simple. Perhaps too simple. Here are its key limitations:

- **Annotation hell**: Advanced features require vendor-specific annotations
- **Limited protocol support**: Primarily HTTP/HTTPS, with poor TCP/UDP support
- **No traffic splitting**: Native canary deployments aren't possible
- **Flat structure**: No separation between infrastructure and application concerns

### Gateway API Advantages

The Gateway API addresses these limitations through a layered resource model:

| Aspect | Ingress | Gateway API |
|--------|---------|-------------|
| Role separation | Single resource | GatewayClass → Gateway → Routes |
| Protocol support | HTTP/HTTPS only | HTTP, TCP, UDP, gRPC, TLS |
| Traffic management | Via annotations | Native weight-based routing |
| Extensibility | Annotations | Policy attachments |
| Portability | Vendor-specific | Standardized across implementations |

## Prerequisites

Before we start, ensure you have the following installed:

- Docker (running)
- kind v0.20.0 or later
- kubectl v1.28 or later
- Helm v3.x (optional, but recommended)

```bash
# Verify installations
docker --version
kind --version
kubectl version --client
```

## Setting Up a kind Cluster

Let's create a kind cluster with extra port mappings for our Gateway:

```yaml
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
```

Create the cluster:

```bash
kind create cluster --name gateway-demo --config kind-config.yaml
```

Verify the cluster is running:

```bash
kubectl cluster-info --context kind-gateway-demo
kubectl get nodes
```

## Installing Gateway API CRDs

The Gateway API resources are not included in Kubernetes by default. We need to install the Custom Resource Definitions (CRDs):

```bash
# Install the standard channel CRDs (stable APIs)
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml

# Verify the CRDs are installed
kubectl get crds | grep gateway
```

You should see:

```
gatewayclasses.gateway.networking.k8s.io
gateways.gateway.networking.k8s.io
httproutes.gateway.networking.k8s.io
referencegrants.gateway.networking.k8s.io
```

## Choosing a Gateway Controller

The Gateway API is just a specification. You need a controller to implement it. Popular options include:

- **Envoy Gateway**: CNCF project, Envoy-based
- **Cilium**: eBPF-based, excellent performance
- **NGINX Gateway Fabric**: NGINX-backed
- **Contour**: Envoy-based, mature project
- **Traefik**: Popular choice with broad feature set

For this tutorial, we'll use **Envoy Gateway** as it's a CNCF project with excellent Gateway API support:

```bash
# Install Envoy Gateway using Helm
helm install eg oci://docker.io/envoyproxy/gateway-helm \
  --version v1.2.0 \
  -n envoy-gateway-system \
  --create-namespace

# Wait for the deployment
kubectl wait --timeout=5m -n envoy-gateway-system \
  deployment/envoy-gateway \
  --for=condition=Available
```

Verify the GatewayClass is available:

```bash
kubectl get gatewayclass
```

## Understanding the Resource Model

The Gateway API uses a three-tier model:

```
┌─────────────────────────────────────────────────────────────┐
│  GatewayClass                                               │
│  (Infrastructure Provider - "What kind of gateway?")        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Gateway                                                    │
│  (Cluster Operator - "Where to listen?")                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  HTTPRoute / TCPRoute / GRPCRoute                           │
│  (Application Developer - "How to route?")                  │
└─────────────────────────────────────────────────────────────┘
```

This separation allows different teams to manage their respective concerns without stepping on each other's toes.

## Creating Your First Gateway

Let's create a Gateway that listens on port 80:

```yaml
# gateway.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: demo-gateway
  namespace: default
spec:
  gatewayClassName: eg
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All
```

Apply it:

```bash
kubectl apply -f gateway.yaml

# Check the Gateway status
kubectl get gateway demo-gateway
```

Wait until the Gateway shows `Programmed: True`:

```bash
kubectl wait --for=condition=Programmed gateway/demo-gateway --timeout=2m
```

## Deploying a Sample Application

Let's deploy a simple application to route traffic to:

```yaml
# app.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: httpbin
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: httpbin
  template:
    metadata:
      labels:
        app: httpbin
    spec:
      containers:
      - name: httpbin
        image: kennethreitz/httpbin
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: httpbin
  namespace: default
spec:
  selector:
    app: httpbin
  ports:
  - port: 80
    targetPort: 80
```

```bash
kubectl apply -f app.yaml
kubectl wait --for=condition=Available deployment/httpbin --timeout=2m
```

## Creating an HTTPRoute

Now let's create an HTTPRoute to expose our application:

```yaml
# httproute.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: httpbin-route
  namespace: default
spec:
  parentRefs:
  - name: demo-gateway
  hostnames:
  - "httpbin.local"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: httpbin
      port: 80
```

```bash
kubectl apply -f httproute.yaml
```

Test the route:

```bash
# Add host entry (or use curl with Host header)
curl -H "Host: httpbin.local" http://localhost/get
```

## Advanced Routing: Traffic Splitting

One powerful feature is native traffic splitting for canary deployments:

```yaml
# canary-route.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: canary-route
  namespace: default
spec:
  parentRefs:
  - name: demo-gateway
  hostnames:
  - "app.local"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: app-stable
      port: 80
      weight: 90
    - name: app-canary
      port: 80
      weight: 10
```

This sends 90% of traffic to the stable version and 10% to the canary—no annotations required.

## Header-Based Routing

Route traffic based on headers:

```yaml
# header-route.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: header-route
spec:
  parentRefs:
  - name: demo-gateway
  hostnames:
  - "api.local"
  rules:
  - matches:
    - headers:
      - name: X-Version
        value: beta
    backendRefs:
    - name: api-beta
      port: 80
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: api-stable
      port: 80
```

## TLS Configuration

Adding TLS is straightforward:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: secure-gateway
spec:
  gatewayClassName: eg
  listeners:
  - name: https
    protocol: HTTPS
    port: 443
    tls:
      mode: Terminate
      certificateRefs:
      - kind: Secret
        name: tls-secret
    allowedRoutes:
      namespaces:
        from: All
```

## Best Practices

Based on production experience, here are key recommendations:

### 1. Use Namespaces for Isolation

Separate Gateway resources by environment or team:

```bash
kubectl create namespace gateway-prod
kubectl create namespace gateway-staging
```

### 2. Leverage ReferenceGrants

Control cross-namespace references explicitly:

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-gateway-to-backend
  namespace: backend-ns
spec:
  from:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    namespace: routes-ns
  to:
  - group: ""
    kind: Service
```

### 3. Monitor Gateway Status

Always check conditions:

```bash
kubectl get gateway -o jsonpath='{.items[*].status.conditions}'
```

### 4. Start with Standard Channel

Use the stable APIs first. Experimental features are in the experimental channel but may change.

### 5. Test Locally First

kind makes it easy to validate configurations before deploying to production.

## Cleanup

When you're done experimenting:

```bash
kind delete cluster --name gateway-demo
```

## Conclusion

The Gateway API represents the future of Kubernetes ingress. Its role-oriented design, native traffic management, and standardized approach make it a compelling upgrade from the traditional Ingress resource.

Starting with a local kind cluster, you can explore all features risk-free before implementing them in production. The transition from Ingress to Gateway API can be gradual—both can coexist in the same cluster.

The ecosystem is mature enough for production use, with multiple implementations available. Whether you choose Envoy Gateway, Cilium, or another controller, the core concepts remain the same.

## Further Reading

- [Gateway API Official Documentation](https://gateway-api.sigs.k8s.io/)
- [Envoy Gateway Docs](https://gateway.envoyproxy.io/)
- [kind Documentation](https://kind.sigs.k8s.io/)
- [Gateway API Implementations](https://gateway-api.sigs.k8s.io/implementations/)
