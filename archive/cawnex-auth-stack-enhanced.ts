import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

interface CawnexAuthStackEnhancedProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
  domainName?: string; // Optional - for SES integration
  sesIdentityArn?: string; // Optional - SES identity ARN
}

export class CawnexAuthStackEnhanced extends cdk.Stack {
  /** Cognito User Pool — exported for cross-stack references */
  public readonly userPool: cognito.UserPool;

  /** iOS Client — exported for cross-stack references */
  public readonly iosClient: cognito.UserPoolClient;

  /** Web Client — exported for cross-stack references */
  public readonly webClient: cognito.UserPoolClient;

  /** DynamoDB Table — shared between auth and app */
  public readonly table: dynamodb.Table;

  /** Custom Email Sender Lambda */
  public readonly customEmailSenderFn: lambda.Function;

  constructor(scope: Construct, id: string, props: CawnexAuthStackEnhancedProps) {
    super(scope, id, props);

    const { stage, domainName, sesIdentityArn } = props;

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
    });

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
    // Custom Email Sender Lambda
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
        CONFIG_SET_NAME: `cawnex-${stage}`,
        STAGE: stage,
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
    // Cognito User Pool — Enhanced with Custom Email
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

      // Custom message Lambda trigger for enhanced emails
      lambdaTriggers: {
        customMessage: this.customEmailSenderFn,
      },

      // Basic email settings (will be overridden by custom Lambda)
      userVerification: {
        emailSubject: "Verify your Cawnex account",
        emailBody:
          "Thanks for signing up! Your verification code is {####}. This code expires in 24 hours.",
        emailStyle: cognito.VerificationEmailStyle.CODE,
      },

      removalPolicy:
        stage === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    // Grant custom email sender permission to be invoked by Cognito
    this.customEmailSenderFn.addPermission("CognitoInvoke", {
      principal: new iam.ServicePrincipal("cognito-idp.amazonaws.com"),
      sourceArn: this.userPool.userPoolArn,
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
    // Post-confirmation Lambda — creates tenant + sends welcome email
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

    // Grant permissions to post-confirmation Lambda
    postConfirmationFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["cognito-idp:AdminUpdateUserAttributes"],
        resources: [this.userPool.userPoolArn],
      })
    );

    postConfirmationFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["lambda:InvokeFunction"],
        resources: [this.customEmailSenderFn.functionArn],
      })
    );

    this.table.grantWriteData(postConfirmationFn);

    // Add post-confirmation trigger to user pool
    this.userPool.addTrigger(
      cognito.UserPoolOperation.POST_CONFIRMATION,
      postConfirmationFn
    );

    // ─────────────────────────────────────────────
    // Cross-Stack Exports
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "TableName", {
      value: this.table.tableName,
      exportName: `CawnexAuthStackEnhanced-${stage}-TableName`,
      description: "DynamoDB table name",
    });

    new cdk.CfnOutput(this, "TableArn", {
      value: this.table.tableArn,
      exportName: `CawnexAuthStackEnhanced-${stage}-TableArn`,
      description: "DynamoDB table ARN",
    });

    new cdk.CfnOutput(this, "UserPoolId", {
      value: this.userPool.userPoolId,
      exportName: `CawnexAuthStackEnhanced-${stage}-UserPoolId`,
      description: "Cognito User Pool ID",
    });

    new cdk.CfnOutput(this, "UserPoolArn", {
      value: this.userPool.userPoolArn,
      exportName: `CawnexAuthStackEnhanced-${stage}-UserPoolArn`,
      description: "Cognito User Pool ARN",
    });

    new cdk.CfnOutput(this, "iOSClientId", {
      value: this.iosClient.userPoolClientId,
      exportName: `CawnexAuthStackEnhanced-${stage}-iOSClientId`,
      description: "Cognito iOS app client ID",
    });

    new cdk.CfnOutput(this, "WebClientId", {
      value: this.webClient.userPoolClientId,
      exportName: `CawnexAuthStackEnhanced-${stage}-WebClientId`,
      description: "Cognito Web app client ID",
    });

    new cdk.CfnOutput(this, "CognitoDomain", {
      value: userPoolDomain.domainName,
      exportName: `CawnexAuthStackEnhanced-${stage}-CognitoDomain`,
      description: "Cognito hosted UI domain",
    });

    new cdk.CfnOutput(this, "CustomEmailSenderArn", {
      value: this.customEmailSenderFn.functionArn,
      exportName: `CawnexAuthStackEnhanced-${stage}-CustomEmailSenderArn`,
      description: "Custom Email Sender Lambda ARN",
    });

    new cdk.CfnOutput(this, "Region", {
      value: this.region,
      exportName: `CawnexAuthStackEnhanced-${stage}-Region`,
      description: "AWS region for SDK configuration",
    });
  }
}
