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
