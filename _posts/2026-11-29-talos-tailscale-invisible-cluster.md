---
title: "Talos Linux on Hetzner Bare Metal with Cilium – Part 5: The Invisible Cluster"
description: "Take the Talos API and the Kubernetes API off the public internet: Tailscale as a Talos system extension, a default-deny host firewall, kubectl over the tailnet, and kubectl permissions from your Tailscale identity."
date: 2026-11-29 08:00 +0100
categories: [kubernetes, talos]
tags: [talos, tailscale, kubernetes, hetzner, firewall, zero-trust, cilium, fluxcd, wireguard]
image:
  path: /assets/img/talos-tailscale-invisible.png
  alt: A Talos cluster on Hetzner whose management APIs are only reachable through Tailscale
---

In **[Part 1]({% post_url 2026-11-19-talos-hetzner-bare-metal-cilium %})** we brought up a single-node Talos cluster on Hetzner bare metal with Cilium. **[Part 2]({% post_url 2026-11-20-talos-hetzner-fluxcd-gitops %})** handed it over to FluxCD, **[Part 3]({% post_url 2026-11-21-talos-flux-sops-age-secrets %})** moved every secret into Git, and **[Part 4]({% post_url 2026-11-25-talos-upgrades-renovate-gitops %})** made upgrades boring.

There's one thing all four parts quietly accepted: **the management APIs are on the public internet.** Port `50000` (the Talos API) and port `6443` (the Kubernetes API) answer anyone who asks. Both are protected by mutual TLS, so that's not a disaster. But every scanner on the internet knows they're there, every future CVE in either of them is your problem on day zero, and in Part 1 I even had to warn you about the unauthenticated maintenance-mode window.

This part makes the cluster **invisible**. From the internet, the server answers on exactly two TCP ports, `80` and `443`, for the websites it hosts. Everything else only exists inside my tailnet:

- 👉 **Tailscale as a Talos system extension**: no DaemonSet, no sidecar, it runs in the OS itself
- 👉 **`talosctl` and `kubectl` over the tailnet**, with a few `certSANs` and no other changes to the workflow
- 👉 a **default-deny host firewall** in the Talos machine config, applied with `--mode=try` so you can't lock yourself out
- 👉 **kubectl permissions from your Tailscale identity** via the Tailscale operator's API server proxy

If you read my post on **[Tailscale as the identity provider for the homelab]({% post_url 2026-11-26-tailscale-identity-provider-homelab %})**, the last step will feel familiar: the WireGuard key is the credential, now for Kubernetes too.

## Why at the OS Level?

The usual way to get a cluster into a tailnet is the Tailscale Kubernetes operator. I use it too (Step 6), but it can't solve this problem on its own: it runs **inside** Kubernetes. If the cluster is broken, the operator is broken, and the Talos API, the one thing you need to fix a broken cluster, would have to stay public.

Talos runs Tailscale as a **system extension**: a service managed by Talos itself, next to `apid` and `kubelet`, that starts before Kubernetes does. It survives a broken etcd, a crash-looping Cilium, and a botched Flux change. That's exactly the access path you want for repairs.

So the plan is two layers:

| Layer | Runs in | Used for |
|---|---|---|
| Tailscale extension | Talos OS | `talosctl`, break-glass `kubectl`, repairs |
| Tailscale operator | Kubernetes | Daily `kubectl` with identity-based RBAC |

## Step 1: Add the Extension to the Schematic

Extensions are baked into the image, so the schematic from Part 1 gets one more line:

```yaml
# talos/schematic.yaml
customization:
  systemExtensions:
    officialExtensions:
      - siderolabs/iscsi-tools
      - siderolabs/util-linux-tools
      - siderolabs/tailscale
```

```bash
curl -s -X POST --data-binary @talos/schematic.yaml https://factory.talos.dev/schematics
# {"id":"<NEW_SCHEMATIC_ID>"}
```

Put the new ID into `talos/versions.env` **and** into the installer image in `talos/patch.yaml` (both from Part 4). Then it's a regular upgrade to the same Talos version with a different image:

```bash
git commit -am "talos: add tailscale extension"
./talos/upgrade.sh
talosctl get extensions
```

`talosctl get extensions` should list `tailscale` now. The extension is installed but does nothing yet, because it has no configuration.

> Committing `talos/schematic.yaml` is worth it. The schematic ID is a hash of this file, so the file tells you what's actually in the ID, and you can rebuild it at any time.
{: .prompt-tip }

## Step 2: Prepare the Tailnet

The node joins as a **tagged device**, not as my user. Tagged devices don't expire with my login, and permissions can target the tag. In the Tailscale policy file:

```json
{
  "tagOwners": {
    "tag:talos": ["autogroup:admin"]
  },
  "grants": [
    {
      "src": ["group:admins"],
      "dst": ["tag:talos"],
      "ip":  ["tcp:50000", "tcp:6443"]
    }
  ]
}
```

Only admins may reach the two management ports, and nobody else in the tailnet sees anything of the node. Then create an **auth key** in the admin console: pre-approved, tagged with `tag:talos`.

Node key expiry is disabled by default for tagged devices, which is what you want for a server. The auth key itself only matters for the first registration.

## Step 3: Configure the Extension, Encrypted

The extension is configured with an `ExtensionServiceConfig` document. It contains the auth key, so it's a secret and gets the Part 3 treatment. The first rule in `.sops.yaml` already encrypts everything under `talos/`:

```yaml
# talos/tailscale.yaml (encrypt before committing!)
apiVersion: v1alpha1
kind: ExtensionServiceConfig
name: tailscale
environment:
  - TS_AUTHKEY=tskey-auth-xxxxxxxxxxxx
  - TS_HOSTNAME=talos-hetzner
  - TS_EXTRA_ARGS=--advertise-tags=tag:talos
  - TS_AUTH_ONCE=true
  - TS_ACCEPT_DNS=false
```

```bash
sops --encrypt --in-place talos/tailscale.yaml
```

What the variables do:

- **`TS_AUTH_ONCE=true`**: only log in if not logged in yet. Without it, the extension forces a new login on every start, which fails as soon as the auth key has expired.
- **`TS_ACCEPT_DNS=false`**: the node keeps using its normal resolvers. A Kubernetes node whose DNS depends on the tailnet is a fun way to debug things at 3 am.
- The extension runs with **kernel networking** (a real `tailscale0` interface) and keeps its state in `/var/lib/tailscale` on the node, so it stays the same machine in your tailnet across reboots.

Generating the config now needs **two** decrypted files, and this part adds a third patch later. Instead of a growing one-liner, I put config generation into one small script that every other step uses:

```bash
#!/usr/bin/env bash
# talos/gen-config.sh: renders controlplane.yaml from Git
set -euo pipefail
cd "$(dirname "$0")/.."
source talos/versions.env

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
sops --decrypt talos/secrets.yaml   > "$tmp/secrets.yaml"
sops --decrypt talos/tailscale.yaml > "$tmp/tailscale.yaml"

patches=(--config-patch @talos/patch.yaml --config-patch "@$tmp/tailscale.yaml")
[[ -f talos/firewall.yaml ]] && patches+=(--config-patch @talos/firewall.yaml)

talosctl gen config my-cluster "https://${NODE}:6443" \
  --with-secrets "$tmp/secrets.yaml" \
  "${patches[@]}" \
  --kubernetes-version "${KUBERNETES_VERSION#v}" \
  --output-types controlplane \
  --force
```

The decrypted files live in a temp directory outside the repository and are deleted when the script exits, even on errors. The output `controlplane.yaml` contains the same secrets, so it stays in `.gitignore` as before.

```bash
chmod +x talos/gen-config.sh
./talos/gen-config.sh
talosctl -n "$NODE" apply-config -f controlplane.yaml
rm controlplane.yaml
```

The `ExtensionServiceConfig` is just another YAML document in the machine config. Check that the service runs:

```bash
talosctl -n "$NODE" service ext-tailscale
talosctl -n "$NODE" logs ext-tailscale
tailscale status | grep talos-hetzner
```

The node shows up in `tailscale status` on your laptop. Try `tailscale ping talos-hetzner`: on a Hetzner box with a public IP, you should get a direct connection within a few pings.

## Step 4: Point talosctl and kubectl at the Tailnet

Both APIs only accept connections whose hostname is in their certificate. Add the MagicDNS name to both in `talos/patch.yaml`:

```yaml
# talos/patch.yaml
machine:
  certSANs:
    - talos-hetzner.your-tailnet.ts.net
  # ... install, kubelet, network from Part 1 ...

cluster:
  apiServer:
    certSANs:
      - talos-hetzner.your-tailnet.ts.net
  # ... rest from Part 1 ...
```

Regenerate and apply with `talos/gen-config.sh` as in Step 3. Then switch the clients:

```bash
export TALOSCONFIG=$PWD/talosconfig
talosctl config endpoint talos-hetzner.your-tailnet.ts.net
talosctl -n "$NODE" version

kubectl config set-cluster my-cluster \
  --server=https://talos-hetzner.your-tailnet.ts.net:6443
kubectl get nodes
```

Notice the trick: the **endpoint** (where `talosctl` connects to) is the tailnet name, but the **node** (`-n`, which machine should answer) stays the public IP from `versions.env`. `apid` recognizes its own address and answers locally, so nothing ever connects to the public IP. The `upgrade.sh` script from Part 4 keeps working without a single change.

I deliberately keep the **cluster endpoint** in `talosctl gen config` at the public IP. The node's own components reach the API server through KubePrism on `localhost:7445` anyway, and the cluster's internals shouldn't depend on Tailscale being up.

## Step 5: Close the Doors

Now the actual point of this part. Talos has a built-in host firewall, configured with two more documents. The default action becomes **block**, and only what's listed is allowed:

```yaml
# talos/firewall.yaml
apiVersion: v1alpha1
kind: NetworkDefaultActionConfig
ingress: block
---
# Management: tailnet only
apiVersion: v1alpha1
kind: NetworkRuleConfig
name: apid-ingress
portSelector:
  ports: [50000]
  protocol: tcp
ingress:
  - subnet: 100.64.0.0/10
  - subnet: fd7a:115c:a1e0::/48
---
apiVersion: v1alpha1
kind: NetworkRuleConfig
name: kubernetes-api-ingress
portSelector:
  ports: [6443]
  protocol: tcp
ingress:
  - subnet: 100.64.0.0/10
  - subnet: fd7a:115c:a1e0::/48
  - subnet: 10.244.0.0/16      # pods talking to the API server
---
# Cluster-internal: kubelet (metrics-server), Cilium health, Hubble
apiVersion: v1alpha1
kind: NetworkRuleConfig
name: cluster-internal-ingress
portSelector:
  ports: [10250, 4240, 4244]
  protocol: tcp
ingress:
  - subnet: 10.244.0.0/16
---
# Public: the websites behind the Cilium Gateway
apiVersion: v1alpha1
kind: NetworkRuleConfig
name: web-ingress
portSelector:
  ports: [80, 443]
  protocol: tcp
ingress:
  - subnet: 0.0.0.0/0
  - subnet: ::/0
---
# Public: WireGuard, for direct Tailscale connections
apiVersion: v1alpha1
kind: NetworkRuleConfig
name: tailscale-wireguard
portSelector:
  ports: [41641]
  protocol: udp
ingress:
  - subnet: 0.0.0.0/0
  - subnet: ::/0
```

Why each rule is there:

- **`100.64.0.0/10` and `fd7a:115c:a1e0::/48`** are the address ranges Tailscale uses for tailnet IPs. Traffic arriving on `tailscale0` comes from there. Who inside the tailnet may connect is decided by the grant from Step 2, so the firewall doesn't need to know about users.
- **`10.244.0.0/16`** is Talos's default pod subnet. With Cilium's kube-proxy replacement, a pod connecting to the `kubernetes` Service ends up at the node's address on port `6443`, with the pod IP as the source. Block that, and Flux, cert-manager, and every operator lose their API server. The same goes for metrics-server reaching the kubelet on `10250`.
- **`80/443`** stay public, because that's what the server is for. The Gateway's Envoy binds to the host network (Part 1), so it's protected by the host firewall like everything else.
- **UDP `41641`** is optional. Tailscale works through NAT without it, but with it open, peers can connect directly instead of falling back to a relay. It's WireGuard: anything without a valid key gets silently dropped.

Talos always allows loopback, so KubePrism on `localhost:7445` keeps working. It also allows established connections and rate-limited ICMP. Outbound traffic isn't affected at all: Flux still pulls from GitHub, and cert-manager still talks to Let's Encrypt.

> The Talos firewall protects the **host**. Traffic between pods is not affected; that's what Cilium network policies are for. And don't mix it with Cilium **host policies** (we enabled `hostFirewall` in Part 1 but never added any). One host firewall is enough, and the Talos one sits below Kubernetes, so it keeps working when the cluster doesn't.
{: .prompt-info }

### Apply it without locking yourself out

This is the step where you can lock yourself out of a server with no SSH and no console. Talos has a mode built exactly for this: **`--mode=try`** applies the config and **rolls it back automatically after one minute** unless you apply it again.

`talos/gen-config.sh` picks up `talos/firewall.yaml` automatically as soon as the file exists:

```bash
./talos/gen-config.sh
talosctl -n "$NODE" apply-config -f controlplane.yaml --mode=try
```

Now you have one minute. From your laptop, **over the tailnet**:

```bash
talosctl -n "$NODE" version                 # Talos API via tailnet
kubectl get nodes                           # Kubernetes API via tailnet
curl -sI https://app.example.com | head -1  # website still public
```

And from a machine **outside** the tailnet (your phone with Tailscale off, or a cloud shell):

```bash
nc -vz -w 3 <NODE_PUBLIC_IP> 50000   # should time out
nc -vz -w 3 <NODE_PUBLIC_IP> 6443    # should time out
```

If everything behaves, apply it for real:

```bash
talosctl -n "$NODE" apply-config -f controlplane.yaml
rm controlplane.yaml
talosctl -n "$NODE" get nftableschain
```

If something goes wrong, do nothing. Within a minute the old config is back.

> From now on, **always** render the config with `talos/gen-config.sh`. A config generated by hand from only `patch.yaml` looks fine, applies fine, and quietly removes your firewall and your Tailscale config. Update the CI validation from Part 4 to add `--config-patch @talos/firewall.yaml` too; it can't decrypt `tailscale.yaml`, and it doesn't need to.
{: .prompt-warning }

## Step 6: kubectl with Your Tailscale Identity

At this point the cluster is invisible, but `kubectl` still uses the admin kubeconfig with a client certificate: a file that is cluster-admin forever and can't be revoked without rotating the CA. That's the last thing I want to fix.

The **Tailscale Kubernetes operator** has an **API server proxy**. It joins the tailnet as its own device, authenticates every request by Tailscale identity, and forwards it to the API server **impersonating** a user or group you choose in the policy file. Same idea as Serve headers and tsidp in the identity post, applied to `kubectl`.

### The policy

```json
{
  "tagOwners": {
    "tag:k8s-operator": ["autogroup:admin"],
    "tag:k8s":          ["tag:k8s-operator"]
  },
  "grants": [
    {
      "src": ["group:admins"],
      "dst": ["tag:k8s-operator"],
      "ip":  ["tcp:443"],
      "app": {
        "tailscale.com/cap/kubernetes": [
          { "impersonate": { "groups": ["system:masters"] } }
        ]
      }
    },
    {
      "src": ["group:family"],
      "dst": ["tag:k8s-operator"],
      "ip":  ["tcp:443"],
      "app": {
        "tailscale.com/cap/kubernetes": [
          { "impersonate": { "groups": ["tailnet-readers"] } }
        ]
      }
    }
  ]
}
```

Admins become `system:masters`. Everyone in `group:family` lands in a Kubernetes group called `tailnet-readers`, which doesn't need to exist anywhere, you just bind RBAC to it. Then create an OAuth client in the admin console with write access to **Devices: Core**, **Keys: Auth Keys**, and **General: Services**, tagged `tag:k8s-operator`.

### The operator, the GitOps way

The OAuth credentials go into a SOPS-encrypted secret, exactly like in Part 3:

```yaml
# infrastructure/controllers/tailscale-oauth-secret.yaml (sops-encrypted)
apiVersion: v1
kind: Secret
metadata:
  name: tailscale-oauth
  namespace: tailscale
stringData:
  clientId: <OAUTH_CLIENT_ID>
  clientSecret: <OAUTH_CLIENT_SECRET>
```

```yaml
# infrastructure/controllers/tailscale-operator.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tailscale
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: tailscale
  namespace: tailscale
spec:
  interval: 24h
  url: https://pkgs.tailscale.com/helmcharts
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: tailscale-operator
  namespace: tailscale
spec:
  interval: 30m
  chart:
    spec:
      chart: tailscale-operator
      version: "1.104.7"
      sourceRef:
        kind: HelmRepository
        name: tailscale
  valuesFrom:
    - kind: Secret
      name: tailscale-oauth
      valuesKey: clientId
      targetPath: oauth.clientId
    - kind: Secret
      name: tailscale-oauth
      valuesKey: clientSecret
      targetPath: oauth.clientSecret
  values:
    apiServerProxyConfig:
      mode: "true"
```

`apiServerProxyConfig.mode: "true"` (a string, not a boolean) enables the proxy in **auth mode**, running inside the operator pod. Renovate from Part 4 picks up the chart version automatically.

Bind the readers to the built-in `view` role:

```yaml
# infrastructure/configs/tailnet-readers.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: tailnet-readers-view
subjects:
  - kind: Group
    name: tailnet-readers
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: view
  apiGroup: rbac.authorization.k8s.io
```

### Using it

Once Flux has reconciled, the operator appears in your tailnet as `tailscale-operator`. On any device logged into the tailnet:

```bash
tailscale configure kubeconfig tailscale-operator
kubectl get pods -A
kubectl auth whoami
```

No certificate in the kubeconfig, no token, no OIDC plugin. `kubectl auth whoami` shows your Tailscale login, with the groups from the grant. Remove someone from `group:admins` in the policy file and their next `kubectl` call is a viewer's, instantly.

The admin kubeconfig with the client certificate becomes what it should be: a **break-glass credential** in the password manager, next to the age key from Part 3. Nobody uses it day to day.

> The proxy only exposes the Kubernetes API. To expose other Services to the tailnet (the `tailscale.com/expose` annotation or `loadBalancerClass: tailscale`), read the operator's Cilium compatibility notes first: with Cilium's socket load balancing, pod-to-ClusterIP traffic can bypass the proxy's rules unless you limit socket LB to the host namespace (`socketLB.hostNamespaceOnly`).
{: .prompt-info }

## What If Tailscale Breaks?

The obvious question. An invisible cluster you can't reach is just a server you pay for. Here's how I think about it:

- **Tailscale's control plane being down** doesn't break existing connections. Nodes keep their keys and peer lists, and established tailnet paths keep working. You just can't add new devices or change the policy for a while.
- **The extension crashing on the node**: Talos restarts it (`restart: always`). The service is independent of Kubernetes, so a broken cluster doesn't take it down.
- **A bad firewall change** is what `--mode=try` is for.
- **The real worst case**, the node can't reach the tailnet at all: boot the Hetzner rescue system, wipe, and rebuild from Git. Since Part 3, the cluster is one repository plus one age key, and Part 4 gave you encrypted etcd snapshots. That's the actual break-glass procedure, and it doesn't care about Tailscale.

If that's too drastic for you, add a break-glass rule for a static IP you control:

```yaml
# in talos/firewall.yaml, rule apid-ingress
ingress:
  - subnet: 100.64.0.0/10
  - subnet: fd7a:115c:a1e0::/48
  - subnet: 203.0.113.10/32   # break-glass: my office IP
```

I don't use one. A port that's open "just in case" is a port that's open.

## Final Thoughts

From the outside, the server is now just a web server. The scan shows `80` and `443`, and nothing about it says "Kubernetes" or "Talos". On the inside:

- **Talos API and Kubernetes API**: reachable only through the tailnet, enforced by the OS firewall
- **Tailscale in the OS**, not in the cluster, so the repair path survives a broken cluster
- **daily `kubectl`** authenticated by Tailscale identity, with RBAC driven by the policy file
- **the admin kubeconfig** demoted to a break-glass credential
- **everything still in Git**: schematic, patches, encrypted Tailscale config, firewall, operator

The stack from this series is now Talos, Cilium, Flux, SOPS, Renovate, and Tailscale. Six tools, one repository, one key, and no management port on the internet.

Next up: backups for the data that isn't in Git. Persistent volumes, restic, an off-site target, and a monthly restore test that runs on its own, because a backup you've never restored is just a hope.

Happy hiding 🫥
