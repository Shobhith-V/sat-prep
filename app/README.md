# SAT Prep — Web Application

An adaptive SAT practice platform. Students sign in, practice questions drawn
from 945 officially-sourced SAT items, and track competency by topic over time.
Built with React + Vite + TypeScript, Supabase (Auth + Postgres), and deployed
to GitHub Pages.

> The question dataset is produced by the extraction pipeline in the repository
> root (`scripts/`, `output/`). This `app/` directory is the frontend that
> consumes it. See the root `README.md` for the pipeline.

---

## 1. Overview

- **Auth** — email/password via Supabase; a profile row is auto-created on signup.
- **Dashboard** — competency "skill map", headline metrics, accuracy charts,
  weakest/strongest topics, and a Start Practice CTA.
- **Practice** — three modes (Adaptive, Random, Topic Drill), section/difficulty
  filters, configurable count, live availability counts.
- **Session** — one question at a time, MC + numeric response, expandable source
  images, progress/timer, question flagging, forward-only navigation.
- **Results** — score + performance band, per-question review (your answer vs.
  correct + explanation), filters, this-session strongest/weakest topics, and
  one-shot persistence to Supabase.
- **Flagged Questions** — review everything you flagged, split correct/incorrect.

## 2. Features

| Area | Details |
|---|---|
| Practice modes | Adaptive (competency-weighted), Random, Topic Drill (topic + optional subtopic) |
| Difficulty | Mixed / Easy / Medium / Hard |
| Question types | Multiple choice + numeric response (fraction/decimal/multi-form aware) |
| Flagging | Flag during a session; review later on the Flagged page |
| Competency | Per-topic accuracy with red/yellow/green/grey bands |
| Charts | Topic accuracy, Reading vs. Math, by difficulty (Recharts) |
| Persistence | Atomic Supabase RPC writes session + attempts + competency |

## 3. Screenshots

_Add screenshots here before public launch._

- `docs/screenshot-dashboard.png` — Dashboard
- `docs/screenshot-setup.png` — Practice Setup
- `docs/screenshot-session.png` — Practice Session
- `docs/screenshot-results.png` — Results

## 4. Local development

```bash
cd app
cp .env.example .env        # fill in Supabase URL + anon key
npm install
npm run dev                 # predev copies the dataset, then starts Vite
# → http://localhost:5173/sat-prep/
```

`npm run dev` / `npm run build` automatically run `scripts/copy-data.mjs`
(`predev` / `prebuild` hooks), which copies `../output/test*.json` into
`src/data/` and the 120 referenced page images into `public/assets/`.

## 5. Environment variables

| Variable | Purpose |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/publishable key (safe in a frontend build; RLS protects data) |

Local: in `app/.env`. Production: as GitHub Actions secrets of the same names.
Never commit `.env` or use the `service_role` key in the frontend.

## 6. Supabase setup

1. Create a Supabase project.
2. Open **SQL Editor** and run `supabase/migrations/0001_init.sql` (repo root).
   This creates the four tables, enables RLS, adds the signup trigger, and the
   `record_session` RPC.
3. **Authentication → Providers**: ensure Email is enabled. For instant local
   testing you may disable "Confirm email"; the app handles both cases.
4. Copy the project URL + anon key into `app/.env`.

## 7. Database schema overview

| Table | Purpose | Key columns |
|---|---|---|
| `profiles` | One row per user | `id` (= auth.uid), `name`, `created_at` |
| `question_attempts` | Every answered question | `student_id`, `question_id`, `topic`, `subtopic`, `section`, `difficulty`, `student_answer`, `correct_answer`, `is_correct`, `flagged`, `attempted_at` |
| `topic_competency` | Per-topic rollup | `student_id`, `topic`, `subtopic`, `attempts`, `correct`, `accuracy`, unique `(student_id, topic, subtopic)` |
| `practice_sessions` | One row per session | `student_id`, `started_at`, `completed_at`, `section`, `total_questions`, `score` |

**RLS**: every table restricts rows to `auth.uid() = student_id` (profiles use
`id`). **`record_session(p_session, p_attempts)`**: a `security invoker` RPC that
inserts the session, inserts all attempts, and upserts competency (recomputing
accuracy in SQL) in one transaction.

## 8. Deployment (GitHub Pages)

Automated via `.github/workflows/deploy.yml` on push to `main`.

**Required GitHub settings**
- **Settings → Pages → Build and deployment → Source: GitHub Actions**.
- **Settings → Secrets and variables → Actions**: add `VITE_SUPABASE_URL` and
  `VITE_SUPABASE_ANON_KEY`.
- The dataset (`output/test*.json`, `output/assets/`) must be committed — the
  build copies from it.

The site publishes to `https://<user>.github.io/sat-prep/`. The Vite `base` is
`/sat-prep/`; routing uses `HashRouter` so deep links survive refreshes without
server rewrites.

## 9. Architecture

```
src/
├── context/      AuthContext (session) · SessionContext (live practice state)
├── hooks/        useDashboardData · useQuestionBank · usePracticeProfile · useFlaggedQuestions
├── lib/          supabase · queries · stats · questionFilters · adaptive · scoring · results · taxonomy
├── components/   layout · ui · auth · dashboard · practice · results
├── pages/        Login · SignUp · Dashboard · PracticeSetup · PracticeSession · Results · FlaggedQuestions
└── data/         loadQuestionBank() — dynamic-imports the dataset (code-split)
```

All aggregation/selection/scoring lives in `lib/` as **pure functions**;
components render and dispatch only. State is React Context (no Redux), and the
live session is in-memory (never `localStorage`).

## 10. Dataset architecture

The 8 datasets (`test4`–`test11`, 945 questions) are copied into `src/data/` and
loaded via dynamic `import()`, so Vite splits them into per-test chunks
(~59 KB gzip each) that download only when a student enters practice — keeping
the login/dashboard bundle lean. Image-backed questions reference full-page PNG
scans under `public/assets/` (served at the base path), shown in an expandable
panel.

## 11. Adaptive engine

`lib/adaptive.ts` exposes one pure entry point, `selectQuestions()`:

- **Random / Topic Drill** — prefer-unseen, uniform shuffle within the filtered pool.
- **Adaptive** — competency-weighted roulette sampling without replacement:
  accuracy `<50% → ×5`, `50–75% → ×3`, `>75% → ×1`, never-attempted `→ ×2`
  (looked up at subtopic level, then topic level). For Mixed difficulty it
  balances the count across easy/medium/hard, then interleaves.

The RNG is injectable, so selection is deterministic in tests.
```
