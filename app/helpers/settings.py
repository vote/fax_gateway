import os

MAX_FAX_ATTEMPTS = int(os.environ["MAX_FAX_ATTEMPTS"])
BACKOFF_DELAY = int(os.environ["BACKOFF_DELAY"])

FAX_QUEUE_URL = os.environ["QUEUE_URL_FAX"]
WEBHOOK_QUEUE_URL = os.environ["QUEUE_URL_WEBHOOK"]
RETRY_QUEUE_URL = os.environ["QUEUE_URL_RETRY"]
