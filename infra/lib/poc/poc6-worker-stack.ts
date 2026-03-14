import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as efs from "aws-cdk-lib/aws-efs";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as logs from "aws-cdk-lib/aws-logs";
import * as lambdaEvents from "aws-cdk-lib/aws-lambda-event-sources";
import * as iam from "aws-cdk-lib/aws-iam";

interface Poc6WorkerStackProps extends cdk.StackProps {
  stage: "dev" | "staging" | "prod";
}

/**
 * POC 6 — Worker Lambda + EFS + Worktrees
 *
 * Worker runs inside VPC with EFS for persistent repo storage.
 * Uses Docker image with git + gh CLI.
 * Triggered by DynamoDB Streams (TASK records with status=pending).
 *
 * Resources:
 * - VPC (2 AZs, private + public subnets)
 * - NAT Instance (t4g.nano, ~$3/mth)
 * - EFS filesystem + access point
 * - ECR repository (Docker image)
 * - Worker Lambda (Docker, VPC, EFS)
 * - VPC Gateway Endpoint for DynamoDB ($0)
 */
export class Poc6WorkerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Poc6WorkerStackProps) {
    super(scope, id, props);

    const stage = props.stage;

    // ─────────────────────────────────────────────
    // Reference existing blackboard from POC 5
    // ─────────────────────────────────────────────
    const blackboardTableName = `cawnex-poc5-blackboard-${stage}`;

    // Stream ARN passed as CDK context (looked up at deploy time)
    const blackboardStreamArn =
      (this.node.tryGetContext("blackboardStreamArn") as string) ||
      `arn:aws:dynamodb:${this.region}:${this.account}:table/${blackboardTableName}/stream/*`;

    const blackboard = dynamodb.Table.fromTableAttributes(this, "Blackboard", {
      tableName: blackboardTableName,
      tableStreamArn: blackboardStreamArn,
      globalIndexes: [],
    });

    // ─────────────────────────────────────────────
    // VPC — 2 AZs, public + private subnets
    // ─────────────────────────────────────────────
    const vpc = new ec2.Vpc(this, "WorkerVpc", {
      vpcName: `cawnex-poc6-vpc-${stage}`,
      maxAzs: 2,
      natGateways: 0, // We'll use a NAT Instance instead
      subnetConfiguration: [
        {
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: "Private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
      ],
    });

    // ─────────────────────────────────────────────
    // NAT Instance (t4g.nano ~$3/mth)
    // ─────────────────────────────────────────────
    const _natInstance = new ec2.NatInstanceProviderV2({
      // TODO: Integrate with VPC configuration
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T4G,
        ec2.InstanceSize.NANO
      ),
      defaultAllowedTraffic: ec2.NatTrafficDirection.OUTBOUND_ONLY,
    });

    // Attach NAT instance to VPC private subnets
    // CDK v2 requires configuring NAT in VPC — we need a workaround
    // since natGateways=0. We'll add routes manually.
    const natSg = new ec2.SecurityGroup(this, "NatSg", {
      vpc,
      description: "NAT Instance security group",
      allowAllOutbound: true,
    });
    natSg.addIngressRule(
      ec2.Peer.ipv4(vpc.vpcCidrBlock),
      ec2.Port.allTraffic(),
      "Allow VPC traffic"
    );

    const natAmi = ec2.MachineImage.latestAmazonLinux2023({
      cpuType: ec2.AmazonLinuxCpuType.ARM_64,
    });

    // Force replacement when user data changes (v2 = NAT interface fix)
    const natEc2 = new ec2.Instance(this, "NatInstanceV2", {
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T4G,
        ec2.InstanceSize.NANO
      ),
      machineImage: natAmi,
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroup: natSg,
      sourceDestCheck: false,
      associatePublicIpAddress: true,
    });

    // Enable IP forwarding + NAT (auto-detect interface name)
    natEc2.addUserData(
      "yum install iptables-services -y",
      "systemctl enable iptables",
      "systemctl start iptables",
      "echo 'net.ipv4.ip_forward = 1' > /etc/sysctl.d/custom-ip-forwarding.conf",
      "sysctl -p /etc/sysctl.d/custom-ip-forwarding.conf",
      "IFACE=$(ip route show default | awk '{print $5}')",
      "iptables -t nat -A POSTROUTING -o $IFACE -j MASQUERADE",
      "iptables -F FORWARD",
      "service iptables save"
    );

    // Route private subnet traffic through NAT instance
    vpc.privateSubnets.forEach((subnet, i) => {
      new ec2.CfnRoute(this, `NatRoute${i}`, {
        routeTableId: subnet.routeTable.routeTableId,
        destinationCidrBlock: "0.0.0.0/0",
        instanceId: natEc2.instanceId,
      });
    });

    // ─────────────────────────────────────────────
    // VPC Gateway Endpoint — DynamoDB ($0)
    // ─────────────────────────────────────────────
    vpc.addGatewayEndpoint("DynamoDbEndpoint", {
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
    });

    // ─────────────────────────────────────────────
    // EFS — Persistent repo storage
    // ─────────────────────────────────────────────
    const fileSystem = new efs.FileSystem(this, "RepoFs", {
      vpc,
      fileSystemName: `cawnex-poc6-repos-${stage}`,
      performanceMode: efs.PerformanceMode.GENERAL_PURPOSE,
      throughputMode: efs.ThroughputMode.BURSTING,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    const accessPoint = fileSystem.addAccessPoint("ReposAccessPoint", {
      path: "/repos",
      createAcl: {
        ownerGid: "1000",
        ownerUid: "1000",
        permissions: "755",
      },
      posixUser: {
        gid: "1000",
        uid: "1000",
      },
    });

    // ─────────────────────────────────────────────
    // ECR — Import existing repository (created before CDK deploy)
    // ─────────────────────────────────────────────
    const repository = ecr.Repository.fromRepositoryName(
      this,
      "WorkerRepo",
      `cawnex-poc6-worker-${stage}`
    );

    // ─────────────────────────────────────────────
    // Worker Lambda (Docker)
    // ─────────────────────────────────────────────
    const workerFn = new lambda.DockerImageFunction(this, "WorkerFunction", {
      functionName: `cawnex-poc6-worker-${stage}`,
      code: lambda.DockerImageCode.fromEcr(repository, {
        tagOrDigest: "latest",
      }),
      memorySize: 1024,
      timeout: cdk.Duration.minutes(15),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      filesystem: lambda.FileSystem.fromEfsAccessPoint(
        accessPoint,
        "/mnt/repos"
      ),
      environment: {
        STAGE: stage,
        BLACKBOARD_TABLE: blackboardTableName,
        ANTHROPIC_MODEL: "claude-sonnet-4-20250514",
        EFS_MOUNT: "/mnt/repos",
        // GITHUB_TOKEN and ANTHROPIC_AUTH_TOKEN injected by workflow
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
      description: "POC 6 — Worker (Docker + EFS + git worktrees)",
    });

    // Allow Lambda to access EFS
    fileSystem.connections.allowDefaultPortFrom(workerFn);

    // DynamoDB permissions
    blackboard.grantReadWriteData(workerFn);

    // Grant stream read permissions
    workerFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "dynamodb:DescribeStream",
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:ListStreams",
        ],
        resources: [blackboardStreamArn],
      })
    );

    // DynamoDB Stream trigger — filter for TASK records
    workerFn.addEventSource(
      new lambdaEvents.DynamoEventSource(blackboard, {
        startingPosition: lambda.StartingPosition.LATEST,
        batchSize: 1,
        retryAttempts: 2,
        filters: [
          lambda.FilterCriteria.filter({
            eventName: lambda.FilterRule.isEqual("INSERT"),
            dynamodb: {
              NewImage: {
                SK: {
                  S: lambda.FilterRule.exists(),
                },
                status: {
                  S: lambda.FilterRule.isEqual("pending"),
                },
              },
            },
          }),
        ],
      })
    );

    // ─────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────
    new cdk.CfnOutput(this, "WorkerFunctionName", {
      value: workerFn.functionName,
      description: "Worker Lambda function name",
    });

    new cdk.CfnOutput(this, "WorkerLogGroup", {
      value: workerFn.logGroup.logGroupName,
      description: "Worker CloudWatch log group",
    });

    new cdk.CfnOutput(this, "EfsFileSystemId", {
      value: fileSystem.fileSystemId,
      description: "EFS filesystem ID",
    });

    new cdk.CfnOutput(this, "EcrRepositoryUri", {
      value: repository.repositoryUri,
      description: "ECR repository URI (for docker push)",
    });

    new cdk.CfnOutput(this, "VpcId", {
      value: vpc.vpcId,
      description: "VPC ID",
    });

    new cdk.CfnOutput(this, "NatInstanceId", {
      value: natEc2.instanceId,
      description: "NAT Instance ID (stop to save cost when not testing)",
    });
  }
}
