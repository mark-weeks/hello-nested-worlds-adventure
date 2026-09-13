# Discovery and return pilot protocol

**Status:** Ready to run after a separately authorized staging installation and
cohort recruitment. No participant research has been conducted by this batch.

Use the unranked signal situation. Choose a bounded cohort and a seven-day
observation window before invitations. Explain voluntary observation and use
pseudonymous participant IDs in the research file. Keep invite credentials,
private journal contents and real-world identifying details out of it. Store
research outside the repository and world database with an explicit owner and
retention/deletion date; journal access is not research consent.

Observe the first session with minimal prompting. Ask the person what they think
is happening and what each route would change after they have explored. Do not
supply the answer and then count the repeated answer as understanding. Record
concrete observations separately from interpretation.

| Field | Evidence required for true | Denominator |
|---|---|---|
| `curiosity` | Person pursues or articulates a question beyond the first presented instruction. | Participants with an observed first session. |
| `understood_choice` | Person explains a benefit and cost of each route in their own words. | Participants asked after exploring both clues. |
| `unprompted_return` | A second visit within the fixed window, with `reminded: false` and a reason the person supplied. | Participants whose whole return window was observed. |
| `useful_return` | On return, the person recognizes a relevant change and identifies or performs something they want to do next. | Participants with an observed return session. |

Use false for an observed negative and null/missing for unknown. A visit after a
research reminder is not an unprompted return. A returning visitor with no
observed return interview has unknown useful-return evidence. Report each
numerator/denominator and missing count; do not merge sessions or participants.
“Active on two days” remains an operational count, not this product success test.

Create a local JSON list, one row per participant:

```json
[{"participant":"P01","curiosity":null,"understood_choice":null,
  "unprompted_return":null,"reminded":null,"useful_return":null}]
```

Run `python scripts/pilot_report.py /absolute/path/to/observations.json`. The report
reads only that file and emits aggregate counts; it never reads notes, adds world
events or invents missing observations. Context/evidence notes can be held in a
separate restricted research record. These counts cannot establish causation.

Use the roadmap's precommitted pilot gates as decision hypotheses: test curiosity,
comprehension, at least half returning unprompted within seven days, and a useful
return. Inspect failures before adding systems. Specifically test the 60-second
window, legitimate opposing goals, meaningful late arrival, whether the reference
marker helps anyone, and whether a 40-second promise gives any reason to return
after the first session. A fair-ranking experiment and a public client-default
change require their own acceptance evidence.
