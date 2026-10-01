# Agent mode: a simulated operator

Use this when the user asks to run seed-me with an agent standing in for the human — to test the
skill, to dogfood it at scale, or to produce a proposal when no person is available. It answers
"how does seed-me behave?", not "what would a person decide?".

## The safety rule

A simulated operator's answers are **never** recorded as the user's. They carry
`authority: simulated`, the session is `operator: simulated`, and the result cannot be confirmed
by the operator agent. A person must read it and confirm it before anything is built from it.
The scripts enforce this: a simulated session cannot hold `user` or `delegated` answers, and a
human session cannot hold `simulated` ones.

## Starting

- Full path: `python3 "<skill>/scripts/session.py" init --operator simulated`. The viewer then shows
  a "Simulated operator — no human decided this" banner and a "Simulated" pill. Start the viewer
  as usual; in a sandbox with no loopback or background processes, complete with
  `end ... --no-viewer "<why>"` instead, and say so in the report.
- Lean path: put `operator: simulated` in the file header and tag operator answers `[simulated]`.

## The operator agent

Run it in a separate agent context (any harness: a subagent, another session). It gets only:

- a **persona brief** (below), and
- the interviewer's messages exactly as a person would see them: the working draft, the question
  turns, the seed contract. Nothing else.

It **must not see**: this skill, the ledger file, the interviewer's tool output or notes, or any
file paths beyond what a question turn quotes. Anything it "knows" beyond the brief and the
messages is leakage, so treat a run that shows it as invalid.

### Operator brief (template)

```text
You are playing a person who is being interviewed about an idea. Stay in role; answer in the first
person, briefly, the way this person would.
Who you are: <role, context>
What you want: <the idea, in the person's own rough words>
What you know and don't know: <facts you can state; things you would have to guess>
Decision style: <for example: "you accept the assistant's suggestion about 1 time in 3, otherwise you
  say what you would do instead; you dislike jargon; you give one-line answers">
You may say: "show me", "your arrow", "skip", "stop". You may not read files, run tools, or
invent things you would not know. If a question is unclear, say so.
```

**Large briefs.** A brief too big to paste (an engram is about 25K characters) may be written to a file that the
operator is told it may read: that one file and nothing else. Say so in the operator's instructions, note it in the
run, and treat any other tool use as leakage.

**The operator decides; it does not build.** Operators, especially engram ones, drift toward implementation ("build
the script and show me the table"). The interviewer answers that building comes after the interview, which produces
the contract it would be built from, and steers back to the next question.

Vary the decision style across runs. An operator that always accepts the suggestion measures
nothing.

## Using an engram as the operator

An engram is a folder of persona files for a person, such as `~/.tink-library/skills/engrams/paul-graham/`.
Build the operator brief from it with the helper instead of pasting files by hand:

```sh
python3 "<skill>/scripts/engram_brief.py" paul-graham --idea "<the rough idea>"
python3 "<skill>/scripts/engram_brief.py" paul-graham --check   # completeness and size only
```

The helper hands the operator the engram's `PERSON`, `MIND`, `CONSTITUTION`, `STAKES`, and `FIDELITY` files as
data and leaves out the engram's `SKILL.md`, whose workflow (research with tools, ask other personas) conflicts
with the no-tools rule. It refuses an engram missing `MIND.md` or `CONSTITUTION.md`, any symlinked file, and one
over the size cap (raise `--max-chars` on purpose). It never writes.

Rules for an engram operator, on top of the ones above:
- The persona is a **simulation of a person's public record, not the person.** Record the persona as
  `engram: <name> (simulation, not the person)` in `authority_source`, never as the person's own words, and
  never quote it as something the real person said.
- The operator cannot research. The interviewer supplies facts, and the operator may say "I'd need to know X."
- The operator answers about *someone else's idea*. Its answers show how this mind would push on the idea; they
  are not that person's endorsement and not the idea owner's decisions.
- Report which engram was used at the top of the simulated seed contract.

## Lessons from the first engram runs (rules)
- **Defer what only a person knows.** If the deciding fact is something only the human owner has (what their notes
  contain, whether they need an old file), the operator must hand it back instead of guessing. Record it as a
  `deferred` item owned by "the human owner", with a `revisit_condition` that names the moment it must be answered.
  A simulated session can end with such an item open; it never fabricates the answer.
- **Do not hand personal file names to the operator.** Give types, sizes, counts, and dates. It can decide from those.
- **Check the operator's provenance claims.** If it calls something "documented", look for it in its persona
  material; record an unsupported label as an inference, not as a documented position.
- **Do not take its arithmetic or its "done" claims.** Operator summaries have miscounted and have described a
  decision as an action already taken. Recompute every figure in code and keep "decided" apart from "done".
- **A teach-back from an agent that can see the contract is weak evidence.** Record it as such, and note any real
  mismatch it finds; a human's own-words teach-back is still owed before adoption.
- **Ask open probes first.** Put the pre-mortem and counter-example to the operator before revealing any finding.

## The interviewer

- Record each operator reply as `authority: simulated`, with `authority_source` quoting the reply
  and naming the persona ("operator agent, persona: cautious: 'only to the Trash'"). Never `user`,
  never `delegated`.
- Follow the same question format and rules as with a person, including instinct first for
  hard-to-undo questions.
- Save the result as `seed-contract.simulated.md`, never `seed-contract.md`, with the status
  `simulated — not confirmed by a human`. The operator's "confirm" is recorded as a simulated
  answer, not as confirmation, and never authorizes implementation.
- To adopt a simulated contract, a person reads it and starts a normal session or lean file
  with their own confirmation. The simulated session's operator cannot be changed afterwards.

## Limits

Simulated operators are more cooperative and consistent than people. Report what the run showed
about the skill (turns, question quality, where the operator was confused, what the validator
refused), and do not report usability findings or product decisions as if a human made them.
