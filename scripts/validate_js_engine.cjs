/* Does the browser engine still agree with the Python one?
 *
 * Two implementations of one model can drift apart, and if they do the
 * interactive page starts telling a different story from the paper. This runs
 * the JS engine at the paper's baseline configuration and prints the statistics
 * the Python run reports, so the two can be compared directly.
 *
 * Agreement is statistical, not bit-for-bit: NumPy's PCG64 is not reproduced in
 * the browser, so the same seed gives different draws. What must match is where
 * the populations converge.
 *
 *   node scripts/validate_js_engine.cjs
 */

const Engine = require("../web/engine.js");

const SEASONS = 600;
const REPLICATES = 8;
const TAIL = 30;

// Measured by the Python engine at threshold 1 vs 10, 600 seasons x 16
// replicates (results/threshold10). Tolerances are deliberately loose: with 8
// replicates the JS run has wide intervals of its own, and the check is for
// drift, not for equality.
const PYTHON = {
  aggression_a: { value: 0.0865, tol: 0.05 },
  aggression_b: { value: 0.2422, tol: 0.09 },
  aggression_gap: { value: 0.1557, tol: 0.09 },
  offense_a: { value: 0.9339, tol: 0.02 },
  offense_b: { value: 0.9302, tol: 0.02 },
  marginSd_a: { value: 11.237, tol: 1.5 },
  marginSd_b: { value: 13.339, tol: 2.0 },
  marginSd_gap: { value: 2.102, tol: 1.5 },
  blowoutRate_a: { value: 0.3894, tol: 0.06 },
  blowoutRate_b: { value: 0.4677, tol: 0.07 },
};

function tailMean(history, key) {
  const tail = history.slice(-TAIL);
  return tail.reduce((acc, row) => acc + row[key], 0) / tail.length;
}

function main() {
  console.log(`JS engine: ${SEASONS} seasons x ${REPLICATES} replicates, threshold 1 vs 10\n`);
  const started = Date.now();

  const collected = { A: {}, B: {} };
  for (const key of ["aggression", "offense", "marginSd", "blowoutRate"]) {
    collected.A[key] = []; collected.B[key] = [];
  }

  for (let replicate = 0; replicate < REPLICATES; replicate++) {
    const run = Engine.createRun({
      seed: 1000 + replicate,
      leagues: [{ name: "A", threshold: 1 }, { name: "B", threshold: 10 }],
    });
    for (let s = 0; s < SEASONS; s++) Engine.step(run);
    for (const league of run.leagues) {
      for (const key of Object.keys(collected[league.name])) {
        collected[league.name][key].push(tailMean(league.history, key));
      }
    }
    process.stdout.write(`  replicate ${replicate + 1}/${REPLICATES}\r`);
  }

  const avg = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
  const observed = {
    aggression_a: avg(collected.A.aggression),
    aggression_b: avg(collected.B.aggression),
    offense_a: avg(collected.A.offense),
    offense_b: avg(collected.B.offense),
    marginSd_a: avg(collected.A.marginSd),
    marginSd_b: avg(collected.B.marginSd),
    blowoutRate_a: avg(collected.A.blowoutRate),
    blowoutRate_b: avg(collected.B.blowoutRate),
  };
  observed.aggression_gap = observed.aggression_b - observed.aggression_a;
  observed.marginSd_gap = observed.marginSd_b - observed.marginSd_a;

  console.log(`${" ".repeat(40)}\r`);
  console.log(`${"statistic".padEnd(20)}${"python".padStart(10)}${"js".padStart(10)}` +
              `${"diff".padStart(10)}${"tol".padStart(8)}  status`);
  console.log("-".repeat(70));

  let failures = 0;
  for (const [key, { value, tol }] of Object.entries(PYTHON)) {
    const got = observed[key];
    const diff = got - value;
    const ok = Math.abs(diff) <= tol;
    if (!ok) failures += 1;
    console.log(
      `${key.padEnd(20)}${value.toFixed(4).padStart(10)}${got.toFixed(4).padStart(10)}` +
      `${diff.toFixed(4).padStart(10)}${tol.toFixed(3).padStart(8)}  ${ok ? "ok" : "DRIFT"}`,
    );
  }

  // The qualitative claims matter more than any single number.
  const checks = [
    ["League B evolves higher aggression", observed.aggression_b > observed.aggression_a],
    ["League B is more volatile", observed.marginSd_b > observed.marginSd_a],
    ["League B has more blowouts", observed.blowoutRate_b > observed.blowoutRate_a],
    ["League B is not more skilled", observed.offense_b <= observed.offense_a + 0.005],
  ];
  console.log("");
  for (const [label, passed] of checks) {
    if (!passed) failures += 1;
    console.log(`  ${passed ? "PASS" : "FAIL"}  ${label}`);
  }

  console.log(`\n${failures === 0 ? "AGREES with the Python engine" : `${failures} DISAGREEMENT(S)`}` +
              ` (${((Date.now() - started) / 1000).toFixed(0)}s)`);
  process.exit(failures === 0 ? 0 : 1);
}

main();
