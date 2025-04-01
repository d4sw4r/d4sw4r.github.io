---
title: Tailscale A Zero Trust Network Made Easy
date: 2024-06-14 20:51
categories: [k8s, kubernetes, docker, ansible, network, vpn]
tags: [kubernetes, k8s , docker, ansible, network, tailscale, wireguard]     # TAG names should always be lowercase
---


![Tkubernetes is beautiful!](/assets/img/tailscale_network.png "tailscale-network")

---

## Tailscale: A Zero Trust Network Made Easy

In today's digital landscape, ensuring secure, zero-trust networking is paramount. Tailscale offers a streamlined solution through its Mesh WireGuard VPN, making zero-trust networking accessible and straightforward. This article explores the features of Tailscale, including its integration with gitOps, self-hosting capabilities, and practical use cases such as setting up an exit node for secure browsing.


### What is Tailscale?

Tailscale is a mesh VPN built on WireGuard, designed to be easy to use and highly secure. It simplifies network configuration and management by allowing devices to connect directly to each other using WireGuard's fast and secure protocol. This makes Tailscale an excellent choice for implementing a zero-trust network.

### Key Features of Tailscale

#### 1. Mesh WireGuard VPN
Tailscale leverages WireGuard's lightweight and high-performance VPN protocol, creating a mesh network where every node connects directly to every other node. This ensures secure, peer-to-peer connectivity without the need for central VPN servers.

#### 2. Easy Zero-Trust Implementation
Tailscale's zero-trust networking model ensures that every connection is authenticated and authorized, providing robust security for your network. It simplifies the setup process, making it accessible for users of all technical levels.

#### 3. GitOps Integration via GitHub Actions
Tailscale can be integrated into your gitOps workflow using GitHub Actions. This allows for automated deployment and management of your Tailscale network, enhancing your CI/CD pipeline and ensuring consistent, repeatable configurations.

#### 4. Self-Hosted Option with Headscale
For those who prefer self-hosting, Tailscale offers Headscale, an open-source implementation of Tailscale's control server. This gives you complete control over your network, enabling you to host it on your own infrastructure.

#### 5. Exit Node for Secure Browsing
One of Tailscale's standout features is the ability to configure an exit node. This allows you to route your internet traffic through a specific node in your Tailscale network, effectively replacing traditional VPN solutions for secure browsing.

### Using Tailscale with Cloud-Init
You can quickly set up Tailscale on your cloud instances using cloud-init. Here's an example configuration:

```yaml
#cloud-config
# The above header must generally appear on the first line of a cloud config
# file, but all other lines that begin with a # are optional comments.

runcmd:
  # One-command install, from https://tailscale.com/download/
  - ['sh', '-c', 'curl -fsSL https://tailscale.com/install.sh | sh']
  # Set sysctl settings for IP forwarding (useful when configuring an exit node)
  - ['sh', '-c', "echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf && echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf && sudo sysctl -p /etc/sysctl.d/99-tailscale.conf"]
  # Generate an auth key from your Admin console
  # https://login.tailscale.com/admin/settings/keys
  # and replace the placeholder below
  - ['tailscale', 'up', '--authkey=<auth_key>']
  # Optional: Include this line to make this node available over Tailscale SSH
  - ['tailscale', 'set', '--ssh']
  # Optional: Include this line to configure this machine as an exit node
  - ['tailscale', 'set', '--advertise-exit-node']
```

### Using Tailscale with Docker as a Network Driver
Tailscale can be used with Docker to create secure, containerized applications. Here's an example Docker Compose configuration:

```yaml
---
version: "3.7"
services:
  tailscale-nginx:
    image: tailscale/tailscale:latest
    hostname: tailscale-nginx
    environment:
      - TS_AUTHKEY=<auth_key>
      - TS_EXTRA_ARGS=--advertise-tags=tag:container
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_USERSPACE=false
    volumes:
      - ${PWD}/tailscale-nginx/state:/var/lib/tailscale
      - /dev/net/tun:/dev/net/tun
    cap_add:
      - net_admin
      - sys_module
    restart: unless-stopped
  code-server:
    image: lscr.io/linuxserver/code-server:latest
    container_name: code-server
    depends_on:
      - tailscale-nginx
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
      - PASSWORD=password #optional
      - HASHED_PASSWORD= #optional
      - SUDO_PASSWORD=password #optional
      - SUDO_PASSWORD_HASH= #optional
      - DEFAULT_WORKSPACE=/config/workspace #optional
    volumes:
      - ./config:/config
    restart: unless-stopped
    network_mode: service:tailscale-nginx
```


### Ansible Role for Tailscale
Automate the setup and management of Tailscale using Ansible. Here's a snippet from the requirements.yml file to get you started:

```yaml
# cat requirements.yml
# from GitH
- name: artis3n.tailscale
  src: https://github.com/artis3n/ansible-role-tailscale.git
```

### Conclusion
Tailscale simplifies the implementation of zero-trust networks with its user-friendly interface and powerful features. Whether you're integrating it into a gitOps workflow, setting up a self-hosted network with Headscale, or using it as a VPN replacement with an exit node, Tailscale offers a flexible and secure solution for modern networking needs. Try out the configurations and integrations mentioned in this article to harness the full potential of Tailscale in your environment.
