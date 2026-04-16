[README.md](https://github.com/user-attachments/files/26795962/README.md)
# K — AI Voice Assistant

K is a voice-controlled personal assistant that manages your Google Calendar and Gmail entirely through natural speech. Talk to K the same way you'd talk to a person — it understands context, handles ambiguity, and confirms everything it does.

---

## What K can do

| Capability | Example voice command |
|---|---|
| List today's events | "What's on my calendar today?" |
| Create events | "Schedule a team meeting tomorrow at 3pm" |
| Delete events | "Cancel my dentist appointment on Friday" |
| Check for conflicts | "Am I free Thursday afternoon?" |
| Send email | "Send an email to Sarah at gmail dot com about the project update" |
| Draft email | "Draft an email to John saying I'll be late, don't send it" |
| Search contacts | "Email Alex about the Q2 report" (looks up Alex in your contacts) |
| Calendar invites | "Invite the team to the standup — book it for 9am daily" |

---

## How it works

```
Browser mic (Web Speech API)
        │
        ▼
  FastAPI backend  ──►  Claude claude-sonnet-4-6 (AI agent)
        │                       │
        │               Tool calls as needed:
        │                 • Google Calendar API
        │                 • Gmail API (send / draft)
        │                 • Google People API (contacts)
        ▼
  TTS spoken reply  ──►  Browser speaker (Web Speech API)
```

1. **Speech-to-text** — The browser's Web Speech API transcribes your voice in real time. After 2 seconds of silence the transcript is submitted.
2. **AI agent** — Claude claude-sonnet-4-6 receives the transcript plus today's date/time and decides which Google API tools to call, in what order.
3. **Google APIs** — K calls Calendar, Gmail, and Contacts on your behalf using your stored OAuth token.
4. **Text-to-speech** — The agent's plain-text reply is spoken back to you word-by-word with a floating subtitle pill.

---

## Tech stack

| Layer | Technology |
|---|---|
| AI agent | Anthropic Claude claude-sonnet-4-6 (`claude-sonnet-4-6`) |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Google auth | OAuth 2.0 via `google-auth-oauthlib` |
| Google APIs | Calendar v3, Gmail v1, People v1 |
| Frontend | Vanilla HTML/CSS/JS — zero npm, zero build step |
| Speech | Web Speech API (Chrome / Edge required) |

---

## Project structure

```
voice assistance/
├── backend/
│   ├── agent/
│   │   ├── agent.py        # Claude tool-use loop
│   │   ├── prompts.py      # System prompt (date/time injected per request)
│   │   └── tools.py        # Tool definitions passed to Claude
│   ├── middleware/
│   │   └── security.py     # Security headers middleware
│   ├── routes/
│   │   ├── auth.py         # GET /auth/login, /auth/callback, /auth/status, POST /auth/logout
│   │   ├── command.py      # POST /command — main voice command handler
│   │   └── events.py       # GET /events/today
│   ├── services/
│   │   ├── calendar.py     # Google Calendar API wrapper
│   │   ├── contacts.py     # Google People API wrapper
│   │   ├── gmail.py        # Gmail send / draft / invite
│   │   └── token_store.py  # OAuth token persistence & refresh
│   ├── config.py           # Environment variable loading & validation
│   ├── main.py             # FastAPI app, routers, static files
│   └── models.py           # Pydantic request/response models
├── frontend/
│   ├── index.html          # Single-page app (all CSS inline, no build)
│   ├── app.js              # State machine, Web Speech API, TTS, subtitle
│   └── style.css           # Base styles (mostly overridden by index.html)
├── tokens/                 # OAuth tokens stored here — git-ignored, auto-created
├── .env.example            # Copy this to .env and fill in your keys
├── .gitignore
├── requirements.txt
└── start.sh                # One-command startup script
```

---

## Setup

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd "voice assistance"
cp .env.example .env
```

Open `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
```

### 2. Get your API keys

**Anthropic (Claude)**
- Go to [console.anthropic.com](https://console.anthropic.com)
- Create an API key and paste it as `ANTHROPIC_API_KEY`

**Google OAuth**
- Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
- Create an **OAuth 2.0 Client ID** (Web application type)
- Add `http://localhost:8000/auth/callback` as an **Authorised redirect URI**
- Enable these APIs in your project:
  - Google Calendar API
  - Gmail API
  - Google People API
- Copy the Client ID and Client Secret into `.env`

### 3. Start

```bash
bash start.sh
```

The script automatically creates a virtual environment, installs dependencies, and launches the server. Open **http://localhost:8000** in Chrome or Edge.

> Safari is not supported — it doesn't implement the Web Speech API.

### 4. Connect your Google account

Click **Connect Google** in the top-right nav. Sign in and grant the requested permissions (Calendar, Gmail, Contacts). You only need to do this once — the token is stored locally in `tokens/` and auto-refreshed.

---

## Usage

Hold the microphone button (or press **Space**) and speak. Release and wait — K processes after 2 seconds of silence and speaks the reply back to you.

**Tip — spoken email addresses:** Say email addresses naturally:
- "john dot smith at gmail dot com" → `john.smith@gmail.com`
- "alice underscore w at company dot io" → `alice_w@company.io`

**Interrupt K:** Tap the mic button while K is speaking to stop it immediately.

---

## Security notes

- Your `.env` file and `tokens/` directory are git-ignored and never committed
- OAuth tokens are stored in `tokens/token.json` with `600` permissions (owner read/write only)
- The token directory is created with `700` permissions on startup
- All API calls go through your own credentials — no third-party relay

---

## Requirements

- Python 3.11 or later
- Chrome or Edge (for Web Speech API)
- A Google account with Calendar and Gmail
- Anthropic API key

---

## Known limitations

- Voice recognition requires Chrome or Edge; Safari is unsupported
- TTS quality depends on the voices installed on your OS — macOS with "Samantha (Premium)" sounds best
- The agent scope is intentionally narrow: calendar + email only; off-topic requests are politely declined
