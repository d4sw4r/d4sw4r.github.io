---
title: Deploy Prometheus to k8s with operator using kustomize
date: 2024-02-13 17:10
categories: [k8s, kubernetes, k3s, prometheus, alertmanager, kustomize]
tags: [kubernetes, k8s , prometheus, alertmanager, kustomize]     # TAG names should always be lowercase
---


![Tkubernetes is beautiful!](https://avatars.githubusercontent.com/u/66682517?s=280&v=4 "Prometheus-operator")

---
# Deploy Prometheus to k8s with operator using kustomize

When it comes to deploy Prometheus in kubernetes environment there is no better solution then using an operator. Sadly most operator projects ship a lot of predefined rules and configs which not fit your needs. To get the best out of the Prometheus operator I highly recommend to build up your own deployment with the operator instead of using a prebuild solution you don´t understand.

And here is how we are going to install our own operator including CRDs and minimal subsystems. You can find all the code in my [prometheus-operator-example](https://github.com/d4sw4r/prometheus-operator-example) repository.

## 1. Research
First I tried to find some useful docs and examples, but there was not much information. Most Blogs and Tutorials are just using the **kube-prometheus** or **helm chart**. So here is what I used to build up everything:
 - [prometheus-operator-docs](https://github.com/prometheus-operator/prometheus-operator)
 - [prometheus-operator-repo](https://prometheus-operator.dev/docs/prologue/introduction/)
 - [kube-prometheus](https://github.com/prometheus-operator/kube-prometheus)

## 2. How to deploy?
I choose to pick **kustomize** for the deployment of all my components, since its **kubectl** native and offers great ways to structure the code. While it´s also easy to maintain and helps to extend our subsystems.

## 3. Lets put it together
### Custom Resource Definitions for the operator
The very first step is to deploy the CRDs needed by the operator, which can be found here [operator repo](https://github.com/prometheus-operator/prometheus-operator/tree/main/example/prometheus-operator-crd-full). These CRDs are needed by the operator to deploy our services. 

***IMPORTANT NOTE:*** You can strip down the amount of CRDs which are deployed and only deploy the ones you need, but the operator would log constantly many errors that CRDs are not found. So I recommend to deploy all of them.

### Deploy operator itself
The operator itself is a normal container deployment, but here I recommend to deploy it with a service account and also a Role / Rolebinding to be able to fetch scrapeconfigs from different namespaces later on aswell. All needed files can be found here [operator-files](https://github.com/d4sw4r/prometheus-operator-example/tree/main/base/operator)

### Deploy Prometheus
For Prometheus we also deploy a service account and rules to read scrapeconfigs from different namespaces. All needed files are in `base/prometheus`.

### Deploy other ressources
The example deployment contains alertmanager which is also deployed as a CRD and blackbox-exporter which is a normal Deployment kind.

## Running the example in minikube
```bash
git clone https://github.com/d4sw4r/prometheus-operator-example

cd prometheus-operator-example
```
```bash
minikube start --driver=docker
```
```bash
kubectl get nodes -o wide

NAME       STATUS   ROLES           AGE   VERSION   INTERNAL-IP    EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION    CONTAINER-RUNTIME
minikube   Ready    control-plane   24d   v1.24.3   192.168.49.2   <none>        Ubuntu 20.04.4 LTS   6.4.16-linuxkit   docker://20.10.17
```
```bash
kubectl create -k bootstrap
```
```bash
kubectl apply -k base/
Warning: resource namespaces/default is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
namespace/default configured
serviceaccount/blackbox-exporter created
serviceaccount/prometheus unchanged
Warning: resource serviceaccounts/prometheus-operator is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
serviceaccount/prometheus-operator configured
clusterrole.rbac.authorization.k8s.io/blackbox-exporter created
clusterrole.rbac.authorization.k8s.io/prometheus unchanged
Warning: resource clusterroles/prometheus-operator is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
clusterrole.rbac.authorization.k8s.io/prometheus-operator configured
clusterrolebinding.rbac.authorization.k8s.io/blackbox-exporter created
clusterrolebinding.rbac.authorization.k8s.io/prometheus unchanged
Warning: resource clusterrolebindings/prometheus-operator is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
clusterrolebinding.rbac.authorization.k8s.io/prometheus-operator configured
configmap/blackbox-exporter-configuration created
service/alertmanager-service created
service/blackbox-exporter created
service/prometheus configured
Warning: resource services/prometheus-operator is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
service/prometheus-operator configured
deployment.apps/blackbox-exporter created
Warning: resource deployments/prometheus-operator is missing the kubectl.kubernetes.io/last-applied-configuration annotation which is required by kubectl apply. kubectl apply should only be used on resources created declaratively by either kubectl create --save-config or kubectl apply. The missing annotation will be patched automatically.
deployment.apps/prometheus-operator configured
alertmanager.monitoring.coreos.com/alertmanager created
prometheus.monitoring.coreos.com/prometheus configured
prometheusrule.monitoring.coreos.com/alertmanager-rules created
prometheusrule.monitoring.coreos.com/prometheus-rules created
alertmanagerconfig.monitoring.coreos.com/alertmanager-config created
scrapeconfig.monitoring.coreos.com/alertmanager created
scrapeconfig.monitoring.coreos.com/blackbox-exporter created
scrapeconfig.monitoring.coreos.com/prometheus created
networkpolicy.networking.k8s.io/blackbox-exporter created

```
```bash
kubectl get pods
NAME                                   READY   STATUS    RESTARTS        AGE
alertmanager-alertmanager-0            2/2     Running   0               37s
blackbox-exporter-6c9bb6f694-8g52m     3/3     Running   0               37s
prometheus-operator-57698ff5c9-b4cvd   1/1     Running   2 (2m40s ago)   24d
prometheus-prometheus-0                2/2     Running   2 (24d ago)     24d
```

## Conclusion
After some research its a quite simple and easy solution to install a prometheus with some subsystems e.g. alertmanager. From now on we can extend the config with more subsystems or patch the replica amount etc. with the power of kustomize.