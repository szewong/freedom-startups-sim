/* Founder Wealth Simulator — browser engine.
 *
 * A direct port of src/foundersim (latents, business, captable, waterfall,
 * cohort, ledger) so the page can simulate live rather than replay stored runs.
 *
 * Two implementations of one model is a real risk: they drift, and the live
 * numbers stop meaning what FINDINGS.md says. scripts/validate_js_engine.cjs
 * runs this engine at both frozen configurations and compares its statistics
 * against the Python ones, so drift fails a check instead of lying quietly.
 *
 * It is NOT bit-identical to the Python: NumPy's PCG64 is not reproduced here,
 * so a given seed draws different numbers. Agreement is statistical, which is
 * the only kind the claims rest on.
 *
 * Structure note: the Python runs vectorised across founders, one arm at a
 * time. This runs one *founder* at a time, all arms, on a single set of draws.
 * That is slower in principle and much clearer in practice — the common random
 * numbers that make the fork a clean counterfactual are guaranteed by the loop
 * structure rather than by remembering to reuse an array.
 */

const Engine = (() => {
  "use strict";

  // -- random numbers -------------------------------------------------------

  function mulberry32(a) {
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hashSeed(str) {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h >>> 0;
  }

  function makeRng(seed) {
    const u = mulberry32(seed);
    let spare = null;

    function normal() {
      if (spare !== null) {
        const s = spare;
        spare = null;
        return s;
      }
      let x, y, r;
      do {
        x = 2 * u() - 1;
        y = 2 * u() - 1;
        r = x * x + y * y;
      } while (r === 0 || r >= 1);
      const f = Math.sqrt((-2 * Math.log(r)) / r);
      spare = y * f;
      return x * f;
    }

    // Marsaglia-Tsang. Beta(a,b) is then X/(X+Y) with X~Gamma(a), Y~Gamma(b).
    function gamma(shape) {
      if (shape < 1) return gamma(shape + 1) * Math.pow(u(), 1 / shape);
      const d = shape - 1 / 3;
      const c = 1 / Math.sqrt(9 * d);
      for (;;) {
        let x, v;
        do {
          x = normal();
          v = 1 + c * x;
        } while (v <= 0);
        v = v * v * v;
        const uu = u();
        if (uu < 1 - 0.0331 * x * x * x * x) return d * v;
        if (Math.log(uu) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
      }
    }

    function beta(a, b) {
      const x = gamma(a);
      const y = gamma(b);
      return x / (x + y);
    }

    return { uniform: u, normal, beta };
  }

  const clip = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);

  // -- the model ------------------------------------------------------------

  function churnRate(fit, b) {
    return clip(b.churn_hi - b.churn_fit_slope * fit, 0.02, 0.6);
  }

  function grossNewCustomers(fit, skill, customers, spend, ceiling, execNoise, boost, b, execSigma) {
    const headroom = clip(1 - customers / Math.max(ceiling, 1), 0, 1);
    const quality = fit * skill * (1 + boost);
    const paid = b.growth_scale * quality * Math.pow(Math.max(spend, 0) / 1e6, b.spend_alpha);
    const organic = b.organic_scale * quality * customers;
    const effort = b.effort_scale * quality;
    const shock = Math.exp(execSigma * execNoise - 0.5 * execSigma * execSigma);
    return (paid + organic + effort) * headroom * shock;
  }

  const employeesNeeded = (customers, b) =>
    Math.max(customers / b.customers_per_head - 1, 0);

  function capacityFactor(employees, customers, b) {
    return clip(((employees + 1) * b.customers_per_head) / Math.max(customers, 1), 0, 1);
  }

  function decayCeiling(ceiling, customers, b) {
    return customers + Math.max(ceiling - customers, 0) * (1 - b.market_decay);
  }

  function revenueMultiple(growth, noise, ex, arr) {
    let mult = ex.base_revenue_multiple + ex.growth_premium * Math.max(growth - 1, 0);
    if (ex.scale_premium) {
      mult += ex.scale_premium * Math.log10(Math.max(arr, 1) / ex.scale_pivot_arr);
    }
    mult = clip(mult, ex.min_revenue_multiple, ex.max_revenue_multiple);
    const shock = Math.exp(ex.exit_noise_sigma * noise - 0.5 * ex.exit_noise_sigma ** 2);
    return mult * ex.regime * shock;
  }

  function earningsMultiple(earnings, ex) {
    const decades = Math.log10(Math.max(earnings, 1) / ex.earnings_pivot);
    return clip(
      ex.base_earnings_multiple + ex.earnings_multiple_slope * decades,
      ex.min_earnings_multiple,
      ex.max_earnings_multiple
    );
  }

  function enterpriseValue(arr, profit, growth, noise, ex, ownerComp) {
    const revValue = revenueMultiple(growth, noise, ex, arr) * arr;
    const ebitda = Math.max(profit, 0);
    const ebitdaValue = earningsMultiple(ebitda, ex) * ebitda;

    let earnValue = ebitdaValue;
    if (ownerComp !== undefined && ownerComp !== null) {
      const sde = Math.max(profit + ownerComp, 0);
      const sdeValue = earningsMultiple(sde, ex) * sde;
      earnValue = sdeValue <= ex.sde_ceiling ? sdeValue : ebitdaValue;
    }
    return Math.max(revValue, earnValue);
  }

  // -- the waterfall --------------------------------------------------------
  // Preferences are paid in reverse order of investment; each non-participating
  // investor takes the greater of its preference and its share as common. The
  // conversion set is a joint decision, so it is solved by best response.

  function payouts(exitValue, prefs, owns, commonPct, converted, participating) {
    const r = prefs.length;
    const due = new Array(r);
    let totalDue = 0;
    for (let i = 0; i < r; i++) {
      due[i] = !converted[i] && prefs[i] > 0 ? prefs[i] : 0;
      totalDue += due[i];
    }

    // Junior rounds are paid first, so walk the queue from the last round back.
    const paid = new Array(r).fill(0);
    let juniorDue = 0;
    for (let i = r - 1; i >= 0; i--) {
      const available = Math.max(exitValue - juniorDue, 0);
      paid[i] = Math.min(due[i], available);
      juniorDue += due[i];
    }

    const residual = Math.max(exitValue - Math.min(totalDue, exitValue), 0);

    let commonTotal = commonPct;
    const shares = new Array(r);
    for (let i = 0; i < r; i++) {
      shares[i] = converted[i] || (participating && prefs[i] > 0);
      if (shares[i]) commonTotal += owns[i];
    }
    const perPoint = commonTotal > 0 ? residual / commonTotal : 0;

    const out = new Array(r);
    for (let i = 0; i < r; i++) out[i] = paid[i] + (shares[i] ? owns[i] * perPoint : 0);
    return { investor: out, perPoint };
  }

  const MAX_ITERATIONS = 24;

  function solveConversions(exitValue, prefs, owns, commonPct) {
    const r = prefs.length;
    const converted = new Array(r).fill(false);
    let cur = payouts(exitValue, prefs, owns, commonPct, converted, false);

    for (let it = 0; it < MAX_ITERATIONS; it++) {
      let changed = false;
      for (let c = 0; c < r; c++) {
        converted[c] = !converted[c];
        const alt = payouts(exitValue, prefs, owns, commonPct, converted, false);
        if (alt.investor[c] > cur.investor[c] + 1e-6) {
          changed = true;
          cur = alt;
        } else {
          converted[c] = !converted[c];
        }
      }
      if (!changed) break;
    }
    return converted;
  }

  function founderProceeds(exitValue, prefs, owns, founderPct, otherCommon, cap) {
    const commonPct = founderPct + otherCommon;
    const founderShareOfCommon = commonPct > 0 ? founderPct / commonPct : 0;

    const carved = (cap.carve_out || 0) * exitValue;
    const rest = exitValue - carved;

    const converted = cap.participating
      ? new Array(prefs.length).fill(false)
      : solveConversions(rest, prefs, owns, commonPct);
    const res = payouts(rest, prefs, owns, commonPct, converted, cap.participating);
    return carved * founderShareOfCommon + res.perPoint * founderPct;
  }

  // -- one founder, one strategy -------------------------------------------

  // `minArrToRaise` is the founder's own bar, distinct from the investors'. Zero
  // means "raise as soon as anyone will fund you", which in practice means
  // raising at $0 of revenue on day one. A positive threshold is a founder
  // saying: prove it first, then decide.
  const STRATEGIES = [
    { name: "bootstrap", label: "Bootstrap", maxStage: -1, raiseMultiple: 1, minArrToRaise: 0 },
    { name: "friends_family", label: "Friends & family", maxStage: 0, raiseMultiple: 1, minArrToRaise: 0 },
    { name: "seed_and_stop", label: "Seed and stop", maxStage: 1, raiseMultiple: 1, minArrToRaise: 0 },
    { name: "standard_venture", label: "Standard venture", maxStage: 5, raiseMultiple: 1, minArrToRaise: 0 },
    { name: "max_venture", label: "Maximum venture", maxStage: 5, raiseMultiple: 1.4, minArrToRaise: 0 },
    { name: "freedom", label: "Freedom startup", maxStage: 5, raiseMultiple: 1, minArrToRaise: 100e3 },
  ];

  function runArm(cfg, lat, noise, strat) {
    const b = cfg.business;
    const sp = cfg.spend;
    const cap = cfg.capital;
    const ex = cfg.exit;
    const led = cfg.ledger;
    const terms = cap.stage_terms;
    const horizon = ex.horizon_years;
    const nStages = terms.length;
    const topStage = Math.min(strat.maxStage, nStages - 1);

    let founderPct = 1;
    let otherCommon = 0;
    const invPct = new Array(nStages).fill(0);
    const invAmt = new Array(nStages).fill(0);

    let customers = 0;
    let cash = b.founder_savings;
    let ceiling = lat.market / b.price;
    let arr = 0;
    let arrPrior = 0;
    let stage = -1;
    let alive = true;
    let settled = false;
    let starvingYears = 0;

    const salaryCash = new Array(horizon).fill(0);
    const distCash = new Array(horizon).fill(0);
    const capitalCash = new Array(horizon).fill(0);
    const active = new Array(horizon).fill(false);

    let exitValue = 0, exitYear = -1, died = false, exited = false, abandoned = false;
    let firstStage = -1;
    let founderGross = 0, raised = 0, finalArr = 0, founderAtExit = 1;

    const baseChurn = churnRate(lat.fit, b);
    const growthOf = (cur, prior) => cur / Math.max(prior, b.price);

    let profit = 0;
    let salary = 0;

    /* A company raising its *first* round enters the ladder at the highest stage
     * it qualifies for rather than always at pre-seed. A business with $2M of
     * revenue raising its first round is raising a Series A, and forcing it
     * through the early rounds would charge it ~19% of the company for money it
     * does not need. Companies already on the ladder move one stage at a time.
     *
     * This changes nothing for the arms that raise on day one — at zero revenue
     * the only gate that clears is pre-seed — and it is what makes a delayed
     * first raise mean anything.
     */
    function attemptRounds(eligible, t, growth) {
      if (!eligible) return;
      if (arr < (strat.minArrToRaise || 0)) return;
      const entering = stage < 0;
      const order = [];
      if (entering) for (let s = topStage; s >= 0; s--) order.push(s);
      else for (let s = 0; s <= topStage; s++) order.push(s);

      for (const s of order) {
        if (!entering && stage !== s - 1) continue;
        const term = terms[s];
        const sg = cap.gate_noise_sigma;
        const arrBar = term.gate_arr * Math.exp(sg * noise.gateArr[t] - 0.5 * sg * sg);
        const growthBar = term.gate_growth * Math.exp(sg * noise.gateGrowth[t] - 0.5 * sg * sg);
        if (!(arr >= arrBar && growth >= growthBar)) {
          if (entering) continue; // try the next stage down
          return;
        }

        const pn = cap.price_noise_sigma;
        const priceShock = Math.exp(pn * noise.price[t] - 0.5 * pn * pn);
        let pre = Math.max(term.pre_money_base, arr * term.arr_multiple) * priceShock;
        let amount = pre * term.raise_ratio * strat.raiseMultiple;
        // A founder raising $250k to hire is not raising the ladder's pre-seed,
        // and pricing it as one would hand them a valuation they have not earned.
        if (entering && strat.entryAmount) amount = strat.entryAmount;
        if (entering && strat.entryPreMoney) pre = strat.entryPreMoney;
        const post = pre + amount;

        let newInv = post > 0 ? amount / post : 0;
        let poolAdd = term.pool_refresh;
        if (cap.null_control) {
          newInv = 0;
          poolAdd = 0;
        }
        const keep = 1 - newInv - poolAdd;

        founderPct *= keep;
        otherCommon = otherCommon * keep + poolAdd;
        for (let k = 0; k < nStages; k++) invPct[k] *= keep;
        invPct[s] = newInv;
        invAmt[s] = amount;
        cash += amount;
        raised += amount;
        stage = s;
        if (firstStage < 0) firstStage = s;

        if (s >= cap.secondary_min_stage && noise.secondary[t] < cap.secondary_prob) {
          let frac = Math.min(cap.secondary_frac, founderPct);
          frac = Math.min(frac, cap.secondary_cap / Math.max(post, 1));
          const proceeds = frac * post;
          founderPct -= frac;
          otherCommon += frac;
          capitalCash[t] += proceeds * (1 - led.tax_rate_capital);
        }
        return; // at most one round a year
      }
    }

    function liquidate(value, t) {
      const prefs = new Array(nStages);
      for (let k = 0; k < nStages; k++) {
        prefs[k] = cap.null_control ? 0 : invAmt[k] * cap.pref_multiple;
      }
      const take = founderProceeds(value, prefs, invPct, founderPct, otherCommon, cap);
      founderGross = take;
      capitalCash[t] += take * (1 - led.tax_rate_capital);
      exitValue = value;
      exitYear = t;
      founderAtExit = founderPct;
      finalArr = arr;
      settled = true;
      alive = false;
    }

    for (let t = 0; t < horizon; t++) {
      if (!alive || settled) break;
      active[t] = true;

      let growth = growthOf(arr, arrPrior);
      // "More rounds ahead" has to mean money is actually coming, not merely
      // intended: a founder still below their own bar lives within their means
      // and takes distributions, exactly like one who never intends to raise.
      const eligibleNow = arr >= (strat.minArrToRaise || 0);
      attemptRounds(stage < topStage, t, growth);
      let moreRounds = stage < topStage && eligibleNow;

      // 2. spend
      const expectedRevenue = Math.max(arr, customers * b.price);
      const expectedGp = expectedRevenue * b.gross_margin;
      const plannedEmployees = employeesNeeded(customers, b);
      const expectedOpex = plannedEmployees * b.cost_per_head + led.salary_floor;
      const reserve = (expectedOpex * sp.boot_reserve_months) / 12;
      const fromProfit = sp.boot_reinvest_frac * Math.max(expectedGp - expectedOpex, 0);
      const rate = moreRounds ? sp.funded_spend_rate : sp.patient_spend_rate;
      const deploy = fromProfit + rate * Math.max(cash - reserve, 0);
      // The deployment budget splits between marketing and payroll. At a share
      // of zero this is exactly the calibrated behaviour.
      const spend = deploy * (1 - (b.growth_hire_share || 0));
      const growthEmployees = (deploy * (b.growth_hire_share || 0)) / b.cost_per_head;

      // 3. staffing
      const boost = stage >= 2 ? b.capital_execution_boost : 0;
      // Payroll counts toward acquisition at its own efficiency, so a team can
      // win customers rather than only serve them.
      const acquisitionSpend =
        spend + growthEmployees * b.cost_per_head * (b.team_acquisition_efficiency || 0);
      const potentialNew = grossNewCustomers(
        lat.fit, lat.skill, customers, acquisitionSpend, ceiling,
        noise.exec[t], boost, b, cfg.latents.exec_sigma
      );
      const projected = customers * (1 - baseChurn) + potentialNew;
      const desiredEmployees = employeesNeeded(projected, b);

      const marketSalary = clip(
        led.salary_revenue_share * expectedRevenue, led.salary_floor, led.salary_cap
      );
      const stageSalary = stage >= 0 ? terms[Math.min(stage, nStages - 1)].founder_salary : 0;
      const salaryTarget = stage >= 0 ? Math.max(marketSalary, stageSalary) : marketSalary;
      const burnFrac = moreRounds ? sp.funded_burn_frac : sp.boot_burn_frac;
      const affordable = Math.max(cash * burnFrac + expectedGp - spend, 0);
      salary = Math.min(salaryTarget, affordable);

      const staffBudget = Math.max(cash * burnFrac + expectedGp - spend - salary, 0);
      // Hire for the book of business, or for growth, whichever is larger. The
      // growth hires are already paid for out of the deployment budget.
      const employees = Math.max(
        Math.min(desiredEmployees, staffBudget / b.cost_per_head), growthEmployees
      );

      // 4. customers
      const capacity = capacityFactor(employees, Math.max(projected, 1), b);
      const churn = clip(baseChurn + b.understaffing_churn * (1 - capacity), 0, 0.95);
      const newCustomers = potentialNew * (1 - b.understaffing_growth * (1 - capacity));
      const opening = customers;
      customers = opening * (1 - churn) + newCustomers;

      // 5. cash
      const revenue = 0.5 * (opening + customers) * b.price;
      const grossProfit = revenue * b.gross_margin;
      const opex = employees * b.cost_per_head + salary;
      cash += grossProfit - opex - spend;

      arrPrior = arr;
      arr = customers * b.price;
      profit = grossProfit - opex;

      // 6. the founder is paid
      const distReserve = (opex * led.distribution_reserve_months) / 12;
      const payable = Math.min(Math.max(cash - distReserve, 0), Math.max(profit, 0));
      let distribution = 0;
      if (!moreRounds && payable > 0) {
        distribution = led.distribution_frac * payable;
        cash -= distribution;
      }
      const founderDistribution = distribution * founderPct;
      const income = salary + founderDistribution;
      const afterTax = 1 - led.tax_rate_income;
      salaryCash[t] += salary * afterTax;
      distCash[t] += founderDistribution * afterTax;

      // 7. out of cash
      if (cash < 0) {
        attemptRounds(stage < topStage, t, growthOf(arr, arrPrior));
        if (cash < 0) {
          const pAcq = Math.min(employees * ex.acquihire_prob_per_head, ex.acquihire_prob_cap);
          const soft = noise.acquihire[t] < pAcq;
          liquidate(soft ? employees * ex.acquihire_value_per_head : 0, t);
          died = true;
          continue;
        }
      }

      // 7b. the founder gives up
      const progressing =
        growthOf(arr, arrPrior) >= ex.abandon_growth && arr - arrPrior >= ex.abandon_income;
      starvingYears = income < ex.abandon_income && !progressing ? starvingYears + 1 : 0;
      if (starvingYears >= ex.abandon_years) {
        liquidate(
          enterpriseValue(arr, profit, growthOf(arr, arrPrior), noise.exitMult[t], ex, salary), t
        );
        died = true;
        abandoned = true;
        continue;
      }

      // 8. acquisition offers
      const g = growthOf(arr, arrPrior);
      const stalled = g < ex.stall_growth;
      const offered =
        (arr >= ex.offer_min_arr && stalled && noise.offer[t] < ex.offer_prob) ||
        (arr >= ex.large_liquidity_arr && noise.offer[t] < ex.large_liquidity_prob);
      if (offered) {
        liquidate(enterpriseValue(arr, profit, g, noise.exitMult[t], ex, salary), t);
        exited = true;
        continue;
      }

      // 9. the market moves on
      ceiling = decayCeiling(ceiling, customers, b);
    }

    if (alive && !settled) {
      const last = horizon - 1;
      const value =
        enterpriseValue(arr, profit, growthOf(arr, arrPrior), noise.exitMult[last], ex, salary) *
        (1 - ex.horizon_illiquidity_discount);
      liquidate(value, last);
      exited = true;
    }

    // -- ledger -------------------------------------------------------------
    const oppAfterTax = led.opportunity_cost * (1 - led.tax_rate_income);
    let fromSalary = 0, fromDist = 0, fromExit = 0, opportunity = 0, yearsActive = 0;
    let nominal = 0, yearsToMillion = horizon + 1;
    for (let t = 0; t < horizon; t++) {
      const df = Math.pow(1 + led.discount_rate, -(t + 0.5));
      fromSalary += salaryCash[t] * df;
      fromDist += distCash[t] * df;
      fromExit += capitalCash[t] * df;
      if (active[t]) {
        opportunity += oppAfterTax * df;
        yearsActive += 1;
      }
      nominal += salaryCash[t] + distCash[t] + capitalCash[t];
      if (nominal >= 1e6 && yearsToMillion === horizon + 1) yearsToMillion = t + 1;
    }
    const ownership = fromDist + fromExit;
    const gross = fromSalary + ownership;

    return {
      gross,
      net: gross - opportunity,
      labour: fromSalary - opportunity,
      ownership,
      fromSalary,
      fromDistributions: fromDist,
      fromExit,
      yearsActive,
      yearsToMillion,
      equityZero: founderGross <= 0,
      died,
      // Two different endings wear the word "failed", and they are not
      // comparable: `abandoned` is a founder walking away from a small business
      // they usually still sell, `died && !abandoned` is a company burning
      // through its capital and leaving the founder nothing.
      abandoned,
      exited,
      maxStage: stage,
      firstStage,
      raised,
      exitValue,
      exitYear,
      founderPct: founderAtExit,
      finalArr,
    };
  }

  // -- a cohort -------------------------------------------------------------

  function drawFounder(rng, cfg, horizon) {
    const lc = cfg.latents;
    const lat = {
      market: Math.exp(Math.log(lc.market_median) + lc.market_sigma * rng.normal()),
      fit: rng.beta(lc.fit_a, lc.fit_b),
      skill: rng.beta(lc.skill_a, lc.skill_b),
    };
    const noise = {
      exec: [], gateArr: [], gateGrowth: [], price: [],
      offer: [], exitMult: [], acquihire: [], secondary: [],
    };
    for (let t = 0; t < horizon; t++) {
      noise.exec.push(rng.normal());
      noise.gateArr.push(rng.normal());
      noise.gateGrowth.push(rng.normal());
      noise.price.push(rng.normal());
      noise.exitMult.push(rng.normal());
      noise.offer.push(rng.uniform());
      noise.acquihire.push(rng.uniform());
      noise.secondary.push(rng.uniform());
    }
    return { lat, noise };
  }

  /* Run every strategy over the same founders.
   *
   * The draws happen once per founder and every arm reads them, so the arms are
   * paired by construction: same market, same fit, same skill, same luck in the
   * same year, forked only at the capital decision.
   */
  function simulate(cfg, opts) {
    const options = opts || {};
    const nFounders = options.nFounders || 2000;
    const seed = options.seed === undefined ? 20260803 : options.seed;
    const strategies = options.strategies || STRATEGIES;
    const horizon = cfg.exit.horizon_years;

    const rng = makeRng(hashSeed(String(seed)));
    const arms = {};
    for (const s of strategies) arms[s.name] = { strategy: s, rows: [] };
    const quality = new Array(nFounders);
    const markets = new Array(nFounders);

    for (let i = 0; i < nFounders; i++) {
      const { lat, noise } = drawFounder(rng, cfg, horizon);
      quality[i] = lat.fit * lat.skill;
      markets[i] = lat.market;
      for (const s of strategies) arms[s.name].rows.push(runArm(cfg, lat, noise, s));
    }
    return { arms, quality, markets, nFounders, config: cfg };
  }

  // -- statistics -----------------------------------------------------------

  function percentile(sorted, p) {
    if (!sorted.length) return 0;
    const idx = (p / 100) * (sorted.length - 1);
    const lo = Math.floor(idx), hi = Math.ceil(idx);
    if (lo === hi) return sorted[lo];
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
  }

  const sortedOf = (rows, key) => rows.map((r) => r[key]).sort((a, b) => a - b);
  const median = (rows, key) => percentile(sortedOf(rows, key), 50);
  const share = (rows, pred) => rows.reduce((a, r) => a + (pred(r) ? 1 : 0), 0) / rows.length;

  const BANDS = [
    { name: "worse than a job", lo: -Infinity, hi: 0 },
    { name: "$0 - $1M", lo: 0, hi: 1e6 },
    { name: "$1M - $10M", lo: 1e6, hi: 10e6 },
    { name: "$10M - $100M", lo: 10e6, hi: 100e6 },
    { name: "over $100M", lo: 100e6, hi: Infinity },
  ];

  function summarise(result, baselineName) {
    const out = {};
    const base = result.arms[baselineName] ? result.arms[baselineName].rows : null;

    for (const [name, arm] of Object.entries(result.arms)) {
      const rows = arm.rows;
      const net = sortedOf(rows, "net");
      const own = sortedOf(rows, "ownership");

      const stats = {
        label: arm.strategy.label,
        netMedian: percentile(net, 50),
        netP10: percentile(net, 10),
        netP90: percentile(net, 90),
        netP99: percentile(net, 99),
        ownMedian: percentile(own, 50),
        ownP90: percentile(own, 90),
        labourMedian: median(rows, "labour"),
        pEquityZero: share(rows, (r) => r.equityZero),
        pDied: share(rows, (r) => r.died),
        pGaveUp: share(rows, (r) => r.abandoned),
        pRanDry: share(rows, (r) => r.died && !r.abandoned),
        pFailedWithNothing: share(rows, (r) => r.died && r.equityZero),
        pEverRaised: share(rows, (r) => r.firstStage >= 0),
        medianFounderPct: median(rows, "founderPct"),
        medianFailYear: (() => {
          const yrs = rows.filter((r) => r.died).map((r) => r.exitYear + 1).sort((a2, b2) => a2 - b2);
          return yrs.length ? percentile(yrs, 50) : 0;
        })(),
        medianFailValue: (() => {
          const v = rows.filter((r) => r.died).map((r) => r.exitValue).sort((a2, b2) => a2 - b2);
          return v.length ? percentile(v, 50) : 0;
        })(),
        pWorseThanJob: share(rows, (r) => r.net < 0),
        pGt1m: share(rows, (r) => r.net > 1e6),
        pGt10m: share(rows, (r) => r.net > 10e6),
        meanRaised: rows.reduce((a, r) => a + r.raised, 0) / rows.length,
        medianExitValue: median(rows, "exitValue"),
        medianFinalArr: median(rows, "finalArr"),
        bands: BANDS.map((b) => share(rows, (r) => r.net >= b.lo && r.net < b.hi)),
      };

      if (base) {
        // Paired within founder: the difference is taken per founder and only
        // then summarised, which is what removes starting-condition luck.
        const dNet = rows.map((r, i) => r.net - base[i].net).sort((a, b) => a - b);
        const dOwn = rows.map((r, i) => r.ownership - base[i].ownership).sort((a, b) => a - b);
        const dLab = rows.map((r, i) => r.labour - base[i].labour).sort((a, b) => a - b);
        stats.gapNet = percentile(dNet, 50);
        stats.gapOwn = percentile(dOwn, 50);
        stats.gapLabour = percentile(dLab, 50);
        stats.pBeatsBaseline = share(rows, (r, i) => false) || 0;
        let wins = 0;
        for (let i = 0; i < rows.length; i++) if (rows[i].net > base[i].net) wins++;
        stats.pBeatsBaseline = wins / rows.length;
      }
      out[name] = stats;
    }
    return out;
  }

  /* Median outcome by percentile of an index (founder quality, market size).
   * "At what percentile of luck does raising overtake bootstrapping?" */
  function crossing(result, index, key, nBins) {
    const bins = nBins || 20;
    const order = index.map((v, i) => i).sort((a, b) => index[a] - index[b]);
    const names = Object.keys(result.arms);
    const rows = [];
    for (let k = 0; k < bins; k++) {
      const from = Math.floor((k * order.length) / bins);
      const to = Math.floor(((k + 1) * order.length) / bins);
      const slice = order.slice(from, to);
      const row = { pctLo: (100 * k) / bins, pctHi: (100 * (k + 1)) / bins };
      for (const n of names) {
        const vals = slice.map((i) => result.arms[n].rows[i][key]).sort((a, b) => a - b);
        row[n] = percentile(vals, 50);
      }
      rows.push(row);
    }
    return rows;
  }

  return {
    STRATEGIES,
    BANDS,
    makeRng,
    hashSeed,
    simulate,
    summarise,
    crossing,
    percentile,
    // exported for the validator and for tests
    enterpriseValue,
    earningsMultiple,
    revenueMultiple,
    founderProceeds,
    solveConversions,
    runArm,
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Engine;
