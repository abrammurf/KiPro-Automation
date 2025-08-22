# KiPro Automation

**AJA Ki Pro → Dropbox Automation (with Auto‑Record & Media Wipe)**

---

## About The Project

This project automates **weekly backups of AJA Ki Pro recordings to Dropbox**, with optional **automatic start/stop recording** on multiple Ki Pros and **post‑backup media formatting**.

**What it does**

* Authenticates to Dropbox (one‑time OAuth) and persists tokens locally.
* Switches a Ki Pro into **Data‑LAN mode** for file transfer, detects expected clip names (e.g., `YYYYMMDD_9AM`, `YYYYMMDD_11AM`), downloads, then uploads to **timestamped folders** in Dropbox.
* Can **start/stop recording** on all configured Ki Pros at scheduled times using the HTTP config API.
* Optionally **formats Ki Pro media** when uploads succeed, then returns units to **Record‑Play** mode.
* Runs on a simple **Python scheduler** (`schedule`) with structured logging to file + console.

> ⚠️ **Media erase warning**: The `format_kipro_media()` routine will wipe media on all configured Ki Pros. Keep this enabled only if you’re confident uploads completed successfully and you intend to clear the media.

---

## Built With

* Python 3.10+
* [`requests`](https://pypi.org/project/requests/) — HTTP calls to Ki Pros
* [`dropbox`](https://pypi.org/project/dropbox/) — Dropbox SDK (upload & sessions)
* [`schedule`](https://pypi.org/project/schedule/) — Lightweight job scheduler
* `logging`, `pathlib`, `datetime`, `json`
* Hardware: **AJA Ki Pro** units reachable over LAN

---

## Getting Started

Follow these steps to run the automation and (optionally) schedule it.

### Prerequisites

1. **Network**: Ki Pros reachable via HTTP on the LAN. Update the IPs in the script if needed.
2. **Dropbox App**: Create a Dropbox app and note its **App key** and **App secret**.
3. **Python**: Python 3.10+ with pip available.

### Installation

```bash
# 1) Clone your repo and enter it
git clone <YOUR_REPO_URL>.git
cd <YOUR_REPO_NAME>

# 2) (Recommended) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3) Install dependencies
pip install --upgrade pip wheel
pip install requests dropbox schedule

# 4) (Optional) Create a log directory if you prefer a custom path
# The script defaults to a file named kipro_automation.log in the project root
```

---

## Configuration

Update these constants at the top of the script:

* `KIPRO_1_IP`, `KIPRO_2_IP`, `KIPRO_3_IP` — Ki Pro IP addresses
* `DROPBOX_FOLDER` — Destination root in Dropbox (e.g., `/AUTO TEST`)
* `LOCAL_TEMP_DIR` — Temp download directory (created if missing)
* `LOG_FILE` — Log file name
* `TOKEN_FILE` — Where OAuth tokens are stored (JSON)

### Dropbox App Credentials

The script currently sets:

```python
APP_KEY = '...'
APP_SECRET = '...'
```

For production, **prefer environment variables** and load them in code:

```python
import os
APP_KEY = os.getenv('DROPBOX_APP_KEY')
APP_SECRET = os.getenv('DROPBOX_APP_SECRET')
```

Then set them on your host:

```bash
export DROPBOX_APP_KEY=your_key
export DROPBOX_APP_SECRET=your_secret
```

### Scheduling (default)

The `main()` function (commented in the script) schedules:

* **Weekly upload**: Sundays at **02:00** → `automation.run_weekly_upload()`
* **Auto‑record start**: Sundays **08:55** for `9AM`, **10:55** for `11AM`
* **Auto‑record stop**: Sundays **09:55** and \*\*11:55\`

Adjust these in `main()` to fit your workflow.

### File Naming Convention

Recording starts use names like:

```
YYYYMMDD_9AM_KiPro1
YYYYMMDD_11AM_KiPro3
```

The upload routine checks for `YYYYMMDD_9AM` and `YYYYMMDD_11AM` (with or without `.mov`).

---

## Usage

### 1) First‑run OAuth

Run the script once to complete Dropbox OAuth. You’ll be shown a URL to authorize and asked for a code:

```bash
python kipro_automation.py
```

Tokens are stored in `dropbox_token.json` for subsequent runs.

### 2) Validate Devices & Recording Commands (optional)

The `__main__` block includes basic tests:

* Reachability checks for all Ki Pros
* `start_all_recordings("TEST")` then `stop_all_recordings()`
  Check `kipro_automation.log` and console output for results.

### 3) Run the Weekly Scheduler

Uncomment the `main()` call at the bottom of the script to enable the scheduler, then run:

```bash
python kipro_automation.py
```

Leave the process running.

## What The Weekly Upload Does (Step‑By‑Step)

1. **Switch to Data‑LAN** (`eParamID_MediaState=1`) for file transfer.
2. Build expected filenames for today (`YYYYMMDD_9AM`, `YYYYMMDD_11AM`), probe with/without `.mov`.
3. For each existing file on the Ki Pro (default base: `10.3.10.13`), **download → upload** to Dropbox under `/<DROPBOX_FOLDER>/upload_<timestamp>/`.
4. **Clean up** temporary local files.
5. If all uploads succeeded, **format media** on all Ki Pros and wait.
6. Return all units to **Record‑Play** (`eParamID_MediaState=0`).

---

## Security Notes

* **Do not commit** `dropbox_token.json` or your app credentials to version control.
* Restrict permissions on token and log files: `chmod 600 dropbox_token.json kipro_automation.log`.
* Consider running under a dedicated OS user with least privileges.

---

## Troubleshooting

* **Dropbox auth fails / token invalid**

  * Re‑run the script to perform OAuth again. Ensure `DROPBOX_APP_KEY/SECRET` are correct.
* **Cannot reach Ki Pro**

  * Verify IPs, cabling, and that the Ki Pro web/config interface is enabled. Try `curl http://<IP>/config?action=get&paramid=eParamID_TransportState`.
* **Recording didn’t start**

  * Firmware sometimes reports interim states. The script retries a status probe after starting. Ensure the unit is in Record‑Play (not Data‑LAN) before sending record.
* **Large uploads stall**

  * Files >150MB use a **sessioned upload** in 4MB chunks with progress logs. Check connectivity and Dropbox rate limits.
* **Media formatting skipped**

  * The script only formats when **all uploads succeed**. Review logs for any failed file.
* **Scheduler not running**

  * Make sure `main()` is uncommented, the process is running, and your system clock/timezone is correct.

---

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

## Contact

Project Maintainer – *Abram Murphy*
Email: *[abrammurphy22@gmail.com](mailto:abrammurphy22@gmail.com)*
Project Link: [https://github.com/abrammurf/KiPro-Automation](https://github.com/abrammurf/KiPro-Automation)

---

## Acknowledgments

* Dropbox Python SDK
* AJA Ki Pro HTTP config docs
* `schedule` library
* Inspired by the awesome **Best‑README‑Template** by *othneildrew*
