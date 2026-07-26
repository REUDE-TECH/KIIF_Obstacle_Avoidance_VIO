# Remote access (camera on your PC)

Render cannot use the OAK-D. For remote viewing, run Streamlit **on the PC with the camera** and tunnel it out.

## One-time

1. Plug in OAK-D.
2. Detach from Docker/WSL if needed:
   ```powershell
   usbipd list
   usbipd detach --busid <BUSID>
   ```
3. Install tunnel client:
   ```bat
   install_remote_tunnel.bat
   ```

## Every session

```bat
run_remote.bat
```

1. A Streamlit window starts (camera pipeline on this PC).
2. Cloudflare prints a public URL: `https://xxxx.trycloudflare.com`
3. Open that URL on your phone or another laptop.
4. In the app: **Start pipeline** (not demo).

Keep both windows open. Closing the tunnel window ends remote access.

## Notes

- Quick tunnels (`*.trycloudflare.com`) are temporary; URL changes each run.
- Anyone with the URL can open the UI while the tunnel is up — stop the tunnel when done.
- For a stable private URL, use Tailscale Serve or a named Cloudflare tunnel later.
