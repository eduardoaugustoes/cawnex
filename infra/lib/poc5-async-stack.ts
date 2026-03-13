import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigw from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwIntegrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as logs from "aws-cdk-lib/aws-logs";
import * as lambdaEvents from "aws-cdk-lib/aws-lambda-event-sources";
import * as path from "path";

interface Poc5AsyncStackProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
}

/**
 * POC 5 — Async Blackboard Loop
 *
 * Validates: Decoupled Murder (judge) + Crow (worker) via DynamoDB blackboard.
 * Murder is triggered by Streams. Crows can run anywhere (Lambda, local, Fargate).
 *
 * Resources:
 * - DynamoDB table (blackboard) with Streams
 * - Murder Lambda (stream-triggered state machine)
 * - API Lambda (POST /murder, GET /murder/{id})
 * - API Gateway v2
 */
export class Poc5AsyncStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Poc5AsyncStackProps) {
    super(scope, id, props);

    const stage = props.stage;

    // ─────────────────────────────────────────────
    // DynamoDB — Blackboard
    // ─────────────────────────────────────────────
    const blackboard = new dynamodb.Table(this, "Blackboard", {
      tableName: `cawnex-poc5-blackboard-${stage}`,
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    // ─────────────────────────────────────────────
    // Murder Lambda (Stream-triggered)
    // ─────────────────────────────────────────────
    const murderFn = new lambda.Function(this, "MurderFunction", {
      functionName: `cawnex-poc5-murder-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../lambdas/poc5-murder")
      ),
      memorySize: 256,
      timeout: cdk.Duration.seconds(30), // Murder should be fast (<5s)
      environment: {
        STAGE: stage,
        BLACKBOARD_TABLE: blackboard.tableName,
        ANTHROPIC_MODEL: "claude-sonnet-4-20250514",
        // ANTHROPIC_API_KEY and GITHUB_TOKEN injected by workflow
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      description: "POC 5 — Murder (stream-triggered state machine)",
    });

    blackboard.grantReadWriteData(murderFn);

    // Stream trigger — Murder handler filters in code
    // (only reacts to META with status=pending and *#REPORT records)
    murderFn.addEventSource(
      new lambdaEvents.DynamoEventSource(blackboard, {
        startingPosition: lambda.StartingPosition.LATEST,
        batchSize: 1,
        retryAttempts: 2,
      })
    );

    // ─────────────────────────────────────────────
    // API Lambda
    // ─────────────────────────────────────────────
    const apiFn = new lambda.Function(this, "ApiFunction", {
      functionName: `cawnex-poc5-api-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../lambdas/poc5-api")
      ),
      memorySize: 256,
      timeout: cdk.Duration.seconds(15),
      environment: {
        STAGE: stage,
        BLACKBOARD_TABLE: blackboard.tableName,
        // GITHUB_TOKEN injected by workflow
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      description: "POC 5 — API (create execution + status)",
    });

    blackboard.grantReadWriteData(apiFn);

    // ─────────────────────────────────────────────
    // API Gateway v2
    // ─────────────────────────────────────────────
    const httpApi = new apigw.HttpApi(this, "Api", {
      apiName: `cawnex-poc5-${stage}`,
      description: "POC 5 — Async Murder API",
      corsPreflight: {
        allowOrigins: ["*"],
        allowMethods: [
          apigw.CorsHttpMethod.POST,
          apigw.CorsHttpMethod.GET,
          apigw.CorsHttpMethod.OPTIONS,
        ],
        allowHeaders: ["Content-Type"],
      },
    });

    const apiIntegration = new apigwIntegrations.HttpLambdaIntegration(
      "ApiIntegration",
      apiFn
    );

    httpApi.addRoutes({
      path: "/murder",
      methods: [apigw.HttpMethod.POST],
      integration: apiIntegration,
    });

    httpApi.addRoutes({
      path: "/murder/{id}",
      methods: [apigw.HttpMethod.GET],
      integration: apiIntegration,
    });

    // ─────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "ApiEndpoint", {
      value: httpApi.apiEndpoint,
      description: "API base URL",
    });

    new cdk.CfnOutput(this, "CreateEndpoint", {
      value: `${httpApi.apiEndpoint}/murder`,
      description: "POST — create execution",
    });

    new cdk.CfnOutput(this, "StatusEndpoint", {
      value: `${httpApi.apiEndpoint}/murder/{execution_id}`,
      description: "GET — check execution status",
    });

    new cdk.CfnOutput(this, "BlackboardTable", {
      value: blackboard.tableName,
      description: "DynamoDB blackboard table (for local worker)",
    });

    new cdk.CfnOutput(this, "MurderFunctionName", {
      value: murderFn.functionName,
      description: "Murder Lambda",
    });

    new cdk.CfnOutput(this, "MurderLogGroup", {
      value: murderFn.logGroup.logGroupName,
      description: "Murder CloudWatch logs",
    });

    new cdk.CfnOutput(this, "ApiLogGroup", {
      value: apiFn.logGroup.logGroupName,
      description: "API CloudWatch logs",
    });
  }
}
