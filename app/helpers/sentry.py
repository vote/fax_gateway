import os

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

sentry_sdk.init(
    dsn=os.environ["SENTRY_DSN"],
    environment=os.environ["SENTRY_ENVIRONMENT"],
    integrations=[AwsLambdaIntegration()],
)
