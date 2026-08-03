/* Does the browser engine still agree with the Python one?
 *
 * Two implementations of one model can drift apart, and if they do the
 * interactive page starts telling a different story from FINDINGS.md. This runs
 * the JS engine at both frozen configurations and compares its statistics
 * against the Python ones directly.
 *
 * Agreement is statistical, not bit-for-bit: NumPy's PCG64 is not reproduced in
 * the browser, so the same seed draws different numbers. What must match is
 * where the cohort lands.
 *
 * METHOD §7: the browser port of the sibling simulation caught three defects the
 * Python had carried for hours. Disagreement here is information, not nuisance.
 *
 *   node scripts/validate_js_engine.cjs
 */

const Engine = require("../web/engine.js");
const WORLDS = require("../web/worlds.js");

const N_FOUNDERS = 6000;
const SEEDS = [1, 2, 3, 4];
const BASELINE = "bootstrap";

// Measured by the Python engine: results/counterfactual_smallcap.json and
// results/counterfactual.json, 5,000 founders x 8 replicates at the config
// hashes named below. Dollar tolerances are absolute; rate tolerances are in
// probability points. They allow roughly four times the disagreement actually
// observed, which is enough headroom for sampling noise across seeds and tight
// enough that a real divergence fails rather than passing quietly.
//
// The config hashes moved when pre-seed gained an ARR-based price. Not one of
// these numbers moved with them: no arm that raises on day one ever reaches that
// row with revenue, and a Python test asserts the calibrated arms are
// bit-identical across the change.
const PYTHON = {
  smallcap: {
    hash: "b37d74e2b7e016da",
    checks: [
      ["bootstrap.netMedian", -461537, 60e3],
      ["bootstrap.ownMedian", 613732, 60e3],
      ["bootstrap.pEquityZero", 0.0, 0.005],
      ["bootstrap.pDied", 0.4519, 0.03],
      ["standard_venture.netMedian", -275312, 60e3],
      ["standard_venture.ownMedian", 0, 40e3],
      ["standard_venture.pEquityZero", 0.5874, 0.06],
      ["standard_venture.gapNet", 95963, 60e3],
      ["standard_venture.gapOwn", -29266, 40e3],
      ["max_venture.netMedian", -160911, 80e3],
      ["max_venture.pEquityZero", 0.7556, 0.06],
      ["max_venture.gapOwn", -80470, 50e3],
    ],
  },
  venture: {
    hash: "f489a543e3928b5c",
    checks: [
      ["bootstrap.netMedian", -398005, 60e3],
      ["bootstrap.ownMedian", 705102, 70e3],
      ["bootstrap.pEquityZero", 0.0, 0.005],
      ["bootstrap.pDied", 0.4443, 0.03],
      ["standard_venture.netMedian", 98910, 110e3],
      ["standard_venture.pEquityZero", 0.516, 0.06],
      ["standard_venture.gapNet", 584869, 90e3],
      ["standard_venture.gapOwn", -22053, 50e3],
      ["max_venture.netMedian", 2189077, 250e3],
      ["max_venture.pEquityZero", 0.6023, 0.06],
      ["max_venture.gapOwn", 1387545, 300e3],
    ],
  },
};

// Structural facts both engines must agree on regardless of tuning. These are
// the claims FINDINGS.md actually makes; if one of these breaks, the page is
// wrong even if every median above happens to land inside tolerance.
const INVARIANTS = [
  {
    note: "a bootstrapper's equity is never cancelled — nothing stands in front of it",
    check: (s) => s.bootstrap.pEquityZero === 0,
  },
  {
    note: "raising more leaves the founder owning less",
    check: (s) => s.max_venture.pEquityZero > s.standard_venture.pEquityZero,
  },
  {
    note: "venture pays more wages than bootstrapping",
    check: (s) => s.standard_venture.gapLabour > 0 && s.max_venture.gapLabour > 0,
  },
  {
    note: "the ledger decomposes exactly: net = wage + ownership",
    check: (s, result) =>
      Object.values(result.arms).every((arm) =>
        arm.rows.every((r) => Math.abs(r.labour + r.ownership - r.net) < 1e-6)
      ),
  },
  {
    note: "every founder reaches an ending",
    check: (s, result) =>
      Object.values(result.arms).every((arm) => arm.rows.every((r) => r.died || r.exited)),
  },
  {
    note: "delaying the first raise protects the founder's equity",
    check: (s) => s.freedom.pEquityZero < s.standard_venture.pEquityZero,
  },
  {
    note: "delaying means entering the ladder higher, so raising less in total",
    check: (s) => s.freedom.meanRaised < s.standard_venture.meanRaised,
  },
  {
    note: "no NaNs anywhere",
    check: (s, result) =>
      Object.values(result.arms).every((arm) =>
        arm.rows.every((r) => Number.isFinite(r.net) && Number.isFinite(r.ownership))
      ),
  },
];

function get(stats, path) {
  const [arm, key] = path.split(".");
  return stats[arm][key];
}

function meanStats(world, seeds) {
  const cfg = WORLDS[world].config;
  let acc = null;
  let last = null;
  for (const seed of seeds) {
    const result = Engine.simulate(cfg, { nFounders: N_FOUNDERS, seed });
    const stats = Engine.summarise(result, BASELINE);
    last = { result, stats };
    if (acc === null) {
      acc = JSON.parse(JSON.stringify(stats));
    } else {
      for (const arm of Object.keys(stats)) {
        for (const k of Object.keys(stats[arm])) {
          if (typeof stats[arm][k] === "number") acc[arm][k] += stats[arm][k];
        }
      }
    }
  }
  for (const arm of Object.keys(acc)) {
    for (const k of Object.keys(acc[arm])) {
      if (typeof acc[arm][k] === "number") acc[arm][k] /= seeds.length;
    }
  }
  return { stats: acc, sample: last };
}

function money(v) {
  return (v < 0 ? "-$" : "$") + (Math.abs(v) / 1e6).toFixed(3) + "M";
}

function main() {
  console.log(
    `JS engine vs Python: ${N_FOUNDERS} founders x ${SEEDS.length} seeds, ` +
      `${Object.keys(PYTHON).length} worlds\n`
  );
  const started = Date.now();
  let failures = 0;

  for (const [world, spec] of Object.entries(PYTHON)) {
    if (WORLDS[world].hash !== spec.hash) {
      console.log(
        `! ${world}: config hash is ${WORLDS[world].hash}, the reference numbers were ` +
          `measured at ${spec.hash}. Recalibrated since — refresh the reference block.`
      );
      failures++;
    }

    const { stats, sample } = meanStats(world, SEEDS);
    console.log(`${WORLDS[world].label}  (${WORLDS[world].hash})`);

    for (const [path, expected, tol] of spec.checks) {
      const got = get(stats, path);
      const delta = Math.abs(got - expected);
      const ok = delta <= tol;
      if (!ok) failures++;
      const fmt = Math.abs(expected) > 1.5 || Math.abs(got) > 1.5 ? money : (v) => v.toFixed(4);
      console.log(
        `  ${ok ? "ok  " : "FAIL"} ${path.padEnd(34)} python ${fmt(expected).padStart(10)}` +
          `   js ${fmt(got).padStart(10)}   d ${fmt(delta).padStart(10)}  tol ${fmt(tol)}`
      );
    }

    for (const inv of INVARIANTS) {
      const ok = !!inv.check(stats, sample.result);
      if (!ok) failures++;
      console.log(`  ${ok ? "ok  " : "FAIL"} ${inv.note}`);
    }
    console.log("");
  }

  const secs = ((Date.now() - started) / 1000).toFixed(1);
  if (failures) {
    console.log(`${failures} check(s) failed in ${secs}s — the engines disagree.`);
    process.exit(1);
  }
  console.log(`all checks passed in ${secs}s`);
}

main();
