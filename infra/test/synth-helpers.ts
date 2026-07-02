import * as fs from "fs";
import * as path from "path";
import * as cdk from "aws-cdk-lib";
import { CawnexAuthStack } from "../lib/cawnex-auth-stack";
import { CawnexStack } from "../lib/cawnex-stack";

export const STAGE = "dev" as const;

const FIXED_ENV = { account: "123456789012", region: "us-east-1" };

/**
 * `CawnexStack` and the auth-post-confirmation Lambda load their code via
 * `lambda.Code.fromAsset(...)`, which requires the asset directory to exist
 * and be non-empty at synth time. `apps/api/dist` is a gitignored build
 * output — present locally after `make build-lambda`, absent otherwise (e.g.
 * a fresh CI checkout). Create a placeholder so synth never depends on
 * running the real Python build. The `lambdas` asset directories already
 * exist in-repo, so they need no placeholder.
 */
function ensureAssetDirExists(relativeDirFromInfra: string): void {
  const dir = path.resolve(__dirname, "..", relativeDirFromInfra);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  if (fs.readdirSync(dir).length === 0) {
    fs.writeFileSync(path.join(dir, "handler.py"), "# placeholder for CDK asset synth in tests\n");
  }
}

/**
 * Synthesizes both stacks the same way `bin/cawnex.ts` wires them for the
 * `dev` stage: auth stack first, main stack second, main depends on auth.
 * No domain stack — `bin/cawnex.ts` only creates one when `domainName` is
 * passed via context, which the default `dev` deploy does not do.
 */
export function synthCawnexStacks(): {
  authStack: CawnexAuthStack;
  mainStack: CawnexStack;
} {
  ensureAssetDirExists("../apps/api/dist");

  const app = new cdk.App();

  const authStack = new CawnexAuthStack(app, `CawnexAuthStack-${STAGE}`, {
    stage: STAGE,
    env: FIXED_ENV,
    description: `Cawnex Authentication Stack (${STAGE})`,
  });

  const mainStack = new CawnexStack(app, `Cawnex-${STAGE}`, {
    stage: STAGE,
    env: FIXED_ENV,
    description: `Cawnex Main Stack (${STAGE})`,
  });

  mainStack.addDependency(authStack);

  return { authStack, mainStack };
}

const ASSET_HASH_PLACEHOLDER = "<content-hash>";

/**
 * CDK derives Lambda `S3Key` zip names and Docker image tags from the
 * content hash of their asset directory (`apps/api/dist`, the murder and
 * monarch lambda source directories, the three Dockerfile build contexts).
 * That hash changes whenever the asset content differs — including
 * harmless differences like a fresh
 * checkout without a local Python build, or an `.egg-info`/`__pycache__`
 * left behind by a different Python version. None of that reflects an
 * infrastructure change, so it must not make the snapshot flaky. Redact
 * both shapes (`<64-hex>.zip` and the `:<64-hex>` docker tag) to a fixed
 * placeholder before snapshotting.
 */
export function normalizeAssetHashes<T>(template: T): T {
  const json = JSON.stringify(template);
  const withZipsRedacted = json.replace(
    /[a-f0-9]{64}\.zip/g,
    `${ASSET_HASH_PLACEHOLDER}.zip`
  );
  const withDockerTagsRedacted = withZipsRedacted.replace(
    /:[a-f0-9]{64}(?=["\\])/g,
    `:${ASSET_HASH_PLACEHOLDER}`
  );
  return JSON.parse(withDockerTagsRedacted) as T;
}
