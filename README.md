# Role-fit case assessments

Structured scenario assessments for evaluating whether a candidate can do a
specific role. Each assessment puts the candidate in a realistic situation,
gives them incomplete information and a real constraint, changes the facts
halfway through, and asks them to produce the artifact the job actually
produces.

Scored by humans against anchored rubrics. No automated pass/fail.

## What's here

```
assessments/
  customer-success-csm.json    CSM, mid-level, 45 min
  gtm-lead.json                GTM lead, senior, 50 min
docs/
  design-principles.md         Why they're built this way, plus legal constraints
  writing-a-new-assessment.md  How to add a role (~4-6 hours each)
```

Each assessment is a single JSON file holding both the candidate-facing content
and the reviewer-facing scoring guidance.

## The structure

Every assessment runs the same four stages:

1. **Diagnose** — a pile of mixed signals, one of which is buried and binding
2. **Allocate** — a fixed budget of time or money against a costed menu
3. **Curveball** — new information that invalidates the obvious plan
4. **Artifact** — write the actual email, memo, or plan

Stages 1-2 test analysis. Stage 3 is the most predictive and the one most
assessments skip: it tests whether someone updates or defends. Stage 4 is the
only stage that is a work sample rather than a description of work.

## Running one

1. Send the candidate the stages in order. Do not reveal stage 3 before stage 2
   is submitted — the curveball only works if the earlier commitment was real.
2. Two reviewers score independently and blind, 1-4 per competency against the
   anchors in `facilitator_only.rubric`.
3. Reconcile any gap of 2+ levels in conversation.
4. Apply the bar in `scoring_summary`. Score the profile, not the total.

Everything under `facilitator_only` must be stripped before the file reaches a
candidate. It contains the buried signals and the answer key.

## Data format

```jsonc
{
  "id": "...",
  "role": "...",
  "competencies": [ { "id", "name", "definition" } ],
  "context": { "company", "company_description", "candidate_role", "situation" },
  "stages": [
    {
      "id": "...",
      "order": 1,
      "time_minutes": 12,
      "brief": "...",
      "materials": { "title", "facts": [ { "label", "value" } ] },
      "tasks": [ { "id", "type", "prompt", "word_limit" } ],
      "facilitator_only": {
        "what_this_tests": ["competency_id"],
        "rubric": { "1": "...", "2": "...", "3": "...", "4": "..." }
      }
    }
  ],
  "scoring_summary": { "method", "bar", "note" }
}
```

Task types in use: `ranked_text`, `short_text`, `long_text`,
`ordered_selection` (with `budget_hours`), `budget_allocation` (with `budget`).

Content is data rather than prose so the same renderer can present any
assessment in the series, and so rubrics stay attached to the stage they score.

## Before using these for real hiring

Read `docs/design-principles.md` — the section on legal and validity
constraints is not optional. In short: same scenario and rubric for every
candidate at a level, keep the records, track adverse impact once you have
volume, and check current obligations in your jurisdictions (NYC Local Law 144,
Illinois, Maryland, EU AI Act) before adding any automated scoring.

Calibrate each assessment against 2-3 current strong performers before running a
real candidate through it. An uncalibrated assessment is an opinion with a
rubric attached.
