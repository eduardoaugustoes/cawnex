#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { CawnexStack } from "../lib/cawnex-stack";
import { Poc1CrowStack } from "../lib/poc1-crow-stack";
import { Poc3MurderStack } from "../lib/poc3-murder-stack";
import { Poc5AsyncStack } from "../lib/poc5-async-stack";
import { Poc6WorkerStack } from "../lib/poc6-worker-stack";

const app = new cdk.App();

const stage = (app.node.tryGetContext("stage") as "dev" | "staging" | "prod") ?? "dev";
const stack = app.node.tryGetContext("stack") as string | undefined;

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
};

// Only instantiate requested stack (avoids asset validation errors for unbuilt stacks)
if (!stack || stack === "main") {
  new CawnexStack(app, `Cawnex-${stage}`, { stage, env });
}

if (!stack || stack === "poc1") {
  new Poc1CrowStack(app, `CawnexPoc1-${stage}`, { stage, env });
}

if (!stack || stack === "poc3") {
  new Poc3MurderStack(app, `CawnexPoc3-${stage}`, { stage, env });
}

if (!stack || stack === "poc5") {
  new Poc5AsyncStack(app, `CawnexPoc5-${stage}`, { stage, env });
}

if (!stack || stack === "poc6") {
  new Poc6WorkerStack(app, `CawnexPoc6-${stage}`, { stage, env });
}
