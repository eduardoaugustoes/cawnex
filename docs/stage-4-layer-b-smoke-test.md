# Stage 4 Layer B — Smoke Test Procedure

Runbook for verifying Layer B end-to-end against a dev deployment. Layer B is
"shippable" only after every step here passes.

## Prerequisites

- `cdk deploy -c stage=dev --require-approval never` completed for both
  Layer A and Layer B (this changeset)
- iOS dev build installed on a phone or Simulator, pointing at the dev API
- A dev project with at least one completed wave in `under_human_review`
  (run the Layer A smoke test runbook to produce one)
- Xcode-side wiring complete: every new Swift file in
  `apps/ios/Cawnex/Cawnex/Features/WaveReview/` and the three fixture JSONs
  in `CawnexTests/Contracts/Fixtures/` are added to the appropriate target
  membership (Cawnex for the WaveReview/ sources, CawnexTests for the
  fixtures + decoding tests, CawnexUITests for `WaveReviewUITests.swift`).

## Step 1 — Confirm live banner fires

Open the iOS app, navigate to the Wave Execution screen for the project.

Expected: a `Council voted approve — review now` banner appears within ~5s of
the Layer A Council Fargate writing the `status=completed` row.
(`WaveExecutionViewModel.pendingCouncilBanner` is set by the SSE handler.)

## Step 2 — Tap the banner

Expected: pushes Wave Review screen. All 6 advisor cards render with name,
vote chip, reasoning, and (where present) cited evidence rows.

## Step 3 — Verify decision card metrics

Council Decision card shows action (Approve/etc), confidence, advisor count
(6), tool call total, veto count (0 in happy path), and token count.

## Step 4 — Drill into each advisor

Tap "View investigation" on each of the 6 advisor cards.

Expected: Investigation Trace screen pushes; advisor header shows correct
name + vote chip + stats; tool-call rows render with index, tool name chip,
args key-value rows, result summary, duration.

## Step 5 — Approve flow

Back to Wave Review. Tap "Approve & merge wave". Confirmation sheet
appears with "Approve & Merge" CTA. Tap.

Expected within ~10s:

- Wave row in DDB transitions `under_human_review → delivered`
- Both PRs on GitHub get merged (or the partial-merge error appears
  if a PR can't be merged)
- iOS navigates back to the previous screen

Verify with:

```bash
aws dynamodb get-item --table-name cawnex-dev \
  --key '{"PK":{"S":"T#<tenant>#P#<projectId>"},"SK":{"S":"S#<waveId>"}}' \
  --query 'Item.status.S'
```

Expected: `"delivered"`.

## Step 6 — Reject flow (on a second wave)

Repeat with a synthetic wave that should be rejected. Tap "Reject", enter a
reason ("scope creep"), confirm.

Expected: wave transitions to `cancelled`, reason recorded in wave metadata.

## Step 7 — Verify accessibility identifiers

Run the UI test target locally against the dev build:

```bash
xcodebuild test \
  -project apps/ios/Cawnex/Cawnex.xcodeproj \
  -scheme CawnexUITests \
  -destination 'platform=iOS Simulator,name=iPhone 15'
```

Expected: `WaveReviewUITests` passes.

## Step 8 — Mark Layer B done

If steps 1-7 all passed:

```bash
git commit --allow-empty -m "chore(stage-4): Layer B smoke test passed on dev"
git tag stage-4-layer-b-ga
```

If any step failed, do NOT tag. Open issues and iterate.
