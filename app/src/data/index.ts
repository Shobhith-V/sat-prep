/**
 * Question bank loader.
 *
 * The 8 dataset files are copied here by scripts/copy-data.mjs. They are loaded
 * via dynamic import so Vite code-splits them into their own chunk — the login
 * and dashboard screens stay lean; the ~2 MB bank only downloads when a student
 * enters the practice flow. The merged result is cached after first load.
 */
import type { Question } from '../types';

const loaders = [
  () => import('./test4.json'),
  () => import('./test5.json'),
  () => import('./test6.json'),
  () => import('./test7.json'),
  () => import('./test8.json'),
  () => import('./test9.json'),
  () => import('./test10.json'),
  () => import('./test11.json'),
];

let cache: Question[] | null = null;

export async function loadQuestionBank(): Promise<Question[]> {
  if (cache) return cache;
  const modules = await Promise.all(loaders.map((load) => load()));
  cache = modules.flatMap((m) => m.default as unknown as Question[]);
  return cache;
}
