import { Template } from "aws-cdk-lib/assertions";
import { synthCawnexStacks } from "./synth-helpers";

/**
 * L2 CDK constructs suffix their logical ID with an 8-character hash derived
 * from the construct's path in the tree. If that path ever changes — a
 * rename, a re-parent, moving construction order relative to a sibling —
 * the hash changes too, and CloudFormation treats the resource as a brand
 * new one: for stateful resources (databases, buckets, queues, key material,
 * filesystems, user pools) that means data loss on deploy.
 *
 * These are the automated falsifier for later restructure stages' "no
 * CloudFormation resource replacement" invariant: if a stage's refactor
 * changes any of the pinned IDs below, this suite fails loudly instead of
 * only being caught (or missed) during a real deploy.
 */
describe("stateful resource logical IDs (must never change silently)", () => {
  const { authStack, mainStack } = synthCawnexStacks();
  const authTemplate = Template.fromStack(authStack).toJSON();
  const mainTemplate = Template.fromStack(mainStack).toJSON();

  it("pins CawnexAuthStack's MainTable logical ID", () => {
    const resource = authTemplate.Resources.MainTable74195DAB;
    expect(resource.Type).toBe("AWS::DynamoDB::Table");
    expect(resource.Properties.TableName).toBe("cawnex-dev");
  });

  it("pins CawnexAuthStack's UserPool logical ID", () => {
    const resource = authTemplate.Resources.UserPool6BA7E5F2;
    expect(resource.Type).toBe("AWS::Cognito::UserPool");
    expect(resource.Properties.UserPoolName).toBe("cawnex-dev");
  });

  it("pins Cawnex main stack's ArtifactsBucket logical ID", () => {
    const resource = mainTemplate.Resources.ArtifactsBucket2AAC5544;
    expect(resource.Type).toBe("AWS::S3::Bucket");
  });

  it("pins Cawnex main stack's AssetsBucket logical ID", () => {
    const resource = mainTemplate.Resources.AssetsBucket5CB76180;
    expect(resource.Type).toBe("AWS::S3::Bucket");
  });

  it("pins Cawnex main stack's VaultKey logical ID", () => {
    const resource = mainTemplate.Resources.VaultKey6B75F33E;
    expect(resource.Type).toBe("AWS::KMS::Key");
  });

  it("pins Cawnex main stack's EventsTable logical ID", () => {
    const resource = mainTemplate.Resources.EventsTableD24865E5;
    expect(resource.Type).toBe("AWS::DynamoDB::Table");
    expect(resource.Properties.TableName).toBe("cawnex-events-dev");
  });

  it("pins Cawnex main stack's RepoFileSystem logical ID", () => {
    const resource = mainTemplate.Resources.RepoFileSystemF033F757;
    expect(resource.Type).toBe("AWS::EFS::FileSystem");
  });
});

describe("stateful resources use Delete policy on dev (cheap extra pin)", () => {
  const { authStack, mainStack } = synthCawnexStacks();
  const authTemplate = Template.fromStack(authStack).toJSON();
  const mainTemplate = Template.fromStack(mainStack).toJSON();

  const authResourceIds = ["MainTable74195DAB", "UserPool6BA7E5F2"];
  const mainResourceIds = [
    "ArtifactsBucket2AAC5544",
    "AssetsBucket5CB76180",
    "VaultKey6B75F33E",
    "EventsTableD24865E5",
    "RepoFileSystemF033F757",
  ];

  it.each(authResourceIds)(
    "auth stack resource %s has DeletionPolicy and UpdateReplacePolicy Delete on dev",
    (logicalId) => {
      const resource = authTemplate.Resources[logicalId];
      expect(resource.DeletionPolicy).toBe("Delete");
      expect(resource.UpdateReplacePolicy).toBe("Delete");
    }
  );

  it.each(mainResourceIds)(
    "main stack resource %s has DeletionPolicy and UpdateReplacePolicy Delete on dev",
    (logicalId) => {
      const resource = mainTemplate.Resources[logicalId];
      expect(resource.DeletionPolicy).toBe("Delete");
      expect(resource.UpdateReplacePolicy).toBe("Delete");
    }
  );
});
