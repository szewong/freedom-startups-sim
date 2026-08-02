/* Incentive Evolution Simulator — browser engine.
 *
 * A direct port of src/incentive_sim (match, tournament, learning, evolution)
 * so the page can simulate live instead of replaying stored runs.
 *
 * Two implementations of one model is a real risk: they can drift apart and the
 * live numbers stop meaning what the paper says. scripts/validate_js_engine.cjs
 * runs this engine and compares its converged statistics against the Python
 * results, so drift shows up as a failing check rather than a quiet lie.
 *
 * It is NOT bit-identical to the Python: NumPy's PCG64 is not reproduced here,
 * so a given seed gives a different draw. Agreement is statistical, over
 * replicates — which is the only kind that matters for the claims.
 */

const Engine = (() => {
  "use strict";

  // -- column layout (mirrors config.ATTRIBUTES / config.STRATEGY) -----------
  const A_OFF = 0, A_DEF = 1, A_RISK = 2, A_ADAPT = 3, A_STAM = 4, N_ATTR = 5;
  const S_AGG = 0, S_OFFE = 1, S_DEFE = 2, S_TEMPO = 3, S_MARGIN = 4, S_END = 5, N_STRAT = 6;

  const DEFAULTS = {
    nTeams: 64,
    regularSeasonGames: 12,

    basePossessions: 60.0,
    tempoScale: 40.0,
    basePoints: 1.05,
    skillScale: 0.55,
    overreachPenalty: 0.90,
    baseVariance: 0.65,
    varianceGain: 2.20,
    nSegments: 4,
    endgameVarianceDamp: 0.55,
    endgameMeanCost: 0.06,
    marginSeekVarianceGain: 0.35,
    fatiguePerGame: 0.030,
    fatigueAggressionGain: 0.55,
    fatigueStaminaDamp: 0.80,

    evalWindow: 150,
    stepSize: 0.06,
    stepAdaptabilityGain: 1.5,

    replaceFraction: 0.20,
    attrMutation: 0.02,
    strategyMutation: 0.04,
    attributeBudget: 2.50,
    attrMin: 0.05,
    attrMax: 0.95,
  };

  // -- randomness ------------------------------------------------------------

  /** mulberry32 gives correlated streams for nearby seeds, and the two leagues
   *  are seeded one apart — which would quietly couple their randomness and
   *  break the one property the design rests on. Mix the seed hard first. */
  function mixSeed(x) {
    x = ((x | 0) + 0x9E3779B9) | 0;
    x = Math.imul(x ^ (x >>> 16), 0x21f0aaad);
    x = Math.imul(x ^ (x >>> 15), 0x735a2d97);
    return (x ^ (x >>> 15)) >>> 0;
  }

  function makeRng(seed) {
    let a = mixSeed(seed) || 1;
    let spare = null;

    const next = () => {
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };

    const normal = () => {
      if (spare !== null) { const v = spare; spare = null; return v; }
      let u = 0, v = 0, s = 0;
      do {
        u = next() * 2 - 1;
        v = next() * 2 - 1;
        s = u * u + v * v;
      } while (s >= 1 || s === 0);
      const f = Math.sqrt((-2 * Math.log(s)) / s);
      spare = v * f;
      return u * f;
    };

    // Marsaglia-Tsang, shape > 1 only (we use 12).
    const gamma = (shape) => {
      const d = shape - 1 / 3;
      const c = 1 / Math.sqrt(9 * d);
      for (;;) {
        let x, v;
        do { x = normal(); v = 1 + c * x; } while (v <= 0);
        v = v * v * v;
        const u = next();
        if (u < 1 - 0.0331 * x * x * x * x) return d * v;
        if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
      }
    };

    for (let i = 0; i < 16; i++) next();
    return { next, normal, gamma, int: (n) => Math.floor(next() * n) };
  }

  // -- population ------------------------------------------------------------

  function renormaliseBudget(attrs, n, cfg) {
    const { attrMin: lo, attrMax: hi, attributeBudget: budget } = cfg;
    for (let i = 0; i < attrs.length; i++) attrs[i] = Math.min(hi, Math.max(lo, attrs[i]));

    for (let pass = 0; pass < 64; pass++) {
      let worst = 0;
      for (let t = 0; t < n; t++) {
        const base = t * N_ATTR;
        let total = 0;
        for (let k = 0; k < N_ATTR; k++) total += attrs[base + k];
        const deficit = budget - total;
        if (Math.abs(deficit) < 1e-9) continue;
        worst = Math.max(worst, Math.abs(deficit));

        // Spread the shortfall only over attributes with headroom the right way,
        // so the clip below cannot undo it.
        let room = 0;
        for (let k = 0; k < N_ATTR; k++) {
          room += deficit > 0 ? hi - attrs[base + k] : attrs[base + k] - lo;
        }
        if (room <= 1e-12) continue;
        for (let k = 0; k < N_ATTR; k++) {
          const share = (deficit > 0 ? hi - attrs[base + k] : attrs[base + k] - lo) / room;
          attrs[base + k] = Math.min(hi, Math.max(lo, attrs[base + k] + share * deficit));
        }
      }
      if (worst < 1e-9) break;
    }
    return attrs;
  }

  function initialPopulation(n, rng, cfg) {
    const attributes = new Float64Array(n * N_ATTR);
    const strategy = new Float64Array(n * N_STRAT);

    for (let t = 0; t < n; t++) {
      let sum = 0;
      const draws = new Array(N_ATTR);
      for (let k = 0; k < N_ATTR; k++) { draws[k] = rng.gamma(12.0); sum += draws[k]; }
      for (let k = 0; k < N_ATTR; k++) {
        attributes[t * N_ATTR + k] = (draws[k] / sum) * cfg.attributeBudget;
      }
      for (let k = 0; k < N_STRAT; k++) {
        strategy[t * N_STRAT + k] = Math.min(1, Math.max(0, 0.5 + rng.normal() * 0.08));
      }
    }
    renormaliseBudget(attributes, n, cfg);
    return { n, attributes, strategy };
  }

  /** Net points per 100 possessions against a fixed neutral team, averaged over
   *  the population. A readout, not part of the model.
   *
   *  Per 100 possessions, not per game, and that matters: a per-game figure
   *  multiplies by possession count, so a population that merely evolved a
   *  faster tempo reads as more capable without being any better. Pace is not
   *  skill. (This is why basketball analytics reports ratings per 100
   *  possessions rather than per game.)
   *
   *  Both halves of the game count: the team's offense against the reference's
   *  defense, AND the reference's offense against the team's defense. An
   *  offense-only measure would call a strong defensive population weak.
   *
   *  It is a fresh-legs number — it cannot see stamina or fatigue — and it is
   *  absolute rather than relative, so pair it with headToHead() below. */
  const REF = 0.5 * 0.5;   // neutral team: attribute 0.5, emphasis 0.5

  function trueStrength(pop, cfg) {
    let total = 0;
    for (let t = 0; t < pop.n; t++) {
      const a = t * N_ATTR, s = t * N_STRAT;
      const over = Math.max(0, pop.strategy[s + S_AGG] - pop.attributes[a + A_RISK]);
      const overreach = 1 - cfg.overreachPenalty * over * over;

      const scored = Math.max(0, cfg.basePoints
        * (1 + cfg.skillScale * (pop.attributes[a + A_OFF] * pop.strategy[s + S_OFFE] - REF))
        * overreach);
      const conceded = Math.max(0, cfg.basePoints
        * (1 + cfg.skillScale * (REF - pop.attributes[a + A_DEF] * pop.strategy[s + S_DEFE])));

      total += 100 * (scored - conceded);
    }
    return total / pop.n;
  }

  /** Who would actually beat whom. Zero-sum, so it measures relative standing
   *  only — it cannot tell "both improved" from "both declined". That is what
   *  trueStrength is for. Returns the second population's win rate. */
  function headToHead(popX, popY, cfg, rng, nGames) {
    const merged = {
      n: popX.n + popY.n,
      attributes: new Float64Array(popX.n * N_ATTR + popY.n * N_ATTR),
      strategy: new Float64Array(popX.n * N_STRAT + popY.n * N_STRAT),
    };
    merged.attributes.set(popX.attributes, 0);
    merged.attributes.set(popY.attributes, popX.n * N_ATTR);
    merged.strategy.set(popX.strategy, 0);
    merged.strategy.set(popY.strategy, popX.n * N_STRAT);

    let winsY = 0, marginSum = 0;
    for (let i = 0; i < nGames; i++) {
      const x = rng.int(popX.n);
      const y = popX.n + rng.int(popY.n);
      const [sx, sy] = simulateGame(merged, x, y, 0, 0, cfg, rng);
      if (sy > sx) winsY += 1;
      marginSum += sy - sx;
    }
    return { winRate: winsY / nGames, meanMargin: marginSum / nGames };
  }

  // -- match engine (reward-blind: knows nothing about thresholds) -----------

  function perPossession(pop, atk, def, fatigue, cfg) {
    const a = atk * N_ATTR, sa = atk * N_STRAT, d = def * N_ATTR, sd = def * N_STRAT;
    const skill = pop.attributes[a + A_OFF] * pop.strategy[sa + S_OFFE]
                - pop.attributes[d + A_DEF] * pop.strategy[sd + S_DEFE];
    let mean = cfg.basePoints * (1 + cfg.skillScale * skill);
    const over = Math.max(0, pop.strategy[sa + S_AGG] - pop.attributes[a + A_RISK]);
    mean *= 1 - cfg.overreachPenalty * over * over;
    mean = Math.max(mean * (1 - fatigue), 0.05);
    const variance = cfg.baseVariance * (1 + cfg.varianceGain * pop.strategy[sa + S_AGG]);
    return [mean, variance];
  }

  function fatigueOf(pop, team, played, cfg) {
    const a = team * N_ATTR, s = team * N_STRAT;
    const f = cfg.fatiguePerGame * played
      * (1 + cfg.fatigueAggressionGain * pop.strategy[s + S_AGG])
      * (1 - cfg.fatigueStaminaDamp * pop.attributes[a + A_STAM]);
    return Math.min(0.6, Math.max(0, f));
  }

  function simulateGame(pop, x, y, playedX, playedY, cfg, rng) {
    const [meanX, varX] = perPossession(pop, x, y, fatigueOf(pop, x, playedX, cfg), cfg);
    const [meanY, varY] = perPossession(pop, y, x, fatigueOf(pop, y, playedY, cfg), cfg);

    const tempo = 0.5 * (pop.strategy[x * N_STRAT + S_TEMPO] + pop.strategy[y * N_STRAT + S_TEMPO]);
    const perSegment = (cfg.basePossessions + cfg.tempoScale * tempo) / cfg.nSegments;

    let scoreX = 0, scoreY = 0;
    for (let seg = 0; seg < cfg.nSegments; seg++) {
      let mmX = 1, mmY = 1, vmX = 1, vmY = 1;
      if (seg === cfg.nSegments - 1) {
        const lead = scoreX - scoreY;
        if (lead > 0) [mmX, vmX] = endgame(pop, x, cfg);
        else if (lead < 0) [mmY, vmY] = endgame(pop, y, cfg);
      }
      scoreX += Math.max(0, perSegment * meanX * mmX + rng.normal() * Math.sqrt(perSegment * varX * vmX));
      scoreY += Math.max(0, perSegment * meanY * mmY + rng.normal() * Math.sqrt(perSegment * varY * vmY));
    }

    let finalX = Math.round(scoreX), finalY = Math.round(scoreY);
    for (let ot = 0; ot < 20 && finalX === finalY; ot++) {
      finalX += Math.round(Math.max(0, 6 * meanX + rng.normal() * Math.sqrt(6 * varX)));
      finalY += Math.round(Math.max(0, 6 * meanY + rng.normal() * Math.sqrt(6 * varY)));
    }
    if (finalX === finalY) finalX += 1;
    return [finalX, finalY];
  }

  function endgame(pop, team, cfg) {
    const s = team * N_STRAT;
    const varMult = (1 - cfg.endgameVarianceDamp * pop.strategy[s + S_END])
                  * (1 + cfg.marginSeekVarianceGain * pop.strategy[s + S_MARGIN]);
    return [1 - cfg.endgameMeanCost * pop.strategy[s + S_END], varMult];
  }

  // -- bracket ---------------------------------------------------------------

  function bracketOrder(n) {
    let order = [0];
    for (let size = 1; size < n; size *= 2) {
      const next = [];
      for (const seed of order) { next.push(seed); next.push(2 * size - 1 - seed); }
      order = next;
    }
    return order;
  }

  // -- learning: per-team (1+1) evolution strategy ---------------------------

  function makeLearner(pop, cfg, rng) {
    const n = pop.n;
    const incumbent = Float64Array.from(pop.strategy);
    const candidate = new Float64Array(n * N_STRAT);
    const phase = new Int8Array(n);
    const games = new Int32Array(n);
    const reward = new Float64Array(n);
    const incumbentScore = new Float64Array(n).fill(-1);

    const step = (t) => cfg.stepSize * (1 + cfg.stepAdaptabilityGain * pop.attributes[t * N_ATTR + A_ADAPT]);
    const mutateInto = (target, t) => {
      const sz = step(t);
      for (let k = 0; k < N_STRAT; k++) {
        target[t * N_STRAT + k] = Math.min(1, Math.max(0,
          incumbent[t * N_STRAT + k] + rng.normal() * sz));
      }
    };
    for (let t = 0; t < n; t++) mutateInto(candidate, t);

    const apply = () => {
      for (let t = 0; t < n; t++) {
        const src = phase[t] === 0 ? incumbent : candidate;
        for (let k = 0; k < N_STRAT; k++) pop.strategy[t * N_STRAT + k] = src[t * N_STRAT + k];
      }
    };
    apply();

    return {
      incumbent,
      record(team, value) { reward[team] += value; games[team] += 1; },
      settle() {
        for (let t = 0; t < pop.n; t++) {
          if (games[t] < cfg.evalWindow) continue;
          const score = reward[t] / games[t];
          if (phase[t] === 0) {
            incumbentScore[t] = score;
          } else {
            if (score > incumbentScore[t]) {
              for (let k = 0; k < N_STRAT; k++) incumbent[t * N_STRAT + k] = candidate[t * N_STRAT + k];
              incumbentScore[t] = score;
            }
            mutateInto(candidate, t);
          }
          phase[t] = 1 - phase[t];
          games[t] = 0;
          reward[t] = 0;
        }
        apply();
      },
      reseed(team, strategyRow) {
        for (let k = 0; k < N_STRAT; k++) incumbent[team * N_STRAT + k] = strategyRow[k];
        mutateInto(candidate, team);
        phase[team] = 0; games[team] = 0; reward[team] = 0; incumbentScore[team] = -1;
        for (let k = 0; k < N_STRAT; k++) pop.strategy[team * N_STRAT + k] = strategyRow[k];
      },
    };
  }

  // -- one season ------------------------------------------------------------

  function runSeason(state, cfg, rng) {
    const { pop, learner, threshold } = state;
    const n = pop.n;
    const reward = new Float64Array(n);
    const played = new Int32Array(n);
    const order = new Int32Array(n);
    for (let i = 0; i < n; i++) order[i] = i;

    let games = 0, marginSum = 0, marginSq = 0, blowouts = 0, close = 0, scoreSum = 0;

    const record = (x, y, sx, sy) => {
      const margin = sx - sy;
      const rx = margin >= threshold ? 1 : 0;
      const ry = -margin >= threshold ? 1 : 0;
      reward[x] += rx; reward[y] += ry;
      played[x] += 1; played[y] += 1;
      learner.record(x, rx); learner.record(y, ry);
      games += 1;
      marginSum += margin; marginSq += margin * margin;
      const abs = Math.abs(margin);
      if (abs >= 10) blowouts += 1;
      if (abs <= 3) close += 1;
      scoreSum += sx + sy;
    };

    // Regular season: everyone plays the same number of games, on fresh legs.
    for (let round = 0; round < cfg.regularSeasonGames; round++) {
      for (let i = n - 1; i > 0; i--) {
        const j = rng.int(i + 1);
        const tmp = order[i]; order[i] = order[j]; order[j] = tmp;
      }
      for (let i = 0; i < n / 2; i++) {
        const x = order[i], y = order[i + n / 2];
        const [sx, sy] = simulateGame(pop, x, y, 0, 0, cfg, rng);
        record(x, y, sx, sy);
      }
    }

    // Seed by the league's own success metric, ties broken at random.
    // The jitter must be drawn ONCE PER TEAM, not inside the comparator: a
    // comparator that re-randomises on every call is non-transitive, and with
    // integer rewards there are many ties, so the resulting order is garbage
    // rather than a ranking.
    const keyed = new Float64Array(n);
    for (let i = 0; i < n; i++) keyed[i] = reward[i] + rng.next() * 1e-6;
    const seeds = Array.from({ length: n }, (_, i) => i).sort((p, q) => keyed[q] - keyed[p]);
    const seedOf = new Int32Array(n);
    seeds.forEach((team, pos) => { seedOf[team] = pos; });

    // Bracket. Fatigue accumulates: a team in round r has played r bracket games.
    let alive = bracketOrder(n).map((slot) => seeds[slot]);
    const bracketGames = [];
    let upsets = 0;
    for (let round = 0; alive.length > 1; round++) {
      const winners = [];
      for (let i = 0; i < alive.length; i += 2) {
        const x = alive[i], y = alive[i + 1];
        const [sx, sy] = simulateGame(pop, x, y, round, round, cfg, rng);
        record(x, y, sx, sy);
        const xWon = sx > sy;
        const winner = xWon ? x : y, loser = xWon ? y : x;
        if (seedOf[winner] > seedOf[loser]) upsets += 1;
        bracketGames.push({
          stage: round, margin: Math.abs(sx - sy),
          hi: Math.max(sx, sy), lo: Math.min(sx, sy),
          winSeed: seedOf[winner] + 1, loseSeed: seedOf[loser] + 1,
          counted: Math.abs(sx - sy) >= threshold,
        });
        winners.push(winner);
      }
      alive = winners;
    }

    learner.settle();
    reproduce(pop, learner, reward, cfg, rng);

    const meanMargin = marginSum / games;
    const stats = {
      aggression: mean(pop.strategy, pop.n, N_STRAT, S_AGG),
      offense: mean(pop.attributes, pop.n, N_ATTR, A_OFF),
      defense: mean(pop.attributes, pop.n, N_ATTR, A_DEF),
      riskCapacity: mean(pop.attributes, pop.n, N_ATTR, A_RISK),
      tempo: mean(pop.strategy, pop.n, N_STRAT, S_TEMPO),
      trueStrength: trueStrength(pop, cfg),
      marginSd: Math.sqrt(Math.max(0, marginSq / games - meanMargin * meanMargin)),
      blowoutRate: blowouts / games,
      closeRate: close / games,
      upsetRate: upsets / (n - 1),
      avgScore: scoreSum / (2 * games),
      rewardRate: sum(reward) / sum(played),
      champion: alive[0],
      championSeed: seedOf[alive[0]] + 1,
    };
    return { stats, bracketGames };
  }

  function reproduce(pop, learner, reward, cfg, rng) {
    const n = pop.n;
    const nReplace = Math.max(1, Math.round(cfg.replaceFraction * n));
    const ranked = Array.from({ length: n }, (_, i) => i).sort((p, q) => reward[p] - reward[q]);
    const losers = ranked.slice(0, nReplace);
    const winners = ranked.slice(n - nReplace);

    const child = new Float64Array(N_STRAT);
    for (const loser of losers) {
      const parent = winners[rng.int(winners.length)];
      for (let k = 0; k < N_ATTR; k++) {
        pop.attributes[loser * N_ATTR + k] =
          pop.attributes[parent * N_ATTR + k] + rng.normal() * cfg.attrMutation;
      }
      for (let k = 0; k < N_STRAT; k++) {
        child[k] = Math.min(1, Math.max(0,
          learner.incumbent[parent * N_STRAT + k] + rng.normal() * cfg.strategyMutation));
      }
      learner.reseed(loser, child);
    }
    renormaliseBudget(pop.attributes, n, cfg);
  }

  const mean = (arr, n, stride, col) => {
    let total = 0;
    for (let t = 0; t < n; t++) total += arr[t * stride + col];
    return total / n;
  };
  const sum = (arr) => { let t = 0; for (let i = 0; i < arr.length; i++) t += arr[i]; return t; };

  // -- public API ------------------------------------------------------------

  /** Both leagues start from a byte-identical population; only the rule differs. */
  function createRun(options) {
    const cfg = Object.assign({}, DEFAULTS, options.config || {});
    const leagues = options.leagues.map((league, index) => {
      const rng = makeRng(options.seed * 7919 + 1);           // same population...
      const pop = initialPopulation(cfg.nTeams, rng, cfg);
      const runRng = makeRng(options.seed * 104729 + index + 1); // ...different stream
      return {
        name: league.name,
        threshold: league.threshold,
        pop,
        learner: makeLearner(pop, cfg, runRng),
        rng: runRng,
        history: [],
        latestBracket: [],
      };
    });
    // A separate stream, so measurement never perturbs either league.
    return { cfg, leagues, season: 0, h2hHistory: [], measureRng: makeRng(options.seed * 31 + 13) };
  }

  const H2H_EVERY = 4;
  const H2H_GAMES = 600;

  function step(run) {
    for (const league of run.leagues) {
      const { stats, bracketGames } = runSeason(
        { pop: league.pop, learner: league.learner, threshold: league.threshold },
        run.cfg, league.rng,
      );
      league.history.push(stats);
      league.latestBracket = bracketGames;
    }
    run.season += 1;

    // Relative standing between the two evolved populations, on fresh legs.
    if (run.leagues.length === 2 && (run.season % H2H_EVERY === 0 || run.season === 1)) {
      const [x, y] = run.leagues;
      run.headToHead = headToHead(x.pop, y.pop, run.cfg, run.measureRng, H2H_GAMES);
      run.h2hHistory.push({ season: run.season, ...run.headToHead });
    }
    return run;
  }

  return { DEFAULTS, createRun, step, makeRng, initialPopulation, trueStrength, headToHead, simulateGame };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Engine;
