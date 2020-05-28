from typing import Any

import requests

from app.helpers.messages import Webhook


# Take a webhook record from the queue and try to send it to the calling
# application
def handler(event: Any, context: Any) -> Any:
    # We set batchSize to 1 so there should always be 1 record
    assert len(event["Records"]) == 1
    record = event["Records"][0]

    webhook = Webhook.json_loads(record["body"])

    response = requests.post(
        webhook.callback_url,
        data=webhook.payload.json_dumps(),
        headers={"Content-Type": "application/json"},
    )

    response.raise_for_status()
