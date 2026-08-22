# HealthVault — frontend

The HealthVault web app: React + Vite, talking to the FastAPI backend in
`../backend`. This is being built as the real, final UI — not a throwaway
prototype — so it's worth reading `src/styles/tokens.css` before adding new
screens; every color, spacing, and type value should come from a token, not
a one-off hex code.

## Running it on Windows

1. **Install Node.js** (skip if you already have it — you need version 20 or
   newer). Download the "LTS" installer from
   [nodejs.org](https://nodejs.org/) and run it, keeping all the defaults.
   To check what you already have, open **PowerShell** (search for it in the
   Start menu) and run:

   ```powershell
   node --version
   ```

   If that prints `v20.x.x` or higher, you're set.

2. **Open PowerShell in the frontend folder.** In File Explorer, navigate to
   the `frontend` folder inside this repo, hold **Shift** and right-click
   inside it, then choose **"Open PowerShell window here"** (or "Open
   Terminal here" on Windows 11).

3. **Create your local env file** (one time only):

   ```powershell
   copy .env.example .env
   ```

   The `VITE_API_BASE_URL` default already points at `http://localhost:8000`,
   which is where the backend runs locally. You also need to fill in the six
   `VITE_FIREBASE_*` values (from Firebase console → Project settings →
   General → "Your apps") before sign-in will work — see **Setting up
   sign-in locally** below.

4. **Install dependencies** (one time only, or whenever `package.json`
   changes):

   ```powershell
   npm install
   ```

5. **Start the dev server:**

   ```powershell
   npm run dev
   ```

   PowerShell will print something like:

   ```
   ➜  Local:   http://127.0.0.1:5173/
   ```

6. **Open that URL in your browser** — `http://127.0.0.1:5173/` — and you
   should see the HealthVault landing page. Leave the PowerShell window open
   while you're working; press `Ctrl+C` in it to stop the server when
   you're done.

The page live-reloads: while the dev server is running, saving any file in
`src/` updates the browser automatically, no restart needed.

### If something goes wrong

- **"npm is not recognized"** — Node.js isn't installed, or PowerShell needs
  to be reopened after installing it (close and reopen the window).
- **"Port 5173 is already in use"** — another copy of the dev server is
  probably still running in another window; close it, or just open the URL
  it printed instead.
- **The page loads but looks unstyled** — hard-refresh the browser
  (`Ctrl+Shift+R`) — this can happen if the dev server restarted while a
  stale tab was still open.

## Setting up sign-in locally

Sign-in needs BOTH the frontend and the backend running at the same time —
the frontend talks to Firebase directly to sign you in, then hands the
backend a signed token to verify and set up your account.

**Google sign-in is the primary method** ("Continue with Google" on the
Login screen) — it needs no reCAPTCHA setup and works reliably on
localhost. Phone number sign-in still exists (tap "Sign in with a phone
number instead" on the Login screen) but is secondary for now, since it
depends on Firebase's reCAPTCHA step working correctly for your project —
see the phone-specific troubleshooting below if you use it.

1. **Fill in `frontend/.env`** with your Firebase project's values
   (`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`,
   `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`,
   `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`) if you
   haven't already. If any of these are blank, the Login screen shows a
   plain "sign-in isn't set up yet" message instead of crashing — that's
   expected, just fill them in and restart `npm run dev`.

2. **Enable Google as a sign-in provider** in Firebase console →
   Authentication → Sign-in method → Google → Enable. Firebase handles the
   OAuth consent screen for you; you don't need your own Google Cloud
   OAuth client for this to work locally. `localhost` needs to be in
   Firebase console → Authentication → Settings → Authorized domains — it's
   there by default on a new project.

3. **Start the backend** in a separate PowerShell/terminal window (see the
   root [`README.md`](../README.md) for full backend setup):

   ```powershell
   cd backend
   .venv\Scripts\activate
   uvicorn app.main:app --reload
   ```

   Leave this running — you should see `Uvicorn running on
   http://127.0.0.1:8000`. The backend is already configured (via
   `app/main.py`'s CORS settings) to accept requests from the frontend dev
   server at `http://localhost:5173`.

4. **Start the frontend** in its own window, as described above
   (`npm run dev`), and open `http://127.0.0.1:5173/`.

5. **Click "Sign in"** in the header, then select **Continue with Google**
   and pick any real Google account in the popup that opens.

6. **What you should see**: after the popup closes, you're taken to a
   "Set up your profile" screen (first time only) — fill in a name and
   select **Continue** — and then a "Welcome" screen confirming you're
   signed in, with a **Sign out** button. Refresh the page: you should stay
   signed in (Firebase persists the session). Select **Sign out**, then
   sign in again with the same Google account: this time you should land
   straight on the "Welcome" screen, skipping profile setup, since
   HealthVault already has a profile for you.

### If Google sign-in doesn't work

- **"Sign-in isn't set up yet" won't go away after filling in `.env`** —
  Vite only reads `.env` when it starts, so stop the dev server
  (`Ctrl+C`) and run `npm run dev` again.
- **Nothing happens when you click "Continue with Google" / a popup flashes
  and closes immediately** — your browser (or an extension) is blocking
  the popup. Allow popups for `localhost` and try again; the error shown
  on screen (`Your browser blocked the sign-in popup...`) says this
  directly.
- **"An account already exists with this email using a different sign-in
  method"** — that Google account's email already has a HealthVault user
  under a different Firebase sign-in method; this is a real edge case
  Firebase itself reports, not something to work around locally.
- **Any other error after the popup closes** — open the browser's DevTools
  console (`F12`): every failed attempt logs a `[HealthVault] Firebase
  Auth error (google-sign-in)` entry with Firebase's full error object.
  Also check that the backend is running and reachable (see step 2 above)
  — Google sign-in itself can succeed with the backend down, but the app
  won't consider you signed in until `/auth/me` responds.

### If phone sign-in (secondary) doesn't work

Tap "Sign in with a phone number instead" on the Login screen to reach it.
You'll need a **phone number for testing** configured in Firebase console →
Authentication → Sign-in method → Phone → "Phone numbers for testing"
first (e.g. `+1 650-555-3434` / `123456`) — no real SMS is sent for one of
these, and nothing is billed.

- **The code screen never appears / an error shows after "Send code"** —
  open the browser's DevTools console (`F12`) for the real error. The
  most common cause locally is the backend not running, or CORS blocking
  the request because the backend was started before `app/main.py`'s CORS
  settings existed — pull the latest backend code and restart it.
- **Stuck on "Sending code…" forever, no error at all** — `signInWithPhoneNumber`
  depends on Google's reCAPTCHA script loading in the browser, which can
  silently stall (no thrown error) if it's blocked by an ad blocker, a
  corporate network, or a slow connection. Every Firebase call now has a
  20-second timeout (`src/lib/withTimeout.js`) so it fails with a clear
  message instead of hanging forever even if something stalls it.
- **An error appears after "Send code", and it ends with a code in
  parentheses** like `(auth/invalid-app-credential)` or a bare
  `Something went wrong signing you in. (400)` — that code is Firebase's
  own, shown only in dev builds so you don't need DevTools open to see
  it. Open the browser console (`F12`) too: every failed attempt logs a
  `[HealthVault] Firebase Auth error (...)` entry with the full error
  object, including anything Firebase attached in `customData` — that's
  the most reliable way to see *why* a request was rejected, not just
  that it was.
  - **`Failed to initialize reCAPTCHA Enterprise config...` followed by a
    400 from `identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode`**
    — this means the Firebase project itself is enrolled in Google's
    newer reCAPTCHA Enterprise-based phone-auth protection, and that
    enrollment isn't fully configured on the Firebase/GCP side. This is a
    Firebase/GCP **console-side** setting, not something fixable from
    this repo's code — it's exactly the kind of localhost friction that
    made Google sign-in the primary method instead. In Firebase console →
    Authentication → Sign-in method → Phone, check whether "reCAPTCHA
    Enterprise" is shown as enabled — if so, either finish that setup
    (link a GCP project, enable the reCAPTCHA Enterprise API, create a
    site key for this domain) or look for an option to use classic
    reCAPTCHA v2 for phone auth instead. Also double-check the test
    number is entered in Firebase console *exactly* matching what you
    type in the app, country code included — a mismatched test number
    falls back to the real, non-test verification path, which also
    triggers full reCAPTCHA. The logged error's `customData` (see above)
    may also carry a Google-provided explanation string worth reading
    directly.
- **"That code didn't match"** — double check you typed the exact test
  code configured in Firebase console for that exact test number; a typo
  in either one fails the same way a real wrong code would.

## Uploading and processing a report

Once you're signed in, HealthVault can accept a lab report photo or PDF,
store it, and process it (OCR → AI extraction → trust checks) in the
background. Testing this needs a THIRD process, on top of the backend API
and the frontend:

1. **Start the background worker** in its own terminal (separate from
   the `uvicorn` one):

   ```powershell
   cd backend
   .venv\Scripts\activate
   python -m app.jobs.worker
   ```

   This is what actually processes an upload — without it running, a
   report will sit at "Waiting to start" forever (harmlessly; nothing is
   lost, the worker just picks it up whenever it starts). Leave it
   running alongside the backend and frontend.

2. **For processing to actually complete** (not just move to
   "Processing" and then fail), `backend/.env` needs real credentials for
   Cloudflare R2 (`R2_*`) and Claude (`ANTHROPIC_API_KEY`) — see the root
   [`SETUP.md`](../SETUP.md). `OCR_PROVIDER=tesseract` (the default) needs
   the Tesseract binary installed locally; see the root
   [`README.md`](../README.md) if OCR fails specifically.

3. **From Home, select "Upload a lab report"**, then either **Take a
   photo** (opens your camera on a phone/laptop with one) or **Choose a
   file** (any JPEG, PNG, HEIC, or PDF up to 25MB).

   Don't have a real lab report handy? Use one of the de-identified
   sample reports already checked into the repo, at
   `backend/tests/fixtures/lab_reports/` — entirely fabricated data (a
   fake lab, fake patient label, fake values), each stamped with a
   visible "SYNTHETIC SAMPLE - NOT A REAL PATIENT" banner:
   - `clear.png` — a clean, straightforward table layout (the easiest
     one — good for a first end-to-end test)
   - `blurry.png` — the same report, blurred (tests a poor-quality scan)
   - `rotated.png` — the same report, rotated ~7° (tests a skewed photo)
   - `unusual_layout.png` — a non-tabular, inline-label layout
   - `multi_page.pdf` — a 2-page report (hematology, then chemistry)

   On your phone, AirDrop/email/transfer one of these image files to
   the device first, then select it via **Choose a file** (the camera
   option obviously won't work for a file that's already an image). On
   a laptop, just choose the file directly from the repo.

4. **Check the preview.** For a photo, HealthVault runs a few quick,
   local checks — blur, brightness/glare, resolution, cut-off edges, and
   (for JPEGs) sideways orientation — and shows any as gentle warnings
   right on the preview. These never block you; the button still says
   "Upload anyway" if you'd rather proceed. Select **Replace or remove**
   to pick a different file instead.

5. **Select Confirm & upload** (or **Upload anyway**). You're taken to a
   processing screen with an animated "working on it" indicator and
   cycling status messages — this is normal and can take anywhere from a
   few seconds to a couple of minutes depending on the file and which OCR
   provider is configured.

6. **Try leaving the screen**: select the "Safe to leave" link (or just
   navigate to Home). Processing keeps going in the background regardless
   — your report shows up in the "Your reports" list on Home with its
   current status, and reopening it (tap the row) picks the live status
   back up, exactly where it left off.

7. **What you should see when it finishes**: a status badge changes to
   one of **Done** (select **View results** to see the extracted values
   - see "Viewing results, explanations, and corrections" below),
   **Needs a quick review** (a normal outcome for a hard-to-read scan,
   not an error), or **Couldn't process** (select **Try again** to
   retry — your original file is untouched and doesn't need
   re-uploading).

### If upload/processing doesn't work

- **Stuck on "Waiting to start" indefinitely** — the worker (step 1
  above) isn't running, or crashed. Check that terminal for errors.
- **Always ends up "Couldn't process"** — open the failed report; the
  technical detail shown there (and the worker's own terminal output) is
  usually the real reason — most commonly a missing/placeholder R2 or
  Anthropic credential in `backend/.env` (see step 2 above).
- **"That file is too large" / "doesn't look like a photo or PDF..."** —
  these are real limits (25MB max; JPEG, PNG, HEIC, or PDF only) enforced
  both instantly in the browser and again by the backend — not a bug.

## Viewing results, explanations, and corrections

Once a report reaches **Done**, selecting **View results** opens a
two-column screen: your original report's page image on the left (the
"trust anchor" - shown by default, the actual scanned/rendered page,
not a re-typed summary) and a clean list of extracted test cards on the
right, each showing the test name, the reference range exactly as
printed, the value, and a status badge (Normal = green, High = amber,
Low = a distinct purple - always icon + word + color together, never
color alone). On a narrow screen the two stack, report on top.

1. **Tap a value** - either its card on the right, or the highlighted
   region directly on the report image on the left - to open its "What
   is this?" panel. Both are linked: tapping one selects the other too.
   This shows only a one-line, plain-language explanation of what the
   test measures (fetched on demand - the FIRST tap on ANY result in
   the report makes one request that generates explanations for the
   whole report at once, since the backend caches one AI call per
   distinct test name, not per result - see
   `backend/app/ai/explanation_service.py`; every result after that is
   instant). By design this panel never says anything about whether a
   value is good or bad, or what to do about it - only what the test
   measures.

2. **A result with a small "Needs a quick review" tag** on its card
   means the extraction itself wasn't fully confident about that
   reading - a normal outcome, not an error state. It's still worth a
   glance at the original report image next to it.

3. **Select "Fix this value"** in the panel to correct a misread value:
   you'll see exactly what was extracted, a field to type the correct
   value, and an optional reason. Saving updates the result immediately
   (its status badge recalculates against the same printed reference
   range) - nothing is silently overwritten. Below that, **Correction
   history** lists every past correction, old and new value, with a
   timestamp.

4. **"Hide report"**, top-right of the screen, collapses the report
   image away and lets the results list use the full width - useful on
   a smaller laptop screen. **"See trend over time"** (in the panel),
   **"View trends for this report"**, and **"Share with doctor"**
   (bottom of the screen) are all coming-soon placeholders for now -
   they show a short note when tapped rather than doing anything yet.

5. **Select "Full OCR inspection ↗"**, top-right of the report panel,
   to open a page showing the report's own page image with a box drawn
   around every word HealthVault's OCR engine detected - useful for
   digging into exactly what the extraction saw. `multi_page.pdf` has
   two pages; use the Previous/Next page buttons to move between them
   on either that screen or the results screen's own report panel.

### If results/explanations/corrections don't work

- **A result never gets an explanation, just "We couldn't generate an
  explanation for this test right now."** — the backend's explanation
  generation has its own guardrails and can legitimately skip a test
  name (see `backend/app/ai/explanation_prompt.py`); this isn't a bug,
  though a real Claude API error would look the same from here - check
  the backend/worker terminal if it happens for every result.
- **"Fix this value" doesn't seem to change the status badge** — the
  status (High/Low/Normal) is only recalculated when you correct the
  **value** field specifically, against that same result's printed
  reference range - if the range itself was misread, the value's status
  may still look surprising even after fixing the value.
- **A value on the report image isn't tappable** — that specific result
  has no linked OCR evidence (the AI extraction didn't report which
  words it came from for that one value); its card in the results list
  is still fully usable, there's just nothing to highlight on the image
  for it.

## Running it on Mac/Linux

Same steps, using a regular terminal. To test sign-in, run these in two
separate terminal windows:

```bash
# Terminal 1 — backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend
cp .env.example .env   # first time only, then fill in the VITE_FIREBASE_* values
npm install
npm run dev
```

Then open http://127.0.0.1:5173/ and follow **Setting up sign-in locally**
above.

## Other commands

```bash
npm run build      # production build, output to dist/
npm run preview    # serve that production build locally, to sanity-check it
```

## Project layout

```
src/
├── styles/
│   ├── tokens.css       Design tokens — color, spacing, type, radius, shadow.
│   └── global.css       Resets + base typography, imports tokens.css.
├── theme/
│   ├── ThemeProvider.jsx  Light/dark state, persisted to localStorage.
│   └── ThemeToggle.jsx    The header's light/dark switch.
├── context/
│   └── AuthContext.jsx    Session state: Firebase sign-in + backend user +
│                          profiles, and `authFetch` for authenticated calls.
├── routes/
│   ├── RequireAuth.jsx     Route guard: sends signed-out visitors to /login.
│   └── RequireProfile.jsx  Route guard: sends visitors with no profile yet
│                           to /profile-setup.
├── lib/
│   ├── apiClient.js       Fetch wrapper using VITE_API_BASE_URL (JSON or
│   │                      FormData bodies).
│   ├── firebase.js        Firebase client init from VITE_FIREBASE_* env vars.
│   ├── phone.js           Turns typed input into the E.164 format Firebase needs.
│   ├── authErrors.js      Firebase/backend errors -> plain-language messages.
│   ├── imageQualityChecks.js  Client-side blur/dark/glare/resolution/cut-off/
│   │                          rotation heuristics, run before an upload.
│   ├── reportStatus.js    report+job status -> a <StatusBadge> tone + label,
│   │                      shared by Home's list and the processing screen.
│   └── resultStatus.js    a result's flag/trust_status -> a <StatusBadge>
│                          tone + label, shared by the results screen.
├── components/            Shared, reusable pieces every screen can use:
│   ├── Button/               primary / accent / secondary / ghost variants
│   ├── Card/                 the one surface/panel component
│   ├── Input/                 labeled text input with icon+text error state
│   ├── Logo/                 the HealthVault mark + wordmark
│   ├── Layout/                header + footer shell wrapping every page
│   ├── LoadingScreen/        shown while a route guard is resolving
│   ├── ProcessingAnimation/  the playful "working on it" visual + cycling
│   │                          reassurance messages for the processing screen
│   ├── StatusBadge/          the ONLY way a result's status is ever shown —
│   │                          always icon + color + word together
│   └── ContourMotif/          the signature background pattern
└── pages/
    ├── Landing/            The public landing page.
    ├── Login/               Phone number -> 6-digit code -> signed in.
    ├── ProfileSetup/        First-time-only "who are these records for".
    ├── Home/                 Signed-in home base: upload entry point +
    │                        the profile's report list.
    ├── Upload/               Capture/choose a file, preview it, quality
    │                        warnings, confirm -> uploads and kicks off
    │                        processing.
    ├── Processing/           Polls a report's job status live; the playful
    │                        loading state, review/done/failed outcomes,
    │                        and retry.
    ├── ReportResults/        The report's page image (tappable, linked
    │                        to the results list) beside a clean list of
    │                        test cards - tap either for an on-demand
    │                        "what is this?" explanation, correction
    │                        (with full history), and a link to OCR
    │                        inspection.
    └── OcrInspection/        The report's own page image with a box
                              drawn around every OCR-detected word -
                              proves exactly where a value came from.
```

## Design system, in brief

- **Palette**: earthy — sage/olive as the primary brand color, terracotta/
  clay as a sparing accent, warm sand as the light-mode background. Dark
  mode is a warm charcoal/brown, never cold black. Every value is a named
  token in `tokens.css` — change the palette there, once, and it ripples
  everywhere.
- **Type**: Fraunces (a warm, soft-edged serif) for headlines only; Figtree
  (a legible, rounded sans) for everything else. IBM Plex Mono is reserved
  for numeric lab values in later screens.
- **Accessibility is load-bearing, not decoration**: an 18px base font size,
  48px-minimum tap targets, a highly visible focus ring on every
  interactive element, and — critically — status is NEVER shown with color
  alone. `<StatusBadge>` always pairs a color with an icon and a word; reuse
  it rather than inventing a new status treatment.
- **Theme**: light is always the default for a first-time visitor. Once
  someone toggles dark mode, that choice is remembered (`localStorage`) and
  reapplied on every later visit, with no flash of the wrong theme on
  reload.
