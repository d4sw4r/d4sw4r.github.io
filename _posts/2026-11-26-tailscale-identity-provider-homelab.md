---
title: "Zero Passwords, Zero Open Ports: Tailscale as the Identity Provider for My Homelab"
description: "Tailscale already knows who sends every packet. Use that identity to log into Grafana without a login page, run your own OIDC provider with tsidp, and build a Wake-on-LAN button whose permissions live in your ACL file."
date: 2026-11-26 08:00 +0100
categories: [network, security]
tags: [tailscale, wireguard, zero-trust, sso, oidc, tsidp, tsnet, grafana, homelab, go]
image:
  path: /assets/img/tailscale-identity-provider.png
  alt: Tailscale as the identity provider for a homelab with Serve identity headers, tsidp and tsnet
---

A while ago I wrote about **[Tailscale as a zero trust network]({% post_url 2024-06-14-tailscale %})** and about **[on-demand exit nodes for pennies]({% post_url 2024-10-30-vpn-4-pennys %})**. Both posts treat Tailscale as what most people think it is: a very good VPN.

Here is the thing that took me way too long to realize: **Tailscale is not really a VPN. It's an identity system that happens to move packets.** Every single packet that reaches one of my machines is cryptographically tied to a WireGuard key, that key is tied to a device, and that device is tied to a person who logged in with SSO and MFA.

And then I open Grafana on that machine and... type a password. Into a login form. That I had to create. Over a connection where the server *already knows exactly who I am*.

This post fixes that. By the end, my homelab has no login pages, no local user databases, and no open ports, and permissions live in **one file**: the Tailscale policy file.

This post covers three levels, from "five minutes" to "slightly unhinged":

- 👉 **Level 1: identity headers.** `tailscale serve` tells your app who's calling. Grafana logs you in without a login form.
- 👉 **Level 2: your own OIDC provider.** `tsidp` turns your tailnet into a real OpenID Connect IdP for apps that only speak OIDC (Proxmox, Forgejo, Immich, …).
- 👉 **Level 3: apps that are their own tailnet node.** A tiny Go service built with `tsnet` that asks Tailscale *who* is calling and reads *what they may do* straight from the ACL file. My example: a Wake-on-LAN button for the family.

## The Idea: The WireGuard Key Is the Credential

When a request arrives over Tailscale, the local `tailscaled` can answer one question with certainty: **which node and which user sent this?** It's not a guess based on a cookie or a header. It comes from the WireGuard handshake, and the control plane only handed that peer's key to my machine because the policy file allowed it.

So the authentication already happened, when I logged into Tailscale with my identity provider, including MFA. Everything a classic login page does afterwards is redundant at best and an extra attack surface at worst.

The three levels below are just three different ways of handing that identity to an application.

| Level | How the app learns who you are | Works for | Effort |
|---|---|---|---|
| 1. Serve headers | HTTP headers set by `tailscale serve` | Apps with "auth proxy" / header auth | 5 minutes |
| 2. tsidp | Standard OIDC login flow | Anything with "Login with OpenID Connect" | 30 minutes |
| 3. tsnet + WhoIs | The app asks `tailscaled` directly | Your own tools | An evening |

## Level 1: Grafana Without a Login Page

`tailscale serve` is a reverse proxy built into the Tailscale client. It gets a real TLS certificate for `machine.your-tailnet.ts.net` and forwards requests to a local port. What most people miss: it also adds **identity headers** to every proxied request:

- `Tailscale-User-Login`: the login name, e.g. `alice@example.com`
- `Tailscale-User-Name`: the display name, e.g. `Alice Architect`
- `Tailscale-User-Profile-Pic`: the profile picture URL, if your IdP provides one

If a client tries to send these headers itself, Serve strips them. Grafana has had an auth proxy mode for years that does exactly what we need: "trust this header, it contains the username."

### Step 1: Run Grafana on localhost only

This is the important part. The headers are only trustworthy if **nobody can reach Grafana without going through Serve**. So Grafana listens on `127.0.0.1` and nowhere else:

```yaml
# compose.yaml
services:
  grafana:
    image: grafana/grafana:latest   # pin a version in real life
    network_mode: host
    restart: unless-stopped
    environment:
      GF_SERVER_HTTP_ADDR: "127.0.0.1"
      GF_SERVER_HTTP_PORT: "3000"
      GF_SERVER_ROOT_URL: "https://homelab.your-tailnet.ts.net/"

      # Trust the identity headers from tailscale serve
      GF_AUTH_PROXY_ENABLED: "true"
      GF_AUTH_PROXY_HEADER_NAME: "Tailscale-User-Login"
      GF_AUTH_PROXY_HEADER_PROPERTY: "username"
      GF_AUTH_PROXY_HEADERS: "Name:Tailscale-User-Name"
      GF_AUTH_PROXY_AUTO_SIGN_UP: "true"
      GF_AUTH_PROXY_WHITELIST: "127.0.0.1"

      # No login form, new users are viewers
      GF_AUTH_DISABLE_LOGIN_FORM: "true"
      GF_USERS_AUTO_ASSIGN_ORG_ROLE: "Viewer"

      # The built-in admin *is* my Tailscale login
      GF_SECURITY_ADMIN_USER: "alice@example.com"
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  grafana-data:
```

Two details I like here:

- `GF_AUTH_PROXY_WHITELIST` is a second line of defense. Even if something else on the box could reach port 3000, Grafana only accepts the header from `127.0.0.1`.
- `GF_SECURITY_ADMIN_USER` set to my Tailscale login means the auth proxy maps me straight onto Grafana's built-in admin account. Everyone else lands as a Viewer.

### Step 2: Put Serve in front

```bash
docker compose up -d
sudo tailscale serve --bg 3000
tailscale serve status
```

Open `https://homelab.your-tailnet.ts.net` and you're logged in. Logout doesn't really mean anything anymore, and that's fine: the only way to "log out" is to not be on the tailnet.

> Identity headers are **not** set for requests from **tagged devices** (servers, CI runners), and **never for Funnel** traffic from the public internet. That's a feature: a Funnel request can't impersonate anyone. Just don't expect Grafana to work for a tagged node that scrapes dashboards via Serve.
{: .prompt-warning }

> Display names with non-ASCII characters can arrive RFC 2047 encoded, e.g. `=?utf-8?q?Ferris_B=C3=BCller?=`. Login names are what you match on, so this only affects how your name looks in the UI.
{: .prompt-info }

### Bonus: roles from the policy file

Since Tailscale v1.92, Serve can also forward **app capabilities**: arbitrary JSON you attach to users or groups in the policy file. You tell Serve which capabilities to pass along:

```bash
sudo tailscale serve --bg --accept-app-caps=example.com/cap/grafana 3000
```

The backend then receives a `Tailscale-App-Capabilities` header with the JSON your grant defines, for example `{"role": "editor"}`. Grafana can't map a JSON header to a role on its own, but your own apps can. That's exactly what Level 3 does, without a proxy in between.

## Level 2: tsidp, an OIDC Provider Made of Your Tailnet

Header auth is great, but lots of software only knows one way to do SSO: **OpenID Connect**. Proxmox, Forgejo, Immich, Paperless, Outline, and so on. Normally that means running Keycloak or Authentik, which is yet another user database with yet another admin password.

**tsidp** is a small OIDC provider from Tailscale that runs as its own node on your tailnet. When an app sends you to tsidp to log in, tsidp doesn't show a form. It looks at the incoming connection, asks Tailscale who you are, and issues the token. If you're on the tailnet, you're logged in. If you're not, you can't even reach the IdP.

> tsidp is explicitly **experimental** and below v1.0. The README warns about breaking changes, and the capability schema may change. I use it for homelab apps, not for anything I'd be paged for.
{: .prompt-warning }

### Step 1: Policy file

tsidp gets its own tag. Everyone may reach it, but only admins may use its admin UI (where you register clients):

```json
{
  "tagOwners": {
    "tag:tsidp": ["autogroup:admin"]
  },
  "grants": [
    {
      "src": ["autogroup:member"],
      "dst": ["tag:tsidp"],
      "ip":  ["tcp:443"]
    },
    {
      "src": ["group:admins"],
      "dst": ["tag:tsidp"],
      "app": {
        "tailscale.com/cap/tsidp": [
          { "allow_admin_ui": true, "allow_dcr": true }
        ]
      }
    }
  ]
}
```

Admin UI and dynamic client registration are denied by default. App capability grants are evaluated per request, so you don't need to restart tsidp after changing them.

### Step 2: Run it

Create a **tagged** auth key (`tag:tsidp`) in the admin console, store it in a file, and run the official image:

```yaml
# compose.yaml
services:
  tsidp:
    image: ghcr.io/tailscale/tsidp:latest
    restart: unless-stopped
    volumes:
      - tsidp-data:/data
    secrets:
      - ts_authkey
    environment:
      TAILSCALE_USE_WIP_CODE: "1"   # required while tsidp is < 1.0
      TS_STATE_DIR: "/data"         # persistent state, NOT optional
      TS_HOSTNAME: "idp"            # -> https://idp.your-tailnet.ts.net
      TS_AUTHKEY_FILE: "/run/secrets/ts_authkey"

secrets:
  ts_authkey:
    file: ./ts_authkey

volumes:
  tsidp-data:
```

```bash
docker compose up -d
curl -s https://idp.your-tailnet.ts.net/.well-known/openid-configuration | jq '.issuer, .claims_supported'
```

The first start can take a minute while the TLS certificate is issued. Without a persistent state directory, tsidp re-registers as a new node on every restart and forgets all registered clients, so keep that volume.

### Step 3: Register a client and log into Proxmox

Open `https://idp.your-tailnet.ts.net` (you'll only get the admin UI if your grant allows it), create a client, and set the redirect URI of the app, for Proxmox that's `https://pve.your-tailnet.ts.net:8006`. You get a client ID and secret.

On the Proxmox host, which must itself be on the tailnet to reach the IdP:

```bash
pveum realm add tailscale --type openid \
  --issuer-url https://idp.your-tailnet.ts.net \
  --client-id <client-id> \
  --client-key <client-secret> \
  --username-claim email \
  --autocreate 1 \
  --default 1
```

The Proxmox login screen now has a "tailscale" realm. Click login, get bounced to tsidp, get bounced straight back, done. The user shows up as `alice@example.com@tailscale`, and you give it permissions with `pveum acl modify` like any other user.

The same pattern works for every app with a generic OIDC setting: issuer URL, client ID, secret, done. One IdP, and the "user database" is your tailnet.

> Want to log into a SaaS tool with your tailnet identity? tsidp can run with `--funnel` so it's reachable from the internet. Think carefully before doing that. The whole charm of the setup is that the IdP itself is unreachable for everyone outside your tailnet.
{: .prompt-danger }

## Level 3: An App That Is Its Own Tailnet Node

Now the slightly unhinged part. With **`tsnet`**, a Go program embeds a full Tailscale node. No sidecar, no `tailscaled` on the host, no port mapping: the binary itself appears as a machine in your tailnet, gets a TLS certificate, and can ask Tailscale about every connection with `WhoIs`.

Combine that with **app capabilities** in grants and you get something that feels like magic: authorization rules for *your own app* that live in the Tailscale policy file, next to your network rules.

My use case: a Wake-on-LAN button. My partner may wake the gaming PC. I may wake everything, including the NAS and the backup box. Nobody needs an account, and nothing listens on the LAN except a magic packet now and then.

### Step 1: Define the capability in the policy file

The capability name is just a string you own, conventionally a domain you control. Its JSON shape is entirely up to you:

```json
{
  "tagOwners": {
    "tag:wol": ["autogroup:admin"]
  },
  "groups": {
    "group:family": ["partner@example.com"],
    "group:admins": ["alice@example.com"]
  },
  "grants": [
    {
      "src": ["group:family", "group:admins"],
      "dst": ["tag:wol"],
      "ip":  ["tcp:443"]
    },
    {
      "src": ["group:family"],
      "dst": ["tag:wol"],
      "app": {
        "d4sw4r.github.io/cap/wol": [{ "machines": ["gaming-pc"] }]
      }
    },
    {
      "src": ["group:admins"],
      "dst": ["tag:wol"],
      "app": {
        "d4sw4r.github.io/cap/wol": [{ "machines": ["nas", "gaming-pc", "backup"] }]
      }
    }
  ]
}
```

If someone matches several grants, they get several entries, and the app merges them.

### Step 2: The service

The whole thing is one file. It builds against `tailscale.com v1.106.1` (which needs Go 1.27):

```go
// wol: a Wake-on-LAN button that lives on your tailnet.
// No login page, no passwords: who you are comes from WireGuard,
// what you may wake comes from your Tailscale policy file.
package main

import (
	"flag"
	"fmt"
	"html/template"
	"log"
	"net"
	"net/http"
	"slices"

	"tailscale.com/tailcfg"
	"tailscale.com/tsnet"
)

// The capability name is ours. Any domain you control works.
const capWOL tailcfg.PeerCapability = "d4sw4r.github.io/cap/wol"

// What the policy file grants: which machines this user may wake.
type wolCap struct {
	Machines []string `json:"machines"`
}

// Machines on the home LAN: name -> MAC address.
var machines = map[string]string{
	"nas":       "aa:bb:cc:dd:ee:01",
	"gaming-pc": "aa:bb:cc:dd:ee:02",
	"backup":    "aa:bb:cc:dd:ee:03",
}

var page = template.Must(template.New("p").Parse(`<!doctype html>
<title>wol</title>
<h1>Hi {{.Name}} 👋</h1>
{{range .Allowed}}<form method="post"><button name="m" value="{{.}}">Wake {{.}}</button></form>{{else}}
<p>Your policy grants you nothing to wake.</p>{{end}}
{{if .Woke}}<p>Magic packet sent to <b>{{.Woke}}</b>.</p>{{end}}`))

func main() {
	dir := flag.String("dir", "/var/lib/wol", "tsnet state directory")
	flag.Parse()

	srv := &tsnet.Server{Hostname: "wol", Dir: *dir}
	defer srv.Close()

	lc, err := srv.LocalClient()
	if err != nil {
		log.Fatal(err)
	}
	ln, err := srv.ListenTLS("tcp", ":443")
	if err != nil {
		log.Fatal(err)
	}

	log.Fatal(http.Serve(ln, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		who, err := lc.WhoIs(r.Context(), r.RemoteAddr)
		if err != nil {
			http.Error(w, "who are you?", http.StatusForbidden)
			return
		}

		caps, err := tailcfg.UnmarshalCapJSON[wolCap](who.CapMap, capWOL)
		if err != nil {
			http.Error(w, "bad capability", http.StatusInternalServerError)
			return
		}
		var allowed []string
		for _, c := range caps {
			for _, m := range c.Machines {
				if _, ok := machines[m]; ok && !slices.Contains(allowed, m) {
					allowed = append(allowed, m)
				}
			}
		}

		var woke string
		if r.Method == http.MethodPost {
			m := r.FormValue("m")
			if !slices.Contains(allowed, m) {
				http.Error(w, "not yours to wake", http.StatusForbidden)
				return
			}
			if err := wake(machines[m]); err != nil {
				http.Error(w, err.Error(), http.StatusBadGateway)
				return
			}
			log.Printf("%s woke %s", who.UserProfile.LoginName, m)
			woke = m
		}

		page.Execute(w, map[string]any{
			"Name":    who.UserProfile.DisplayName,
			"Allowed": allowed,
			"Woke":    woke,
		})
	})))
}

// wake sends a Wake-on-LAN magic packet: 6x 0xFF, then the MAC 16 times.
func wake(mac string) error {
	hw, err := net.ParseMAC(mac)
	if err != nil {
		return err
	}
	pkt := make([]byte, 0, 102)
	for range 6 {
		pkt = append(pkt, 0xFF)
	}
	for range 16 {
		pkt = append(pkt, hw...)
	}
	conn, err := net.Dial("udp4", "255.255.255.255:9")
	if err != nil {
		return fmt.Errorf("dial broadcast: %w", err)
	}
	defer conn.Close()
	_, err = conn.Write(pkt)
	return err
}
```

What's happening:

1. `tsnet.Server` joins the tailnet as a node called `wol`, and `ListenTLS` serves HTTPS on `https://wol.your-tailnet.ts.net` with a real certificate.
2. For every request, `WhoIs(r.RemoteAddr)` returns the **user profile** and the **CapMap**: the app capabilities that the policy grants this caller on this node.
3. `tailcfg.UnmarshalCapJSON` decodes our `d4sw4r.github.io/cap/wol` entries into a Go struct. No config file, no user table.
4. The magic packet goes out as a plain UDP broadcast on the LAN the box is connected to.

### Step 3: Run it

The binary needs to run on a machine in the same LAN as the sleeping devices, a Raspberry Pi is perfect. Create a tagged auth key with `tag:wol` and start it once with that key:

```bash
go build -o wol .
sudo mkdir -p /var/lib/wol
sudo TS_AUTHKEY=tskey-auth-xxxxx ./wol -dir /var/lib/wol
```

After the first start, the state lives in `/var/lib/wol` and the key is no longer needed, so wrap it in a systemd unit without it. Open `https://wol.your-tailnet.ts.net` on your phone and there's a button with your name on it.

Want to give your partner the backup box too? Edit the policy file, save, refresh. No deploy, no restart. The policy file just became the admin UI of your app.

> HTTPS certificates must be enabled for the tailnet (DNS settings in the admin console), otherwise `ListenTLS` can't get a certificate. And please don't log `TS_AUTHKEY` into your shell history on a shared box. Read it from a file instead.
{: .prompt-tip }

## "But Is This Actually Secure?"

Fair question, because "no passwords" sounds like a red flag at first. My take:

- **Authentication still happens**, just once and in the right place: when you log into Tailscale with your IdP, including MFA. Every app downstream inherits that.
- **Revocation is instant and central.** Lost phone? Remove the device in the admin console, and it's out of every app at the same time. Compare that with rotating ten passwords.
- **The weak spot is the app being reachable without Tailscale.** Header auth (Level 1) is only safe if the app listens on localhost. A Grafana on `0.0.0.0:3000` with auth proxy enabled lets anyone on the LAN send a fake `Tailscale-User-Login` header and become admin. That's why the whitelist exists.
- **Tagged devices are not people.** Servers and CI runners don't get identity headers, and `WhoIs` reports them as tagged nodes. Design for that: give machines capabilities through grants on tags, not through a user identity.
- **Key expiry is session expiry.** When a device key expires, the device is off the tailnet and every app session ends with it. I find that a feature.

## Final Thoughts

I started this expecting a neat trick. It ended with deleting local user accounts and admin passwords instead of adding more. What I have now:

- **one identity source:** my Tailscale login with MFA
- **zero login forms** on internal apps, via Serve identity headers
- **one OIDC provider** for everything that only speaks OIDC, which doesn't even exist outside my tailnet (tsidp)
- **authorization in the policy file**, even for my own tools, via app capabilities and `tsnet`
- **zero open ports**, as before

The mental shift is the real takeaway: stop thinking of Tailscale as the tunnel *in front of* your apps, and start treating it as the identity layer *underneath* them.

Next up, I want to take this one step further: giving **AI agents and MCP servers** their own tailnet identity, with tsidp handing out scoped tokens, so an agent can only touch what its grant allows.

Happy tailnetting 🔐
