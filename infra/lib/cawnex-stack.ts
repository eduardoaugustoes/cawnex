import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as lambdaEventSources from "aws-cdk-lib/aws-lambda-event-sources";
import * as apigw from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwIntegrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as apigwAuthorizers from "aws-cdk-lib/aws-apigatewayv2-authorizers";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as logs from "aws-cdk-lib/aws-logs";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as efs from "aws-cdk-lib/aws-efs";
import * as events from "aws-cdk-lib/aws-events";
import * as eventsTargets from "aws-cdk-lib/aws-events-targets";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";

interface CawnexStackProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
}

export class CawnexStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: CawnexStackProps) {
    super(scope, id, props);

    const stage = props.stage;

    // ─────────────────────────────────────────────
    // Import DynamoDB table from AuthStack
    // ─────────────────────────────────────────────
    const tableName = cdk.Fn.importValue(`CawnexAuthStack-${stage}-TableName`);
    const tableArn = cdk.Fn.importValue(`CawnexAuthStack-${stage}-TableArn`);
    const tableStreamArn = cdk.Fn.importValue(`CawnexAuthStack-${stage}-TableStreamArn`);

    const table = dynamodb.Table.fromTableAttributes(this, "MainTable", {
      tableArn,
      tableStreamArn,
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
        stage === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
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
    // KMS — Vault encryption key
    // ─────────────────────────────────────────────
    const vaultKey = new kms.Key(this, "VaultKey", {
      alias: `alias/cawnex-vault-${stage}`,
      description: "Encrypts secrets in the Cawnex vault",
      enableKeyRotation: true,
      removalPolicy:
        stage === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    // ─────────────────────────────────────────────
    // S3 — Assets bucket (uploads, human task files)
    // ─────────────────────────────────────────────
    const assetsBucket = new s3.Bucket(this, "AssetsBucket", {
      bucketName: `cawnex-assets-${stage}-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy:
        stage === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: stage !== "prod",
      cors: [
        {
          allowedOrigins: ["*"],
          allowedMethods: [
            s3.HttpMethods.PUT,
            s3.HttpMethods.GET,
          ],
          allowedHeaders: ["*"],
          maxAge: 3600,
        },
      ],
      lifecycleRules: [
        {
          id: "expire-temp-uploads",
          prefix: "tmp/",
          expiration: cdk.Duration.days(1),
        },
      ],
    });

    // ─────────────────────────────────────────────
    // DynamoDB — Events table (separate from main, TTL enabled)
    // ─────────────────────────────────────────────
    const eventsTable = new dynamodb.Table(this, "EventsTable", {
      tableName: `cawnex-events-${stage}`,
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: "expires_at",
      removalPolicy:
        stage === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    eventsTable.addGlobalSecondaryIndex({
      indexName: "GSI1",
      partitionKey: { name: "GSI1PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "GSI1SK", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
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
    // Import Cognito resources from AuthStack
    // ─────────────────────────────────────────────
    const userPoolId = cdk.Fn.importValue(
      `CawnexAuthStack-${stage}-UserPoolId`
    );
    const _userPoolArn = cdk.Fn.importValue(
      `CawnexAuthStack-${stage}-UserPoolArn`
    ); // Reserved for future IAM policies
    const iosClientId = cdk.Fn.importValue(
      `CawnexAuthStack-${stage}-iOSClientId`
    );
    const webClientId = cdk.Fn.importValue(
      `CawnexAuthStack-${stage}-WebClientId`
    );
    const cognitoDomain = cdk.Fn.importValue(
      `CawnexAuthStack-${stage}-CognitoDomain`
    );

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
      architecture: lambda.Architecture.X86_64, // CI builds on x86_64
      environment: {
        STAGE: stage,
        TABLE_NAME: tableName,
        BUCKET_NAME: artifactsBucket.bucketName,
        QUEUE_URL: taskQueue.queueUrl,
        USER_POOL_ID: userPoolId,
        USER_POOL_CLIENT_ID: webClientId,
        IOS_CLIENT_ID: iosClientId,
        COGNITO_DOMAIN: cognitoDomain,
        AWS_REGION_NAME: this.region,
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // Anthropic auth token for AI chat proxy
    const anthropicAuthForApi = secretsmanager.Secret.fromSecretNameV2(
      this, "AnthropicAuthForApi", `cawnex/${stage}/anthropic-auth-token`
    );
    anthropicAuthForApi.grantRead(apiFunction);

    // Pass secret ARN so Lambda can fetch at runtime
    apiFunction.addEnvironment(
      "ANTHROPIC_AUTH_SECRET_ARN", anthropicAuthForApi.secretArn
    );

    // Add vault, assets, events, and ECS env vars to API
    apiFunction.addEnvironment("VAULT_KMS_KEY_ID", vaultKey.keyId);
    apiFunction.addEnvironment("ASSETS_BUCKET_NAME", assetsBucket.bucketName);
    apiFunction.addEnvironment("EVENTS_TABLE_NAME", eventsTable.tableName);
    apiFunction.addEnvironment("ECS_CLUSTER_NAME", `cawnex-${stage}`);
    apiFunction.addEnvironment("ECS_SERVICE_NAME", `cawnex-worker-${stage}`);

    // Grant API access to resources
    table.grantReadWriteData(apiFunction);
    eventsTable.grantReadWriteData(apiFunction);
    artifactsBucket.grantReadWrite(apiFunction);
    assetsBucket.grantReadWrite(apiFunction);
    vaultKey.grantEncrypt(apiFunction);
    taskQueue.grantSendMessages(apiFunction);

    // Allow API to scale ECS worker
    apiFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ecs:UpdateService", "ecs:DescribeServices"],
        resources: [`arn:aws:ecs:${this.region}:${this.account}:service/cawnex-${stage}/cawnex-worker-${stage}`],
      })
    );

    // HTTP API (API Gateway v2)
    const httpApi = new apigw.HttpApi(this, "HttpApi", {
      apiName: `cawnex-api-${stage}`,
      corsPreflight: {
        allowOrigins: [
          stage === "prod" ? "https://app.cawnex.ai" : "http://localhost:5173",
        ],
        allowMethods: [apigw.CorsHttpMethod.ANY],
        allowHeaders: ["Authorization", "Content-Type"],
        maxAge: cdk.Duration.hours(1),
      },
    });

    // JWT authorizer — validates Cognito tokens, extracts tenant_id
    const jwtAuthorizer = new apigwAuthorizers.HttpJwtAuthorizer(
      "CognitoAuthorizer",
      `https://cognito-idp.${this.region}.amazonaws.com/${userPoolId}`,
      {
        jwtAudience: [iosClientId, webClientId],
        identitySource: ["$request.header.Authorization"],
      }
    );

    const apiIntegration = new apigwIntegrations.HttpLambdaIntegration(
      "ApiIntegration",
      apiFunction
    );

    // Public endpoints — no auth required
    httpApi.addRoutes({
      path: "/health",
      methods: [apigw.HttpMethod.GET],
      integration: apiIntegration,
    });

    httpApi.addRoutes({
      path: "/config",
      methods: [apigw.HttpMethod.GET],
      integration: apiIntegration,
    });

    // All other routes — JWT required
    httpApi.addRoutes({
      path: "/{proxy+}",
      methods: [apigw.HttpMethod.ANY],
      integration: apiIntegration,
      authorizer: jwtAuthorizer,
    });

    // ─────────────────────────────────────────────
    // Lambda — Murder (DynamoDB Streams orchestrator)
    // ─────────────────────────────────────────────
    const murderFn = new lambda.Function(this, "MurderFunction", {
      functionName: `cawnex-murder-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "murder.handler.lambda_handler",
      code: lambda.Code.fromAsset("../lambdas/murder/src"),
      memorySize: 512,
      timeout: cdk.Duration.seconds(60),
      architecture: lambda.Architecture.ARM_64,
      environment: {
        TABLE_NAME: tableName,
        STAGE: stage,
        ANTHROPIC_MODEL: "claude-sonnet-4-20250514",
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    murderFn.addEnvironment("EVENTS_TABLE_NAME", eventsTable.tableName);

    table.grantReadWriteData(murderFn);
    table.grantStreamRead(murderFn);
    eventsTable.grantReadWriteData(murderFn);

    murderFn.addEventSource(
      new lambdaEventSources.DynamoEventSource(table, {
        startingPosition: lambda.StartingPosition.TRIM_HORIZON,
        batchSize: 10,
        bisectBatchOnError: true,
        retryAttempts: 3,
      })
    );

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

    // ─────────────────────────────────────────────
    // EFS — Persistent repo storage with tenant isolation
    // ─────────────────────────────────────────────
    const repoFs = new efs.FileSystem(this, "RepoFileSystem", {
      fileSystemName: `cawnex-repos-${stage}`,
      vpc,
      encrypted: true,
      performanceMode: efs.PerformanceMode.GENERAL_PURPOSE,
      throughputMode: efs.ThroughputMode.BURSTING,
      lifecyclePolicy: efs.LifecyclePolicy.AFTER_30_DAYS,
      removalPolicy:
        stage === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    // Access Point — hard tenant isolation at NFS level
    // MVP: single access point for dev tenant
    // Production: create access point per tenant at signup time
    const devAccessPoint = repoFs.addAccessPoint("DevTenantAP", {
      path: "/T/dev-tenant",
      posixUser: { uid: "1000", gid: "1000" },
      createAcl: { ownerUid: "1000", ownerGid: "1000", permissions: "750" },
    });

    // Restrict NFS traffic to ECS security group only
    const workerSg = new ec2.SecurityGroup(this, "WorkerSG", {
      vpc,
      description: "Worker ECS tasks",
      allowAllOutbound: true,
    });
    repoFs.connections.allowDefaultPortFrom(workerSg, "ECS worker NFS access");

    const workerTaskDef = new ecs.FargateTaskDefinition(this, "WorkerTask", {
      family: `cawnex-worker-${stage}`,
      cpu: 1024, // 1 vCPU
      memoryLimitMiB: 2048, // 2 GB
    });

    // Mount EFS via Access Point
    workerTaskDef.addVolume({
      name: "repos",
      efsVolumeConfiguration: {
        fileSystemId: repoFs.fileSystemId,
        transitEncryption: "ENABLED",
        authorizationConfig: {
          accessPointId: devAccessPoint.accessPointId,
          iam: "ENABLED",
        },
      },
    });

    // Runtime secrets from AWS Secrets Manager
    const githubTokenSecret = secretsmanager.Secret.fromSecretNameV2(
      this, "GithubTokenSecret", `cawnex/${stage}/github-token`
    );
    const anthropicAuthSecret = secretsmanager.Secret.fromSecretNameV2(
      this, "AnthropicAuthSecret", `cawnex/${stage}/anthropic-auth-token`
    );

    const workerContainer = workerTaskDef.addContainer("worker", {
      containerName: "murder",
      image: ecs.ContainerImage.fromAsset("..", {
        file: "apps/worker/Dockerfile",
      }),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: "murder",
        logRetention: logs.RetentionDays.ONE_MONTH,
      }),
      environment: {
        STAGE: stage,
        TABLE_NAME: tableName,
        EVENTS_TABLE_NAME: eventsTable.tableName,
        BUCKET_NAME: artifactsBucket.bucketName,
        QUEUE_URL: taskQueue.queueUrl,
        ANTHROPIC_MODEL: "claude-sonnet-4-20250514",
        EFS_MOUNT: "/mnt/repos",
        MEMORY_INJECTION_ENABLED: "true",
        VAULT_KMS_KEY_ID: vaultKey.keyId,
        ASSETS_BUCKET_NAME: assetsBucket.bucketName,
      },
      secrets: {
        GITHUB_TOKEN: ecs.Secret.fromSecretsManager(githubTokenSecret),
        ANTHROPIC_AUTH_TOKEN: ecs.Secret.fromSecretsManager(anthropicAuthSecret),
      },
    });

    workerContainer.addMountPoints({
      containerPath: "/mnt/repos",
      sourceVolume: "repos",
      readOnly: false,
    });

    // Grant Worker access to resources
    table.grantReadWriteData(workerTaskDef.taskRole);
    eventsTable.grantReadWriteData(workerTaskDef.taskRole);
    artifactsBucket.grantReadWrite(workerTaskDef.taskRole);
    assetsBucket.grantRead(workerTaskDef.taskRole);
    vaultKey.grantDecrypt(workerTaskDef.taskRole);
    taskQueue.grantConsumeMessages(workerTaskDef.taskRole);
    taskQueue.grantSendMessages(workerTaskDef.taskRole);
    repoFs.grantReadWrite(workerTaskDef.taskRole);

    // Worker ECS service — outbound internet for LLM APIs + GitHub
    const _workerService = new ecs.FargateService(this, "WorkerService", {
      serviceName: `cawnex-worker-${stage}`,
      cluster,
      taskDefinition: workerTaskDef,
      desiredCount: 0, // wave activation scales up, scaler scales down
      assignPublicIp: stage !== "prod",
      securityGroups: [workerSg],
      platformVersion: ecs.FargatePlatformVersion.VERSION1_4, // required for EFS
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
    // Lambda — Checker (scheduled verification)
    // ─────────────────────────────────────────────
    const checkerFn = new lambda.Function(this, "CheckerFunction", {
      functionName: `cawnex-checker-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.lambda_handler",
      code: lambda.Code.fromAsset("../lambdas/orchestration/checker"),
      memorySize: 256,
      timeout: cdk.Duration.seconds(60),
      architecture: lambda.Architecture.ARM_64,
      environment: {
        TABLE_NAME: tableName,
        STAGE: stage,
        QUEUE_URL: taskQueue.queueUrl,
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    table.grantReadWriteData(checkerFn);
    taskQueue.grantSendMessages(checkerFn);

    // Run checker every hour
    new events.Rule(this, "CheckerSchedule", {
      ruleName: `cawnex-checker-${stage}`,
      schedule: events.Schedule.rate(cdk.Duration.hours(1)),
      targets: [new eventsTargets.LambdaFunction(checkerFn)],
    });

    // ─────────────────────────────────────────────
    // Lambda — SSE (Server-Sent Events streaming)
    // ─────────────────────────────────────────────
    const sseFn = new lambda.Function(this, "SSEFunction", {
      functionName: `cawnex-sse-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset("../lambdas/sse"),
      memorySize: 256,
      timeout: cdk.Duration.minutes(15),
      architecture: lambda.Architecture.ARM_64,
      environment: {
        EVENTS_TABLE_NAME: eventsTable.tableName,
        TABLE_NAME: tableName,
        USER_POOL_ID: userPoolId,
        COGNITO_DOMAIN: cognitoDomain,
        AWS_REGION_NAME: this.region,
        STAGE: stage,
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    eventsTable.grantReadData(sseFn);
    table.grantReadData(sseFn);

    const sseUrl = sseFn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE, // JWT validated in code
      invokeMode: lambda.InvokeMode.RESPONSE_STREAM,
      cors: {
        allowedOrigins: ["*"],
        allowedMethods: [lambda.HttpMethod.GET],
        allowedHeaders: ["Authorization", "Content-Type"],
        maxAge: cdk.Duration.hours(1),
      },
    });

    // ─────────────────────────────────────────────
    // Lambda — Worker Scaler (auto scale-down)
    // ─────────────────────────────────────────────
    const scalerFn = new lambda.Function(this, "WorkerScalerFunction", {
      functionName: `cawnex-worker-scaler-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.lambda_handler",
      code: lambda.Code.fromAsset("../lambdas/orchestration/worker-scaler"),
      memorySize: 128,
      timeout: cdk.Duration.seconds(30),
      architecture: lambda.Architecture.ARM_64,
      environment: {
        TABLE_NAME: tableName,
        ECS_CLUSTER_NAME: `cawnex-${stage}`,
        ECS_SERVICE_NAME: `cawnex-worker-${stage}`,
        STAGE: stage,
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    table.grantReadData(scalerFn);
    scalerFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ecs:UpdateService", "ecs:DescribeServices"],
        resources: [`arn:aws:ecs:${this.region}:${this.account}:service/cawnex-${stage}/cawnex-worker-${stage}`],
      })
    );

    // Run scaler every 15 minutes
    new events.Rule(this, "WorkerScalerSchedule", {
      ruleName: `cawnex-worker-scaler-${stage}`,
      schedule: events.Schedule.rate(cdk.Duration.minutes(15)),
      targets: [new eventsTargets.LambdaFunction(scalerFn)],
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
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
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

    new cdk.CfnOutput(this, "AssetsBucketName", {
      value: assetsBucket.bucketName,
      description: "S3 bucket for human task file uploads",
    });

    new cdk.CfnOutput(this, "VaultKeyId", {
      value: vaultKey.keyId,
      description: "KMS key for vault encryption",
    });

    new cdk.CfnOutput(this, "EventsTableName", {
      value: eventsTable.tableName,
      description: "DynamoDB events table (separate from main, TTL enabled)",
    });

    new cdk.CfnOutput(this, "SSEUrl", {
      value: sseUrl.url,
      description: "Lambda Function URL for SSE event streaming",
    });

    new cdk.CfnOutput(this, "RepoFileSystemId", {
      value: repoFs.fileSystemId,
      description: "EFS filesystem for git repos",
    });

    // Note: PostConfirmation Lambda is handled entirely in AuthStack
    // including DynamoDB permissions and table access

    // ─────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "UserPoolId", {
      value: userPoolId,
      description: "Cognito User Pool ID",
    });

    new cdk.CfnOutput(this, "CognitoDomain", {
      value: cognitoDomain,
    });

    new cdk.CfnOutput(this, "iOSClientId", {
      value: iosClientId,
      description: "Cognito iOS app client ID",
    });

    new cdk.CfnOutput(this, "WebClientId", {
      value: webClientId,
      description: "Cognito Web app client ID",
    });

    new cdk.CfnOutput(this, "Region", {
      value: this.region,
      description: "AWS region for SDK configuration",
    });
  }
}
