#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { CawnexAuthStack } from "../lib/cawnex-auth-stack";
import { CawnexStack } from "../lib/cawnex-stack";

const app = new cdk.App();

// Get stage from context
const stage = (app.node.tryGetContext("stage") || "dev") as "dev" | "staging" | "prod";

// Environment configuration
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || "us-east-1",
};

// Deploy Auth Stack first (independent)
const authStack = new CawnexAuthStack(app, `CawnexAuthStack-${stage}`, {
  stage,
  env,
  description: `Cawnex Authentication Stack (${stage})`,
});

// Deploy Main Stack second (depends on Auth Stack)
const mainStack = new CawnexStack(app, `Cawnex-${stage}`, {
  stage,
  env,
  description: `Cawnex Main Stack (${stage})`,
});

// Ensure main stack waits for auth stack
mainStack.addDependency(authStack);

// Tags for both stacks
cdk.Tags.of(authStack).add("Project", "Cawnex");
cdk.Tags.of(authStack).add("Stage", stage);
cdk.Tags.of(authStack).add("Stack", "Auth");

cdk.Tags.of(mainStack).add("Project", "Cawnex");
cdk.Tags.of(mainStack).add("Stage", stage);  
cdk.Tags.of(mainStack).add("Stack", "Main");