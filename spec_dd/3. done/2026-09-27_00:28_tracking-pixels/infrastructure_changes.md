# Infrastructure changes for the Meta and TikTok pixels

Changes to `/home/sheena/workspace/first_class/infrastructure` and the First Class LS app repo that
production needs before the pixels fire there. Nothing here blocks the FLS work: without them
`VISITOR_COUNTRY_HEADER` is unset or the header is empty, so every visitor counts as unknown and
the pixels stay dormant.

## Why a new header

Every request reaches the box through Cloudflare, then the `edge-caddy` container
(`roles/edge/templates/Caddyfile.j2`). EDGE-11 in `docs/app_repo_contract/edge.md` says an app reads
only headers the edge sets, never Cloudflare's own, so the app never learns which CDN is in front.
The visitor's country follows the same rule: Cloudflare supplies `CF-IPCountry`, and Caddy copies it
into `X-Visitor-Country`, which is the one name FLS reads.

`header_up` overwrites, so a visitor who sends `X-Visitor-Country` directly cannot choose their own
value. Cloudflare sets `CF-IPCountry` itself, and the firewall admits web traffic from Cloudflare
only (EDGE-9), so the value is Cloudflare's.

## 1. Cloudflare: turn on IP Geolocation

In the zone's dashboard, Network → IP Geolocation → On. This is a zone setting (`ip_geolocation`),
and `roles/dns`'s API token only carries Zone:DNS:Edit, so it is a one-off dashboard step. Add it
to the setup how-to that creates the zone (`docs/setup-how-to/`) and to the checks in
`docs/running-how-to/`.

The header holds an ISO 3166-1 alpha-2 code (`ZA`, `DE`). Cloudflare sends `XX` when it cannot
place the IP and `T1` for Tor. FLS treats both as unknown.

## 2. `roles/edge`

`roles/edge/defaults/main.yml`, beside `edge_client_ip_header`:

```yaml
# The header the Caddyfile sets on every proxied request, holding the visitor's country as an
# ISO 3166-1 alpha-2 code, copied from Cloudflare's CF-IPCountry. Empty when Cloudflare sends
# none. Both app repos read this name, never CF-IPCountry. EDGE-13 in
# docs/app_repo_contract/edge.md.
edge_visitor_country_header: X-Visitor-Country
```

`roles/edge/templates/Caddyfile.j2`, inside the `reverse_proxy` block, after the
`header_up {{ edge_client_ip_header }} {client_ip}` line:

```caddyfile
header_up {{ edge_visitor_country_header }} {http.request.header.CF-IPCountry}
```

Add the variable to the table in `docs/architecture-reference/roles/edge.md`.

## 3. `docs/app_repo_contract/edge.md`: a new clause

Add `EDGE-13. The edge tells you the visitor's country, in X-Visitor-Country`, shaped like EDGE-11:
the header, where its value comes from, the `XX`/`T1`/empty cases, the literal name (an app repo
cannot read `roles/edge/defaults/main.yml`), and that `CF-IPCountry` is not the app's to read.

Say also that HTML responses must not be cached at Cloudflare. The pixel loaders are rendered per
visitor country, so a cached page would carry one visitor's gate to the next. Cloudflare does not
cache HTML by default, so this rules out adding a Cache Rule that does.

## 4. First Class LS app repo

- `settings_prod`: pin `VISITOR_COUNTRY_HEADER = "X-Visitor-Country"` as a settings constant, the way
  EDGE-11 has `X-Real-IP` pinned. Not an env key, so ENV-10 is unaffected by it.
- `.env.example`: add `META_PIXEL_ID` and `TIKTOK_PIXEL_ID`.

## 5. Env keys (`docs/app_repo_contract/env.md`, ENV-10)

Add a row: "Meta and TikTok pixels | `META_PIXEL_ID`, `TIKTOK_PIXEL_ID`, public, read from
fleet-level variables in `inventory/group_vars/all/vars.yml`. Staging sets both blank, which keeps
test sign-ups out of the production pixels."

Render both keys in the LS stacks' `inventory/group_vars/*/vars.yml` next to the Google keys: the
production values in prod, blank in staging. Adding the keys is a two-repo change (ENV-1), and
ENV-11 fails until `.env.example` and the rendered set match.

## Checking it works

After the edge change is applied and `META_PIXEL_ID` is set on production, load the site from a South African connection and confirm the Meta Pixel
Helper sees the pixel, then load it through a VPN exit in Germany and confirm no request to
`connect.facebook.net` is made.
