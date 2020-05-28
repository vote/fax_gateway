from unittest import mock

from freezegun import freeze_time  # type: ignore

from .fax_processor import handler, poll_until_fax_delivered
from .helpers.messages import Fax, FaxStatus, Webhook, WebhookPayload


def mock_client(mocker, statuses):
    next_status = 0

    def mock_fetch():
        nonlocal next_status

        ret = mock.MagicMock()
        ret.status = statuses[next_status]

        next_status += 1

        return ret

    def mock_faxes(fax_sid):
        assert fax_sid == "mock-sid"

        fax = mock.MagicMock()
        fax.fetch.side_effect = mock_fetch

        return fax

    mock_client = mocker.patch("app.fax_processor.client")
    mock_client.fax.faxes.side_effect = mock_faxes
    mock_client.fax.faxes.create.return_value = mock.Mock(sid="mock-sid")

    return mock_client


def test_poll_until_fax_delivered_success(mocker):
    statuses = ["queued", "processing", "sending", "delivered"]
    client = mock_client(mocker, statuses)

    mock_time = mocker.patch("app.fax_processor.time")

    assert poll_until_fax_delivered("mock-sid") == "delivered"
    mock_time.sleep.assert_has_calls([mock.call(15), mock.call(15), mock.call(15)])


def test_poll_until_fax_delivered_failure(mocker):
    statuses = ["queued", "processing", "sending", "busy"]
    client = mock_client(mocker, statuses)

    mock_time = mocker.patch("app.fax_processor.time")

    assert poll_until_fax_delivered("mock-sid") == "busy"
    mock_time.sleep.assert_has_calls([mock.call(15), mock.call(15), mock.call(15)])


def test_fax_success(mocker):
    mock_client(mocker, ["delivered"])
    mock_enqueue_webhook = mocker.patch("app.fax_processor.enqueue_webhook")

    handler(
        {
            "Records": [
                {
                    "body": Fax(
                        fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=0
                    ).json_dumps()
                }
            ]
        },
        {},
    )

    mock_enqueue_webhook.assert_called_with(
        Webhook(
            callback_url="d",
            payload=WebhookPayload(
                fax_id="a", status=FaxStatus.SENT, message="Fax sent successfully"
            ),
        )
    )


@freeze_time("2012-01-14 05:06:07 UTC")
def test_fax_temp_failure(mocker):
    mock_client(mocker, ["failed"])
    mock_enqueue_webhook = mocker.patch("app.fax_processor.enqueue_webhook")
    mock_enqueue_retry = mocker.patch("app.fax_processor.enqueue_retry")

    handler(
        {
            "Records": [
                {
                    "body": Fax(
                        fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=8
                    ).json_dumps()
                }
            ]
        },
        {},
    )

    mock_enqueue_webhook.assert_called_with(
        Webhook(
            callback_url="d",
            payload=WebhookPayload(
                fax_id="a",
                status=FaxStatus.TEMPORARY_FAILURE,
                message="Failed to deliver fax (attempt 9 of 10). Fax status: failed",
            ),
        )
    )

    mock_enqueue_retry.assert_called_with(
        Fax(fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=9)
    )


@freeze_time("2012-01-14 05:06:07 UTC")
def test_fax_perm_failure(mocker):
    mock_client(mocker, ["busy"])
    mock_enqueue_webhook = mocker.patch("app.fax_processor.enqueue_webhook")

    handler(
        {
            "Records": [
                {
                    "body": Fax(
                        fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=9
                    ).json_dumps()
                }
            ]
        },
        {},
    )

    mock_enqueue_webhook.assert_called_with(
        Webhook(
            callback_url="d",
            payload=WebhookPayload(
                fax_id="a",
                status=FaxStatus.PERMANENT_FAILURE,
                message="Failed to deliver fax after 10 tries. Last attempt status: busy",
            ),
        )
    )
