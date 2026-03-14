import * as cdk from "aws-cdk-lib";
import * as ses from "aws-cdk-lib/aws-ses";
import { Construct } from "constructs";

interface CawnexDomainCloudflareStackProps extends cdk.StackProps {
  domainName: string;
  stage: "dev" | "staging" | "prod";
}

export class CawnexDomainCloudflareStack extends cdk.Stack {
  /** SES Domain Identity for email sending */
  public readonly sesIdentity: ses.EmailIdentity;

  constructor(
    scope: Construct,
    id: string,
    props: CawnexDomainCloudflareStackProps
  ) {
    super(scope, id, props);

    const { domainName, stage } = props;

    // ─────────────────────────────────────────────
    // SES Domain Identity — Custom Email Sending
    // (DNS records will be added manually in Cloudflare)
    // ─────────────────────────────────────────────
    this.sesIdentity = new ses.EmailIdentity(this, "SESIdentity", {
      identity: ses.Identity.domain(domainName),
      dkimSigning: true, // Enable DKIM signing
    });

    // ─────────────────────────────────────────────
    // SES Configuration Set (for email tracking)
    // ─────────────────────────────────────────────
    const configSet = new ses.ConfigurationSet(this, "EmailConfigSet", {
      configurationSetName: `cawnex-${stage}`,
      sendingEnabled: true,
    });

    // ─────────────────────────────────────────────
    // Outputs for Manual DNS Configuration
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "DomainName", {
      value: domainName,
      exportName: `CawnexCloudflareStack-${stage}-DomainName`,
      description: "Domain name for Cloudflare DNS setup",
    });

    new cdk.CfnOutput(this, "SESIdentityArn", {
      value: this.sesIdentity.emailIdentityArn,
      exportName: `CawnexCloudflareStack-${stage}-SESIdentityArn`,
      description: "SES Email Identity ARN",
    });

    new cdk.CfnOutput(this, "SESConfigSetName", {
      value: configSet.configurationSetName,
      exportName: `CawnexCloudflareStack-${stage}-SESConfigSetName`,
      description: "SES Configuration Set for email sending",
    });

    // Email sender addresses for reference
    const emailSenders = {
      noreply: `noreply@${domainName}`,
      support: `support@${domainName}`,
      security: `security@${domainName}`,
      admin: `admin@${domainName}`,
    };

    new cdk.CfnOutput(this, "EmailSenders", {
      value: JSON.stringify(emailSenders),
      exportName: `CawnexCloudflareStack-${stage}-EmailSenders`,
      description: "Standard email sender addresses",
    });

    // Instructions for manual DNS setup
    new cdk.CfnOutput(this, "CloudflareDNSInstructions", {
      value:
        "Add these records in Cloudflare: SPF, DMARC, and 3 DKIM CNAME records. Get DKIM tokens from SES console.",
      description: "Manual DNS setup required in Cloudflare",
    });

    new cdk.CfnOutput(this, "SPFRecord", {
      value: "v=spf1 include:amazonses.com ~all",
      description: "Add as TXT record for @ (root domain) in Cloudflare",
    });

    new cdk.CfnOutput(this, "DMARCRecord", {
      value: `v=DMARC1; p=quarantine; fo=1; rua=mailto:dmarc@${domainName}; ruf=mailto:dmarc@${domainName}`,
      description: "Add as TXT record for _dmarc in Cloudflare",
    });
  }
}
