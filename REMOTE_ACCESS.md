# Remote access (camera on your PC)

Render cannot use the OAK-D. For remote viewing, run Streamlit **on the PC with the camera** and tunnel it out.

## Stable hostname (your Cloudflare account)

Dashboard: https://dash.cloudflare.com/f2ed2ffed361450d643350ed475ae9b1/home

You need a **domain already added** to that Cloudflare account.

```bat
setup_named_tunnel.bat
```

1. Browser opens → authorize Cloudflare (same account as the dashboard).
2. Creates tunnel `kiif-oak-streamlit`.
3. Route DNS (example):

```bat
cloudflared tunnel route dns kiif-oak-streamlit oak.yourdomain.com
```

4. Edit `cloudflared.yml` → set `hostname:` to that same name.
5. Run:

```bat
run_remote_named.bat
```

Manage tunnels: [Zero Trust → Networks → Tunnels](https://one.dash.cloudflare.com/).

## Quick tunnel (no domain)

```bat
run_remote.bat
```

Gives a temporary `https://xxxx.trycloudflare.com` URL (changes each run).
