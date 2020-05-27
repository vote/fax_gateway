from app.helpers.messages import Fax

from .retry_processor import handler


def test_retry_processor(mocker):
    mock_enqueue_fax = mocker.patch("app.retry_processor.enqueue_fax")

    fax = Fax(fax_id="a", to="b", pdf_url="c", callback_url="d", retry_count=9)

    handler({"Records": [{"body": fax.json_dumps()}]}, {})

    mock_enqueue_fax.assert_called_with(fax)
