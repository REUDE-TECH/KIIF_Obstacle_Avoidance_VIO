# Troubleshooting

This document outlines common issues encountered during setup and how to resolve them.

## Docker Permission Errors

### Problem
When running `./scripts/build.sh` or `./scripts/run.sh`, you see an error similar to:
`permission denied while trying to connect to the Docker daemon socket`

### Cause
Your user does not have permission to access the Docker engine. This usually happens if the user was not added to the `docker` group, or if the group changes haven't taken effect yet.

### Solution
1. **Apply Group Changes**: The most common fix is to simply log out of your session and log back in, or restart your terminal.
2. **Manually Add to Group**: If the install script failed to do so, you can manually add your user:
   ```bash
   sudo usermod -aG docker $USER
   ```
   Then, log out and log back in.
3. **Use Sudo (Not Recommended)**: As a temporary workaround, you can prefix the script with `sudo` (e.g., `sudo ./scripts/build.sh`), but it is highly recommended to fix the user group permissions instead for a smoother development experience.

## Building Without Cache

### Problem
You made changes to your Dockerfile or source files, but Docker is using old cached layers, causing unexpected behavior or missing updates.

### Solution
You can force Docker to rebuild the image entirely from scratch without using the cache. You can run the build command manually with the `--no-cache` flag:

```bash
docker compose build --no-cache
```

## Windows: Failed to connect to the docker API (npipe)

### Problem
When running docker commands (like `docker compose build` or `docker compose up`), you see an error similar to:
```
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

### Cause
Docker Desktop is not currently running or the Docker daemon background service has stopped.

### Solution
1. **Use the Launch Scripts**:
   The Windows batch scripts (`windows\build.bat` and `windows\run.bat`) automatically kill hung Docker processes, run `wsl --shutdown`, and restart Docker Desktop to clear out any API socket issues. Double-clicking those scripts is the easiest way to recover automatically.
2. **Launch Docker Desktop Manually**:
   - Open your Start menu and search for **Docker Desktop**.
   - Click to start the application.
   - Wait until the Docker status indicator (usually in the bottom-left corner of the window, or the tray icon in the taskbar) changes to **green** (indicating the Engine is running).
3. **Verify WSL 2 Integration** (if running commands from WSL):
   - In Docker Desktop, go to **Settings (gear icon) > Resources > WSL integration**.
   - Ensure that **Enable integration with my default WSL distro** is checked, and toggle the switch for your specific Linux distribution if you are running the commands inside WSL.
4. **Force Clean Restart via terminal**:
   - If the engine gets stuck, you can force-restart the subsystem by executing the following commands in PowerShell:
     ```powershell
     taskkill /F /IM "Docker Desktop.exe"
     wsl --shutdown
     Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
     ```
