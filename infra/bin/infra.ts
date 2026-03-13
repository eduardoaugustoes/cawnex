#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { CawnexStack } from "../lib/cawnex-stack";
import { Poc1CrowStack } from "../lib/poc1-crow-stack";

const app = new cdk.App();

const stage = (app.node.tryGetContext("stage") as "dev" | "staging" | "prod") ?? "dev";

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
};

// Production stack (not deployed yet)
new CawnexStack(app, `Cawnex-${stage}`, { stage, env });

// POC 1 — MCP Crow on Lambda
new Poc1CrowStack(app, `CawnexPoc1-${stage}`, { stage, env });
