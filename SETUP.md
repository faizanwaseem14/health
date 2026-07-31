# MedVault Setup Checklist

This is your checklist of outside accounts to create and keys to paste in.
I (the AI) cannot create these for you — they require your own email/login
and, in some cases, payment details. For each one: create the account,
copy the value it gives you, and paste it into `backend/.env` (copy
`backend/.env.example` to `backend/.env` first if you haven't already).

## Required for Day 1

- [ ] **Neon — PostgreSQL database**
  1. Sign up at https://neon.tech (free tier is fine).
  2. Create a project.
  3. On the project dashboard, open "Connection Details" and copy the
     connection string.
  4. Paste it into `DATABASE_URL` in `backend/.env`. Make sure the string
     ends with `?sslmode=require` — Neon requires an encrypted connection.

- [ ] **Firebase — phone number login (OTP)**
  1. Create a project at https://console.firebase.google.com
  2. Go to Authentication -> Sign-in method -> enable "Phone".
  3. Go to Project settings (gear icon) -> Service accounts -> click
     "Generate new private key". This downloads a `.json` file.
  4. Open that file in a text editor, copy the ENTIRE contents onto one
     line, and paste it into `FIREBASE_SERVICE_ACCOUNT_JSON` in
     `backend/.env`.

- [ ] **Cloudflare R2 — private file storage**
  1. Sign up / log in at https://dash.cloudflare.com
  2. Go to R2 -> create a bucket (keep it private — do not enable public
     access).
  3. Go to R2 -> "Manage API tokens" -> create a token with read/write
     access scoped to that bucket.
  4. Paste the values into `backend/.env`:
     - `R2_ACCOUNT_ID`
     - `R2_ACCESS_KEY_ID`
     - `R2_SECRET_ACCESS_KEY`
     - `R2_BUCKET_NAME`
     - `R2_ENDPOINT_URL` — set this to
       `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` (swap in your
       real account ID).

## Not needed until Day 2 (safe to skip for now)

- [ ] **Upstash — Redis**
  1. Sign up at https://upstash.com
  2. Create a Redis database.
  3. Copy the connection URL into `REDIS_URL` in `backend/.env`.

- [ ] **Google Cloud Vision — OCR (reads text from report photos)**
  1. Create/open a project at https://console.cloud.google.com
  2. Enable the "Cloud Vision API".
  3. Create an API key scoped to that API.
  4. Paste it into `GOOGLE_VISION_API_KEY` in `backend/.env`.

- [ ] **Anthropic (Claude) — plain-language explanations**
  1. Sign up at https://console.anthropic.com
  2. Go to API Keys -> Create Key.
  3. Paste it into `ANTHROPIC_API_KEY` in `backend/.env`.

## How you'll know it worked

Once the "Required for Day 1" items are filled in, later tasks will prove
each connection actually works (for example, Task 4 does a real
database health-check). Today (Task 2), the backend only checks that a
value is *present* for each required key — not that it's valid yet.
