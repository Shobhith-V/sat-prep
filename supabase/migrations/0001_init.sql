-- ============================================================================
-- SAT Prep — initial schema
--   tables: profiles, question_attempts, topic_competency, practice_sessions
--   security: Row Level Security on every table (users see only their own rows)
--   automation: profile auto-creation on signup, atomic session recording RPC
--
-- Apply via the Supabase SQL editor or `supabase db push`.
-- ============================================================================

-- ── Extensions ──────────────────────────────────────────────────────────────
create extension if not exists "pgcrypto"; -- gen_random_uuid()

-- ── profiles ────────────────────────────────────────────────────────────────
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  name        text not null default '',
  created_at  timestamptz not null default now()
);

-- ── question_attempts ───────────────────────────────────────────────────────
create table if not exists public.question_attempts (
  id              uuid primary key default gen_random_uuid(),
  student_id      uuid not null references auth.users (id) on delete cascade,
  question_id     text not null,
  topic           text not null,
  subtopic        text not null,
  section         text not null check (section in ('reading', 'math')),
  difficulty      text not null check (difficulty in ('easy', 'medium', 'hard')),
  student_answer  text not null default '',
  correct_answer  text not null default '',
  is_correct      boolean not null default false,
  flagged         boolean not null default false,   -- NEW: user can flag a question
  attempted_at    timestamptz not null default now()
);

create index if not exists question_attempts_student_idx
  on public.question_attempts (student_id);
create index if not exists question_attempts_student_question_idx
  on public.question_attempts (student_id, question_id);
create index if not exists question_attempts_flagged_idx
  on public.question_attempts (student_id, flagged) where flagged;

-- ── topic_competency ────────────────────────────────────────────────────────
create table if not exists public.topic_competency (
  id            uuid primary key default gen_random_uuid(),
  student_id    uuid not null references auth.users (id) on delete cascade,
  topic         text not null,
  subtopic      text not null,
  attempts      integer not null default 0,
  correct       integer not null default 0,
  accuracy      numeric(5, 2) not null default 0,    -- 0..100
  last_updated  timestamptz not null default now(),
  unique (student_id, topic, subtopic)
);

create index if not exists topic_competency_student_idx
  on public.topic_competency (student_id);

-- ── practice_sessions ───────────────────────────────────────────────────────
create table if not exists public.practice_sessions (
  id               uuid primary key default gen_random_uuid(),
  student_id       uuid not null references auth.users (id) on delete cascade,
  started_at       timestamptz not null default now(),
  completed_at     timestamptz,
  section          text not null,           -- 'reading' | 'math' | 'both'
  total_questions  integer not null default 0,
  score            integer not null default 0
);

create index if not exists practice_sessions_student_idx
  on public.practice_sessions (student_id, started_at desc);

-- ============================================================================
-- Row Level Security
-- ============================================================================
alter table public.profiles            enable row level security;
alter table public.question_attempts   enable row level security;
alter table public.topic_competency    enable row level security;
alter table public.practice_sessions   enable row level security;

-- profiles: a user may read/update only their own profile row (id = auth.uid())
create policy "profiles_select_own" on public.profiles
  for select using (auth.uid() = id);
create policy "profiles_insert_own" on public.profiles
  for insert with check (auth.uid() = id);
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

-- question_attempts: scoped to the owning student
create policy "attempts_select_own" on public.question_attempts
  for select using (auth.uid() = student_id);
create policy "attempts_insert_own" on public.question_attempts
  for insert with check (auth.uid() = student_id);
create policy "attempts_update_own" on public.question_attempts
  for update using (auth.uid() = student_id) with check (auth.uid() = student_id);

-- topic_competency: scoped to the owning student
create policy "competency_select_own" on public.topic_competency
  for select using (auth.uid() = student_id);
create policy "competency_insert_own" on public.topic_competency
  for insert with check (auth.uid() = student_id);
create policy "competency_update_own" on public.topic_competency
  for update using (auth.uid() = student_id) with check (auth.uid() = student_id);

-- practice_sessions: scoped to the owning student
create policy "sessions_select_own" on public.practice_sessions
  for select using (auth.uid() = student_id);
create policy "sessions_insert_own" on public.practice_sessions
  for insert with check (auth.uid() = student_id);
create policy "sessions_update_own" on public.practice_sessions
  for update using (auth.uid() = student_id) with check (auth.uid() = student_id);

-- ============================================================================
-- Auto-create a profile row when a new auth user signs up.
-- The name is taken from the signUp options.data.name metadata.
-- ============================================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'name', ''))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================================
-- record_session(p_session jsonb, p_attempts jsonb)
--   Atomically: insert all question_attempts, upsert topic_competency
--   (recomputing attempts/correct/accuracy), and insert the practice_sessions
--   row. Runs as the authenticated user; writes are forced to auth.uid().
--
--   p_session  : { "section": text, "total_questions": int, "score": int,
--                  "started_at": timestamptz, "completed_at": timestamptz }
--   p_attempts : [ { "question_id","topic","subtopic","section","difficulty",
--                    "student_answer","correct_answer","is_correct","flagged" }, ... ]
--   returns    : the new practice_sessions.id
-- ============================================================================
create or replace function public.record_session(p_session jsonb, p_attempts jsonb)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_uid        uuid := auth.uid();
  v_session_id uuid;
  a            jsonb;
begin
  if v_uid is null then
    raise exception 'not authenticated';
  end if;

  -- 1. practice session
  insert into public.practice_sessions
    (student_id, section, total_questions, score, started_at, completed_at)
  values (
    v_uid,
    coalesce(p_session ->> 'section', 'both'),
    coalesce((p_session ->> 'total_questions')::int, 0),
    coalesce((p_session ->> 'score')::int, 0),
    coalesce((p_session ->> 'started_at')::timestamptz, now()),
    coalesce((p_session ->> 'completed_at')::timestamptz, now())
  )
  returning id into v_session_id;

  -- 2. attempts + competency
  for a in select * from jsonb_array_elements(p_attempts)
  loop
    insert into public.question_attempts
      (student_id, question_id, topic, subtopic, section, difficulty,
       student_answer, correct_answer, is_correct, flagged)
    values (
      v_uid,
      a ->> 'question_id',
      a ->> 'topic',
      a ->> 'subtopic',
      a ->> 'section',
      a ->> 'difficulty',
      coalesce(a ->> 'student_answer', ''),
      coalesce(a ->> 'correct_answer', ''),
      coalesce((a ->> 'is_correct')::boolean, false),
      coalesce((a ->> 'flagged')::boolean, false)
    );

    insert into public.topic_competency
      (student_id, topic, subtopic, attempts, correct, accuracy, last_updated)
    values (
      v_uid,
      a ->> 'topic',
      a ->> 'subtopic',
      1,
      case when (a ->> 'is_correct')::boolean then 1 else 0 end,
      case when (a ->> 'is_correct')::boolean then 100 else 0 end,
      now()
    )
    on conflict (student_id, topic, subtopic) do update
      set attempts     = public.topic_competency.attempts + 1,
          correct      = public.topic_competency.correct
                         + case when (a ->> 'is_correct')::boolean then 1 else 0 end,
          accuracy     = round(
                           100.0 * (public.topic_competency.correct
                             + case when (a ->> 'is_correct')::boolean then 1 else 0 end)
                           / (public.topic_competency.attempts + 1), 2),
          last_updated = now();
  end loop;

  return v_session_id;
end;
$$;
