import pytest  # type: ignore

from .messages import Fax, FaxStatus, Webhook, WebhookPayload


def test_enqueue_fax(mocker):
    from .sqs import enqueue_fax

    mock_client = mocker.patch("app.helpers.sqs.client")

    fax = Fax(fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=5)

    enqueue_fax(fax)

    mock_client.send_message.assert_called_once_with(
        QueueUrl="fax-queue-url",
        MessageBody=fax.json_dumps(),
        MessageGroupId="b",
        MessageDeduplicationId="a",
    )


def test_enqueue_retry(mocker):
    from .sqs import enqueue_retry

    mock_client = mocker.patch("app.helpers.sqs.client")

    fax = Fax(fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=5)

    enqueue_retry(fax)

    mock_client.send_message.assert_called_once_with(
        QueueUrl="retry-queue-url", MessageBody=fax.json_dumps(), DelaySeconds=100
    )


def test_enqueue_webhook(mocker):
    from .sqs import enqueue_webhook

    mock_client = mocker.patch("app.helpers.sqs.client")

    webhook = Webhook(
        callback_url="a",
        payload=WebhookPayload(
            fax_id="b", status=FaxStatus.SENT, message="c", timestamp=1590590198
        ),
    )

    enqueue_webhook(webhook)

    mock_client.send_message.assert_called_once_with(
        QueueUrl="webhook-queue-url", MessageBody=webhook.json_dumps(), DelaySeconds=0
    )
