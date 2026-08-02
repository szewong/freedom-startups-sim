# Method

Rules these simulations follow. Most were learned by breaking them first — the
incentive-evolution sim retracted a headline claim, an entire mechanism, and two
individual effects before it was closed. Each rule below cites the mistake that
produced it.

---

## 1. A mean curve is not a finding until you look at its spread

The incentive-evolution paper reported that one league improved faster than the
other for its first hundred seasons, complete with a mechanism. The mean curve
traced that shape clearly across 16 replicates.

The per-replicate spread was 0.184 against a mean of 0.042. Not significant at
any season. **Withdrawn.**

Early trajectories are roughly three times noisier than converged ones, so a mean
over replicates traces shapes that no individual run shares. Compute the interval
before believing the picture — especially when the picture is one you were hoping
to see.

## 2. Run a null control, and report effects against it, not against zero

A confidence interval excluding zero only establishes that two populations ended
up different. It does not establish that the *treatment* caused it: identically
treated populations also drift apart, and some traits drift a great deal.

Run the identical machinery with the treatment removed, then test each effect
against that distribution. In the incentive sim this withdrew two effects
(tempo, risk capacity) whose intervals comfortably excluded zero.

## 3. A mechanism whose only function is to hurt will always be found to hurt

Twice a mechanism was built where the modelled quantity had no upside — a
"signal" that did nothing but earn reward, and later a capital variable with no
survival benefit. Both produced exactly the predicted damage, and both were
worthless as evidence.

If you are testing whether X is harmful, X must be able to help, and that help
must be a swept parameter rather than an assumption. Otherwise the conclusion was
written into the setup.

## 4. Calibrate first, freeze, then run the counterfactual

Fit the model to known aggregate facts about the world it claims to describe.
Freeze the parameters. *Then* ask the question.

Any parameter touched after seeing a counterfactual result is a p-hacking
exposure and must be recorded as one. The temptation is strongest when an effect
is nearly visible — which is exactly when tuning is least defensible.

## 5. Start identical

Where a comparison is the point, the arms must begin byte-identical, not merely
same-distribution, and be paired when analysed. Difference *within* a replicate
before aggregating; that removes starting-condition luck entirely rather than
hoping it averages out.

## 6. Make the engine blind to the thing being tested

The incentive sim's match engine cannot see the reward threshold, and a test
tokenises its source and fails if the executable code references one. Comments
may discuss the design; the code may not act on it.

Without that guarantee, any divergence is an artefact you built rather than a
result you found — and you will not be able to tell the difference afterwards.

## 7. Two implementations disagree usefully

The browser port of the incentive engine caught three defects the Python had
carried for hours: a non-transitive sort comparator, correlated random streams
between the two arms, and a pace-contaminated metric. Converged statistics stayed
inside tolerance through all of them.

Cross-check where you can, check *trajectories* and not only endpoints, and treat
disagreement as information rather than nuisance.

## 8. Ask the question that has an answer

"Which league is better" turned out to be ill-posed: every candidate yardstick
was one league's home rule, and a direct match between them is zero-sum and
symmetric by construction. The answerable replacement was a curve — performance
across *every* threshold, measured against a common third party. The location
where it crossed was the result.

When a comparison resists a single number, the resistance is usually telling you
the question is wrong.

## 9. Effects are usually monotone in the parameter you chose

If the effect grows with a knob, you can pick the knob setting that makes any
claim look as strong as you like. Report the **sweep**; any single setting is an
illustration, and should be labelled as one.

## 10. Publish the retractions

Every withdrawn claim in this work is still in the papers, with the reason it
fell. A result that survived that treatment is worth more than one that was never
examined, and a reader has no way to know which they are holding unless you say.

---

## Reporting checklist

- [ ] Effect measured against a null control, not against zero
- [ ] Interval computed on **paired** per-replicate differences
- [ ] The swept parameter reported as a curve, not a chosen point
- [ ] Any mechanism claimed harmful given a real, swept upside
- [ ] Parameters frozen before the counterfactual ran; exceptions noted
- [ ] Distributions reported, not means alone, wherever outcomes are skewed
- [ ] Retractions kept in the document
