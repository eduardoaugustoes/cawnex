#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { CawnexStack } from "../lib/cawnex-stack";

const app = new cdk.App();

const stage = (app.node.tryGetContext("stage") as "dev" | "staging" | "prod") ?? "dev";

new CawnexStack(app, `Cawnex-${stage}`, {
  stage,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
  },
});
