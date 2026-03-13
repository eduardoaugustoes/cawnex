import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigw from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwIntegrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as logs from "aws-cdk-lib/aws-logs";
import * as path from "path";

interface Poc1CrowStackProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
}

/**
 * POC 1 — MCP Crow on Lambda
 *
 * Validates: Can a crow run as an MCP server on Lambda
 * with Streamable HTTP transport via API Gateway v2?
 *
 * Resources:
 * - Lambda function (Python 3.12) — MCP server
 * - API Gateway v2 HTTP API — single POST /mcp route
 * - S3 bucket — session state (for future stateful calls)
 * - CloudWatch Log Group — observability
 */
export class Poc1CrowStack extends cdk.Stack {
  public readonly apiUrl: string;

  constructor(scope: Construct, id: string, props: Poc1CrowStackProps) {
    super(scope, id, props);

    const stage = props.stage;

    // ─────────────────────────────────────────────
    // S3 — Session State
    // ─────────────────────────────────────────────
    const sessionBucket = new s3.Bucket(this, "SessionState", {
      bucketName: `cawnex-poc1-sessions-${stage}-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(7),
          id: "expire-sessions",
        },
      ],
    });

    // ─────────────────────────────────────────────
    // Lambda — MCP Crow Server
    // ─────────────────────────────────────────────
    const crowFn = new lambda.Function(this, "CrowFunction", {
      functionName: `cawnex-poc1-crow-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../lambdas/poc1-crow")
      ),
      memorySize: 512,
      timeout: cdk.Duration.minutes(5),
      environment: {
        STAGE: stage,
        SESSION_BUCKET: sessionBucket.bucketName,
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      description: "POC 1 — MCP Crow server (stub)",
    });

    sessionBucket.grantReadWrite(crowFn);

    // ─────────────────────────────────────────────
    // API Gateway v2 — HTTP API
    // ─────────────────────────────────────────────
    const httpApi = new apigw.HttpApi(this, "CrowApi", {
      apiName: `cawnex-poc1-crow-${stage}`,
      description: "POC 1 — MCP Crow Streamable HTTP endpoint",
      corsPreflight: {
        allowOrigins: ["*"],
        allowMethods: [apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
        allowHeaders: ["Content-Type", "Authorization"],
      },
    });

    const crowIntegration = new apigwIntegrations.HttpLambdaIntegration(
      "CrowIntegration",
      crowFn
    );

    httpApi.addRoutes({
      path: "/mcp",
      methods: [apigw.HttpMethod.POST],
      integration: crowIntegration,
    });

    // ─────────────────────────────────────────────
    // Outputs — for testing and POC 3 wiring
    // ─────────────────────────────────────────────
    this.apiUrl = httpApi.apiEndpoint;

    new cdk.CfnOutput(this, "McpEndpoint", {
      value: `${httpApi.apiEndpoint}/mcp`,
      description: "MCP Streamable HTTP endpoint for the crow",
      exportName: `cawnex-poc1-mcp-endpoint-${stage}`,
    });

    new cdk.CfnOutput(this, "SessionBucketName", {
      value: sessionBucket.bucketName,
      description: "S3 bucket for crow session state",
    });

    new cdk.CfnOutput(this, "CrowFunctionName", {
      value: crowFn.functionName,
      description: "Lambda function name for the crow",
    });

    new cdk.CfnOutput(this, "CrowLogGroup", {
      value: crowFn.logGroup.logGroupName,
      description: "CloudWatch log group for observability",
    });
  }
}
