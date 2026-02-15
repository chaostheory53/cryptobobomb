# CryptoBobomb Telegram Bot

This is a serverless Telegram bot deployed on Vercel that provides real-time cryptocurrency sentiment analysis using the Google Gemini API.

## Setup Instructions

### 1. Environment Variables
You must configure the following environment variables in your Vercel project settings (and locally in `.env.local` for testing):

- `TELEGRAM_TOKEN`: Your Telegram Bot Token (from @BotFather).
- `NEWS_API_KEY`: Your NewsAPI.org API Key.
- `GEMINI_API_KEY`: Your Google Gemini API Key.

### 2. Deployment on Vercel
1. Install Vercel CLI: `npm i -g vercel`
2. Login: `vercel login`
3. Deploy: `vercel`

### 3. Setting up the Webhook
After deployment, you need to tell Telegram to send updates to your Vercel URL.
Run this command (replace TOKEN and VERCEL_URL):

```bash
curl -F "url=https://YOUR_VERCEL_PROJECT_URL/api/webhook" https://api.telegram.org/botYOUR_TELEGRAM_TOKEN/setWebhook
```

## Usage
In Telegram, send:
`/sentiment solana`
`/sentiment bitcoin`
