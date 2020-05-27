import logging
import time
from typing import Any

from sentry_sdk import capture_exception

from app.helpers.messages import Fax, FaxStatus, Webhook, WebhookPayload
from app.helpers.settings import MAX_FAX_ATTEMPTS
from app.helpers.sqs import enqueue_retry, enqueue_webhook
from app.helpers.twilio import PHONE_NUMBER, client

# Twilio fax status codes indicating still-in-progress or success -- all other
# codes are considered failures.
#
# https://www.twilio.com/docs/fax/api/fax-resource
TWILIO_STATUS_PENDING = ("queued", "processing", "sending")
TWILIO_STATUS_SUCCESS = ("delivered",)

# How frequently to poll for fax status, in seconds
TWILIO_POLL_INTERVAL = 15

# Given a Twilio fax ID, polls for status
def poll_until_fax_delivered(fax_sid: str) -> Any:
    while True:
        try:
            fax = client.fax.faxes(fax_sid).fetch()
        except Exception as e:
            # If there was an error getting the fax status, just log it and
            # keep polling -- we don't want to let a transient error cause
            # the whole lambda function to fail.
            capture_exception(e)
            logging.exception("Error while polling for fax status")

        if fax.status not in TWILIO_STATUS_PENDING:
            return fax.status

        print(f"Fax has pending status: {fax.status}, waiting")
        time.sleep(TWILIO_POLL_INTERVAL)


# Take a fax record from the queue and send it to Twilio. Poll for
# success/failure.
def handler(event: Any, context: Any) -> Any:
    # We set batchSize to 1 so there should always be 1 record
    assert len(event["Records"]) == 1
    record = event["Records"][0]
    fax_record = Fax.json_loads(record["body"])

    print("Sending fax", fax_record)

    # Send the fax to Twilio
    twilio_fax = client.fax.faxes.create(
        from_=PHONE_NUMBER,
        to=fax_record.to,
        media_url=fax_record.pdf_url,
        # Our faxes can contain PII -- instruct Twilio to not retain a copy of
        # the PDF.
        store_media=False,
        # Fail fast (after 5 minutes) rather than leaving the fax queued -- we
        # have our own retry logic, and this lambda function times out after 15
        # minutes so we'd rather gracefully handle the failure ourselves rather
        # than have Twilio hold it in their queue for a long time.
        ttl=5,
    )

    # Wait for status
    fax_status = poll_until_fax_delivered(twilio_fax.sid)
    print(f"Fax final status: {fax_status}")

    if fax_status in TWILIO_STATUS_SUCCESS:
        # Fax was sent! Queue a webhook to deliver the success notification
        print("Fax successful; enqueueing success webhook")
        try:
            enqueue_webhook(
                Webhook(
                    callback_url=fax_record.callback_url,
                    payload=WebhookPayload(
                        fax_id=fax_record.fax_id,
                        status=FaxStatus.SENT,
                        message="Fax sent successfully",
                    ),
                )
            )
        except Exception as e:
            # If there was an error queueing the webhook notification, we
            # just log that and don't error -- we don't want to fail, because
            # that will retry and re-send the fax. We'd rather just fail to
            # send the webhook than duplicate-send faxes.
            capture_exception(e)
            logging.exception("Error enqueueing webhook")
    elif fax_record.retry_count + 1 >= MAX_FAX_ATTEMPTS:
        # We're out of retry attempts. Report a failure to the application.
        print("Fax failed and no more retries available; enqueueing failure webhook")
        enqueue_webhook(
            Webhook(
                callback_url=fax_record.callback_url,
                payload=WebhookPayload(
                    fax_id=fax_record.fax_id,
                    status=FaxStatus.PERMANENT_FAILURE,
                    message=f"Failed to deliver fax after {MAX_FAX_ATTEMPTS} tries. Last attempt status: {fax_status}",
                ),
            )
        )
    else:
        # Fax failed to send, but nevertheless we persist. Queue a webhook to
        # deliver a failure notification and also queue up a retry.
        #
        # We enqueue the retry *second* -- if we did it first, and then failed
        # to enqueue the webhook, we'd end up with a duplicate because this
        # function would error, the job would be retried by the queue, *and*
        # we'd have written the job to the retry queue.
        print(
            f"Fax failed (attempt {fax_record.retry_count + 1} of {MAX_FAX_ATTEMPTS}); enqueuing failure webhook and retry"
        )

        enqueue_webhook(
            Webhook(
                callback_url=fax_record.callback_url,
                payload=WebhookPayload(
                    fax_id=fax_record.fax_id,
                    status=FaxStatus.TEMPORARY_FAILURE,
                    message=f"Failed to deliver fax (attempt {fax_record.retry_count + 1} of {MAX_FAX_ATTEMPTS}). Fax status: {fax_status}",
                ),
            )
        )

        enqueue_retry(
            Fax(
                fax_id=fax_record.fax_id,
                to=fax_record.to,
                pdf_url=fax_record.pdf_url,
                callback_url=fax_record.callback_url,
                retry_count=fax_record.retry_count + 1,
            )
        )
