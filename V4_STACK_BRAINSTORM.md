# V4 Stack Brainstorm — Rebuilding Balkan Fleet Console for Production

> **Status:** decision-support / brainstorm. No code is changed by this document.
> **Author:** architecture review.
> **Scope:** evaluate alternative languages/frameworks for a future v4 rebuild that is
> measurably **more reliable, secure, responsive, and fast** than the current v3.0
> Streamlit app — while respecting that the team is **Python-centric** today.

---

## 1. The baseline we are comparing against (v3.0)

A single-process **Streamlit** (Python) app, ~2,400 LOC, on a **SQLite (WAL)** file DB.
It is genuinely good at what it was built for: a self-bootstrapping, single-author
internal console that seeds its own DB on first run, ships six languages, and gates
features by role. The clean **`services/` + `data/repositories/` layering** (no SQL
above the repo layer, plain-dict returns, no Streamlit in the service layer) is the
single most valuable asset in the codebase and the reason a rebuild is *feasible* rather
than a rewrite-from-zero.

So this is not a criticism of the original choice. It is a question of whether the
*delivery* layer (Streamlit) and the *storage* layer (SQLite file) can carry the app into
a multi-user, mobile-accessed, business-critical phase. They mostly cannot, for the
reasons below.

### 1.1 Streamlit's execution model is the core constraint

- **Full-script rerun on every interaction.** Every widget click re-executes `app.py`
  top to bottom. State must be smuggled through `st.session_state`, `@st.cache_data`,
  and bounded priming reruns. The CLAUDE.md already documents the symptoms: the
  `_cookie_tries < 4` priming reruns so a refresh doesn't log the user out, a
  `time.sleep` after `cookie_mgr.set(...)` so the cookie reaches the browser, the
  "only one `st.dialog` open at a time" workaround where the customer invoice is
  stashed in `session_state` and re-opened after a rerun. These are not bugs — they are
  the price of the rerun model, and every new feature pays it again.
- **You fight the framework for layout.** Responsiveness lives in a hand-written
  `@media (max-width: 640px)` CSS block in `ui/theme.py` that stacks every `st.columns`
  row; the top nav had to be rebuilt from native `st.button`s because
  `streamlit-option-menu`'s iframe collapsed to 0px on Streamlit 1.58; the sidebar is
  suppressed with `showSidebarNavigation = false` and the `pages/` folder is deliberately
  avoided because Streamlit would hijack it into a multipage app. This is "fighting the
  framework," and it caps how good the UX can get.
- **Single-process concurrency ceiling.** Streamlit serves each session on a server-side
  Python thread under the GIL, holding script state in memory. A handful of concurrent
  staff on a phone network is fine; it does not scale horizontally without sticky
  sessions and does not survive a process restart gracefully (in-memory session state is
  lost).
- **Weak true-mobile fit.** The CSS clamps make the page *fit* a phone, but it is still a
  desktop-first DOM squeezed down — no real responsive component system, no offline, no
  app-shell, slow first paint (the CLAUDE.md notes first paint needs the network for
  Google Fonts, vis-timeline, and the cookie/menu components from CDNs).

### 1.2 Security surface is hand-rolled

- **Custom auth** with **SHA-256 password hashing** (fast, unsalted-by-design hash — wrong
  primitive for passwords; see §5).
- Remember-me is a cookie whose **SHA-256 is stored in `sessions`** — better than storing
  the token, but there is **no framework-level session management, no CSRF protection, no
  rotation/expiry policy** beyond what was written by hand.
- Password recovery, SMTP, and RBAC are all bespoke. They work, but every line is the
  team's to secure and audit. A `send_mail` that "never raises" is convenient and also a
  place where failures go silent.
- RBAC is a clean integer-level model (`visitor 0 < employer 1 < admin 2 < super_admin 3`)
  — this is a *strength* and should be ported verbatim.

### 1.3 SQLite write-concurrency and ops

- WAL allows many readers + one writer. For one till/one author that is plenty. For
  multiple staff booking simultaneously, writers serialize and you will eventually meet
  `SQLITE_BUSY`. There is also a real **data-integrity foot-gun already flagged**:
  `hard_delete` of a vehicle leaves orphan `vehicle_photos` rows (no DB-enforced cascade
  being relied on).
- Migrations are four hand-coded `ALTER`/rebuild steps run on every start. Fine at this
  size; not a migration *framework* with up/down, history, or CI verification.

### 1.4 Testability

- **There is no test suite.** The layering *almost* allows one — `core/`, `data/`,
  `services/` are importable under plain `python` — but `ui/`/`views/` are welded to
  Streamlit and can only run under `streamlit run`. There is no seam to assert on the
  rendered UI, and no fixtures/factories. Reliability work has to start here regardless of
  stack.

**Net:** the *business logic* is healthy and portable; the *delivery + storage + security
substrate* is what limits reliability, security, responsiveness, and speed.

---

## 2. Candidate directions

Each candidate is judged on six axes plus a verdict. "Migration cost" is measured against
the asset we most want to keep: the Python `services/` + `data/repositories/` layers.

### A. FastAPI (Python) backend + React/Next.js (TS) + Tailwind + PostgreSQL  ⭐

**Shape.** Keep the Python business logic. Lift `services/` and `data/repositories/`
almost verbatim behind a **FastAPI** HTTP/JSON API (repos already return plain dicts —
that maps directly onto Pydantic response models). Swap the SQLite engine for PostgreSQL
(via SQLAlchemy Core, which the repos can keep using, or SQLModel). Build a real typed
**Next.js/React + TypeScript + Tailwind** frontend that consumes the API.

**Pros**
- **Maximum business-logic reuse.** Availability math (`scheduling_service`), revenue/P&L
  rollups (`finance_service`), audit, the integer-cents money discipline, the RBAC level
  model, the six-language term/i18n data — all of it ports. The "no SQL above the repo"
  rule survives intact; FastAPI just calls the same services.
- **Real frontend fixes the UX ceiling.** No rerun model, no CSS-fighting; Tailwind +
  React give genuine mobile-first responsive components, instant client-side interactions,
  proper dialogs/modals (no "one `st.dialog` at a time" hack), and fast first paint.
- **Strong typing on both ends.** Pydantic on the backend; TypeScript on the frontend.
  Generate the TS client from the FastAPI **OpenAPI** schema so the contract is enforced
  by the compiler.
- **Testability arrives for free.** FastAPI's `TestClient` lets you unit-test services and
  integration-test endpoints with zero Streamlit coupling; the frontend tests with
  Vitest/Playwright. This is the single biggest reliability win.
- **Team fit is the best of any "real rebuild" option** — the backend stays Python, so the
  hardest, most domain-specific code is written in the language the team already knows.

**Cons**
- **Two languages, two deploy units** (API + frontend). More moving parts than v3.
- The team must learn React/TS for the frontend (mitigated: it's the most transferable
  skill on this list, and the backend stays familiar).
- You own auth wiring (FastAPI doesn't bundle it) — but mature libraries exist (see §5).

### B. Full Next.js (TypeScript) full-stack + Postgres (Prisma/Drizzle) + Auth.js

**Shape.** One TypeScript codebase. API routes / server actions, SSR/RSC, Postgres via
Prisma or Drizzle, Auth.js for sessions.

**Pros**
- **Single language end-to-end**, one repo, one deploy target (e.g. Vercel/Node). Smallest
  *operational* surface of the "modern" options.
- **Fastest, most polished UI** — RSC + streaming SSR, the richest component ecosystem,
  best-in-class i18n via `next-intl`.
- **Auth.js** gives batteries-included sessions, OAuth, CSRF out of the box.

**Cons**
- **Discards all Python business logic.** Every line of `services/` and the repos must be
  re-implemented in TS — the availability math, the cents/rollup logic, the P&L. This is
  the highest *logic*-rewrite risk and where subtle financial bugs creep in.
- Worst **team-fit** for a Python-centric team: the *entire* app is now in an unfamiliar
  language, including the domain logic.
- Server actions / RSC are powerful but have a real learning curve and sharp edges around
  caching and data mutation.

### C. Django / Django REST + React

**Shape.** Django (ORM, admin, auth, sessions, CSRF, migrations all built in) exposing
DRF endpoints to a React frontend.

**Pros**
- **Python-native** — good team fit, and the most *batteries-included security* of any
  option: session framework, CSRF middleware, password hashers (PBKDF2/argon2), permissions,
  and an instant admin for back-office data entry come free.
- Mature, boring, extremely well-documented; migrations are a real framework.
- The `services/` logic ports as plain Python modules called from DRF views.

**Cons**
- **The repository layer doesn't fit cleanly.** Django wants its ORM and models; the
  current "plain-dict repos + raw-ish SQL" pattern would be rewritten into Django models,
  or you fight the ORM to keep the existing repos. Either way it's more churn at the data
  layer than option A.
- Heavier and more opinionated than FastAPI; more framework to learn for less benefit at
  this app's size. The admin is nice but this app already *is* a custom admin.
- Still need a separate React frontend, so you don't save the second-language cost vs A.

### D. SvelteKit + TypeScript + Postgres

**Shape.** SvelteKit full-stack (load functions / form actions), Postgres via Drizzle,
Lucia or Auth.js for auth.

**Pros**
- **Lean and very fast** — minimal client JS, excellent Lighthouse/responsiveness, simple
  mental model (no rerun, no RSC ceremony). Arguably the nicest pure-DX of the JS options.
- Single language, one deploy.

**Cons**
- **Same Python-discard problem as B** — all domain logic rewritten in TS.
- **Smallest ecosystem/hiring pool** of the candidates; fewer libraries, fewer examples,
  more "you'll write it yourself." Riskier for a small team that needs to *maintain* this
  for years.

### E. Stay Python, swap only the UI: NiceGUI / Reflex / FastHTML

**Shape.** Replace Streamlit with a Python UI framework that gives real layout control,
keep everything else.

**Pros**
- **Lowest migration cost by far** — `services/`, repos, RBAC, i18n, money discipline all
  stay; you rewrite only the `views/`/`ui/` layer.
- Stays 100% Python — perfect team fit.
- **NiceGUI** (Vue/Quasar under the hood) and **Reflex** (compiles to React) give far more
  layout/responsiveness control than Streamlit and a proper component/event model instead
  of full-script reruns. **FastHTML** (HTMX + server-rendered) is the lightest and fastest
  to first paint.

**Cons**
- **Still niche.** Smaller communities than Streamlit, let alone React; you can hit the
  same "fighting the framework" wall one tier up, just later.
- Reflex still has a compile/runtime model with its own quirks; NiceGUI couples UI to a
  long-lived server connection (websocket) — better than reruns but still server-stateful.
- **Doesn't fix the architecture** for true scale or a future mobile app — there's no clean
  HTTP API boundary, so a native/mobile client or third-party integration later still
  means building the API anyway. You may pay the migration twice.

### Go / Rust backends — why not

Both are excellent for high-throughput, latency-critical, or systems-level services. This
is a **CRUD business app** for a car-rental shop: a few staff, modest data, occasional
booking writes. The bottleneck is human data entry, not request throughput. Choosing Go or
Rust would **throw away all the Python reuse, slash dev velocity, and add manual memory/
concurrency or borrow-checker overhead** for performance the domain will never need. They
are over-engineering here. (If a single hot path ever needed it, you could drop one Go/Rust
microservice behind the FastAPI gateway — but that's a someday-maybe, not a v4 decision.)

---

## 3. Comparison table

Scores are relative, for *this* app and *this* team (Python-centric, small, maintaining for
years). 5 = best fit. "Migration cost" 5 = cheapest to get there.

| Candidate | Reliability | Security | Responsiveness | Speed | Dev velocity | Migration cost | Team fit | Verdict |
|---|---|---|---|---|---|---|---|---|
| **A. FastAPI + Next/React + TS + Postgres** | 5 | 5 | 5 | 5 | 4 | 3 | 4 | ✅ **Recommended** — best balance; keeps Python logic, real frontend |
| **B. Full Next.js + Postgres + Auth.js** | 4 | 5 | 5 | 5 | 4 | 1 | 2 | Strong UI, but discards all Python logic; worst team fit |
| **C. Django/DRF + React** | 5 | 5 | 4 | 4 | 4 | 3 | 4 | Safe & Python-native, but ORM forces a data-layer rewrite |
| **D. SvelteKit + TS + Postgres** | 4 | 4 | 5 | 5 | 4 | 1 | 2 | Lean & fast, but Python-discard + smallest ecosystem |
| **E. NiceGUI/Reflex/FastHTML (UI swap)** | 3 | 3 | 3 | 3 | 5 | 5 | 5 | Cheapest & all-Python, but still niche; defers the real fix |
| Go / Rust backend | 5 | 5 | 4 | 5 | 2 | 1 | 1 | Over-engineered for a CRUD shop app; not recommended |

Reading the table: **E** wins on cost/velocity/team-fit but doesn't move the needle on the
things that actually hurt (security substrate, true mobile, a clean API boundary). **B/D**
win on UI but pay for it by rewriting the crown-jewel business logic in an unfamiliar
language. **C** is the conservative Python choice but forces a data-layer rewrite for
benefits this app mostly already has. **A** is the only option that keeps the Python logic
*and* delivers a real frontend *and* leaves a clean API for future mobile/integrations.

---

## 4. Data layer — PostgreSQL vs keeping SQLite / Turso / LiteFS

**Recommendation: PostgreSQL.** For a multi-user business app it is the obvious target:
true concurrent writers (MVCC, no single-writer lock), real constraints and cascades (fixes
the orphan-`vehicle_photos` foot-gun with `ON DELETE CASCADE`), `NUMERIC`/`BIGINT` for the
integer-cents money, proper migrations (Alembic), full-text search, backups/PITR, and
managed hosting everywhere.

What ports cleanly:
- **Money stays INTEGER cents** — store as `BIGINT` (or `NUMERIC(12,0)`); the existing
  discipline transfers unchanged.
- **Dates/times → real `timestamptz` / `date`** instead of ISO-8601 text. A genuine
  upgrade: comparisons and the availability math get DB-native instead of string-compares.
- **Status CHECK constraints** become Postgres `CHECK`s or enums; keep them in sync with
  the app's status vocab exactly as today (just one source: a migration).
- **Photos/logos**: base64-in-a-column works but is heavy. v4 should move binary blobs to
  object storage (S3/MinIO/R2) and store only a URL/key — far better for responsiveness and
  DB size. (Acceptable interim: a `BYTEA` column.)

Alternatives, briefly:
- **Turso (libSQL)** — SQLite-compatible, distributed/edge, generous free tier. Tempting if
  you want minimal change, but it's still fundamentally SQLite's write model and a younger
  ecosystem. Good for read-heavy/edge; not the right call for a transactional booking app
  with concurrent writers.
- **LiteFS** — replicates a SQLite file across nodes with a single primary writer. Clever,
  but it keeps the single-writer ceiling and adds operational complexity. Solves
  availability, not write-concurrency.
- **Keep plain SQLite** — only defensible if v4 stays single-till. Given the explicit goal
  of a multi-user app, no.

If migration risk is a concern: SQLAlchemy Core (already in use via `core.db.get_engine()`)
abstracts the dialect, so the repos can target Postgres with minimal SQL changes, and a
one-time ETL script moves the existing `fleet.db` rows over.

---

## 5. Auth & security recommendations

The current SHA-256 + hand-rolled cookie scheme should **not** be ported as-is. Targets:

- **Password hashing → Argon2id** (preferred) or **bcrypt**. Both are deliberately slow and
  salted, which is the entire point for passwords; SHA-256 is the wrong primitive. In
  Python use `argon2-cffi` / `passlib`; in a JS stack use `@node-rs/argon2` or `bcrypt`.
  Provide a transparent upgrade-on-login path: verify against the old SHA-256, and if it
  matches, re-hash with Argon2id and store.
- **Sessions.**
  - *Option A (FastAPI):* server-side sessions (signed, httpOnly, `Secure`, `SameSite=Lax`
    cookie holding an opaque session id; session row in Postgres) — this is essentially the
    current `sessions`-table idea done properly, with rotation and expiry. Prefer this over
    raw JWTs for a server-rendered app because you get instant revocation. Use short-lived
    access + refresh, or stateful sessions; avoid storing JWTs in `localStorage`.
    Libraries: **Authlib** / **fastapi-users** (handles registration, password reset,
    verification, OAuth) or **Lucia**-style session handling.
  - *Option B/D (JS):* **Auth.js** (NextAuth) or **Lucia** — session management, CSRF, and
    OAuth providers out of the box.
- **CSRF.** Required the moment you use cookie auth with a browser. Use double-submit token
  or framework middleware (Django/Auth.js include it; for FastAPI add `fastapi-csrf-protect`
  or rely on `SameSite` + custom header checks for the SPA).
- **RBAC.** **Port the existing level model verbatim** — `visitor 0 < employer 1 < admin 2 <
  super_admin 3` and `can(user, perm)` is clean, well-tested-by-use, and language-agnostic.
  Enforce it **on the API/server**, not just in the UI (the current UI gating must become a
  server-side guard — never trust the client). Keep the **last-super-admin lockout guard**
  and the **audit-on-every-mutation** rule; both are good security hygiene worth preserving.
- **Transport & headers.** HTTPS only, HSTS, secure cookie flags, rate-limit the login and
  password-reset endpoints (the recovery flow is a classic abuse target), and make
  `send_mail` failures observable rather than silent.
- **Secrets.** SMTP creds and signing keys move out of `app_settings` rows into environment
  variables / a secrets manager.

---

## 6. i18n for the six languages (TR/EN/DE/IT/ES/SQ) in a JS stack

The current model — a flat key→string dict per language, identical key-sets (334 keys × 6),
plus a separate `RENTAL_TERMS` block (title + 12 rules per language) — **maps almost 1:1**
onto JS i18n.

- **Next.js (Option A frontend / B):** use **`next-intl`**. It does locale routing, message
  catalogs as JSON per locale, server + client components, and ICU message formatting
  (plurals, dates, currency) — which is *better* than the current manual `format_eur`. Ship
  one `messages/<locale>.json` per language; the existing dicts convert mechanically.
- **Non-Next React / SvelteKit:** **`i18next`** (+ `react-i18next` / `svelte-i18next`) is the
  universal choice — same JSON-catalog shape, lazy-loading per locale, pluralization.
- **Backend strings:** anything the API emits that's user-facing (e.g. invoice/term text the
  server renders) should keep its own catalog. The cleanest split: the **invoice/rental-terms
  content stays a backend concern** (it's a customer document, rendered server-side to
  HTML/PDF), exactly as `config/terms.py` does today; the **UI chrome** moves to the frontend
  catalog. This preserves the existing "invoice offers all six languages regardless of UI
  role gating" rule.
- **Staff-only language gating** (`STAFF_ONLY_LANGS = {"sq"}`, Albanian shown only to level
  ≥ 1) becomes a trivial server-enforced filter on the locale list returned to the client.
- **Validation:** keep the "every key exists in all six languages" invariant — but now you
  can *enforce it in CI* with an i18n lint (e.g. `i18next-parser` / a key-parity test),
  closing a gap the current project checks only by convention.

---

## 7. Recommendation

**Adopt Option A: FastAPI (reusing the existing Python `services/` + `data/repositories/`
layer) + Next.js/React + TypeScript + Tailwind + PostgreSQL.**

Why it wins for *this* app and *this* team:

1. **It keeps the crown jewels.** The availability math, P&L/revenue rollups, integer-cents
   money discipline, RBAC level model, audit logging, and the six-language term data are the
   parts that are expensive to get right and dangerous to rewrite. Option A ports them in
   Python; B and D would re-implement every line in TypeScript, inviting subtle financial and
   scheduling bugs. The existing "no SQL above the repo layer / plain-dict repos" design maps
   directly onto FastAPI + Pydantic, so the migration is mostly *lift-and-shift behind an API*.
2. **It fixes everything that actually hurts.** A real React/Tailwind frontend ends the
   rerun-model contortions, the CSS-fighting, the "one dialog at a time" hack, and the
   desktop-DOM-squeezed-onto-a-phone responsiveness — delivering the *responsive* and *fast*
   goals. PostgreSQL delivers concurrent writers, real constraints/cascades, and proper
   migrations — the *reliable* goal. Argon2id + framework sessions + CSRF + server-enforced
   RBAC + secrets management deliver the *secure* goal.
3. **It unlocks testability** — FastAPI `TestClient` + Vitest/Playwright give the app its
   first real test seam, which is the foundation of long-term reliability.
4. **It leaves a clean API boundary** for a future mobile app or third-party integration —
   something none of the UI-only options (E) provide, and which you'd otherwise have to build
   later anyway.

The honest trade-off is **migration cost and a second language on the frontend**. But the
frontend skill (React/TS) is the most transferable on this list, the *hard* domain code stays
in Python, and the work can be **phased**: (1) stand up FastAPI over the existing services +
add tests; (2) migrate SQLite → Postgres behind SQLAlchemy with an ETL; (3) re-implement auth
on Argon2id + sessions; (4) build the Next.js frontend page-by-page against the live API,
retiring Streamlit views as each lands. At any point you have a working system.

**One-sentence recommendation:** Rebuild v4 as a FastAPI backend that reuses the existing
Python service/repository layer, fronted by a Next.js/React + TypeScript + Tailwind UI on
PostgreSQL — the only option that preserves the valuable Python business logic while
delivering the reliability, security, responsiveness, and speed a multi-user production app
demands.
