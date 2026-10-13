# The comparison paragraph: blocked (2026-10-13)

**What was tried.** A paragraph added to the answer prompt telling the agent how to compare two
records, aimed at the weak cross-document questions. **What happened.** It fixed 3 questions and
broke 5, including one where the agent stopped refusing an unanswerable question. Flywheel
blocked it and the original prompt stayed.

Setup: Claude Haiku 4.5, 36 questions, 3 runs each, before ("base", the original prompt) and
after ("head", with the paragraph). `answer_correct` is a model judge comparing the answer to the
reference; `found_the_source` checks the citations include the section holding the answer;
`refused_correctly` checks the agent refused exactly the unanswerable questions. Trace links point
to a private LangSmith workspace.

The report below is Flywheel's pull-request comment, unedited.

---

<!-- flywheel-report -->
## ❌ Flywheel: this change is blocked

Flywheel ran the agent on 36 test cases, 3 times each, before and after this change, and compared the results case by case. Result: 5 cases that passed before now fail; 3 cases that failed before now pass. Blocked because 5 cases broke (at most 0 allowed).

### Broken: passed before, fail now

- `3a7c93af1edd` {"question":"A static site with no logins or user input arguably doesn't need a Content Security Policy, so why does the portfolio ship one?"}
  - `answer_correct` 2/3 → 0/3
  - traces: [run 1](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13488-c97b-7f93-9e14-359be09714ea?poll=true) · [run 2](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348a-11e9-77a2-9a8f-d11b3f646317?poll=true) · [run 3](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348b-6395-7720-a181-e38d9284a6bf?poll=true)
- `9c6d14545f99` {"question":"What is the minimum number of passing tests the incident-response project's CI requires before the job counts as green?"}
  - `answer_correct` 3/3 → 0/3
  - traces: [run 1](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13489-a2e7-7ec1-9200-0c7baba517ee?poll=true) · [run 2](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348a-f69e-7482-95f4-7a1d4c100126?poll=true) · [run 3](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348c-3da4-7063-856e-86a7f2387775?poll=true)
- `db19b9f43540` {"question":"When the ECC plugin was evaluated, why didn't the team swap WorkHorse's own agents out for ECC's?"}
  - `answer_correct` 3/3 → 0/3
  - traces: [run 1](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13488-fada-71c0-9b30-4f34beefc65f?poll=true) · [run 2](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348a-4215-7673-8c1e-ecd0f5543f36?poll=true) · [run 3](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348b-9291-7a30-83a8-2b5c1a8fa9d9?poll=true)
- `f850e62b6f57` {"question":"Which on-call paging service, such as PagerDuty or Opsgenie, sends production alerts into AgentOps?"}
  - `found_the_source` 3/3 → 0/3, `refused_correctly` 3/3 → 0/3
  - traces: [run 1](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13489-502c-76c2-b41e-12a037a11bdb?poll=true) · [run 2](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348a-a6ad-7090-be1b-54a575700896?poll=true) · [run 3](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348b-e768-7942-9032-7f51521b9c56?poll=true)
- `fc977a5e88f6` {"question":"Why did the team cut the number of human approval points down to Design and Ship?"}
  - `answer_correct` 3/3 → 1/3
  - traces: [run 1](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13488-7d46-7893-8ddd-eb38ceaa0e95?poll=true) · [run 2](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13489-c907-7633-b244-7db0878669d7?poll=true) · [run 3](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348b-1c04-7602-b2a7-9dd4b8ab4075?poll=true)

### Fixed: failed before, pass now

- `3e88e0b3cf8a` {"question":"What did the last release of the desktop app change compared with the one before it?"}
  - `answer_correct` 0/3 → 3/3
  - traces: [run 1](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13488-eb50-7942-8dbf-6a7baaa5d179?poll=true) · [run 2](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348a-3dcc-7540-a404-9c72e26c7b14?poll=true) · [run 3](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348b-817d-76d1-b49f-0f614ecbd825?poll=true)
- `7fdd054a3cd3` {"question":"Why won't the question-answering service start without an API key instead of just running unauthenticated?"}
  - `found_the_source` 0/3 → 3/3
  - traces: [run 1](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13489-2e75-7851-aa43-21910e248885?poll=true) · [run 2](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348a-8040-7a32-a44c-85a459657c12?poll=true) · [run 3](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348b-c97c-7c62-ad59-77b8ac3ae6e2?poll=true)
- `825258e4b7a3` {"question":"How did the Gate screen's approve action change between the original desktop app design and the two-gates release?"}
  - `answer_correct` 0/3 → 3/3
  - traces: [run 1](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13488-7d49-7311-9da9-375b4f45dfcf?poll=true) · [run 2](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a13489-e885-7f91-be8d-72a5d018453a?poll=true) · [run 3](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/projects/p/292a9210-651f-47c5-a27c-b6624d293311/r/01a1348b-30ab-7572-9186-8d7a6dd69229?poll=true)

### Totals

| Metric | Before | After |
|---|---|---|
| `answer_correct` | 95/108 | 91/108 |
| `found_the_source` | 99/108 | 99/108 |
| `refused_correctly` | 108/108 | 105/108 |

Sign test over broken and fixed cases: p = 0.727 (the chance of a split at least this uneven if the change did nothing).

<details><summary>Provenance</summary>

- Before: [flywheel-haiku-v1-x3-05f15409](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/datasets/ec0da4ad-119b-447b-969b-099a02b6a9f5/compare?selectedSessions=436b61c6-436c-4fa0-b7bf-21b870acf050) at `56b6986`, langsmith backend, dataset `616da40513be`, 3 repetition(s)
- After: [flywheel-haiku-compare-prompt-x3-c063c133](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/datasets/ec0da4ad-119b-447b-969b-099a02b6a9f5/compare?selectedSessions=292a9210-651f-47c5-a27c-b6624d293311) at `56b6986`, langsmith backend, dataset `616da40513be`, 3 repetition(s)
- [Compare both experiments side by side in LangSmith](https://smith.langchain.com/o/aab54c19-84ad-4e02-a731-05b0917acc96/datasets/ec0da4ad-119b-447b-969b-099a02b6a9f5/compare?selectedSessions=436b61c6-436c-4fa0-b7bf-21b870acf050,292a9210-651f-47c5-a27c-b6624d293311)

</details>
