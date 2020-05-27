from typing import Optional

import boto3
from botocore.config import Config  # type: ignore
from mypy_boto3 import sqs

from .messages import Fax, Webhook
from .settings import BACKOFF_DELAY, FAX_QUEUE_URL, RETRY_QUEUE_URL, WEBHOOK_QUEUE_URL

client: sqs.SQSClient = boto3.client(
    "sqs", config=Config(retries={"max_attempts": 10, "mode": "standard"})
)


def _enqueue_regular(queue_url: str, body: str, delay_seconds: Optional[int] = 0):
    client.send_message(
        QueueUrl=queue_url, MessageBody=body, DelaySeconds=delay_seconds
    )


def _enqueue_fifo(queue_url: str, body: str, message_group: str, deduplication_id: str):
    client.send_message(
        QueueUrl=queue_url,
        MessageBody=body,
        MessageGroupId=message_group,
        MessageDeduplicationId=deduplication_id,
    )


def enqueue_fax(fax: Fax):
    _enqueue_fifo(
        FAX_QUEUE_URL,
        fax.json_dumps(),
        message_group=fax.to,
        deduplication_id=fax.fax_id,
    )


def enqueue_retry(fax: Fax):
    _enqueue_regular(RETRY_QUEUE_URL, fax.json_dumps(), delay_seconds=BACKOFF_DELAY)


def enqueue_webhook(webhook: Webhook):
    _enqueue_regular(WEBHOOK_QUEUE_URL, webhook.json_dumps())
