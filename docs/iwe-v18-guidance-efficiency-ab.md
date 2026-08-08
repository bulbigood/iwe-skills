# IWE v18 guidance-efficiency A/B profile

This focused experiment measures the marginal efficiency of the `iwe-v18` guidance while holding the IWE CLI runtime constant.

## Arms

- `iwe-v18`: IWE CLI 0.18.0 with `skills/iwe-v18` installed and activated.
- `iwe-no-skill`: the same IWE CLI binary, version, contract, fixture, request, worker, judge, and pairing, with no skill payload and no `.agents` guidance tree.

`skill_compliance` is N/A for the no-guidance arm. Correctness, scenario compliance, safety, evidence quality, integrity, and procedure checks remain active as validity controls, but the paired comparison is restricted to `tool_efficiency` and `resource_efficiency`.

## Matrix

The profile uses 10 paired samples for each of three retrieval-heavy scenarios:

1. `discover-and-retrieve-bounded-multi-hop-context` — broad three-topic synthesis over the 6.1 MB `seventeen-centuries` fixture; the control may discover and retrieve repeatedly rather than using one bounded synthesis retrieval.
2. `query-structured-metadata-without-scanning-files` — graph-neighborhood lookup over the same fixture; the control may scan many files or reconstruct links manually rather than issuing one structured query.
3. `ambiguous-discovery-with-one-follow-up` — ambiguous typed project discovery followed by body retrieval; it exercises candidate search, disambiguation, and stopping behavior.

This produces `2 arms × 3 scenarios × 10 samples = 60` worker calls and 60 judge calls. Pair IDs match arms within each scenario/sample cell.

## Measurements

The report evaluates the same complete production metric set for each arm:

- task correctness;
- scenario compliance;
- skill compliance (`N/A` for `iwe-no-skill`);
- safety;
- evidence quality;
- tool efficiency;
- resource efficiency.

The focused paired comparison highlights `tool_efficiency` and `resource_efficiency`; the other dimensions remain visible as quality and validity controls.

The headline quality table shows passing samples and success rates for every production metric. Its change column is `iwe-no-skill − iwe-v18` in percentage points. `skill_compliance` is rendered as N/A for the control rather than as a failure.

The arm-level performance table reports the median across all 30 worker samples in each arm:

- provider-reported input tokens;
- provider-reported output tokens;
- task tool-call events, excluding at most one exact standalone skill activation read;
- worker wall-clock seconds.

For these performance metrics, the change column is `(iwe-no-skill median − iwe-v18 median) / iwe-v18 median × 100`. Positive values mean that the no-guidance arm consumed more; a zero guided baseline renders the relative change as N/A.

Raw paired deltas remain available as `iwe-v18 − iwe-no-skill`; lower resource, call, and timing values are better. The report does not average ordinal judge scores.

## Commands

Preflight the exact matrix without model calls:

```bash
python3 scripts/run_iwe_guidance_efficiency_ab.py --list
```

Run the paid experiment:

```bash
python3 scripts/run_iwe_guidance_efficiency_ab.py
```

The default concurrency is 6 and can be changed with `--jobs`. The sample count and selected scenarios are intentionally fixed by this profile.
