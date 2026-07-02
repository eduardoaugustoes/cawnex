#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { CawnexStack } from "../lib/cawnex-stack";

const app = new cdk.App();

const stage =
  (app.node.tryGetContext("stage") as "dev" | "staging" | "prod") ?? "dev";
const stack = app.node.tryGetContext("stack") as string | undefined;

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
};

// Main production stack — always instantiated unless a specific POC is requested
if (!stack || stack === "main") {
  new CawnexStack(app, `Cawnex-${stage}`, { stage, env });
}

// POC stacks — only instantiated on explicit request: -c stack=pocN
// These reference assets that may not exist locally.
// Import lazily to avoid TS errors when files are moved.
if (stack === "poc1") {
  const { Poc1CrowStack } = require("../lib/poc/poc1-crow-stack");
  new Poc1CrowStack(app, `CawnexPoc1-${stage}`, { stage, env });
}

if (stack === "poc3") {
  const { Poc3MurderStack } = require("../lib/poc/poc3-murder-stack");
  new Poc3MurderStack(app, `CawnexPoc3-${stage}`, { stage, env });
}

if (stack === "poc5") {
  const { Poc5AsyncStack } = require("../lib/poc/poc5-async-stack");
  new Poc5AsyncStack(app, `CawnexPoc5-${stage}`, { stage, env });
}

if (stack === "poc6") {
  const { Poc6WorkerStack } = require("../lib/poc/poc6-worker-stack");
  new Poc6WorkerStack(app, `CawnexPoc6-${stage}`, { stage, env });
}
