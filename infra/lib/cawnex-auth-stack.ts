import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

interface CawnexAuthStackProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
  domainName?: string; // Optional - for SES integration
  sesIdentityArn?: string; // Optional - SES identity ARN
  sesConfigSetName?: string; // Optional - SES configuration set name (only exists when a domain stack is deployed)
}

export class CawnexAuthStack extends cdk.Stack {
  /** Cognito User Pool — exported for cross-stack references */
  public readonly userPool: cognito.UserPool;

  /** iOS Client — exported for cross-stack references */
  public readonly iosClient: cognito.UserPoolClient;

  /** Web Client — exported for cross-stack references */
  public readonly webClient: cognito.UserPoolClient;

  /** DynamoDB Table — shared between auth and app */
  public readonly table: dynamodb.Table;

  /** DynamoDB Table Stream ARN — for Murder Lambda event source */
  public readonly tableStreamArn: string;

  /** Custom Email Sender Lambda — sends welcome emails via SES */
  public readonly customEmailSenderFn: lambda.Function;

  constructor(scope: Construct, id: string, props: CawnexAuthStackProps) {
    super(scope, id, props);

    const { stage, domainName, sesIdentityArn, sesConfigSetName } = props;

    // ─────────────────────────────────────────────
    // DynamoDB — Single-table design, multi-tenant
    // ─────────────────────────────────────────────
    this.table = new dynamodb.Table(this, "MainTable", {
      tableName: `cawnex-${stage}`,
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      removalPolicy:
        stage === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: "ttl",
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    this.tableStreamArn = this.table.tableStreamArn!;

    // GSI1: Query by type within tenant (e.g., all projects for tenant)
    this.table.addGlobalSecondaryIndex({
      indexName: "GSI1",
      partitionKey: { name: "GSI1PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "GSI1SK", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI2: Cross-tenant queries (admin), status lookups
    this.table.addGlobalSecondaryIndex({
      indexName: "GSI2",
      partitionKey: { name: "GSI2PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "GSI2SK", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ─────────────────────────────────────────────
    // Cognito User Pool — Multi-tenant SaaS
    // ─────────────────────────────────────────────
    this.userPool = new cognito.UserPool(this, "UserPool", {
      userPoolName: `cawnex-${stage}`,
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      standardAttributes: {
        fullname: { required: false, mutable: true },
      },
      customAttributes: {
        tenant_id: new cognito.StringAttribute({ mutable: true }),
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: false,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,

      // Email configuration — SES or Cognito default
      email:
        domainName && sesIdentityArn
          ? cognito.UserPoolEmail.withSES({
              fromEmail: `noreply@${domainName}`,
              fromName: "Cawnex",
              sesRegion: "us-east-1",
              sesVerifiedDomain: domainName,
            })
          : cognito.UserPoolEmail.withCognito(),

      // Email verification settings
      userVerification: {
        emailSubject: "Verify your Cawnex account",
        emailBody:
          "Thanks for signing up! Your verification code is {####}. This code expires in 24 hours.",
        emailStyle: cognito.VerificationEmailStyle.CODE,
      },

      removalPolicy:
        stage === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    // ─────────────────────────────────────────────
    // User Pool Domain
    // ─────────────────────────────────────────────
    const userPoolDomain = this.userPool.addDomain("Domain", {
      cognitoDomain: { domainPrefix: `cawnex-${stage}` },
    });

    // ─────────────────────────────────────────────
    // User Pool Clients
    // ─────────────────────────────────────────────

    // iOS app client
    this.iosClient = this.userPool.addClient("iOSClient", {
      userPoolClientName: `cawnex-ios-${stage}`,
      authFlows: {
        userPassword: true,
        userSrp: true,
      },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: ["cawnex://auth/callback"],
        logoutUrls: ["cawnex://auth/logout"],
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
      ],
    });

    // Web dashboard client
    this.webClient = this.userPool.addClient("WebClient", {
      userPoolClientName: `cawnex-web-${stage}`,
      authFlows: {
        userSrp: true,
      },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: [
          stage === "prod"
            ? "https://app.cawnex.ai/auth/callback"
            : "http://localhost:5173/auth/callback",
        ],
        logoutUrls: [
          stage === "prod"
            ? "https://app.cawnex.ai/auth/logout"
            : "http://localhost:5173/auth/logout",
        ],
      },
    });

    // ─────────────────────────────────────────────
    // Custom Email Sender Lambda — sends welcome emails via SES
    // ─────────────────────────────────────────────
    this.customEmailSenderFn = new lambda.Function(this, "CustomEmailSenderFn", {
      functionName: `cawnex-custom-email-sender-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset("../lambdas/custom-email-sender"),
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
      architecture: lambda.Architecture.ARM_64,
      environment: {
        DOMAIN_NAME: domainName || "cawnex.ai",
        STAGE: stage,
        ...(sesConfigSetName ? { CONFIG_SET_NAME: sesConfigSetName } : {}),
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // Grant SES permissions to custom email sender
    this.customEmailSenderFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "ses:SendEmail",
          "ses:SendTemplatedEmail",
          "ses:SendRawEmail",
        ],
        resources: [
          sesIdentityArn || `arn:aws:ses:${this.region}:${this.account}:identity/${domainName || "cawnex.ai"}`,
          `arn:aws:ses:${this.region}:${this.account}:configuration-set/cawnex-${stage}`,
        ],
      })
    );

    // ─────────────────────────────────────────────
    // Post-confirmation Lambda — creates tenant on first sign-up
    // ─────────────────────────────────────────────
    const postConfirmationFn = new lambda.Function(this, "PostConfirmationFn", {
      functionName: `cawnex-post-confirmation-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset("../lambdas/auth-post-confirmation"),
      memorySize: 128,
      timeout: cdk.Duration.seconds(10),
      architecture: lambda.Architecture.ARM_64,
      environment: {
        TABLE_NAME: this.table.tableName,
        STAGE: stage,
        CUSTOM_EMAIL_SENDER_FUNCTION: this.customEmailSenderFn.functionName,
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // Grant permissions to write to DynamoDB
    this.table.grantWriteData(postConfirmationFn);

    // Grant post-confirmation Lambda permission to invoke the email sender
    postConfirmationFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["lambda:InvokeFunction"],
        resources: [this.customEmailSenderFn.functionArn],
      })
    );

    // Grant cognito-idp:AdminUpdateUserAttributes using account-scoped ARN
    // to avoid circular dependency (UserPool → Lambda → IAM ref UserPool ARN → UserPool)
    postConfirmationFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["cognito-idp:AdminUpdateUserAttributes"],
        resources: [
          `arn:aws:cognito-idp:${this.region}:${this.account}:userpool/*`,
        ],
      })
    );

    // Attach trigger — must come AFTER the IAM policy to avoid circular ref
    this.userPool.addTrigger(
      cognito.UserPoolOperation.POST_CONFIRMATION,
      postConfirmationFn
    );

    // Export DynamoDB table name and ARN for MainStack
    new cdk.CfnOutput(this, "TableName", {
      value: this.table.tableName,
      exportName: `CawnexAuthStack-${stage}-TableName`,
      description: "DynamoDB table name",
    });

    new cdk.CfnOutput(this, "TableArn", {
      value: this.table.tableArn,
      exportName: `CawnexAuthStack-${stage}-TableArn`,
      description: "DynamoDB table ARN",
    });

    new cdk.CfnOutput(this, "TableStreamArn", {
      value: this.tableStreamArn,
      exportName: `CawnexAuthStack-${stage}-TableStreamArn`,
      description: "DynamoDB table stream ARN",
    });

    // ─────────────────────────────────────────────
    // Cross-Stack Exports (for MainStack reference)
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "UserPoolId", {
      value: this.userPool.userPoolId,
      exportName: `CawnexAuthStack-${stage}-UserPoolId`,
      description: "Cognito User Pool ID",
    });

    new cdk.CfnOutput(this, "UserPoolArn", {
      value: this.userPool.userPoolArn,
      exportName: `CawnexAuthStack-${stage}-UserPoolArn`,
      description: "Cognito User Pool ARN",
    });

    new cdk.CfnOutput(this, "iOSClientId", {
      value: this.iosClient.userPoolClientId,
      exportName: `CawnexAuthStack-${stage}-iOSClientId`,
      description: "Cognito iOS app client ID",
    });

    new cdk.CfnOutput(this, "WebClientId", {
      value: this.webClient.userPoolClientId,
      exportName: `CawnexAuthStack-${stage}-WebClientId`,
      description: "Cognito Web app client ID",
    });

    new cdk.CfnOutput(this, "CognitoDomain", {
      value: userPoolDomain.domainName,
      exportName: `CawnexAuthStack-${stage}-CognitoDomain`,
      description: "Cognito hosted UI domain",
    });

    new cdk.CfnOutput(this, "CustomEmailSenderArn", {
      value: this.customEmailSenderFn.functionArn,
      exportName: `CawnexAuthStack-${stage}-CustomEmailSenderArn`,
      description: "Custom Email Sender Lambda ARN",
    });

    new cdk.CfnOutput(this, "Region", {
      value: this.region,
      exportName: `CawnexAuthStack-${stage}-Region`,
      description: "AWS region for SDK configuration",
    });
  }
}
