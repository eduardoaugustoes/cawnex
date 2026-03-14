import * as cdk from "aws-cdk-lib";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as ses from "aws-cdk-lib/aws-ses";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import { Construct } from "constructs";

interface CawnexDomainStackProps extends cdk.StackProps {
  domainName: string;
  hostedZoneId?: string; // Optional - CDK can create if not provided
  stage: "dev" | "staging" | "prod";
}

export class CawnexDomainStack extends cdk.Stack {
  /** Route53 Hosted Zone for the domain */
  public readonly hostedZone: route53.IHostedZone;
  
  /** SES Domain Identity for email sending */
  public readonly sesIdentity: ses.EmailIdentity;
  
  /** Wildcard SSL Certificate */
  public readonly certificate: acm.Certificate;

  constructor(scope: Construct, id: string, props: CawnexDomainStackProps) {
    super(scope, id, props);

    const { domainName, hostedZoneId, stage } = props;

    // ─────────────────────────────────────────────
    // Route53 Hosted Zone — DNS Management
    // ─────────────────────────────────────────────
    if (hostedZoneId) {
      // Import existing hosted zone
      this.hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        "HostedZone",
        { hostedZoneId, zoneName: domainName }
      );
    } else {
      // Create new hosted zone (you'll need to update nameservers at registrar)
      this.hostedZone = new route53.HostedZone(this, "HostedZone", {
        zoneName: domainName,
        comment: `Cawnex ${stage} domain - ${domainName}`,
      });
      
      // Output nameservers for registrar configuration
      new cdk.CfnOutput(this, "NameServers", {
        value: this.hostedZone.hostedZoneNameServers?.join(", ") || "",
        description: "Configure these nameservers at your domain registrar",
      });
    }

    // ─────────────────────────────────────────────
    // Wildcard SSL Certificate (CloudFront + API)
    // ─────────────────────────────────────────────
    this.certificate = new acm.Certificate(this, "WildcardCertificate", {
      domainName: domainName,
      subjectAlternativeNames: [`*.${domainName}`],
      validation: acm.CertificateValidation.fromDns(this.hostedZone),
    });

    // ─────────────────────────────────────────────
    // SES Domain Identity — Custom Email Sending
    // ─────────────────────────────────────────────
    this.sesIdentity = new ses.EmailIdentity(this, "SESIdentity", {
      identity: ses.Identity.domain(domainName),
      dkimSigning: true, // Enable DKIM signing
    });

    // ─────────────────────────────────────────────
    // DNS Records for Email Authentication
    // ─────────────────────────────────────────────

    // SPF Record — Allow AWS SES to send emails
    new route53.TxtRecord(this, "SpfRecord", {
      zone: this.hostedZone,
      values: ["v=spf1 include:amazonses.com ~all"],
      ttl: cdk.Duration.minutes(5),
      comment: "SPF record to allow AWS SES email sending",
    });

    // DMARC Record — Email security policy
    new route53.TxtRecord(this, "DmarcRecord", {
      zone: this.hostedZone,
      recordName: "_dmarc",
      values: [
        stage === "prod" 
          ? `v=DMARC1; p=quarantine; fo=1; rua=mailto:dmarc@${domainName}; ruf=mailto:dmarc@${domainName}`
          : `v=DMARC1; p=none; fo=1; rua=mailto:dmarc@${domainName}`, // Relaxed for dev/staging
      ],
      ttl: cdk.Duration.minutes(5),
      comment: "DMARC policy for email authentication",
    });

    // ─────────────────────────────────────────────
    // Common Subdomain Setup
    // ─────────────────────────────────────────────
    
    // API subdomain (for future use)
    const apiDomain = stage === "prod" ? `api.${domainName}` : `api-${stage}.${domainName}`;
    
    // App subdomain (for future web dashboard)
    const appDomain = stage === "prod" ? `app.${domainName}` : `app-${stage}.${domainName}`;
    
    // Auth subdomain (for Cognito custom domain)
    const authDomain = stage === "prod" ? `auth.${domainName}` : `auth-${stage}.${domainName}`;

    // ─────────────────────────────────────────────
    // Email Templates (common patterns)
    // ─────────────────────────────────────────────
    
    // Email sender addresses
    const emailSenders = {
      noreply: `noreply@${domainName}`,
      support: `support@${domainName}`,
      security: `security@${domainName}`,
      admin: `admin@${domainName}`,
    };

    // ─────────────────────────────────────────────
    // Outputs for Cross-Stack Reference
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "DomainName", {
      value: domainName,
      exportName: `CawnexDomainStack-${stage}-DomainName`,
      description: "Primary domain name",
    });

    new cdk.CfnOutput(this, "HostedZoneId", {
      value: this.hostedZone.hostedZoneId,
      exportName: `CawnexDomainStack-${stage}-HostedZoneId`,
      description: "Route53 Hosted Zone ID",
    });

    new cdk.CfnOutput(this, "SESIdentityArn", {
      value: this.sesIdentity.emailIdentityArn,
      exportName: `CawnexDomainStack-${stage}-SESIdentityArn`,
      description: "SES Email Identity ARN",
    });

    new cdk.CfnOutput(this, "CertificateArn", {
      value: this.certificate.certificateArn,
      exportName: `CawnexDomainStack-${stage}-CertificateArn`,
      description: "Wildcard SSL Certificate ARN",
    });

    new cdk.CfnOutput(this, "ApiDomain", {
      value: apiDomain,
      exportName: `CawnexDomainStack-${stage}-ApiDomain`,
      description: "API subdomain for custom API Gateway domain",
    });

    new cdk.CfnOutput(this, "AppDomain", {
      value: appDomain,
      exportName: `CawnexDomainStack-${stage}-AppDomain`,
      description: "App subdomain for web dashboard",
    });

    new cdk.CfnOutput(this, "AuthDomain", {
      value: authDomain,
      exportName: `CawnexDomainStack-${stage}-AuthDomain`,
      description: "Auth subdomain for Cognito custom domain",
    });

    new cdk.CfnOutput(this, "EmailSenders", {
      value: JSON.stringify(emailSenders),
      exportName: `CawnexDomainStack-${stage}-EmailSenders`,
      description: "Standard email sender addresses",
    });

    // ─────────────────────────────────────────────
    // SES Configuration Set (for tracking/analytics)
    // ─────────────────────────────────────────────
    const configSet = new ses.ConfigurationSet(this, "EmailConfigSet", {
      configurationSetName: `cawnex-${stage}`,
      sendingEnabled: true,
    });

    // Email sending reputation tracking
    configSet.addEventDestination("ReputationTracking", {
      destination: ses.EventDestination.cloudWatchDimensions({
        defaultDimensionValue: "EmailSending",
      }),
      events: [
        ses.EmailSendingEvent.SEND,
        ses.EmailSendingEvent.REJECT,
        ses.EmailSendingEvent.BOUNCE,
        ses.EmailSendingEvent.COMPLAINT,
        ses.EmailSendingEvent.DELIVERY,
      ],
    });

    new cdk.CfnOutput(this, "SESConfigSetName", {
      value: configSet.configurationSetName,
      exportName: `CawnexDomainStack-${stage}-SESConfigSetName`,
      description: "SES Configuration Set for email tracking",
    });
  }
}