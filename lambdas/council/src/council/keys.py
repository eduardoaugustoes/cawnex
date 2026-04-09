"""Key builders for council DynamoDB records."""


def build_pk(tenant: str, project: str) -> str:
    return f"T#{tenant}#P#{project}"


def extract_tenant(pk: str) -> str:
    return pk.split("#")[1]


def extract_project(pk: str) -> str:
    return pk.split("#")[3]
