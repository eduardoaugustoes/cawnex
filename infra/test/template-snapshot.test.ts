import { Template } from "aws-cdk-lib/assertions";
import { normalizeAssetHashes, synthCawnexStacks } from "./synth-helpers";

/**
 * Full CloudFormation template snapshots for both stacks. These catch any
 * unintended change to the synthesized template — resource additions,
 * removals, property drift — that the fine-grained logical-ID pins in
 * stateful-resources.test.ts don't cover (those only check the stateful
 * resources; this covers everything).
 *
 * Asset content hashes (Lambda zip S3 keys, Docker image tags) are
 * normalized before snapshotting — see normalizeAssetHashes for why they'd
 * otherwise make this suite flaky across machines/CI.
 *
 * When a snapshot fails after an intentional change, review the diff
 * carefully before running `jest -u`: a diff touching a stateful resource's
 * logical ID or a Delete->Retain-style policy change is exactly the signal
 * this suite exists to catch.
 */
describe("CDK template snapshots", () => {
  const { authStack, mainStack } = synthCawnexStacks();

  it("matches the CawnexAuthStack (dev) snapshot", () => {
    const template = Template.fromStack(authStack);
    expect(normalizeAssetHashes(template.toJSON())).toMatchSnapshot();
  });

  it("matches the Cawnex main stack (dev) snapshot", () => {
    const template = Template.fromStack(mainStack);
    expect(normalizeAssetHashes(template.toJSON())).toMatchSnapshot();
  });
});
