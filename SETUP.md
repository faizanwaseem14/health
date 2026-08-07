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

  R2 is where uploaded report files (PDFs, photos) will live. The bucket
  must stay **private** — we never enable public access; the app reaches
  files only through short-lived signed URLs (built in Task 7).

  1. Sign up / log in at https://dash.cloudflare.com (a free account is
     fine). If this is your first time using R2, Cloudflare may ask you
     to "enable R2" and add a payment method to your account before it
     lets you create a bucket — R2 still has a generous free tier, this
     is just Cloudflare's account-level requirement, not something this
     app needs you to pay for.
  2. In the left sidebar, click **R2 Object Storage**.
  3. Click **Create bucket**.
     - Name it anything, e.g. `medvault-reports`.
     - Leave location as "Automatic".
     - Leave public access as its default (**disabled**) — do NOT turn
       on "Allow Public Access" for this bucket.
  4. Find your **Account ID**: it's shown on the right-hand side of the
     R2 Object Storage overview page (and also on the main Cloudflare
     dashboard). Copy it into `R2_ACCOUNT_ID` in `backend/.env`.
  5. Create an API token scoped to just this bucket:
     - From the R2 Object Storage page, click **Manage API tokens** (or
       **API** in the sidebar) -> **Create API token**.
     - Permissions: **Object Read & Write**.
     - Scope it to the one bucket you just created (not "all buckets"),
       so this token can't touch anything else in your account.
     - Click **Create API Token**.
  6. Cloudflare will show you the credentials **once** — copy them
     immediately into `backend/.env`:
     - **Access Key ID** -> `R2_ACCESS_KEY_ID`
     - **Secret Access Key** -> `R2_SECRET_ACCESS_KEY`
  7. Set the remaining two values in `backend/.env`:
     - `R2_BUCKET_NAME` — exactly the bucket name you chose in step 3.
     - `R2_ENDPOINT_URL` — Cloudflare shows this on the same token
       confirmation screen (sometimes labeled "S3 API" or "Endpoint").
       It normally looks like
       `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` — use the
       *exact* one Cloudflare shows you, since it can differ slightly if
       you picked a specific data-location jurisdiction (e.g. an `eu.`
       prefix).

## Required for Day 2

- [ ] **Upstash — Redis (REST API)**

  Powers the background job queue (Day 2): when a report is uploaded,
  a job goes on this queue for a separate worker process to pick up,
  so the upload request doesn't have to wait on slow work.

  1. Sign up at https://upstash.com (free tier is fine).
  2. Create a Redis database.
  3. On the database's page, find the **REST API** section (not the
     plain "Connect" / TCP connection string — we specifically use the
     REST API, since it works over plain HTTPS instead of a raw TCP
     connection).
  4. Copy the two values shown there — Upstash labels them exactly:
     - `UPSTASH_REDIS_REST_URL` -> paste into `backend/.env` as-is.
     - `UPSTASH_REDIS_REST_TOKEN` -> paste into `backend/.env` as-is.

## Not needed yet (safe to skip for now)

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
