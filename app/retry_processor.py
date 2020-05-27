from typing import Any

from app.helpers.messages import Fax
from app.helpers.sqs import enqueue_fax


# Take a fax record from the retry queue and sends it back to the fax queue
# to be retried
def handler(event: Any, context: Any) -> Any:
    # We set batchSize to 1 so there should always be 1 record
    assert len(event["Records"]) == 1
    record = event["Records"][0]

    fax_record = Fax.json_loads(record["body"])
    enqueue_fax(fax_record)
