# ⚔️ CoC Clan Telegram Bot — Render Deployment Guide

## Files in this project
```
bot.py            ← the bot
requirements.txt  ← Python dependencies
render.yaml       ← Render infrastructure config
README.md         ← this file
```

---

## Step 1 — Create your Telegram Bot

1. Open Telegram → search **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** (looks like `7123456789:AAFxxx...`)
4. Add the bot to your clan group and make it an **admin** (so it can post)
5. Find your **group chat ID**:
   - Add **@userinfobot** to your group
   - It will reply with the chat ID (a negative number like `-1001234567890`)
   - Remove @userinfobot after

---

## Step 2 — Get your CoC API Key

1. Go to [developer.clashofclans.com](https://developer.clashofclans.com)
2. Log in with your Supercell account
3. Click **My Account → Create New Key**
4. For **Allowed IP Addresses** — enter Render's outbound IPs:
   ```
   Use: 0.0.0.0/0   (allows all — easiest for cloud hosting)
   ```
   Or look up Render's specific IP ranges in their docs
5. Copy the generated API key

---

## Step 3 — Push to GitHub

Create a new GitHub repo and push these 4 files:
```bash
git init
git add bot.py requirements.txt render.yaml README.md
git commit -m "Initial CoC bot"
git remote add origin https://github.com/YOUR_USERNAME/coc-bot.git
git push -u origin main
```

---

## Step 4 — Deploy on Render

1. Go to [render.com](https://render.com) → **New → Web Service**
2. Connect your GitHub repo
3. Render will auto-detect `render.yaml` ✅
4. Click **Create Web Service** — it will start building

### ⚠️ After the first deploy, you get your Render URL:
It looks like: `https://coc-clan-bot.onrender.com`

---

## Step 5 — Set Environment Variables

In the Render dashboard → your service → **Environment** tab, add:

| Key | Value |
|-----|-------|
| `COC_API_KEY` | your CoC developer API key |
| `TELEGRAM_BOT_TOKEN` | from @BotFather |
| `CLAN_TAG` | your clan tag e.g. `#2ABC123` |
| `TELEGRAM_CHAT_ID` | your group chat ID e.g. `-1001234567890` |
| `WEBHOOK_URL` | your Render URL e.g. `https://coc-clan-bot.onrender.com` |

Then click **Save Changes** — Render will redeploy automatically.

---

## Step 6 — Verify it's working

1. Open your bot in Telegram and send `/start`
2. You should see the welcome message
3. Try `/war` to check current war status
4. Check Render logs: Dashboard → your service → **Logs**

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show bot info and commands |
| `/war` | Live war status (stars, destruction, time left) |
| `/warlog` | Last 5 war results |
| `/player #TAG` | Full player card (heroes, trophies, donations) |

## Auto-Alerts (no command needed)
| Alert | Trigger |
|-------|---------|
| ⏰ 2-hour warning | War has 2 hours left |
| 🚨 30-min warning | War has 30 minutes left |
| 🌟 Triple Star | Any clan member gets 3 stars in war |
| 🏁 War Result | Full summary posted when war ends |

---

## Troubleshooting

**Bot doesn't respond to commands**
- Check that the bot is an admin in your Telegram group
- Verify `TELEGRAM_BOT_TOKEN` is correct in Render env vars

**No war alerts**
- Verify `CLAN_TAG` includes the `#` sign
- Check Render logs for CoC API errors
- Make sure your CoC API key allows the IP `0.0.0.0/0`

**"Environment variable not set" error**
- All 5 env vars must be set in Render dashboard
- After setting them, redeploy the service

**Free tier note**
- Render free tier sleeps after 15 minutes of no HTTP traffic
- The bot's Flask server answers health checks to stay alive
- If you notice delays, upgrade to Render's Starter plan ($7/mo)
