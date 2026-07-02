"""File processor Lambda — extracts text from uploaded files.

Triggered by:
1. S3 events (direct upload notification)
2. DynamoDB Stream (when PROCESS# record is written with status=pending)

Writes:
- Extracted text to S3: .../extracted/{filename}.txt
- CTX#{human_task_id} record in DynamoDB (for Crow {{context:...}} resolution)
- Updates PROCESS# record status to completed/failed
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3


TABLE_NAME = os.environ.get("TABLE_NAME", "cawnex")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Route to S3 or DynamoDB Stream handler."""
    s3 = boto3.client("s3")
    table = boto3.resource("dynamodb").Table(TABLE_NAME)

    processed = 0

    for record in event.get("Records", []):
        if "s3" in record:
            # S3 event trigger
            result = _handle_s3_event(record, s3, table)
            if result:
                processed += 1

        elif "dynamodb" in record:
            # DynamoDB Stream trigger (PROCESS# record written)
            result = _handle_stream_event(record, s3, table)
            if result:
                processed += 1

    return {"processed": processed}


def _handle_s3_event(
    record: dict[str, Any],
    s3: Any,
    table: Any,
) -> bool:
    """Process a file uploaded directly via S3 event."""
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]

    if not _is_processable(key):
        return False

    return _process_file(bucket, key, s3, table)


def _handle_stream_event(
    record: dict[str, Any],
    s3: Any,
    table: Any,
) -> bool:
    """Process a PROCESS# record from DynamoDB Stream."""
    event_name = record.get("eventName", "")
    if event_name != "INSERT":
        return False

    new_image = record.get("dynamodb", {}).get("NewImage")
    if not new_image:
        return False

    # Deserialize DynamoDB stream format
    item = _deserialize_stream(new_image)

    sk = item.get("SK", "")
    if not sk.startswith("PROCESS#"):
        return False

    if item.get("status") != "pending":
        return False

    source = item.get("source", "")
    if not source.startswith("s3://"):
        return False

    # Parse s3://bucket/key
    s3_path = source[5:]
    slash_idx = s3_path.index("/")
    bucket = s3_path[:slash_idx]
    key = s3_path[slash_idx + 1:]
    pk = item.get("PK", "")
    process_sk = sk

    success = _process_file(bucket, key, s3, table)

    # Update PROCESS# record status
    table.update_item(
        Key={"PK": pk, "SK": process_sk},
        UpdateExpression="SET #s = :s, #ca = :ca",
        ExpressionAttributeNames={"#s": "status", "#ca": "completed_at"},
        ExpressionAttributeValues={
            ":s": "completed" if success else "failed",
            ":ca": _now_iso(),
        },
    )

    return success


def _process_file(
    bucket: str,
    key: str,
    s3: Any,
    table: Any,
) -> bool:
    """Download, extract text, store in S3 and DynamoDB."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        file_bytes = response["Body"].read()
    except Exception:
        return False

    extracted_text = _extract_text(key, file_bytes)
    if not extracted_text:
        return False

    # Store extracted text back to S3
    dir_part, filename = key.rsplit("/", 1) if "/" in key else ("", key)
    base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
    extracted_path = f"{dir_part}/extracted/{base_name}.txt" if dir_part else f"extracted/{base_name}.txt"

    s3.put_object(
        Bucket=bucket,
        Key=extracted_path,
        Body=extracted_text.encode("utf-8"),
        ContentType="text/plain",
    )

    # Write CTX# record from S3 key path: T/{tenant}/P/{project}/assets/{ht_id}/{filename}
    path_parts = key.split("/")
    if len(path_parts) >= 6:
        tenant = path_parts[1]
        project = path_parts[3]
        ht_id = path_parts[5]
        pk = f"T#{tenant}#P#{project}"
        ctx_sk = f"CTX#{ht_id}"

        table.put_item(Item={
            "PK": pk,
            "SK": ctx_sk,
            "content": extracted_text[:50000],
            "source": key,
            "created_at": _now_iso(),
            "entityType": "Context",
        })

    return True


def _is_processable(key: str) -> bool:
    """Check if the file type is supported for text extraction."""
    lower = key.lower()
    return lower.endswith(".pdf") or lower.endswith(".txt") or lower.endswith(".md")


def _extract_text(key: str, file_bytes: bytes) -> str:
    """Extract text based on file type."""
    lower = key.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf_text(file_bytes)
    if lower.endswith(".txt") or lower.endswith(".md"):
        return file_bytes.decode("utf-8", errors="replace")
    return ""


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyPDF2."""
    try:
        import io

        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        return "(PyPDF2 not available — text extraction skipped)"
    except Exception as e:
        return f"(Error extracting text: {e})"


def _deserialize_stream(image: dict[str, Any]) -> dict[str, Any]:
    """Minimal DynamoDB stream deserializer for string/number/map types."""
    result: dict[str, Any] = {}
    for key, typed_value in image.items():
        if "S" in typed_value:
            result[key] = typed_value["S"]
        elif "N" in typed_value:
            result[key] = typed_value["N"]
        elif "M" in typed_value:
            result[key] = _deserialize_stream(typed_value["M"])
        elif "L" in typed_value:
            result[key] = [_deserialize_stream({"v": v})["v"] for v in typed_value["L"]]
        elif "BOOL" in typed_value:
            result[key] = typed_value["BOOL"]
        elif "NULL" in typed_value:
            result[key] = None
    return result
