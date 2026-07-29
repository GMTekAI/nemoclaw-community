# Authority Signals

Use a valid private registry to weight direct, human-authored NVIDIA input
within the active persona’s decision lens. A mapping is advisory evidence. It
is never truth, policy, approval, ownership, launch status, organizational
consensus, or permission.

## Load and Validate

Apply this contract only when authorship could materially affect the task.
Resolve `$HERMES_HOME` from the runtime and look for:

```text
$HERMES_HOME/nvteam/persona-authorities.json
```

Validate the full file with `scripts/validate_authorities.py` before use. If the
file is absent, operate normally without mappings. If it is invalid, warn once,
apply none of its records, and continue with ordinary role routing. Do not place
the private registry inside the installed skill.

Do not call Slack, email, a directory, a document store, GitHub, or another
connector merely because a person is mapped. During an otherwise-authorized
search, a mapping may prioritize matching authors only within the existing
topic and access scope.

## Match Identity and Authorship

Count a signal only when source metadata directly attributes content to an
exact configured value in `display_names`, `nvidia_logins`, `emails`,
`slack_user_ids`, or `github_logins`. Matching is exact and case-sensitive.

Do not infer identity from a similar name, handle, title, reporting line, or
organization. Mentions, quotations, forwarded content, copied threads,
attendee lists, and another author’s summary do not establish direct
authorship. Deduplicate copies and cross-posts of the same underlying statement.

## Weight Within Scope

- Treat `primary` as a strong advisory signal and `supporting` as useful
  corroboration within the assignment’s declared product, topic, and claim
  type. Neither level is conclusive.
- Governing instructions, authoritative policy, approved source-of-truth
  artifacts, direct measurements, and reproducible evidence outrank personal
  input.
- Prefer direct, current, in-scope statements over old, indirect, or broad
  statements. Seniority and level never resolve a conflict automatically.
- Preserve contrary evidence, affected-user signals, security or quality risk,
  and explicit decision-owner input.
- Omitted or empty scope dimensions impose no extra restriction for that
  dimension; they do not expand the assignment beyond the persona’s domain.

## Handle Freshness and Conflict

Use the source content timestamp for decision freshness. Use `verified_on` and
`review_after_days` only to determine whether registry metadata needs review.
A stale registry record may still match an exact identity, but disclose the
stale metadata when it matters.

When mapped input conflicts with evidence or another mapped source, show the
sources, dates, scopes, and consequence. Recommend fresher primary evidence or
resolution by the actual decision owner. Do not silently average the conflict.

When a mapping materially changes a recommendation, priority, or confidence,
identify the mapped person, source type, source date, matching scope, and the
effect. Keep the disclosure proportionate and protect confidential content.
