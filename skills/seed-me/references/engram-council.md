# Opt-in engram council

Off by default. Use it only when the human asks for it and names the engrams, for example "use the paul-graham and
andrej-karpathy engrams on this". Its purpose: stop the human being the bottleneck on decisions that do not change
what the hunch means, while every decision that does still reaches the human.

## What it is, and what it is not

- Each engram is a **lens**: a disclosed simulation that advises. Its answers are evidence recorded as
  `engram:<name> (simulation, not the person)`, never the person's own words and never a decision.
- The authority for a settled decision is the human's **standing delegation**, given in the opt-in (below).
  The ledger records `authority: delegated` (a human session). Never `simulated`: that is for a simulated operator.
- This is not agent mode. A simulated operator replaces the human and can never confirm. Here the human remains the
  operator, and a human still confirms the final seed contract by affirming the displayed revision label.

## Opt-in

1. The human names the engrams (two or more, so disagreement can show) and states the delegation scope in their own words, for
   example: "Decide anything that does not change what the hunch means. Ask me when a choice changes the problem being
   solved, who it is for, where its boundary sits, or what done means."
2. Record the opt-in and the scope text once in the ledger's first evidence entry. An ambiguous phrase such as
   "whatever you think" still delegates only the node it refers to; only this explicit, recorded scope covers several.
3. No opt-in, no council. Do not infer it from a request to "be faster".

## Running a round

1. Write the ready decisions as a JSON list (`id`, `title`, `options`, `undo`, `grounded`) and run
   `python3 scripts/engram_council.py ask decisions.json --idea "<the hunch in the human's words>"`.
2. Build each engram's brief with `scripts/engram_brief.py`. Run every lens in its own **separate context** with **no tools**
   except reading its brief file and the prompt. A lens that does more is leakage: discard its answers and record why.
3. Save each lens's reply to a file and run `python3 scripts/engram_council.py decide decisions.json --lens name=file ...`.
4. Apply the output:
   - `settle`: record the node settled, `authority: delegated`, `answer` the choice, `evidence` and `authority_source` exactly as
     printed. If `boundary` is true, list it under the contract's decisions to confirm.
   - `surface`: show it to the human as a normal question, with the lenses' choices and dissent beneath the recommendation.
5. `missing` items come from each lens's `MISSING:` line: decisions it says the list left out. Add each as a new decision; never drop one silently.

## The rule the script applies

- A decision that is **hard to undo** or **ungrounded** always surfaces. The human's instinct comes first, and
  ungrounded nodes can never settle by delegation.
- Fewer than two valid lens answers: surface. A malformed line or an invalid choice makes that lens abstain for that
  decision, recorded under `lenses.<name>.abstained`; nothing is skipped without a trace.
- All lenses choose the same option: settle. Lenses diverge and at least one flags that the other option changes the
  hunch's meaning: surface. Lenses diverge and none flags it: settle on a strict plurality, record the dissent, and
  surface on a tie.

## Limits to state to the human

- Engrams are distillations of a public record. Where an engram is silent its answer is a framework inference, and an
  off-domain lens (for example a psychologist on software) is a check on meaning, not on engineering taste.
- Agreement between lenses is evidence, not proof: they may share the same underlying model.
- Whether this filter matches the human's own choices is a measurable question. After a first round, ask the human
  to mark which settled decisions they would have changed, and treat those marks as the calibration.
