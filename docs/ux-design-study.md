# TraceMind UX design study

This is a **self-directed heuristic review**, not a participant study. It documents why the evidence-investigation interface is arranged as it is and one change made after reviewing published usability guidance. It does not establish that users became faster, more accurate, or more trusting.

## User task and design question

The reviewer needs to ask a question, inspect the model's draft, open the cited source, and test whether a hypothesis still has support when an item of evidence is excluded. How can the interface keep those steps visible without letting model and retrieval settings compete with the main task?

## Method

I walked through the existing question-to-source workflow and compared it with Nielsen Norman Group's [usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) and guidance on [progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/). This was a desk-based design review; no interviews, usability sessions, or controlled experiment were conducted.

| Design choice | Rationale | What to check with users later |
| --- | --- | --- |
| Keep the suggested question and primary Investigate action prominent; move model and search controls into an expandable section. | Prioritize the common task and defer optional settings. The closed summary still states the selected model and search mode. | Can a first-time reviewer start an investigation and find settings when needed? |
| Show a busy state while generation runs. | Make system status visible during a potentially long local-model request. | Do reviewers understand that the app is working rather than frozen? |
| Label model output as a draft and show insufficient-evidence status. | Prevent the UI from implying that fluent output or valid citation IDs proves the claim. | Can reviewers distinguish model claims from verified evidence? |
| Put clickable citations next to claims and allow evidence to be excluded and restored. | Support recognition of the source and reversible exploration rather than requiring memory of document IDs. | Can reviewers locate a supporting row or page and undo an exclusion? |

## Change made

The question panel now starts with a short instruction and the primary action. Generator and retrieval controls sit under **Model and search settings**, with the active selections visible in the summary. The options and their defaults are unchanged.

## Limits

Published heuristics explain the design rationale; they do not prove that this particular UI works better. Hiding settings could also make them less discoverable. A next step would be task-based usability sessions with first-time reviewers, recording whether they can find a cited source, change the retrieval mode, and restore excluded evidence. No such results are claimed here.
