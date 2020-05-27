"""
Type-safe Dataclasses representing each kind of message that we send over SQS.

We wrap dataclasses_json's methods with type-safe wrappers:
https://github.com/lidatong/dataclasses-json/issues/23
"""

import time
from dataclasses import dataclass, field
from enum import Enum

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class Fax:
    fax_id: str
    to: str
    pdf_url: str
    callback_url: str
    retry_count: int = 0

    @classmethod
    def json_loads(cls, json: str) -> "Fax":
        return cls.from_json(json)  # type: ignore

    def json_dumps(self) -> str:
        return self.to_json()  # type: ignore


class FaxStatus(Enum):
    SENT = "sent"
    TEMPORARY_FAILURE = "tmp_fail"
    PERMANENT_FAILURE = "perm_fail"


@dataclass_json
@dataclass
class WebhookPayload:
    fax_id: str
    status: FaxStatus
    message: str
    timestamp: int = field(default_factory=lambda: int(time.time()))

    @classmethod
    def json_loads(cls, json: str) -> "WebhookPayload":
        return cls.from_json(json)  # type: ignore

    def json_dumps(self) -> str:
        return self.to_json()  # type: ignore


@dataclass_json
@dataclass
class Webhook:
    callback_url: str
    payload: WebhookPayload

    @classmethod
    def json_loads(cls, json: str) -> "Webhook":
        return cls.from_json(json)  # type: ignore

    def json_dumps(self) -> str:
        return self.to_json()  # type: ignore
