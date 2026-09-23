---
name: code-review
description: "Review changes since a fixed point (commit, branch, tag, or merge-base) along two independent axes: Standards (adherence to repo standards and code smell heuristics) and Spec (fidelity to originating requirements). Runs both reviews in parallel sub-agents and reports findings side by side. Trigger when the user asks to review a PR, branch, diff, or changes since a ref."
---

Two-axis review of the diff between `HEAD` and a user-supplied fixed point:

- **Standards**: does the code conform to this repo's documented coding standards and baseline code smell heuristics?
- **Spec**: does the code faithfully implement the originating issue or specification?

Both axes run as **parallel sub-agents** to keep contexts isolated, and the skill aggregates their findings side by side.

## Process

### 1. Pin the fixed point

Resolve the user-provided fixed point (a commit SHA, branch name, tag, `main`, `HEAD~5`, etc.). If omitted, prompt the user for it.

Capture the diff and commit list:
- Diff: `git diff <fixed-point>...HEAD` (three-dot comparison against the merge-base)
- Commits: `git log <fixed-point>..HEAD --oneline`

Verify early that the ref resolves (`git rev-parse <fixed-point>`) and the diff is non-empty before spawning sub-agents.

### 2. Identify the spec source

Locate the originating specification in this order:

1. Issue or PR references in commit messages (`#123`, `Closes #45`, `!67`, etc.).
2. A spec path or issue link provided directly by the user.
3. A matching specification file under `docs/`, `specs/`, or `.scratch/` corresponding to the branch or feature name.
4. If no spec is found, ask the user for a spec path or issue reference. If none exists, skip the **Spec** sub-agent and report "no spec available".

### 3. Identify the standards sources

Check for repo-specific documentation on code style and architecture (e.g., `CODING_STANDARDS.md`, `CONTRIBUTING.md`, or architecture guides).

Along with repo-documented rules, the Standards axis incorporates the **smell baseline** below (adapted from Fowler, _Refactoring_, ch. 3). Two principles govern the baseline:

- **Repo standards take precedence**: Documented project standards always override baseline smells when they conflict.
- **Judgement calls**: Smells are heuristics ("possible Feature Envy"), not rigid violations. Omit issues already enforced by linters or compiler checks.

Evaluate the diff against these 12 smells (*description* → *remedy*):

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → Rename it; if a clear name is difficult to find, simplify the design.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → Extract the shared logic and call it from each site.
- **Feature Envy**: a method that reaches into another object's data more than its own. → Move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → Bundle them into a dedicated type and pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → Encapsulate the concept in a dedicated value object or type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → Replace with polymorphism or a shared lookup map.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → Consolidate related behavior into a single module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → Split the module so each piece changes for one single reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → Remove the unneeded abstraction and inline until actual demand emerges.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → Encapsulate the chain behind a method on the root object.
- **Middle Man**: a class or function that mostly just delegates onward. → Bypass or remove the delegate and call the target directly.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → Replace inheritance with composition.

### 4. Spawn both sub-agents in parallel

**Standards sub-agent prompt**:
- Include the diff command and commit list.
- Include repo standards files found, plus the smell baseline pasted in full.
- Brief: "Report, per file/hunk where relevant: (a) violations of documented repo standards (cite file and rule); (b) baseline smells identified (name the smell and cite the hunk). Distinguish hard violations from heuristic judgement calls; repo standards override baseline smells. Skip tooling-enforced checks. Keep response under 400 words."

**Spec sub-agent prompt**:
- Include the diff command and commit list.
- Include the path or contents of the spec.
- Brief: "Report: (a) requirements from the spec that are missing or incomplete; (b) changes in the diff not requested by the spec (scope creep); (c) requirements implemented incorrectly. Cite specific spec references for each finding. Keep response under 400 words."

If no spec is available, omit the Spec sub-agent and record this in the final output.

### 5. Aggregate

Present findings under distinct `## Standards` and `## Spec` headings, preserving raw reports without merging or cross-axis reranking.

End with a summary indicating total findings per axis and the most critical issue within each axis. Do not rank findings across axes.

## Why two axes

Separating axes prevents false conclusions:
- Code conforming to all conventions might implement the wrong feature (**Standards pass, Spec fail**).
- Code faithfully fulfilling every requirement might violate critical architectural standards (**Spec pass, Standards fail**).

Independent reporting ensures neither axis obscures the other.
