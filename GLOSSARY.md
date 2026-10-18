# Cash-discipline video checking

Checking short cashier-desk videos for violations of cash-handling rules, and measuring that
check against the organizers' labelled dataset.

## Dataset

**Clip**:
One organizer file together with its organizer label (e.g. `X-47`).
_Avoid_: file, sample

**Video**:
One unique piece of footage, identified by its SHA-256. Duplicate clips share one video.
_Avoid_: clip (when the footage is meant)

**Clip ID**:
The name of one organizer file, written `X-<n>` with a Latin X (e.g. `X-47`).
_Avoid_: file name, video name, Cyrillic `Х-<n>`

**Organizer label**:
The official verdict and timecodes the organizers gave for one clip. The only ground truth for
verdicts and organizer timecodes.
_Avoid_: GT row, official annotation

**Human annotation**:
The team's own reading of a clip: event times, violation type, cited norm, confidence and review
status. An interpretation, never ground truth; where it disagrees with the organizer label, the
disagreement is reviewed, not resolved automatically.
_Avoid_: ground truth, label

**Duplicate**:
A clip whose file is byte-identical to another clip's file (e.g. `X-47` and `X-4`). Each keeps
its own organizer label.
_Avoid_: copy, repeat

**Group**:
Clips that must land on the same side of the split: duplicates, plus a staged violation clip and
its matched clean counterpart.
_Avoid_: pair, cluster

**Dev split**:
The clips used for every development choice.

**Lockbox split**:
The clips held back for one final, human-gated scoring run. Never used for any choice.
_Avoid_: test set, holdout

## Violations

**Event**:
One labelled occurrence of a violation at a point in time in a clip, from an organizer label or a
human annotation.
_Avoid_: incident, finding (for labelled occurrences)

**Finding**:
One occurrence of a violation that the service detected; what gets compared against events.
_Avoid_: event, detection, prediction (in prose)

**Violation type**:
A kind of violation, e.g. cash left unattended while the cashier is away.
_Avoid_: mechanism, mechanism class, category

**Rule**:
Our machine-checkable definition of one visible breach: an ID such as `L-NO-CASH-ON-LEAVE`, an
observable condition, parameters, and the norms it cites. Each rule reports one violation type.
_Avoid_: check, detector

**Act**:
A Kazakhstan legal act (e.g. NBRK resolution № 231) whose clauses can be cited. Only acts in force
count.
_Avoid_: law, document (alone)

**Norm**:
One clause of an act, e.g. `231-20-2`, quoted verbatim and cited as the basis for a rule.
_Avoid_: law, regulation, code (alone)

**Requirement**:
What a norm obliges the cashier to do or not do, in plain words.
_Avoid_: rule (for the legal side)

**Visible breach**:
What an overhead camera would show if a requirement were not met, together with what it cannot show.
_Avoid_: trigger, symptom

**Rulebook**:
The one record of acts, norms, requirements, visible breaches and rules, from which everything the
service reports about the law is generated.
_Avoid_: codex, rule table, workbook

**Legal-citation match**:
Whether a finding cites the same clause as the human annotation's first norm. Says nothing about
whether the violation type is right.
_Avoid_: mechanism score, mechanism accuracy
