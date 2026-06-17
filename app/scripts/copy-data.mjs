/**
 * copy-data.mjs — build step that bridges the Python pipeline output into the app.
 *
 * Runs automatically via the `predev` / `prebuild` npm hooks.
 *
 *   1. Copies output/test{4..11}.json  →  app/src/data/
 *   2. Scans those datasets for referenced image assets and copies ONLY those
 *      page PNGs (≈120 files, ~20 MB) → app/public/assets/  (not all 444 pages).
 *
 * Idempotent: safe to re-run. Missing source files are warned, not fatal,
 * so the app can still scaffold before the pipeline output exists.
 */
import {
  readFileSync, writeFileSync, mkdirSync, copyFileSync, existsSync,
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const appRoot = resolve(here, '..');
const repoRoot = resolve(appRoot, '..');
const outputDir = join(repoRoot, 'output');
const dataDest = join(appRoot, 'src', 'data');
const assetsDest = join(appRoot, 'public', 'assets');

const TESTS = [4, 5, 6, 7, 8, 9, 10, 11];

mkdirSync(dataDest, { recursive: true });

const referencedAssets = new Set();
let datasetCount = 0;

for (const t of TESTS) {
  const src = join(outputDir, `test${t}.json`);
  if (!existsSync(src)) {
    console.warn(`[copy-data] WARN missing dataset: ${src}`);
    continue;
  }
  const raw = readFileSync(src, 'utf-8');
  writeFileSync(join(dataDest, `test${t}.json`), raw);
  datasetCount += 1;

  const questions = JSON.parse(raw);
  for (const q of questions) {
    for (const asset of q.assets ?? []) {
      if (asset?.src) referencedAssets.add(asset.src);
    }
  }
}

let assetCount = 0;
for (const rel of referencedAssets) {
  // rel looks like "assets/test4/page_010.png"
  const from = join(outputDir, rel);
  const to = join(assetsDest, rel.replace(/^assets\//, ''));
  if (!existsSync(from)) {
    console.warn(`[copy-data] WARN missing asset: ${from}`);
    continue;
  }
  mkdirSync(dirname(to), { recursive: true });
  copyFileSync(from, to);
  assetCount += 1;
}

console.log(
  `[copy-data] copied ${datasetCount} datasets, ${assetCount} image assets `
  + `→ src/data/ and public/assets/`,
);
