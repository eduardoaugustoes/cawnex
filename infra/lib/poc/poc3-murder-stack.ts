import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigw from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwIntegrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as logs from "aws-cdk-lib/aws-logs";
import * as path from "path";

interface Poc3MurderStackProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
}

/**
 * POC 3 — Murder as MCP Client + LLM Judge
 *
 * Validates: Can Murder orchestrate crows via MCP,
 * judge their output with Claude, and drive the blackboard loop?
 *
 * Resources:
 * - DynamoDB table (blackboard)
 * - Lambda function (Murder — MCP client + LLM judge)
 * - API Gateway v2 (trigger endpoint)
 * - CloudWatch Log Group (observability)
 *
 * Depends on: POC 1 (crow MCP endpoint)
 */
export class Poc3MurderStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Poc3MurderStackProps) {
    super(scope, id, props);

    const stage = props.stage;

    // Import POC 1 crow endpoint from its stack output
    const crowMcpEndpoint = cdk.Fn.importValue(
      `cawnex-poc1-mcp-endpoint-${stage}`
    );

    // ─────────────────────────────────────────────
    // DynamoDB — Blackboard
    // ─────────────────────────────────────────────
    const blackboard = new dynamodb.Table(this, "Blackboard", {
      tableName: `cawnex-blackboard-${stage}`,
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: "ttl",
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    // ─────────────────────────────────────────────
    // Lambda — Murder
    // ─────────────────────────────────────────────
    const murderFn = new lambda.Function(this, "MurderFunction", {
      functionName: `cawnex-poc3-murder-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../lambdas/poc3-murder")
      ),
      memorySize: 512,
      timeout: cdk.Duration.minutes(14), // Just under Lambda max
      environment: {
        STAGE: stage,
        CROW_MCP_ENDPOINT: crowMcpEndpoint,
        BLACKBOARD_TABLE: blackboard.tableName,
        ANTHROPIC_MODEL: "claude-sonnet-4-20250514",
        MAX_STEPS: "10",
        // ANTHROPIC_API_KEY and GITHUB_TOKEN set via console or Secrets Manager
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      description: "POC 3 — Murder orchestrator (MCP client + LLM judge)",
    });

    blackboard.grantReadWriteData(murderFn);

    // ─────────────────────────────────────────────
    // API Gateway v2 — Trigger endpoint
    // ─────────────────────────────────────────────
    const httpApi = new apigw.HttpApi(this, "MurderApi", {
      apiName: `cawnex-poc3-murder-${stage}`,
      description: "POC 3 — Murder trigger endpoint",
      corsPreflight: {
        allowOrigins: ["*"],
        allowMethods: [apigw.CorsHttpMethod.POST],
        allowHeaders: ["Content-Type"],
      },
    });

    const murderIntegration = new apigwIntegrations.HttpLambdaIntegration(
      "MurderIntegration",
      murderFn
    );

    httpApi.addRoutes({
      path: "/murder",
      methods: [apigw.HttpMethod.POST],
      integration: murderIntegration,
    });

    // ─────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "MurderEndpoint", {
      value: `${httpApi.apiEndpoint}/murder`,
      description: "POST endpoint to trigger Murder (body: {repo, issue_number})",
    });

    new cdk.CfnOutput(this, "BlackboardTableName", {
      value: blackboard.tableName,
      description: "DynamoDB blackboard table",
    });

    new cdk.CfnOutput(this, "MurderFunctionName", {
      value: murderFn.functionName,
      description: "Murder Lambda function name",
    });

    new cdk.CfnOutput(this, "MurderLogGroup", {
      value: murderFn.logGroup.logGroupName,
      description: "CloudWatch log group for Murder observability",
    });

    new cdk.CfnOutput(this, "CrowEndpointUsed", {
      value: crowMcpEndpoint,
      description: "Crow MCP endpoint (imported from POC 1)",
    });
  }
}
