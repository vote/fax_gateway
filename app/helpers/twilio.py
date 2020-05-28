import os

from twilio.rest import Client  # type: ignore

account_sid = os.environ["TWILIO_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]

PHONE_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]

client = Client(account_sid, auth_token)
