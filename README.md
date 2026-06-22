# tools

A collection of utility scripts and tools.

## monitor_server.py

Pings a remote server on a schedule and sends an email alert when it becomes unreachable.

### Setup

1. Install dependencies:
   ```bash
   uv add python-dotenv
   ```

2. Create a `.env` file in the project root:
   ```
   gmail-app-password=xxxx xxxx xxxx xxxx
   email-handle=you@gmail.com
   ```
   To get a Gmail app password: **Google Account → Security → 2-Step Verification → App passwords**.

### Usage

```bash
# Verify email config
uv run python monitor_server.py --server <host> --test-email

# One-shot check (for cron)
uv run python monitor_server.py --server <host> --once

# Daemon mode (checks every 5 minutes)
uv run python monitor_server.py --server <host>
```

### Cron job

Add to `crontab -e` to check every 5 minutes:
```
*/5 * * * * /path/to/.venv/bin/python /path/to/monitor_server.py \
    --server <host> --once >> /tmp/server_monitor.log 2>&1
```

