"""Reference ingest contract for the thesis; not a copy of deployed code.

Configure TELEMETRY_TABLE with a DynamoDB table whose string keys are
sensor_key (partition) and observed_at (sort). API Gateway supplies the
authenticated Lambda proxy event. Derived lags and psychrometry belong to ETL.
"""

import base64
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache

SURFACES = {"LEFT_WALL", "RIGHT_WALL", "BACK_WALL"}
POSITIONS = {"SO", "SE", "NO", "NE"}
NODES = {"N1", "N2", "N3", "N4"}
NUMERIC_FIELDS = (
    "X", "Y", "DS_TEMPERATURE", "DHT_TEMPERATURE", "DHT_HUMIDITY"
)


class InvalidSample(ValueError):
    pass


def response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def parse_observed_at(value):
    if not isinstance(value, str):
        raise InvalidSample("TIMESTAMP must be an ISO 8601 string")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidSample("Invalid TIMESTAMP") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise InvalidSample("TIMESTAMP requires an explicit UTC offset")
    return instant.astimezone(timezone.utc).isoformat(timespec="microseconds")


def validate_event(event):
    raw_body = event.get("body")
    if not isinstance(raw_body, str):
        raise InvalidSample("A JSON request body is required")
    if event.get("isBase64Encoded", False):
        try:
            raw_body = base64.b64decode(raw_body, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise InvalidSample("Invalid encoded request body") from exc
    try:
        data = json.loads(raw_body, parse_float=Decimal)
    except (ValueError, InvalidOperation) as exc:
        raise InvalidSample("Invalid JSON") from exc
    if not isinstance(data, dict):
        raise InvalidSample("The sample must be a JSON object")

    surface = data.get("SURFACE")
    position = data.get("SENSOR_POSITION")
    node = data.get("NODE_ID")
    if not isinstance(surface, str) or surface not in SURFACES:
        raise InvalidSample("Invalid SURFACE")
    if not isinstance(position, str) or position not in POSITIONS:
        raise InvalidSample("Invalid SENSOR_POSITION")
    if surface == "BACK_WALL":
        if node is not None:
            raise InvalidSample("BACK_WALL requires a null NODE_ID")
    elif not isinstance(node, str) or node not in NODES:
        raise InvalidSample("A lateral wall requires NODE_ID N1 to N4")

    observed_at = parse_observed_at(data.get("TIMESTAMP"))
    values = {}
    quality_flags = []
    for field in NUMERIC_FIELDS:
        value = data.get(field)
        if value is None and field not in {"X", "Y"}:
            values[field] = None
            quality_flags.append(field + "_missing")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            raise InvalidSample(field + " must be a finite JSON number")
        value = Decimal(value)
        if not value.is_finite():
            raise InvalidSample(field + " must be finite")
        values[field] = value

    humidity = values["DHT_HUMIDITY"]
    if humidity is not None and not Decimal(0) <= humidity <= Decimal(100):
        quality_flags.append("humidity_outside_physical_domain")

    period_id = data.get("MSR_PRD_ID")
    if period_id is not None:
        if isinstance(period_id, bool) or not isinstance(period_id, int):
            raise InvalidSample("MSR_PRD_ID must be an integer")
        if len(str(period_id)) != 14:
            raise InvalidSample("MSR_PRD_ID requires YYYYMMDDHHMMSS")
        try:
            datetime.strptime(str(period_id), "%Y%m%d%H%M%S")
        except ValueError as exc:
            raise InvalidSample("Invalid calendar value in MSR_PRD_ID") from exc

    return {
        "sensor_key": "|".join((surface, node or "-", position)),
        "observed_at": observed_at,
        "TIMESTAMP_ORIGINAL": data["TIMESTAMP"],
        "MSR_PRD_ID": period_id,
        "SURFACE": surface,
        "NODE_ID": node,
        "SENSOR_POSITION": position,
        **values,
        "temperature_unit": "degC",
        "humidity_unit": "percent",
        "coordinate_unit": "m",
        "quality_flags": quality_flags,
        "original_payload": raw_body,
    }


@lru_cache(maxsize=1)
def telemetry_table():
    # Import lazily so the validator can be reviewed without AWS credentials.
    import boto3

    return boto3.resource("dynamodb").Table(os.environ["TELEMETRY_TABLE"])


# BEGIN_METHOD_EXCERPT
def lambda_handler(event, context):
    try:
        sample = validate_event(event)
    except InvalidSample as exc:
        return response(400, {"error": str(exc)})

    sample["received_at"] = datetime.now(timezone.utc).isoformat()
    sample["request_id"] = getattr(context, "aws_request_id", "")

    try:
        telemetry_table().put_item(
            Item=sample,
            ConditionExpression=(
                "attribute_not_exists(#pk) AND attribute_not_exists(#sk)"
            ),
            ExpressionAttributeNames={
                "#pk": "sensor_key", "#sk": "observed_at"
            },
        )
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            return response(200, {"status": "already_recorded"})
        raise

    return response(201, {"status": "recorded"})
# END_METHOD_EXCERPT
