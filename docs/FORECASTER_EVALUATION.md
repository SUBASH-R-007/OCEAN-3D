# Forecaster evaluation protocol

The Research & methods tab contains a timed task recorder. It opens fixed scientific cases, records a pseudonymous participant code, condition, response, elapsed time and current Ocean3D settings/provenance, then exports JSON. No human evaluation has yet been conducted. Developer practice and automated browser tests are not evidence of improved forecaster performance.

## Run a facilitated comparison

1. Recruit domain practitioners with consent under the institution's normal study procedure. Use codes `P01`–`P9999`; keep any identity mapping outside this application. Do not enter names or contact details in responses. Predeclare participant count, task order, assistance policy and correctness criteria.
2. Use the same pinned source files and questions in Ocean3D and each participant's usual tools. Record the actual build, hardware, browser, network and baseline tool versions. Verify hashes before both conditions. Complete a separate practice task before timing.
3. Counterbalance condition order across participants and rotate task order. Repeating the same data can cause learning effects; report the order and consider equivalent alternate cases established before the study. Do not choose favorable trials retrospectively.
4. Select **Ocean3D** or **Usual workflow**, enter the code, and start the task. Ocean3D opens the specified case; Usual workflow leaves the external tool under facilitator control. Timing includes page loads, navigation and other tabs. Record interruptions; cancel invalid trials and document why outside the exported trial set. Set a predefined time limit, such as ten minutes, and record a timeout as incorrect with the stopping time and explanation.
5. Finish with a response and supporting evidence. Export before reloading/closing the page: trials are held only in page memory. Current Ocean3D provenance is captured at completion; it does not prove what was displayed in an external baseline tool. Retain the facilitator's baseline artifacts separately.
6. A domain assessor scores each answer `0` or `1` according to the criteria below, ideally without seeing the condition. Keep the original unscored export and create an assessor copy. Record assessor, rubric version and disagreements in a separate study log. Never change duration or source evidence to improve results.

## Fixed tasks and assessor rubric

| Task ID | Source case | Correct response requires |
| --- | --- | --- |
| `profile-evidence` | `reference-indian`, Argo `5904729-274-0`, strict QC | 1,001 matched levels; temperature RMSE approximately 0.65527 °C (0.66 °C rounded accepted); separate source times; explains that assimilation independence is unknown and one cast is not general forecast skill |
| `current-interpretation` | `hycom-currents-indian`, initial frame | Two actual available depths and their units; actual model time from the case (7 September 2026, 12:00 UTC); interprets streamlines as frozen-field paths, not time-evolving drift; recognizes missing vertical velocity and that a SAR drift prediction needs more than this visualization |
| `source-meaning` | Fixed `incois-mnt-mccreary-latest` case | Latest retained time 15 July 2026; unspecified source temperature convention; 1° geographic grid and 24 native depths (5–2,000 m); distinguishes display interpolation and vertical exaggeration from resolution and recognizes historical analyses cannot establish a current forecast |

Before using the rubric, the assessor must verify it against the pinned case and independently reproduce numeric answers from the retained files. A changed case requires a versioned rubric and a new study series. Allow supported scientific corrections rather than rewarding memorized interface wording. These tasks evaluate interpretation and navigation; they do not validate operational hazard advisories.

## Analyze exported results

The session schema is `ocean3d-evaluation-session-1`; each trial has `score: null` initially. In an assessor copy, replace it with integer `0` or `1`. Keep `developer-practice` trials labelled; the analyzer always excludes them. It also excludes unscored trials, excludes unmatched condition pairs and rejects duplicate participant/task/condition trials rather than choosing the best one.

```powershell
python -m scripts.analyze_evaluation study/P01-scored.json study/P02-scored.json --output study/paired-summary.json
```

Report the number of participants and paired tasks, correctness by condition, and median within-task time difference (Ocean3D minus usual workflow). Report timeouts, excluded/missing trials, task order and assistance too. Speed must be interpreted alongside correctness. Repeated tasks from one participant are not independent observations; this descriptive analyzer does not calculate significance or assert population benefit. A larger inferential study needs a prespecified participant-level analysis and domain/statistical review.

No fabricated forecaster sessions or claimed usability improvement accompany this implementation. The unit tests use labelled fixtures solely to verify scoring exclusions and arithmetic.
