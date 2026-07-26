# Remote access (camera on your PC)

Render cannot use the OAK-D. For remote viewing, run Streamlit **on the PC with the camera** and tunnel it out.

## Stable hostname (your Cloudflare account)

Dashboard: https://dash.cloudflare.com/f2ed2ffed361450d643350ed475ae9b1/home

You need a **domain already added** to that Cloudflare account (e.g. `reude.tech`).

```bat
setup_named_tunnel.bat
```

Creates tunnel **`REUDETECH`** and hostname **`reudetech.reude.tech`**.

If DNS route fails, add `reude.tech` to Cloudflare first, or edit `HOSTNAME` in `setup_named_tunnel.bat`.

Then run:

```bat
run_remote_named.bat
```

Public URL: `https://reudetech.reude.tech`

## Quick tunnel (no domain)

```bat
run_remote.bat
```

Gives a temporary `https://xxxx.trycloudflare.com` URL (changes each run).
