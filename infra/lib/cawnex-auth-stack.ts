import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

interface CawnexAuthStackProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
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

  constructor(scope: Construct, id: string, props: CawnexAuthStackProps) {
    super(scope, id, props);

    const { stage } = props;

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
        stage === "prod"
          ? cdk.RemovalPolicy.RETAIN
          : cdk.RemovalPolicy.DESTROY,
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
      removalPolicy:
        stage === "prod"
          ? cdk.RemovalPolicy.RETAIN
          : cdk.RemovalPolicy.DESTROY,
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
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
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
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
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
    // Post-confirmation Lambda — creates tenant on first sign-up  
    // ─────────────────────────────────────────────
    const postConfirmationFn = new lambda.Function(
      this,
      "PostConfirmationFn",
      {
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
        },
        logRetention: logs.RetentionDays.ONE_MONTH,
      }
    );

    // Grant permissions to update user attributes and write to DynamoDB
    postConfirmationFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["cognito-idp:AdminUpdateUserAttributes"],
        resources: [this.userPool.userPoolArn],
      })
    );
    
    this.table.grantWriteData(postConfirmationFn);

    // Note: Trigger attachment will be done manually via AWS CLI after deployment
    // to avoid circular dependency: UserPool → Lambda → IAM permissions → UserPool

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

    new cdk.CfnOutput(this, "Region", {
      value: this.region,
      exportName: `CawnexAuthStack-${stage}-Region`,
      description: "AWS region for SDK configuration",
    });
  }
}