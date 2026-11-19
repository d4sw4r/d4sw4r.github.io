---
title: "Talos Linux on Hetzner Bare Metal with Cilium – Part 1: Cluster Bring-up"
description: "Step-by-step guide to installing Talos Linux on a Hetzner dedicated server and bootstrapping a single-node Kubernetes cluster with Cilium as CNI and kube-proxy replacement."
date: 2026-11-19 12:00 +0100
categories: [kubernetes, talos]
tags: [talos, kubernetes, cilium, bare-metal, hetzner, ebpf, gateway-api]
image:
  path: /assets/img/talos_hetzner.png
  alt: Talos Linux on Hetzner bare metal with Cilium
---

In this article we install **Talos Linux** on a **Hetzner dedicated server** and bootstrap a **single-node Kubernetes cluster** that uses **Cilium** as both the CNI and the kube-proxy replacement.

This part is all about infrastructure and getting the cluster up. **[Part 2](/posts/talos-hetzner-fluxcd-gitops/)** (published 20 November) takes it from there with FluxCD, Helm, and GitOps.

If you're wondering *why* Talos and GitOps belong together in the first place, I wrote about the idea in [TalosLinux + GitOps: Immutable Infrastructure Done Right]({% post_url 2026-03-03-talos-linux-gitops %}). This series is the hands-on version.

## Why Talos + Hetzner + Cilium?

- **Talos Linux**: an immutable, API-driven OS that does nothing except run Kubernetes. No SSH, no shell, no package manager.
- **Hetzner bare metal**: a lot of CPU, RAM, and NVMe for the money, with no virtualization overhead.
- **Cilium**:
  - eBPF-based networking
  - full kube-proxy replacement
  - built-in Gateway API support, so you don't need a separate ingress controller
  - a host firewall, which is handy on a node with a public IP

It also works fine as a **single-node cluster**. That's what we build here: one machine that is both control plane and worker.

## What You Need

| Item | Notes |
|------|-------|
| Hetzner dedicated server | amd64, NVMe disks; this guide assumes `nvme0n1` and `nvme1n1` |
| Local tools | `talosctl`, `kubectl`, `helm`, optionally the `cilium` CLI |
| Placeholders | `<NODE_PUBLIC_IP>`, `<SCHEMATIC_ID>`; replace them with your values |

The versions used throughout this guide:

```bash
export TALOS_VERSION=v1.12.2
export CILIUM_VERSION=1.18.6
export GATEWAY_API_VERSION=v1.2.0   # the version Cilium 1.18 expects
```

> These are the versions this setup was built and tested with. Newer releases exist. If you bump them, check the [Cilium Gateway API docs](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/gateway-api/) for the Gateway API version your Cilium release expects. A mismatch there is the most common way to end up with a Gateway that never becomes `Programmed`.
{: .prompt-info }

## Step 1: Build a Talos Image with Extensions

Talos is immutable, so extra system software (for example iSCSI tools for Longhorn) has to be baked into the image. The [Talos Image Factory](https://factory.talos.dev) does this for you: you describe the extensions in a *schematic*, and it gives you back an ID.

```yaml
# schematic.yaml
customization:
  systemExtensions:
    officialExtensions:
      - siderolabs/iscsi-tools
      - siderolabs/util-linux-tools
```

```bash
curl -X POST --data-binary @schematic.yaml https://factory.talos.dev/schematics
# {"id":"<SCHEMATIC_ID>"}
export SCHEMATIC_ID=<SCHEMATIC_ID>
```

We use this ID for both the disk image and the installer, so the extensions are there from the first boot. You don't need an upgrade afterwards to add them.

## Step 2: Boot into the Hetzner Rescue System

1. Open **Hetzner Robot** and select your server.
2. Go to **Rescue**, pick your SSH key, and activate the Linux rescue system.
3. Under **Reset**, trigger a hardware reset.
4. SSH into the server as `root`.

## Step 3: Prepare the Disks

Hetzner servers often come with a software RAID from a previous install. Talos manages its own disk layout and doesn't use mdraid, so wipe everything:

```bash
# Stop any existing software RAID
mdadm --stop /dev/md[0-9]* 2>/dev/null

# Wipe partition tables and signatures
sfdisk --delete /dev/nvme0n1
sfdisk --delete /dev/nvme1n1
wipefs -a -f /dev/nvme0n1 /dev/nvme1n1
```

> This erases **all data** on both disks. Talos is installed on `nvme0n1` only. The second disk stays empty for now and makes a good dedicated disk for Longhorn or another storage system later on.
{: .prompt-danger }

## Step 4: Write Talos to Disk

Still in the rescue system, download the bare-metal image for your schematic and write it to the first disk:

```bash
wget "https://factory.talos.dev/image/${SCHEMATIC_ID}/${TALOS_VERSION}/metal-amd64.raw.zst" \
  -O /tmp/talos.raw.zst

zstd -d /tmp/talos.raw.zst -o /tmp/talos.raw
dd if=/tmp/talos.raw of=/dev/nvme0n1 bs=4M conv=fsync status=progress
sync
reboot
```

(The rescue system doesn't know your local shell variables, so set `SCHEMATIC_ID` and `TALOS_VERSION` there as well, or paste the values in directly.)

After the reboot, Talos comes up in **maintenance mode**. It gets its IPv4 address via DHCP and waits on port `50000` for a configuration. There is no SSH anymore. From now on everything goes through `talosctl`.

> Between this reboot and the bootstrap, the Talos API accepts an unauthenticated config on a public IP. Keep that window short, or restrict ports `50000` and `6443` to your own IP in the Hetzner Robot firewall.
{: .prompt-warning }

## Step 5: Generate the Talos Configuration

On your **local machine**, first generate the cluster secrets. Keep this file safe and out of plain Git; we'll encrypt secrets properly in a later part.

```bash
talosctl gen secrets -o secrets.yaml
```

Then write a config patch with everything specific to this setup:

```yaml
# patch.yaml
machine:
  install:
    disk: /dev/nvme0n1
    image: factory.talos.dev/metal-installer/<SCHEMATIC_ID>:v1.12.2
  kubelet:
    extraArgs:
      rotate-server-certificates: true
  network:
    interfaces:
      - deviceSelector:
          physical: true
        dhcp: true
        # Optional: Hetzner gives you a /64 for IPv6, which DHCP won't configure
        # addresses:
        #   - <YOUR_IPV6>/64
        # routes:
        #   - network: ::/0
        #     gateway: fe80::1

cluster:
  network:
    cni:
      name: none          # Cilium is installed in Step 7
  proxy:
    disabled: true        # Cilium replaces kube-proxy
  allowSchedulingOnControlPlanes: true   # single node: run workloads here too

  apiServer:
    admissionControl:
      - name: PodSecurity
        configuration:
          apiVersion: pod-security.admission.config.k8s.io/v1
          kind: PodSecurityConfiguration
          defaults:
            enforce: privileged

  extraManifests:
    - https://raw.githubusercontent.com/alex1989hu/kubelet-serving-cert-approver/main/deploy/standalone-install.yaml
    - https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

Here's what each part does:

- **`cni: none` + `proxy.disabled`**: Kubernetes starts without networking and without kube-proxy. Cilium takes over both jobs.
- **`allowSchedulingOnControlPlanes`**: on a single-node cluster the control plane also has to run your workloads.
- **`rotate-server-certificates`** together with **kubelet-serving-cert-approver**: the kubelet gets properly signed serving certificates, which **metrics-server** needs so that `kubectl top` works.
- **PodSecurity `privileged`**: a relaxed default that keeps a homelab-style cluster simple. For anything multi-tenant, tighten it and label namespaces individually.

Now generate the config:

```bash
talosctl gen config my-cluster https://<NODE_PUBLIC_IP>:6443 \
  --with-secrets secrets.yaml \
  --config-patch @patch.yaml \
  --output-types controlplane,talosconfig
```

## Step 6: Apply the Config and Bootstrap

```bash
talosctl apply-config \
  --insecure \
  --nodes <NODE_PUBLIC_IP> \
  --file controlplane.yaml
```

Talos now installs itself to `nvme0n1` using the installer image from the patch and reboots. Once it's back, point `talosctl` at the node and bootstrap etcd. Run the bootstrap **exactly once**:

```bash
export TALOSCONFIG=$PWD/talosconfig
talosctl config endpoint <NODE_PUBLIC_IP>
talosctl config node <NODE_PUBLIC_IP>

talosctl bootstrap
talosctl kubeconfig ./kubeconfig
export KUBECONFIG=$PWD/kubeconfig
```

`kubectl get nodes` shows the node as `NotReady`. That's expected, because there is no CNI yet.

> **Adding extensions later:** if you skipped Step 1 or want to add an extension to a running node, build a new schematic and upgrade in place:
> `talosctl upgrade --image factory.talos.dev/metal-installer/<NEW_SCHEMATIC_ID>:v1.12.2`
{: .prompt-tip }

## Step 7: Install Cilium

### Gateway API CRDs

Cilium only turns on its Gateway API controller if the CRDs already exist when it starts, so install them first:

```bash
GW=https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/${GATEWAY_API_VERSION}/config/crd
kubectl apply -f $GW/standard/gateway.networking.k8s.io_gatewayclasses.yaml
kubectl apply -f $GW/standard/gateway.networking.k8s.io_gateways.yaml
kubectl apply -f $GW/standard/gateway.networking.k8s.io_httproutes.yaml
kubectl apply -f $GW/standard/gateway.networking.k8s.io_referencegrants.yaml
kubectl apply -f $GW/standard/gateway.networking.k8s.io_grpcroutes.yaml
kubectl apply -f $GW/experimental/gateway.networking.k8s.io_tlsroutes.yaml
```

### Cilium via Helm

```bash
helm repo add cilium https://helm.cilium.io/
helm repo update

helm install cilium cilium/cilium \
  --version ${CILIUM_VERSION} \
  --namespace kube-system \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=localhost \
  --set k8sServicePort=7445 \
  --set securityContext.capabilities.ciliumAgent="{CHOWN,KILL,NET_ADMIN,NET_RAW,IPC_LOCK,SYS_ADMIN,SYS_RESOURCE,DAC_OVERRIDE,FOWNER,SETGID,SETUID}" \
  --set securityContext.capabilities.cleanCiliumState="{NET_ADMIN,SYS_ADMIN,SYS_RESOURCE}" \
  --set cgroup.autoMount.enabled=false \
  --set cgroup.hostRoot=/sys/fs/cgroup \
  --set operator.replicas=1 \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true \
  --set gatewayAPI.enabled=true \
  --set gatewayAPI.enableAlpn=true \
  --set gatewayAPI.enableAppProtocol=true \
  --set gatewayAPI.hostNetwork.enabled=true \
  --set externalIPs.enabled=true \
  --set l2announcements.enabled=true \
  --set hostFirewall.enabled=true
```

The values that matter most on Talos:

| Setting | Why |
|---------|-----|
| `k8sServiceHost=localhost`, `k8sServicePort=7445` | Without kube-proxy, Cilium needs a direct way to reach the API server. Talos runs **KubePrism**, a local API server load balancer on port 7445 on every node. |
| `securityContext.capabilities.*` | Talos doesn't allow the `SYS_MODULE` capability, so Cilium has to run with an explicit capability list. |
| `cgroup.autoMount.enabled=false`, `cgroup.hostRoot` | Talos already mounts cgroup v2, so Cilium must not try to mount it again. |
| `operator.replicas=1` | There's only one node. The default of 2 would leave one operator pod pending forever. |
| `gatewayAPI.hostNetwork.enabled` | The Gateway's Envoy listener binds directly to ports 80/443 on the node's public IP. On a single bare-metal box this means you need **no LoadBalancer IP**. |
| `hostFirewall.enabled` | This prepares Cilium to enforce host-level network policies. On its own it blocks nothing; you need to add policies, and if you do, allow `50000` and `6443` from your IP or you'll lock yourself out. |
| `l2announcements`, `externalIPs` | These are optional and only matter if you later add extra IPs. Hetzner routes additional IPs to the server's main IP, so on Hetzner you typically won't need L2 announcements. |

Give it a minute, then check:

```bash
cilium status --wait
kubectl get nodes
```

The node should now be `Ready`. If the Gateway API resources don't seem to get picked up, restart Cilium so it sees the CRDs:

```bash
kubectl -n kube-system rollout restart deployment/cilium-operator
kubectl -n kube-system rollout restart daemonset/cilium
```

## Step 8: Sanity Check

```bash
talosctl health
kubectl get pods -A
kubectl top nodes            # metrics-server + signed kubelet certs
kubectl get gatewayclass     # should list "cilium" as Accepted
```

If all of that looks good, you have a working, minimal, fully API-driven Kubernetes node.

## What's Next: Part 2

So far we installed Cilium by hand, which is fine for bootstrapping but not how we want to run things long term. **[Part 2](/posts/talos-hetzner-fluxcd-gitops/)** covers:

- bootstrapping **FluxCD**
- a repository layout for infrastructure and apps
- moving Cilium into Git with a Flux `HelmRelease`
- **cert-manager** with Let's Encrypt and the **Gateway API**
- rebuilding the whole cluster from Git

## Final Thoughts

Talos + Hetzner + Cilium makes for a clean, modern Kubernetes stack:

- no SSH
- no hand-maintained servers
- no kube-proxy
- fully API-driven
- ready for GitOps

If you like minimal, reproducible infrastructure, this setup is hard to beat.

Happy clustering 🚀
