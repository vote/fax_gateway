import pytest  # type: ignore
import requests
import responses  # type: ignore

from app.helpers.messages import FaxStatus, Webhook, WebhookPayload

from .webhook_processor import handler


@responses.activate
def test_webhook_processor_success(mocker):
    responses.add(responses.POST, "http://example.org/abc", status=200)

    webhook = Webhook(
        callback_url="http://example.org/abc",
        payload=WebhookPayload(
            fax_id="b", status=FaxStatus.SENT, message="c", timestamp=1590590198
        ),
    )

    handler({"Records": [{"body": webhook.json_dumps()}]}, {})

    assert responses.calls[0].request.body == webhook.payload.json_dumps()


@responses.activate
def test_webhook_processor_failure(mocker):
    responses.add(responses.POST, "http://example.org/abc", status=500)

    webhook = Webhook(
        callback_url="http://example.org/abc",
        payload=WebhookPayload(
            fax_id="b", status=FaxStatus.SENT, message="c", timestamp=1590590198
        ),
    )

    with pytest.raises(requests.exceptions.HTTPError):
        handler({"Records": [{"body": webhook.json_dumps()}]}, {})
