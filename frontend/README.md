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
the frontend talks to Firebase directly to send/check the code, then hands
the backend a signed token to verify and set up your account.

1. **Fill in `frontend/.env`** with your Firebase project's values
   (`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`,
   `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`,
   `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`) if you
   haven't already. If any of these are blank, the Login screen shows a
   plain "sign-in isn't set up yet" message instead of crashing — that's
   expected, just fill them in and restart `npm run dev`.

2. **Start the backend** in a separate PowerShell/terminal window (see the
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

3. **Start the frontend** in its own window, as described above
   (`npm run dev`), and open `http://127.0.0.1:5173/`.

4. **Click "Sign in"** in the header, then **enter the test phone number**
   you configured in Firebase console → Authentication → Sign-in method →
   Phone → "Phone numbers for testing" (e.g. `+1 650-555-3434`), and select
   **Send code**.

5. **Enter the test verification code** you set for that number in the same
   Firebase console screen (e.g. `123456`) and select **Verify code**. No
   real SMS is sent and nothing is billed — that's the whole point of a
   configured test number.

6. **What you should see**: you're taken to a "Set up your profile" screen
   (first time only) — fill in a name and select **Continue** — and then a
   "Welcome" screen confirming you're signed in, with a **Sign out**
   button. Refresh the page: you should stay signed in (Firebase persists
   the session). Select **Sign out**, then sign in again with the same
   test number: this time you should land straight on the "Welcome" screen,
   skipping profile setup, since HealthVault already has a profile for you.

### If sign-in doesn't work

- **"Sign-in isn't set up yet" won't go away after filling in `.env`** —
  Vite only reads `.env` when it starts, so stop the dev server
  (`Ctrl+C`) and run `npm run dev` again.
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
    enrollment isn't fully configured on the Firebase/GCP side. Local
    dev already sets Firebase's `appVerificationDisabledForTesting` flag
    (see `src/lib/firebase.js`) to ask Firebase to skip reCAPTCHA
    entirely for a configured "phone number for testing" — but it's a
    request, not a guarantee, and a project enrolled in reCAPTCHA
    Enterprise can still reject the request before that flag is
    consulted. This is a Firebase/GCP **console-side** setting, not
    something fixable from this repo's code. In Firebase console →
    Authentication → Sign-in method → Phone, check whether "reCAPTCHA
    Enterprise" is shown as enabled — if so, either finish that setup
    (link a GCP project, enable the reCAPTCHA Enterprise API, create a
    site key for this domain) or look for an option to use classic
    reCAPTCHA v2 for phone auth instead. Also double-check the test
    number is entered in Firebase console *exactly* as `+44 7700 900123`
    (with the country code and matching formatting) — a mismatched test
    number falls back to the real, non-test verification path, which
    also triggers full reCAPTCHA. The logged error's `customData` (see
    above) may also carry a Google-provided explanation string worth
    reading directly.
- **"That code didn't match"** — double check you typed the exact test
  code configured in Firebase console for that exact test number; a typo
  in either one fails the same way a real wrong code would.

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
│   ├── apiClient.js       Fetch wrapper using VITE_API_BASE_URL.
│   ├── firebase.js        Firebase client init from VITE_FIREBASE_* env vars.
│   ├── phone.js           Turns typed input into the E.164 format Firebase needs.
│   └── authErrors.js      Firebase/backend errors -> plain-language messages.
├── components/            Shared, reusable pieces every screen can use:
│   ├── Button/               primary / accent / secondary / ghost variants
│   ├── Card/                 the one surface/panel component
│   ├── Input/                 labeled text input with icon+text error state
│   ├── Logo/                 the HealthVault mark + wordmark
│   ├── Layout/                header + footer shell wrapping every page
│   ├── LoadingScreen/        shown while a route guard is resolving
│   ├── StatusBadge/          the ONLY way a result's status is ever shown —
│   │                          always icon + color + word together
│   └── ContourMotif/          the signature background pattern
└── pages/
    ├── Landing/            The public landing page.
    ├── Login/               Phone number -> 6-digit code -> signed in.
    ├── ProfileSetup/        First-time-only "who are these records for".
    └── Home/                 Minimal signed-in confirmation screen (upload/
                              results screens come in a later step).
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
