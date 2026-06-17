/**
 * adaptive.ts — pure question selection engine.
 *
 * One entry point, selectQuestions(), branches by mode:
 *   - random      : prefer-unseen, uniform shuffle
 *   - topic_drill : same as random within the already topic-narrowed pool
 *   - adaptive    : prefer-unseen, competency-weighted, difficulty-balanced (Mixed)
 *
 * Competency weights (per spec):
 *   accuracy < 50%      → 5
 *   50–75%              → 3
 *   > 75%               → 1
 *   never attempted     → 2
 *
 * An injectable rng keeps selection deterministic in tests.
 */
import type { Question, PracticeConfig, Difficulty } from '../types';
import type { CompetencyRow } from './queries';
import { applyFilters, type SessionFilters } from './questionFilters';

type Rng = () => number;

export interface SelectArgs {
  bank: Question[];
  config: PracticeConfig;
  competency?: CompetencyRow[];
  seenIds?: Set<string>;
  rng?: Rng;
}

function configToFilters(config: PracticeConfig): SessionFilters {
  return {
    section: config.section,
    difficulty: config.difficulty,
    topic: config.topic,
    subtopic: config.subtopic,
  };
}

function shuffle<T>(items: T[], rng: Rng): T[] {
  const a = items.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function weightedSample<T>(items: T[], weight: (it: T) => number, n: number, rng: Rng): T[] {
  const pool = items.slice();
  const weights = pool.map(weight);
  const out: T[] = [];
  const take = Math.min(n, pool.length);
  for (let k = 0; k < take; k++) {
    const total = weights.reduce((s, w) => s + w, 0);
    let r = rng() * total;
    let idx = 0;
    while (idx < pool.length - 1 && r >= weights[idx]) {
      r -= weights[idx];
      idx += 1;
    }
    out.push(pool[idx]);
    pool.splice(idx, 1);
    weights.splice(idx, 1);
  }
  return out;
}

// ── Competency → weights ────────────────────────────────────────────────────

interface Comp { attempts: number; accuracy: number; }

function buildCompetencyMap(rows: CompetencyRow[]): Map<string, Comp> {
  const map = new Map<string, Comp>();
  const topicAgg = new Map<string, { attempts: number; correct: number }>();

  for (const row of rows) {
    map.set(`${row.topic}::${row.subtopic}`, { attempts: row.attempts, accuracy: row.accuracy });
    const agg = topicAgg.get(row.topic) ?? { attempts: 0, correct: 0 };
    agg.attempts += row.attempts;
    agg.correct += row.correct;
    topicAgg.set(row.topic, agg);
  }
  for (const [topic, agg] of topicAgg) {
    map.set(topic, {
      attempts: agg.attempts,
      accuracy: agg.attempts > 0 ? Math.round((100 * agg.correct) / agg.attempts) : 0,
    });
  }
  return map;
}

function weightFor(q: Question, comp: Map<string, Comp>): number {
  const c = comp.get(`${q.topic}::${q.subtopic}`) ?? comp.get(q.topic);
  if (!c || c.attempts === 0) return 2; // never attempted
  if (c.accuracy < 50) return 5;
  if (c.accuracy <= 75) return 3;
  return 1;
}

// ── Prefer-unseen helpers ───────────────────────────────────────────────────

/** Draw n from items, preferring unseen; backfill with seen if needed. */
function preferUnseen(
  items: Question[],
  n: number,
  seen: Set<string>,
  draw: (pool: Question[], k: number) => Question[],
): Question[] {
  const unseen = items.filter((q) => !seen.has(q.id));
  const seenItems = items.filter((q) => seen.has(q.id));
  const picked = draw(unseen, Math.min(n, unseen.length));
  if (picked.length < n) {
    picked.push(...draw(seenItems, n - picked.length));
  }
  return picked;
}

/** Even round-robin split of count across easy/medium/hard. */
function difficultyTargets(count: number): Record<Difficulty, number> {
  const base = Math.floor(count / 3);
  const rem = count % 3;
  return {
    easy: base + (rem >= 1 ? 1 : 0),
    medium: base + (rem >= 2 ? 1 : 0),
    hard: base,
  };
}

// ── Mode selectors ──────────────────────────────────────────────────────────

function selectAdaptive(
  pool: Question[],
  count: number,
  seen: Set<string>,
  comp: Map<string, Comp>,
  mixed: boolean,
  rng: Rng,
): Question[] {
  const draw = (items: Question[], k: number) => weightedSample(items, (q) => weightFor(q, comp), k, rng);

  if (!mixed) return preferUnseen(pool, count, seen, draw);

  // Mixed: balance across difficulties, then mix the final order.
  const targets = difficultyTargets(count);
  const used = new Set<string>();
  const chosen: Question[] = [];

  for (const d of ['easy', 'medium', 'hard'] as Difficulty[]) {
    const bucket = pool.filter((q) => q.difficulty === d && !used.has(q.id));
    const picked = preferUnseen(bucket, targets[d], seen, draw);
    picked.forEach((q) => used.add(q.id));
    chosen.push(...picked);
  }
  if (chosen.length < count) {
    const rest = pool.filter((q) => !used.has(q.id));
    chosen.push(...preferUnseen(rest, count - chosen.length, seen, draw));
  }
  return shuffle(chosen, rng);
}

function selectUniform(pool: Question[], count: number, seen: Set<string>, rng: Rng): Question[] {
  const draw = (items: Question[], k: number) => shuffle(items, rng).slice(0, k);
  return preferUnseen(pool, count, seen, draw);
}

// ── Entry point ─────────────────────────────────────────────────────────────

export function selectQuestions({
  bank,
  config,
  competency = [],
  seenIds = new Set<string>(),
  rng = Math.random,
}: SelectArgs): Question[] {
  const pool = applyFilters(bank, configToFilters(config));
  const count = Math.min(config.count, pool.length);
  if (count === 0) return [];

  if (config.mode === 'adaptive') {
    return selectAdaptive(
      pool, count, seenIds, buildCompetencyMap(competency), config.difficulty === 'mixed', rng,
    );
  }
  // random + topic_drill
  return selectUniform(pool, count, seenIds, rng);
}
