# EZIO SMTP Server and Camera Alert Runner

A Python project for local SMTP email submission, optional outbound SMTP relay, and camera cleanliness/obstruction alert emails.

This README is intended to help a colleague set up the project on a Windows development machine, configure it safely, run the available tests, and send a sample camera alert.

> **Important:** The camera alert runner is a demonstration entry point. It submits a sample alert for `CAM-014`; it does not connect to a camera or run an inference loop by itself. The local SMTP server must be started separately.

## Contents

- [Features](#features)
- [Project layout](#project-layout)
- [Prerequisites](#prerequisites)
- [Setup on Windows](#setup-on-windows)
- [Configuration](#configuration)
- [Start the SMTP server](#start-the-smtp-server)
- [Send a sample camera alert](#send-a-sample-camera-alert)
- [Test SMTP submission](#test-smtp-submission)
- [Run the test suite](#run-the-test-suite)
- [Email template](#email-template)
- [Troubleshooting](#troubleshooting)
- [Security and Git](#security-and-git)
- [Production considerations](#production-considerations)

## Features

- Local SMTP submission endpoint (commonly `127.0.0.1:1025` in this project).
- Optional outbound SMTP relay, depending on the server configuration.
- Camera cleanliness/obstruction alert messages.
- Plain-text and HTML email support.
- HTML template stored separately from the mailer code.
- Configurable alert recipients and cooldown interval.
- Unit tests for email construction and camera-monitor behavior.

## Project layout

The following is the expected high-level layout based on the project files reviewed. Some files may differ in your checkout; keep the actual source files that your project uses.

```text
E:\\SMTP_Server\\
├── .env                         # Local configuration; never commit
├── .env.example                 # Sanitized example configuration (create if absent)
├── .gitignore
├── README.md
├── requirements.txt
├── run_camera_alert.py          # Camera alert launcher
├── camera_alert_runner.py       # Loads .env and runs the sample alert
├── app/                         # SMTP server implementation
│   ├── config.py
│   ├── protocol.py
│   ├── relay.py
│   ├── server.py
│   ├── session.py
│   └── storage.py
├── ezio_camera_alerts/
│   ├── config.py
│   ├── mailer.py
│   ├── monitor.py
│   └── templates/
│       └── camera_dirty_alert.html
├── scripts/
│   ├── __init__.py
│   └── smtp_client_test.py      # Keep one canonical test client if duplicated
├── tests/
│   ├── test_mailer.py
│   └── test_monitor.py
├── mail_spool/                  # Runtime data; do not commit
└── .venv/                       # Local virtual environment; do not commit
```

There may also be a root-level `smtp_client_test.py`. If both root and `scripts/` copies exist, choose one canonical implementation and keep the other as a small launcher or remove it only after checking references. Avoid maintaining two independent copies of the same script.

## Prerequisites

- Windows 10/11 or another supported Python environment.
- Python 3.10 or newer is a reasonable starting point, but use the Python version validated by the project owner and its dependencies.
- `pip`.
- A running local SMTP server for camera alert submissions.
- Authorized relay credentials and network access if outbound relay is enabled.
- Git is optional for downloading the repository.

## Setup on Windows

Open PowerShell and move to the project directory:

```powershell
cd E:\SMTP_Server
```

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, follow your organization's execution-policy guidance. Alternatively, call the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The camera runner imports `python-dotenv`. Ensure `requirements.txt` includes it, for example:

```text
python-dotenv>=1.0,<2.0
```

Install any additional dependencies required by the SMTP server and test suite through the project's maintained requirements file. Do not assume that `python-dotenv` is the only dependency for the whole repository.

## Configuration

### Create `.env`

If `.env.example` exists, copy it to create your local `.env` file:

```powershell
Copy-Item .env.example .env
```

If it does not exist, create `.env` in the project root and add the required settings after checking the variable names in `app/config.py`, `ezio_camera_alerts/config.py`, and the relay implementation.

Example camera-alert settings:

```dotenv
# Camera alert recipients (comma-separated)
EZIO_ALERT_RECIPIENTS=recipient@example.com
EZIO_ALERT_COOLDOWN_SECONDS=900

# Local SMTP endpoint used by the camera alert mailer
EZIO_SMTP_HOST=127.0.0.1
EZIO_SMTP_PORT=1025
EZIO_SMTP_TIMEOUT_SECONDS=15

# Outbound relay settings: use the exact names expected by app/config.py
SMTP_RELAY_ENABLED=false
SMTP_RELAY_HOST=
SMTP_RELAY_PORT=465
SMTP_RELAY_SECURITY=ssl
SMTP_RELAY_USERNAME=
SMTP_RELAY_PASSWORD=
SMTP_RELAY_TIMEOUT_SECONDS=20
```

These are example values, not production credentials. Confirm the exact SMTP relay variable names and accepted security values against the current `app/config.py` before enabling relay. Do not copy real passwords into the README or `.env.example`.

### How the camera runner loads configuration

The runner should load the project-root `.env` before reading environment variables:

```python
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=True)
```

With `override=True`, values from `.env` take precedence over inherited environment variables for that execution. Saving `.env` does not change a Python process that is already running; restart the process to reload configuration.

The camera-alert package uses these settings:

| Variable | Purpose |
|---|---|
| `EZIO_ALERT_RECIPIENTS` | Comma-separated list of alert recipients |
| `EZIO_ALERT_COOLDOWN_SECONDS` | Cooldown interval for repeated alerts |
| `EZIO_SMTP_HOST` | SMTP endpoint used by the camera mailer |
| `EZIO_SMTP_PORT` | SMTP port used by the camera mailer |
| `EZIO_SMTP_TIMEOUT_SECONDS` | SMTP connection timeout |

Consult `ezio_camera_alerts/config.py` and `ezio_camera_alerts/monitor.py` for the current defaults and exact behavior.

## Start the SMTP server

The SMTP server and the camera alert sender are separate processes. Start the SMTP server first, then run the camera alert sender.

The reviewed server implementation is in `app/server.py`, but the correct startup command depends on how that file initializes the server and how the package imports are arranged. **Verify the actual entry point in your checkout before using a command.** Do not assume that `python server.py` works from the repository root.

From the project root, inspect the server entry point and use the startup command maintained by your project. Confirm that the server starts without errors and listens on the expected host and port.

The local SMTP listener has been configured for loopback use in the reviewed implementation. This means it is intended for local submissions on the same machine unless you deliberately change the network configuration and secure it.

## Send a sample camera alert

With the virtual environment activated and the SMTP server running, execute this from the project root:

```powershell
python run_camera_alert.py
```

`run_camera_alert.py` imports `main()` from `camera_alert_runner.py`. The runner:

1. Loads the project-root `.env`.
2. Reads the configured recipients and cooldown.
3. Creates a sample alert for camera `CAM-014`.
4. Submits the alert through the configured local SMTP endpoint.

Example log messages may look like:

```text
INFO:camera-monitor:Loaded alert recipients: ['recipient@example.com']
INFO:camera-monitor:Alert cooldown: 900.0 seconds
INFO:camera-monitor:Camera alert result=alert_sent (cooldown=900.0s)
```

The exact output depends on the monitor state and SMTP server response. Use a test recipient unless you intend to send a real notification.

For production integration, replace the demonstration values in `camera_alert_runner.py` with actual camera status, inference results, camera identifiers, and an approved recipient policy.

## Test SMTP submission

If the root-level `smtp_client_test.py` is present, run:

```powershell
python smtp_client_test.py
```

The updated client can accept an explicit recipient and optional SMTP debug output:

```powershell
python smtp_client_test.py --recipient recipient@example.com
python smtp_client_test.py --recipient recipient@example.com --debug
```

Check `python smtp_client_test.py --help` to see the arguments supported by the version in your checkout. If you use only `scripts/smtp_client_test.py`, run that path instead.

A successful local SMTP submission means the local server accepted the message for submission. It does **not** independently prove that the outbound relay delivered the message to the recipient's inbox. Check server/relay logs and the recipient mailbox.

SMTP debug output can reveal addresses and protocol details. Enable it only when needed and avoid sharing logs that contain sensitive information.

## Run the test suite

From the project root, with the project's virtual environment activated:

Run all tests:

```powershell
python -m unittest discover -s tests -v
```

Or run the mailer and monitor tests separately:

```powershell
python -m unittest tests.test_mailer -v
python -m unittest tests.test_monitor -v
```

Before committing changes, run:

```powershell
git diff --check
git status --short
```

The number of tests can change as the project evolves. Treat the test output from your checkout as authoritative.

## Email template

The camera dirty-alert HTML template is expected at:

```text
ezio_camera_alerts/templates/camera_dirty_alert.html
```

Edit this file to update layout, styling, logo, branding, or signature. Keep its placeholders synchronized with the rendering logic in `ezio_camera_alerts/mailer.py`. The reviewed template logic uses placeholders such as:

```text
{{ severity }}
{{ camera_id }}
{{ camera_name }}
{{ location }}
{{ detected_at }}
{{ confidence }}
{{ details }}
```

Run the relevant tests after changing the template or its rendering logic.

## Troubleshooting

### `ModuleNotFoundError: No module named 'camera_alert_runner'`

Confirm both files exist in the project root:

```text
run_camera_alert.py
camera_alert_runner.py
```

Then run from the root:

```powershell
cd E:\SMTP_Server
python run_camera_alert.py
```

### The old recipient is being used

Check the intended configuration value without printing unrelated secrets:

```powershell
python -c "from dotenv import dotenv_values; print(dotenv_values(r'E:\SMTP_Server\.env').get('EZIO_ALERT_RECIPIENTS'))"
```

Confirm that the runner loads `.env` with `override=True` before reading `os.getenv`, then start a new run. A running process does not automatically reload `.env`.

### SMTP connection refused

- Confirm the SMTP server process is running.
- Verify the host and port in the camera mailer configuration.
- Review the SMTP server logs for startup or bind errors.
- Remember that `127.0.0.1` refers to the same computer running the sender.
- Ensure no other service is already using the configured port.

### HTML template not found

Confirm that `ezio_camera_alerts/templates/camera_dirty_alert.html` exists and that `TEMPLATE_PATH` in `ezio_camera_alerts/mailer.py` points to the same location.

### Email submitted but not received

- Check the local SMTP server's response and logs.
- Check outbound relay configuration and provider logs.
- Check the recipient address and spam/junk folders.
- Check domain email authentication and forwarding rules where relevant.
- Remember that submission acceptance is not the same as final delivery.

### An alert is suppressed by cooldown

The example uses a cooldown configured through `EZIO_ALERT_COOLDOWN_SECONDS` (commonly `900` seconds, or 15 minutes). Review `ezio_camera_alerts/monitor.py` for the precise suppression and recovery behavior. Monitor state is held in memory, so restarting the process may reset it.

## Security and Git

Never commit `.env`, SMTP passwords, access tokens, private keys, sensitive email content, or spool data. Commit a sanitized `.env.example` containing placeholders only.

Suggested `.gitignore` entries:

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/

# Environment and secrets
.env
.env.*
!.env.example

# Logs and runtime spool
*.log
logs/
mail_spool/
spool/

# IDE files
.vscode/
.idea/
```

Adjust these rules to match the actual project. Before pushing:

```powershell
git status --short
git diff --check
python -m unittest discover -s tests -v
```

Review staged files to ensure secrets and runtime data are not included. `.gitignore` does not remove a secret that was already committed. If a credential has been exposed, rotate it immediately; removing it from a file does not erase it from Git history.

For company code, use an appropriately private repository and grant access only to authorized colleagues.

## Production considerations

Before using this system in production:

- Confirm the SMTP server's startup command and operational configuration.
- Configure TLS/SSL and relay credentials according to the provider's requirements.
- Keep the SMTP listener inaccessible to untrusted networks unless remote access is deliberately designed and secured.
- Protect secrets and avoid logging passwords or sensitive email contents.
- Add monitoring, rate limiting, retry handling, and operational alerting appropriate to your environment.
- Decide how spool data is retained, backed up, and cleaned up.
- Test failure cases, including relay timeouts, rejected recipients, and duplicate alert suppression.
- Integrate real camera inference and status updates; the sample runner does not perform live camera monitoring.

## License and maintainers

Add your organization's approved license, maintainer/contact details, and repository URL before distributing this project.
