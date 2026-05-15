# osu! Near-Miss Finder

> Find the maps you almost full-comboed.

Scan an [osu!](https://osu.ppy.sh) username and the app pulls their top plays
from the official API, then surfaces the ones that ended with just a handful of
misses - the maps you should probably retry tonight.

![screenshot placeholder](docs/screenshot.png)

## Features

- 🔎 Scan any public osu! profile by username
- 🎯 Filter plays by miss-count range (`1-5` by default, configurable)
- 🎮 All four modes: standard / taiko / catch / mania
- 📋 Top plays, recent plays, #1 ranks, or pinned scores
- 🎨 Dark, rhythm-game-inspired UI with beatmap covers and difficulty stars
- ⚡ Pure FastAPI + vanilla JS - no build step

## How it works

The app authenticates against the osu! API v2 using the
[`client_credentials`](https://osu.ppy.sh/docs/index.html#client-credentials-grant)
flow (no user login required - only public data is read), fetches a user's top
plays, and filters them by the `count_miss` statistic.

> **Note:** The osu! API does not expose a "list every play ever made" endpoint.
> The app reads from `users/{id}/scores/{best|recent|firsts|pinned}`, which
> covers your top ranked plays (typically 100, paginated up to 200), the last
> 24h of recent attempts, and a couple of smaller lists. That's where the
> near-misses live for most players.

## Setup

### 1. Get osu! API credentials

1. Log in to [osu.ppy.sh](https://osu.ppy.sh) and go to
   **Settings → OAuth → New OAuth Application**.
2. Pick any application name (e.g. `near-miss-finder`).
3. Callback URL can be anything - e.g. `http://localhost:8000`.
   The `client_credentials` flow does not redirect anywhere.
4. Copy the **Client ID** and **Client Secret**.

### 2. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/osu-near-miss-finder.git
cd osu-near-miss-finder

python -m venv .venv

# Activate the venv - pick the line for your shell:
source .venv/bin/activate          # macOS / Linux
source .venv/Scripts/activate      # Windows (Git Bash / MINGW64)
.venv\Scripts\activate             # Windows (PowerShell / cmd)

pip install -r requirements.txt
```

> **Heads-up for Windows users:** Python's `venv` creates a `Scripts/` folder
> on Windows instead of `bin/`, even when you're using Git Bash. If you see
> `bash: .venv/bin/activate: No such file or directory`, use
> `source .venv/Scripts/activate` instead.

### 3. Configure

```bash
cp .env.example .env
# then edit .env and paste your client id + secret
```

### 4. Run

```bash
uvicorn main:app --reload
```

Open <http://localhost:8000> and start scanning.

## API

The frontend talks to a single endpoint:

```
GET /api/near-misses/{username}
```

Query parameters:

| Param         | Default | Description                                         |
|---------------|---------|-----------------------------------------------------|
| `mode`        | `osu`   | `osu`, `taiko`, `fruits`, `mania`                   |
| `score_type`  | `best`  | `best`, `recent`, `firsts`, `pinned`                |
| `min_misses`  | `1`     | Inclusive lower bound on misses                     |
| `max_misses`  | `5`     | Inclusive upper bound on misses                     |
| `limit`       | `100`   | How many plays to scan (1-200, paginated)           |
| `include_fc`  | `false` | If true, includes 0-miss plays regardless of `min`  |

Example:

```bash
curl "http://localhost:8000/api/near-misses/mrekk?max_misses=2&limit=100"
```

## Project layout

```
osu-near-miss-finder/
├── main.py              FastAPI app + osu! API client
├── requirements.txt
├── .env.example         Copy → .env and fill in
├── .gitignore
├── LICENSE              MIT
└── static/
    ├── index.html
    ├── style.css
    └── script.js
```

## Tech

- **Backend:** FastAPI, httpx, python-dotenv
- **Frontend:** Vanilla HTML/CSS/JS (no framework, no build step)
- **API:** [osu! API v2](https://osu.ppy.sh/docs/index.html)

## Roadmap ideas

- [ ] Cache responses so re-scans are instant
- [ ] OAuth Authorization Code flow → access user's *all* recent scores
- [ ] Sort by closest-to-FC (miss count ÷ total objects)
- [ ] Direct "open in osu!direct" links
- [ ] Share-card export for posting on socials

## License

MIT - see [LICENSE](LICENSE).

Not affiliated with osu! or ppy Pty Ltd.