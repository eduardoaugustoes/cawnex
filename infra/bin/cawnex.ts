#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { CawnexDomainStack } from "../lib/cawnex-domain-stack";
import { CawnexDomainCloudflareStack } from "../lib/cawnex-domain-cloudflare-stack";
import { CawnexAuthStack } from "../lib/cawnex-auth-stack";
import { CawnexStack } from "../lib/cawnex-stack";

const app = new cdk.App();

// Get stage from context
const stage = (app.node.tryGetContext("stage") || "dev") as "dev" | "staging" | "prod";

// Get domain configuration from context (optional)
const domainName = app.node.tryGetContext("domainName") as string | undefined;
const hostedZoneId = app.node.tryGetContext("hostedZoneId") as string | undefined;
const useCloudflare = app.node.tryGetContext("cloudflare") === "true";

// Environment configuration
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || "us-east-1",
};

// Deploy Domain Stack first (if domain is configured)
let domainStack: CawnexDomainStack | CawnexDomainCloudflareStack | undefined;
if (domainName) {
  if (useCloudflare) {
    // Cloudflare-managed DNS (SES only, no Route53)
    domainStack = new CawnexDomainCloudflareStack(app, `CawnexCloudflareStack-${stage}`, {
      domainName,
      stage,
      env,
      description: `Cawnex Cloudflare Stack (${stage}) - ${domainName}`,
    });
  } else {
    // Full AWS management (Route53 + SES + SSL)
    domainStack = new CawnexDomainStack(app, `CawnexDomainStack-${stage}`, {
      domainName,
      hostedZoneId,
      stage,
      env,
      description: `Cawnex Domain Stack (${stage}) - ${domainName}`,
    });
  }
}

// Deploy Auth Stack second (independent, but may reference domain)
const authStack = new CawnexAuthStack(app, `CawnexAuthStack-${stage}`, {
  stage,
  domainName: domainName,
  sesIdentityArn: domainStack?.sesIdentity?.emailIdentityArn,
  env,
  description: `Cawnex Authentication Stack (${stage})`,
});

// Deploy Main Stack third (depends on Auth Stack)
const mainStack = new CawnexStack(app, `Cawnex-${stage}`, {
  stage,
  env,
  description: `Cawnex Main Stack (${stage})`,
});

// Set up dependencies
if (domainStack) {
  authStack.addDependency(domainStack);
}
mainStack.addDependency(authStack);

// Tags for both stacks
cdk.Tags.of(authStack).add("Project", "Cawnex");
cdk.Tags.of(authStack).add("Stage", stage);
cdk.Tags.of(authStack).add("Stack", "Auth");

cdk.Tags.of(mainStack).add("Project", "Cawnex");
cdk.Tags.of(mainStack).add("Stage", stage);  
cdk.Tags.of(mainStack).add("Stack", "Main");