import json

from freezegun import freeze_time  # type: ignore

from .messages import Fax, FaxStatus, Webhook, WebhookPayload


def test_fax():
    # load
    assert (
        Fax.json_loads(
            """
            {
                "fax_id": "a",
                "to": "b",
                "pdf_url": "c",
                "callback_url": "d",
                "retry_count": 5
            }
            """
        )
        == Fax(fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=5)
    )

    # load, default retry count
    assert (
        Fax.json_loads(
            """
            {
                "fax_id": "a",
                "to": "b",
                "pdf_url": "c",
                "callback_url": "d"
            }
            """
        )
        == Fax(fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=0)
    )

    # dump
    assert json.loads(
        Fax(
            fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=5
        ).json_dumps()
    ) == {
        "fax_id": "a",
        "to": "b",
        "pdf_url": "c",
        "callback_url": "d",
        "retry_count": 5,
    }

    # symmetry
    fax = Fax(fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=5)
    assert fax == Fax.json_loads(fax.json_dumps())


@freeze_time("2012-01-14 05:06:07 UTC")
def test_webhook():
    now = 1326517567

    # load
    assert (
        Webhook.json_loads(
            """
            {
                "callback_url": "a",
                "payload": {
                    "fax_id": "b",
                    "status": "sent",
                    "message": "c",
                    "timestamp": 1590590198
                }
            }
            """
        )
        == Webhook(
            callback_url="a",
            payload=WebhookPayload(
                fax_id="b", status=FaxStatus.SENT, message="c", timestamp=1590590198
            ),
        )
    )

    # load, default timestamp
    assert (
        Webhook.json_loads(
            """
            {
                "callback_url": "a",
                "payload": {
                    "fax_id": "b",
                    "status": "tmp_fail",
                    "message": "c"
                }
            }
            """
        )
        == Webhook(
            callback_url="a",
            payload=WebhookPayload(
                fax_id="b",
                status=FaxStatus.TEMPORARY_FAILURE,
                message="c",
                timestamp=now,
            ),
        )
    )

    # dump
    assert json.loads(
        Webhook(
            callback_url="a",
            payload=WebhookPayload(
                fax_id="b", status=FaxStatus.PERMANENT_FAILURE, message="c"
            ),
        ).json_dumps()
    ) == {
        "callback_url": "a",
        "payload": {
            "fax_id": "b",
            "status": "perm_fail",
            "message": "c",
            "timestamp": now,
        },
    }

    # symmetry
    webhook = Webhook(
        callback_url="a",
        payload=WebhookPayload(
            fax_id="b", status=FaxStatus.SENT, message="c", timestamp=1590590198
        ),
    )
    assert webhook == Webhook.json_loads(webhook.json_dumps())
