---
title: "Talos Linux on Hetzner Bare Metal with Cilium – Part 3: Secrets in Git with SOPS & age"
description: "Encrypt Kubernetes secrets and Talos machine secrets with SOPS and age, decrypt them in-cluster with FluxCD, and make your GitOps repo the complete source of truth."
date: 2026-11-21 11:00 +0100
categories: [kubernetes, gitops]
tags: [talos, fluxcd, sops, age, secrets, kubernetes, cert-manager, gitops]
---

In **[Part 1]({% post_url 2026-11-19-talos-hetzner-bare-metal-cilium %})** we brought up a single-node Talos cluster on Hetzner bare metal with Cilium. In **[Part 2]({% post_url 2026-11-20-talos-hetzner-fluxcd-gitops %})** we handed the cluster over to FluxCD, so that every change is a Git commit.

That leaves one gap. At the end of Part 2 I said the only things you need to keep yourself are your persistent data and **`secrets.yaml`**. Every API token, password, and certificate key also still lives *outside* Git. As long as that's true, Git isn't really the complete source of truth for the cluster.

This part closes that gap with **SOPS** and **age**:

- 👉 encrypting Kubernetes `Secret`s so they can live in the repo
- 👉 letting Flux decrypt them inside the cluster
- 👉 encrypting the Talos machine secrets from Part 1 too
- 👉 a disaster recovery story that needs exactly **one key**

## Why SOPS + age?

There are several ways to handle secrets in GitOps: Sealed Secrets, External Secrets Operator with Vault or a cloud KMS, and SOPS. For a single-node, self-hosted cluster, SOPS with age is the least amount of moving parts:

| Approach | Needs in-cluster component | Needs external service | Encrypted file readable offline |
|----------|---------------------------|------------------------|---------------------------------|
| Sealed Secrets | yes (controller) | no | no, only the cluster can decrypt |
| External Secrets | yes (operator) | yes (Vault, KMS, ...) | n/a, secrets live elsewhere |
| **SOPS + age** | **no, built into Flux** | **no** | **yes, with your age key** |

That last column matters more than it looks. With Sealed Secrets, the cluster's private key is the only thing that can decrypt your secrets. If you lose the cluster without having backed up that key, the secrets in Git are useless. With SOPS + age, *you* hold the key, and you can decrypt any file on your laptop, before the cluster even exists.

**SOPS** encrypts the *values* in a YAML file and leaves the keys readable. Diffs stay meaningful: you can see *which* field changed, just not its content. **age** is a small, modern encryption tool with short keys and no keyring. Flux's kustomize-controller supports both natively.

## Step 1: Install the Tools and Create a Key

```bash
brew install sops age   # or grab the binaries from GitHub releases
```

Generate a key pair:

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
# Public key: age1q3...xyz
```

The file contains the **private** key, and the comment line shows the **public** key. Tell SOPS where to find the key explicitly. The default path differs between Linux and macOS, so this avoids surprises:

```bash
# in ~/.zshrc or ~/.bashrc
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
```

> This private key can decrypt **every secret in your repository**, including your Talos cluster secrets. Store a copy in your password manager or offline right now, and never commit it. Without it, everything we encrypt below can't be recovered.
{: .prompt-danger }

Add a safety net to `.gitignore` in your `talos-k8s` repo:

```gitignore
*.agekey
keys.txt
```

## Step 2: Tell SOPS What to Encrypt

A `.sops.yaml` in the repository root defines *creation rules*. When you run `sops --encrypt`, SOPS picks the first rule whose `path_regex` matches the file:

```yaml
# .sops.yaml
creation_rules:
  # Talos machine secrets: encrypt every value
  - path_regex: talos/.*\.yaml$
    age: age1q3...xyz

  # Kubernetes Secrets: only encrypt data/stringData
  - path_regex: .*-secret\.yaml$
    encrypted_regex: ^(data|stringData)$
    age: age1q3...xyz
```

`encrypted_regex` is the important part for Kubernetes manifests. Without it, SOPS also encrypts `apiVersion`, `kind`, and `metadata`, and Flux can no longer tell what kind of object the file is. With it, only the secret values get encrypted.

The `-secret.yaml` suffix is a convention, but a useful one: you can see right away which files are encrypted, and the rule can't accidentally apply to a `HelmRelease`.

## Step 3: Give Flux the Key

Flux decrypts inside the cluster, so it needs the private key. Create a secret in `flux-system`. The key name has to end in `.agekey`, otherwise Flux won't recognize it as an age key:

```bash
cat ~/.config/sops/age/keys.txt |
  kubectl create secret generic sops-age \
    --namespace=flux-system \
    --from-file=age.agekey=/dev/stdin
```

This is the **one secret** we create by hand, and that's intentional. It's the root of trust, so it can't come from Git itself.

Now enable decryption on the Flux Kustomizations from Part 2. Add a `decryption` block to every layer that will contain encrypted files:

```yaml
# clusters/talos-hetzner/infrastructure.yaml  (infra-configs)
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infra-configs
  namespace: flux-system
spec:
  dependsOn:
    - name: infra-controllers
  interval: 1h
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure/configs
  prune: true
  decryption:
    provider: sops
    secretRef:
      name: sops-age
```

Do the same for `infra-controllers` and `apps` if they'll contain secrets. A Kustomization *without* `decryption` applies encrypted files as-is, which ends with a confusing error about invalid base64 in your secret.

## Step 4: A Real Example – Wildcard Certificates via DNS-01

In Part 2, cert-manager used HTTP-01 challenges through the Gateway. That works, but it can't issue **wildcard certificates**, and every hostname needs its own listener. DNS-01 can, but it needs an API token for your DNS provider. That's a perfect first secret.

Here's an example with Cloudflare (other providers work the same way). Write the secret in plain text first:

```yaml
# infrastructure/configs/cloudflare-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: cloudflare-api-token
  namespace: cert-manager
type: Opaque
stringData:
  api-token: <YOUR_CLOUDFLARE_TOKEN>
```

Encrypt it in place:

```bash
sops --encrypt --in-place infrastructure/configs/cloudflare-secret.yaml
```

The file now looks roughly like this, and it's safe to commit:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cloudflare-api-token
  namespace: cert-manager
type: Opaque
stringData:
  api-token: ENC[AES256_GCM,data:8f2k...,iv:...,tag:...,type:str]
sops:
  age:
    - recipient: age1q3...xyz
      enc: |
        -----BEGIN AGE ENCRYPTED FILE-----
        ...
  lastmodified: "2026-11-21T10:00:00Z"
  mac: ENC[AES256_GCM,data:...]
  encrypted_regex: ^(data|stringData)$
  version: 3.13.3
```

Then add a DNS-01 issuer next to the HTTP-01 one:

```yaml
# infrastructure/configs/cluster-issuer-dns.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-dns
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: <YOUR_EMAIL>
    privateKeySecretRef:
      name: letsencrypt-dns-account-key
    solvers:
      - dns01:
          cloudflare:
            apiTokenSecretRef:
              name: cloudflare-api-token
              key: api-token
```

A `ClusterIssuer` looks for referenced secrets in cert-manager's own namespace, which is why the secret above lives in `cert-manager`.

Now one listener on the Gateway can serve every subdomain:

```yaml
    - name: https-wildcard
      protocol: HTTPS
      port: 443
      hostname: "*.example.com"
      tls:
        mode: Terminate
        certificateRefs:
          - name: wildcard-example-com-tls
      allowedRoutes:
        namespaces:
          from: All
```

To make cert-manager use the DNS issuer for this Gateway, change the annotation to `cert-manager.io/cluster-issuer: letsencrypt-dns`. Commit, push, and Flux decrypts the token, creates the secret, and cert-manager gets the wildcard certificate.

## Step 5: Secrets in Helm Values

Many charts want credentials in their values, such as an admin password or an S3 key for backups. Don't put those in the `HelmRelease` itself. Put them in an encrypted secret and reference it with `valuesFrom`:

```yaml
# apps/talos-hetzner/monitoring/grafana-secret.yaml  (encrypted with sops)
apiVersion: v1
kind: Secret
metadata:
  name: grafana-admin
  namespace: monitoring
stringData:
  password: <STRONG_PASSWORD>
```

```yaml
# apps/talos-hetzner/monitoring/grafana.yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: grafana
  namespace: monitoring
spec:
  # ... chart, interval, sourceRef as in Part 2 ...
  valuesFrom:
    - kind: Secret
      name: grafana-admin
      valuesKey: password
      targetPath: adminPassword
```

Flux merges the decrypted value into the chart values at `adminPassword`. The `HelmRelease` stays readable in Git, and the password never appears in it.

## Step 6: Encrypting the Talos Machine Secrets

Now for the file from Part 1: **`secrets.yaml`**. It contains the cluster CA, etcd keys, and bootstrap tokens. Whoever holds it can create an admin config for your cluster. So far it has lived somewhere on your laptop.

Move it into the repo and encrypt it. The first rule in `.sops.yaml` encrypts every value:

```bash
mkdir -p talos
mv secrets.yaml talos/secrets.yaml
sops --encrypt --in-place talos/secrets.yaml
cp patch.yaml talos/patch.yaml   # the config patch from Part 1, no secrets in it
```

You don't need to commit the generated `controlplane.yaml` and `talosconfig`. They're derived from `secrets.yaml` + `patch.yaml` and can be regenerated at any time. `sops exec-file` decrypts into a temporary file just long enough for one command, so the plaintext never touches your working tree:

```bash
sops exec-file talos/secrets.yaml \
  'talosctl gen config my-cluster https://<NODE_PUBLIC_IP>:6443 \
     --with-secrets {} \
     --config-patch @talos/patch.yaml \
     --output-types controlplane,talosconfig'
```

`{}` is replaced with the path of the decrypted temporary file.

> `controlplane.yaml` and `talosconfig` contain the same key material in plain text. Add both to `.gitignore` and delete them once you've applied the config, or keep `talosconfig` only in your password manager.
{: .prompt-warning }

Your repository now holds **everything** needed to recreate the cluster: the Talos secrets, the Talos config, every manifest, and every application secret.

## Editing and Rotating

**Editing** an encrypted file is a single command. SOPS decrypts it into your `$EDITOR` and re-encrypts it when you save:

```bash
sops infrastructure/configs/cloudflare-secret.yaml
```

**Adding a second key**, for example for a teammate or a backup key in a safe, means adding another recipient to `.sops.yaml` (as a comma-separated list) and re-encrypting the data key for every file:

```yaml
    age: age1q3...xyz,age1backup...abc
```

```bash
find . -name '*-secret.yaml' -o -path './talos/*.yaml' | xargs -n1 sops updatekeys -y
```

**Rotating the key** works the same way: add the new key, run `updatekeys`, update the `sops-age` secret in the cluster, then remove the old key and run `updatekeys` again. `updatekeys` only re-encrypts the data key, not the values themselves. If you think a key has leaked, rotate the *secrets* too (new API token, new password). Anyone who had the old key and a copy of the repo can still read the old values from Git history.

## A Safety Net Against Plaintext Commits

The most common SOPS mistake isn't cryptographic. It's committing a secret *before* encrypting it. A tiny pre-commit hook catches that:

```bash
#!/usr/bin/env bash
# .git/hooks/pre-commit
fail=0
for f in $(git diff --cached --name-only --diff-filter=ACM | grep -E '(-secret\.yaml$|^talos/secrets\.yaml$)'); do
  if ! grep -q '^sops:' "$f"; then
    echo "✗ $f is not encrypted with sops"
    fail=1
  fi
done
exit $fail
```

```bash
chmod +x .git/hooks/pre-commit
```

For a broader check, tools like **gitleaks** scan for anything that looks like a token, encrypted or not.

> If a plaintext secret ever made it into a pushed commit, encrypting it afterwards doesn't help, because it's still in Git history. Rotate the secret.
{: .prompt-tip }

## The Disaster Recovery Story, Updated

At the end of Part 2, rebuilding the cluster needed your persistent data and a separately stored `secrets.yaml`. Now it looks like this:

1. Get the **age key** from your password manager.
2. Wipe the server and write Talos to disk (Part 1, Steps 2–4).
3. `sops exec-file talos/secrets.yaml 'talosctl gen config ...'`, then apply the config and bootstrap (Part 1, Steps 5–6). Because the secrets are the same, the new cluster has the **same CA**, and your old `talosconfig` and kubeconfig keep working.
4. Install Cilium (Part 1, Step 7).
5. Recreate the `sops-age` secret, then run `flux bootstrap`.
6. Wait.

The only things outside Git are **one age key** and your **persistent volumes**. Everything else, including every secret, comes back from the repository.

## Final Thoughts

SOPS + age is the kind of tool I like best: small, boring, and with no extra moving parts in the cluster. Flux already knows how to use it, the encrypted files stay reviewable, and you're never locked into a cluster-side key you might lose.

With this, the stack from this series is complete:

- an **immutable OS** (Talos)
- **eBPF networking** (Cilium)
- **Git-driven operations** (Flux)
- **secrets in Git**, encrypted (SOPS + age)

The whole setup is now one repository plus one key. Next up: upgrading Talos and Kubernetes the GitOps way, without the "let's hope this reboot works" moment.

Happy encrypting 🔐
