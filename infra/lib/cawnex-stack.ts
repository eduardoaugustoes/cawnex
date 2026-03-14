import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigw from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwIntegrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as apigwAuthorizers from "aws-cdk-lib/aws-apigatewayv2-authorizers";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";

interface CawnexStackProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
}

export class CawnexStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: CawnexStackProps) {
    super(scope, id, props);

    const stage = props.stage;

    // ─────────────────────────────────────────────
    // DynamoDB — Single-table design, multi-tenant
    // ─────────────────────────────────────────────
    const table = new dynamodb.Table(this, "MainTable", {
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
    table.addGlobalSecondaryIndex({
      indexName: "GSI1",
      partitionKey: { name: "GSI1PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "GSI1SK", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI2: Cross-tenant queries (admin), status lookups
    table.addGlobalSecondaryIndex({
      indexName: "GSI2",
      partitionKey: { name: "GSI2PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "GSI2SK", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ─────────────────────────────────────────────
    // S3 — Artifacts, .pen files, worktree snapshots
    // ─────────────────────────────────────────────
    const artifactsBucket = new s3.Bucket(this, "ArtifactsBucket", {
      bucketName: `cawnex-artifacts-${stage}-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: stage === "prod",
      removalPolicy:
        stage === "prod"
          ? cdk.RemovalPolicy.RETAIN
          : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: stage !== "prod",
      lifecycleRules: [
        {
          id: "expire-temp",
          prefix: "tmp/",
          expiration: cdk.Duration.days(7),
        },
      ],
    });

    // ─────────────────────────────────────────────
    // SQS — Task queue (replaces Redis Streams)
    // ─────────────────────────────────────────────
    const taskDlq = new sqs.Queue(this, "TaskDLQ", {
      queueName: `cawnex-tasks-dlq-${stage}`,
      retentionPeriod: cdk.Duration.days(14),
    });

    const taskQueue = new sqs.Queue(this, "TaskQueue", {
      queueName: `cawnex-tasks-${stage}`,
      visibilityTimeout: cdk.Duration.minutes(30), // Murder runs can be long
      deadLetterQueue: {
        queue: taskDlq,
        maxReceiveCount: 3,
      },
    });

    // ─────────────────────────────────────────────
    // Cognito — Auth (Apple Sign In + email/password)
    // ─────────────────────────────────────────────
    const userPool = new cognito.UserPool(this, "UserPool", {
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

    // Post-confirmation trigger will be added AFTER API setup to avoid circular dependency

    // iOS app client
    const iosClient = userPool.addClient("iOSClient", {
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
        // Apple Sign In added after identity provider config
      ],
    });

    // Web dashboard client
    const webClient = userPool.addClient("WebClient", {
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

    const userPoolDomain = userPool.addDomain("Domain", {
      cognitoDomain: { domainPrefix: `cawnex-${stage}` },
    });

    // ─────────────────────────────────────────────
    // Lambda — API (FastAPI via Mangum)
    // ─────────────────────────────────────────────
    const apiFunction = new lambda.Function(this, "ApiFunction", {
      functionName: `cawnex-api-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset("../apps/api/dist"), // built artifact
      memorySize: 512,
      timeout: cdk.Duration.seconds(29), // API GW limit is 30s
      architecture: lambda.Architecture.ARM_64,
      environment: {
        STAGE: stage,
        TABLE_NAME: table.tableName,
        BUCKET_NAME: artifactsBucket.bucketName,
        QUEUE_URL: taskQueue.queueUrl,
        // USER_POOL_ID and USER_POOL_CLIENT_ID removed temporarily to avoid circular dependency
        // These will need to be added via environment variable updates after deployment
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // Grant API access to resources
    table.grantReadWriteData(apiFunction);
    artifactsBucket.grantReadWrite(apiFunction);
    taskQueue.grantSendMessages(apiFunction);

    // HTTP API (API Gateway v2)
    const httpApi = new apigw.HttpApi(this, "HttpApi", {
      apiName: `cawnex-api-${stage}`,
      corsPreflight: {
        allowOrigins: [
          stage === "prod"
            ? "https://app.cawnex.ai"
            : "http://localhost:5173",
        ],
        allowMethods: [apigw.CorsHttpMethod.ANY],
        allowHeaders: ["Authorization", "Content-Type"],
        maxAge: cdk.Duration.hours(1),
      },
    });

    const apiIntegration = new apigwIntegrations.HttpLambdaIntegration(
      "ApiIntegration",
      apiFunction
    );

    // Health endpoint — no auth required (monitoring, deployment checks)
    httpApi.addRoutes({
      path: "/health",
      methods: [apigw.HttpMethod.GET],
      integration: apiIntegration,
    });

    // All other routes — TEMPORARILY no auth to avoid circular dependency
    // TODO: Add JWT authorizer in a separate CDK stack or after deployment
    httpApi.addRoutes({
      path: "/{proxy+}",
      methods: [apigw.HttpMethod.ANY],
      integration: apiIntegration,
      // authorizer: jwtAuthorizer, // TODO: Enable after fixing circular dependency
    });

    // ─────────────────────────────────────────────
    // ECS Fargate — Worker (Murder orchestrator)
    // ─────────────────────────────────────────────
    const vpc = new ec2.Vpc(this, "Vpc", {
      vpcName: `cawnex-${stage}`,
      maxAzs: 2,
      natGateways: stage === "prod" ? 1 : 0,
      subnetConfiguration: [
        {
          name: "public",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        ...(stage === "prod"
          ? [
              {
                name: "private",
                subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
                cidrMask: 24,
              },
            ]
          : []),
      ],
    });

    const cluster = new ecs.Cluster(this, "Cluster", {
      clusterName: `cawnex-${stage}`,
      vpc,
      containerInsights: stage === "prod",
    });

    const workerTaskDef = new ecs.FargateTaskDefinition(this, "WorkerTask", {
      family: `cawnex-worker-${stage}`,
      cpu: 1024, // 1 vCPU
      memoryLimitMiB: 2048, // 2 GB
    });

    workerTaskDef.addContainer("worker", {
      containerName: "murder",
      image: ecs.ContainerImage.fromAsset("../apps/worker"),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: "murder",
        logRetention: logs.RetentionDays.ONE_MONTH,
      }),
      environment: {
        STAGE: stage,
        TABLE_NAME: table.tableName,
        BUCKET_NAME: artifactsBucket.bucketName,
        QUEUE_URL: taskQueue.queueUrl,
      },
    });

    // Grant Worker access to resources
    table.grantReadWriteData(workerTaskDef.taskRole);
    artifactsBucket.grantReadWrite(workerTaskDef.taskRole);
    taskQueue.grantConsumeMessages(workerTaskDef.taskRole);
    taskQueue.grantSendMessages(workerTaskDef.taskRole); // for re-queue

    // Worker needs to call LLM APIs (BYOL) — outbound internet
    const workerService = new ecs.FargateService(this, "WorkerService", {
      serviceName: `cawnex-worker-${stage}`,
      cluster,
      taskDefinition: workerTaskDef,
      desiredCount: stage === "prod" ? 1 : 0, // scale to zero in dev
      assignPublicIp: stage !== "prod", // public subnet in dev (no NAT)
      capacityProviderStrategies: [
        {
          capacityProvider: "FARGATE_SPOT",
          weight: stage === "prod" ? 0 : 1,
        },
        {
          capacityProvider: "FARGATE",
          weight: stage === "prod" ? 1 : 0,
        },
      ],
    });

    // ─────────────────────────────────────────────
    // CloudFront — CDN for API + future web app
    // ─────────────────────────────────────────────
    const distribution = new cloudfront.Distribution(this, "CDN", {
      comment: `cawnex-${stage}`,
      defaultBehavior: {
        origin: new origins.HttpOrigin(
          `${httpApi.httpApiId}.execute-api.${this.region}.amazonaws.com`
        ),
        viewerProtocolPolicy:
          cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy:
          cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      },
    });

    // ─────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "ApiUrl", {
      value: httpApi.url ?? "N/A",
      description: "API Gateway URL",
    });

    new cdk.CfnOutput(this, "CloudFrontUrl", {
      value: `https://${distribution.distributionDomainName}`,
      description: "CloudFront Distribution URL",
    });

    new cdk.CfnOutput(this, "TableName", {
      value: table.tableName,
    });

    new cdk.CfnOutput(this, "BucketName", {
      value: artifactsBucket.bucketName,
    });

    new cdk.CfnOutput(this, "QueueUrl", {
      value: taskQueue.queueUrl,
    });

    // ─────────────────────────────────────────────
    // Post-confirmation Lambda — added AFTER API setup to avoid circular dependency
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
          TABLE_NAME: table.tableName,
          STAGE: stage,
        },
        logRetention: logs.RetentionDays.ONE_MONTH,
      }
    );

    table.grantWriteData(postConfirmationFn);
    postConfirmationFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["cognito-idp:AdminUpdateUserAttributes"],
        resources: [userPool.userPoolArn],
      })
    );

    userPool.addTrigger(
      cognito.UserPoolOperation.POST_CONFIRMATION,
      postConfirmationFn
    );

    // ─────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "UserPoolId", {
      value: userPool.userPoolId,
      description: "Cognito User Pool ID",
    });

    new cdk.CfnOutput(this, "CognitoDomain", {
      value: userPoolDomain.domainName,
    });

    new cdk.CfnOutput(this, "iOSClientId", {
      value: iosClient.userPoolClientId,
      description: "Cognito iOS app client ID",
    });

    new cdk.CfnOutput(this, "WebClientId", {
      value: webClient.userPoolClientId,
      description: "Cognito Web app client ID",
    });

    new cdk.CfnOutput(this, "Region", {
      value: this.region,
      description: "AWS region for SDK configuration",
    });

    new cdk.CfnOutput(this, "PostDeploymentNotes", {
      value: "IMPORTANT: API currently has NO AUTHENTICATION due to circular dependency. Add JWT authorizer manually after deployment.",
      description: "Manual steps required after deployment",
    });
  }
}
