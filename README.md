# 🏰 Disney Availability Tracker

Monitors Disney World and Swan/Dolphin resort availability for your January 2027 runDisney trip. Runs hourly via GitHub Actions, commits results to the repo, and serves a live dashboard via GitHub Pages.

---

## File Overview

| File | Purpose |
|---|---|
| `alerts.json` | Your alert configurations — edit to add/change/disable alerts |
| `check_availability.py` | Checks Disney + Marriott APIs, updates results.json, sends alerts |
| `results.json` | Append-only log of every check run (auto-updated by Actions) |
| `index.html` | Live dashboard served by GitHub Pages |
| `.github/workflows/check.yml` | Hourly scheduler + on-demand trigger |

---

## One-Time Setup (~10 minutes)

### 1. Create a GitHub Repo

Create a **new private repo** (or public — results.json will be readable but that's fine).

Push all files maintaining this structure:
```
.github/workflows/check.yml
check_availability.py
alerts.json
results.json
index.html
requirements.txt
README.md
```

### 2. Enable GitHub Pages

In your repo: **Settings → Pages → Source → Deploy from a branch → main → / (root) → Save**

Your dashboard will be live at: `https://YOUR_USERNAME.github.io/YOUR_REPO/`

### 3. Set Up Gmail App Password

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Make sure 2-Step Verification is enabled
3. Search for "App Passwords" → Create one named "Disney Checker"
4. Copy the 16-character password (no spaces)

### 4. Add GitHub Secrets

Go to: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name    | Value |
|----------------|-------|
| `GMAIL_USER`   | Your Gmail address (e.g. `david@gmail.com`) |
| `GMAIL_APP_PASS` | The 16-char App Password from step 3 |
| `ALERT_EMAILS` | Comma-separated recipient list (e.g. `david@gmail.com,ellen@gmail.com`) |

### 5. Configure the Dashboard

Open `index.html` and update these two lines near the bottom:
```javascript
const GITHUB_OWNER = "YOUR_GITHUB_USERNAME";  // ← your GitHub username
const GITHUB_REPO  = "YOUR_REPO_NAME";         // ← your repo name
```

### 6. Set Up a GitHub PAT for On-Demand Runs *(optional but recommended)*

The "Run Check Now" button on the dashboard needs a token to trigger Actions.

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic)
2. Scopes needed: `repo` (full)
3. Copy the token
4. Add it to `index.html`:
   ```javascript
   const GITHUB_TOKEN = "ghp_your_token_here";
   ```
   > ⚠️ Since this token will be visible in your public HTML, create a fine-grained token scoped only to this repo with only Actions write permission. Or keep the repo private.

### 7. Test It!

In your repo: **Actions → Disney Availability Checker → Run workflow → test_run: true → Run workflow**

Check your inbox — you should receive a test email within ~60 seconds. ✅

---

## Customizing Alerts

Edit `alerts.json` directly in GitHub. Each alert looks like:

```json
{
  "name": "Race Night — Contemporary",
  "hotels": ["Contemporary"],
  "check_in": "2027-01-08",
  "check_out": "2027-01-09",
  "active": true
}
```

**Available hotel names:**

| Name | System |
|---|---|
| `Contemporary` | Disney |
| `Yacht Club` | Disney |
| `Beach Club` | Disney |
| `Polynesian` | Disney |
| `Grand Floridian` | Disney |
| `Wilderness Lodge` | Disney |
| `Swan` | Marriott |
| `Dolphin` | Marriott |
| `Swan Reserve` | Marriott |

Set `"active": false` to pause an alert without deleting it.

---

## Adding SMS Alerts Later (Twilio)

When you're ready to add SMS:

1. Sign up at [twilio.com](https://twilio.com) and get a phone number
2. Add secrets: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `TWILIO_TO`
3. In `check_availability.py`, find the `send_sms()` function and uncomment the Twilio block
4. Add `twilio==8.12.0` to `requirements.txt`

---

## GitHub Actions Usage

Free tier gives **2,000 minutes/month**. Hourly checks use ~720 min/month — well within limits.

Each run takes ~30-60 seconds.
