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

   The default value already points at `http://localhost:8000`, which is
   where the backend runs locally — you don't need to edit anything unless
   your backend is running somewhere else.

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

## Running it on Mac/Linux

Same steps, using a regular terminal:

```bash
cd frontend
cp .env.example .env   # first time only
npm install
npm run dev
```

Then open http://127.0.0.1:5173/.

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
│   └── AuthContext.jsx    Placeholder for real auth (added in a later step).
├── lib/
│   └── apiClient.js       Fetch wrapper using VITE_API_BASE_URL — not yet
│                          called from any screen.
├── components/            Shared, reusable pieces every screen can use:
│   ├── Button/               primary / accent / secondary / ghost variants
│   ├── Card/                 the one surface/panel component
│   ├── Logo/                 the HealthVault mark + wordmark
│   ├── Layout/                header + footer shell wrapping every page
│   ├── StatusBadge/          the ONLY way a result's status is ever shown —
│   │                          always icon + color + word together
│   └── ContourMotif/          the signature background pattern
└── pages/
    └── Landing/            The landing page (the only screen that exists
                             so far). Login/upload/results pages will each
                             get their own folder here.
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
