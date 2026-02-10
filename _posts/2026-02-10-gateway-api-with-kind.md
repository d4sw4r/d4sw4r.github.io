---
title: Kubernetes Gateway API with kind - A Practical Guide
description: Learn how to set up and use Kubernetes Gateway API in a local kind cluster. Covers installation, configuration, HTTPRoute examples, and comparison with Ingress.
date: 2026-02-10 19:00
categories: [kubernetes, networking]
tags: [kubernetes, gateway-api, kind, networking, ingress, envoy, cilium]
---

![Kubernetes Gateway API](/assets/img/gateway-api-kind.png "Gateway API with kind")

---

# Kubernetes Gateway API with kind: A Practical Guide

Gateway API is the next evolution of Kubernetes Ingress. It provides a more expressive, extensible, and role-oriented approach to managing traffic into your cluster. This guide walks through setting up Gateway API in a local kind cluster—perfect for learning and development.

## Why Gateway API?

Ingress has served Kubernetes well, but it has limitations. Different controllers implement annotations differently, there's no standard for TCP/UDP routing, and the model doesn't clearly separate concerns between cluster operators and application developers.

Gateway API addresses these issues:

- **Expressive**: Native support for header-based routing, traffic weighting, and request mirroring
- **Extensible**: Custom resources can extend functionality without annotation hacks
- **Role-oriented**: Clear separation between infrastructure providers, cluster operators, and application developers
- **Portable**: Consistent behavior across implementations

## Prerequisites

You'll need:

- Docker installed and running
- kind (Kubernetes in Docker) v0.20+
- kubectl configured
- Helm 3.x (for some controller installations)

## Setting Up the kind Cluster

First, create a kind cluster with port mappings for the gateway:

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

Verify it's running:

```bash
kubectl cluster-info --context kind-gateway-demo
```

## Installing Gateway API CRDs

Gateway API isn't installed by default. Install the standard channel CRDs:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml
```

This installs the core resources:

- **GatewayClass**: Defines the controller that implements the gateway
- **Gateway**: The actual load balancer/proxy instance
- **HTTPRoute**: Routes HTTP traffic to services
- **ReferenceGrant**: Allows cross-namespace references

Check the installed CRDs:

```bash
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

Gateway API is just a specification. You need a controller to implement it. Popular options:

| Controller | Pros | Best For |
|------------|------|----------|
| Envoy Gateway | Official Envoy project, feature-rich | Production, complex routing |
| Cilium | eBPF-based, high performance | CNI integration, observability |
| NGINX Gateway Fabric | Familiar NGINX backend | Teams with NGINX experience |
| Contour | Mature, well-documented | General purpose |
| Traefik | Easy setup, good dashboard | Development, smaller deployments |

For this guide, we'll use Envoy Gateway—it's the reference implementation and has excellent feature coverage.

## Installing Envoy Gateway

Install Envoy Gateway using Helm:

```bash
helm install eg oci://docker.io/envoyproxy/gateway-helm \
  --version v1.2.0 \
  -n envoy-gateway-system \
  --create-namespace
```

Wait for the deployment:

```bash
kubectl wait --timeout=5m -n envoy-gateway-system \
  deployment/envoy-gateway \
  --for=condition=Available
```

Verify the GatewayClass was created:

```bash
kubectl get gatewayclass
```

Output:

```
NAME    CONTROLLER                        ACCEPTED   AGE
eg      gateway.envoyproxy.io/gatewayclass-controller   True       60s
```

## Creating Your First Gateway

A Gateway represents the actual proxy that handles traffic. Create one:

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
```

The controller provisions a proxy. Check its status:

```bash
kubectl get gateway demo-gateway
```

When `PROGRAMMED` shows `True`, the gateway is ready:

```
NAME           CLASS   ADDRESS        PROGRAMMED   AGE
demo-gateway   eg      172.18.0.200   True         30s
```

## Deploying a Sample Application

Deploy a simple echo server:

```yaml
# echo-app.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echo
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: echo
  template:
    metadata:
      labels:
        app: echo
    spec:
      containers:
      - name: echo
        image: hashicorp/http-echo:1.0
        args:
        - "-text=Hello from Gateway API!"
        ports:
        - containerPort: 5678
---
apiVersion: v1
kind: Service
metadata:
  name: echo
  namespace: default
spec:
  selector:
    app: echo
  ports:
  - port: 80
    targetPort: 5678
```

Apply:

```bash
kubectl apply -f echo-app.yaml
```

## Creating an HTTPRoute

Now connect the gateway to your service with an HTTPRoute:

```yaml
# httproute.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: echo-route
  namespace: default
spec:
  parentRefs:
  - name: demo-gateway
  hostnames:
  - "echo.local"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: echo
      port: 80
```

Apply:

```bash
kubectl apply -f httproute.yaml
```

Test it (add `echo.local` to `/etc/hosts` pointing to 127.0.0.1 or use the Host header):

```bash
curl -H "Host: echo.local" http://localhost
```

Response:

```
Hello from Gateway API!
```

## Advanced Routing Examples

Gateway API's strength is expressive routing. Here are practical examples.

### Header-Based Routing

Route traffic based on request headers:

```yaml
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
        value: v2
    backendRefs:
    - name: api-v2
      port: 80
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: api-v1
      port: 80
```

Requests with `X-Version: v2` header go to `api-v2`, others go to `api-v1`.

### Traffic Splitting (Canary Deployments)

Gradually shift traffic between versions:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: canary-route
spec:
  parentRefs:
  - name: demo-gateway
  hostnames:
  - "app.local"
  rules:
  - backendRefs:
    - name: app-stable
      port: 80
      weight: 90
    - name: app-canary
      port: 80
      weight: 10
```

90% of traffic goes to stable, 10% to canary. Adjust weights as confidence grows.

### Path Rewriting

Rewrite paths before forwarding:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: rewrite-route
spec:
  parentRefs:
  - name: demo-gateway
  hostnames:
  - "api.local"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api/v1
    filters:
    - type: URLRewrite
      urlRewrite:
        path:
          type: ReplacePrefixMatch
          replacePrefixMatch: /
    backendRefs:
    - name: backend
      port: 80
```

Requests to `/api/v1/users` get forwarded as `/users`.

### Request Header Modification

Add or modify headers:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: header-mod-route
spec:
  parentRefs:
  - name: demo-gateway
  rules:
  - filters:
    - type: RequestHeaderModifier
      requestHeaderModifier:
        add:
        - name: X-Gateway
          value: "envoy"
        remove:
        - X-Debug
    backendRefs:
    - name: backend
      port: 80
```

## TLS Configuration

For HTTPS, create a certificate secret and update the gateway:

```bash
# Generate self-signed cert for testing
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=*.local"

kubectl create secret tls demo-tls --cert=tls.crt --key=tls.key
```

Update the gateway:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: demo-gateway
spec:
  gatewayClassName: eg
  listeners:
  - name: http
    protocol: HTTP
    port: 80
  - name: https
    protocol: HTTPS
    port: 443
    tls:
      mode: Terminate
      certificateRefs:
      - name: demo-tls
    allowedRoutes:
      namespaces:
        from: All
```

## Cross-Namespace References

By default, routes can only reference services in the same namespace. To allow cross-namespace references, create a ReferenceGrant:

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-from-default
  namespace: backend-ns
spec:
  from:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    namespace: default
  to:
  - group: ""
    kind: Service
```

This allows HTTPRoutes in `default` namespace to reference Services in `backend-ns`.

## Gateway API vs Ingress

| Feature | Ingress | Gateway API |
|---------|---------|-------------|
| Header routing | Annotation-dependent | Native |
| Traffic splitting | Not standard | Native (weights) |
| TCP/UDP routing | Not supported | GRPCRoute, TCPRoute |
| Role separation | Single resource | GatewayClass/Gateway/Route |
| Cross-namespace | Limited | ReferenceGrant |
| Request modification | Annotation hacks | Native filters |

## Troubleshooting

Common issues and solutions:

**Gateway stuck in "Pending"**

Check controller logs:

```bash
kubectl logs -n envoy-gateway-system deployment/envoy-gateway
```

**Route not working**

Verify route attachment:

```bash
kubectl describe httproute echo-route
```

Look for `Accepted: True` in status conditions.

**Connection refused**

Ensure port mappings in kind config match gateway listeners:

```bash
docker port gateway-demo-control-plane
```

## Cleanup

Remove everything:

```bash
kind delete cluster --name gateway-demo
```

## Conclusion

Gateway API represents a significant improvement over Ingress. The role-oriented design, expressive routing, and consistent behavior across implementations make it worth adopting.

For local development, kind provides a practical environment to learn these concepts. The patterns shown here—traffic splitting, header routing, path rewriting—translate directly to production clusters.

Start with simple HTTPRoutes. Add complexity as needed. The API is designed to grow with your requirements.

## Further Reading

- [Gateway API Documentation](https://gateway-api.sigs.k8s.io/)
- [Envoy Gateway Docs](https://gateway.envoyproxy.io/)
- [Gateway API Implementations](https://gateway-api.sigs.k8s.io/implementations/)
- [GEP Index](https://gateway-api.sigs.k8s.io/geps/overview/) (Gateway Enhancement Proposals)
