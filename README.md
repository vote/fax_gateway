# Fax Gateway

The VoteAmerica fax gateway is a serverless application that is designed to reliably send large volumes of faxes.

Learn more about the Fax Gateway in [this Twilio Blog post](https://www.twilio.com/blog/reliable-fax-pipeline-twilio-aws-expand-access-ballot-box).

## Problem Statement

The fax gateway sites in front of the Twilio programmable fax API to handle a number of reliability concerns:

- Most fax numbers can only receive one fax at a time. So if someone else is faxing that number, you'll get a busy signal and the fax with fail.

- Similarly, you don't usually want to send more than one fax to a particular number at the same time, or you'll be competing with yourself and get more busy signals.

- If the receiving fax machine is out of paper (and doesn't have available memory) or is off, your fax won't go through.

- Faxes are quite slow (about 1 minute per page), so if the receiving fax line is unreliable your fax may have trouble getting through.

## Usage

The Fax Gateway is a set of AWS Simple Queue Service queues, and lambda functions to process from these queues.

To send a fax, you write a message to the fax queue with the following format:

```js
{
  "fax_id": "abc123", // A unique ID for this fax
  "to": "+16175551234", // E.164-formatted number to send the fax to
  "pdf_url": "https://some-url/file.pdf", // URL of the PDF file to save (e.g. must be readable by Twilio -- e.g. a presigned S3 URL)
  "callback_url": "https://some-url/endpoint" // HTTP callback URL (see below)
}
```

The Fax Gateway will send the fax, retrying if the receiver is busy or disconnected. The SQS queue will ensure that only one fax is being sent to a particular destination number at a time (but multiple faxes might be sent at a time if they're to different destination numbers.)

### Callbacks

As the Fax Gateway runs, it will send you notifications of fax progress at the provided callback URL. You'll get a POST request with a JSON body when the fax is sent successfully, when an unsuccessful attempt is made (and will be retried), and when the fax gateway gives up permanently due to too many failures. So you may receive multiple callbacks for the same fax -- one for each failed attempt, plus a final one with the final success/failure.

The payload for a successful send is:

```js
{
  "fax_id": "abc123", // The ID you specified when you enqueued the fax to be sent
  "status": "sent",
  "message": "Fax sent successfully",
  "timestamp": 123456, // UNIX timestamp (seconds since the UNIX epoch)
}
```

The payload for an unsuccessful attempt that will be retried is:

```js
{
  "fax_id": "abc123", // The ID you specified when you enqueued the fax to be sent
  "status": "tmp_fail",
  "message": "Failed to deliver fax (attempt 7 of 20). Fax status: busy",
  "timestamp": 123456, // UNIX timestamp (seconds since the UNIX epoch)
}
```

And the payload for a final unsuccessful attempt it:

```js
{
  "fax_id": "abc123", // The ID you specified when you enqueued the fax to be sent
  "status": "perm_fail",
  "message": "Failed to deliver fax after 20 tries. Last attempt status: busy",
  "timestamp": 123456, // UNIX timestamp (seconds since the UNIX epoch)
}
```

Callbacks will typically be delivered in-order, but they can sometimes arrive out of order. You can check the timestamp of the message to determine the correct ordering.

You must return a 2xx status code. If you return a 4xx or 5xx status code, the Fax Gateway will retry sending the callback later.

## Configuration & Deployment

First, run `yarn install` and `pipenv install` to get your environment set up.

Then, read through the comments in `serverless.yml` to learn about how to configure Fax Gateway. At the very least, you'll need to provide your own Twilio credentials and Twilio phone numbers. There are also a number of other parameters than can be tuned depending on your needs and faxing workload.

Fax Gateway is deployed with [Serverless](https://www.serverless.com/). Just run `yarn sls deploy` to deploy to the `local` environment. To deploy to another environment (e.g. `staging`, `prod`, or whatever you want to name your environments), run `yarn sls deploy -s prod`.

If you use a CI system or other limited-privilege system to deploy Fax Gateway, you can use the `deployment-policy.json` policy from this repo, which has the necessary IAM privileges to deploy Fax Gateway. If you change the service name or AWS region in `serverless.yml`, you'll have to update this policy accordingly.

### Dead-Letter Queues

If there's a bug or infrastructure failure (SQS, Lambda, or Twilio outage), the Fax Gateway will retry processing messages several times. If the error persists, the queue message will eventually be kicked over to a dead-letter queue (DLQ). Each of the three queues that Fax Gateway uses has its own DLQ. Messages will *not* end up here if the receiving fax machine is offline, busy, or malfunctioning -- that type of failure is expected and will be handled via the callback URLs as described above.

However, if there's a problem with Fax Gateway, the underlying AWS services it depends on, or the application that's supposed to receive the callbacks, messages may end up in these DLQs. Fax Gateway does not do any handling of messages in the DLQs; you should configure your monitoring system to alert you if any messages end up in any of the DLQs.

## Design & Tradeoffs

The Fax Gateway is designed for sending relatively short faxes (<5 pages) at high volume with high reliability. A number of design decision and tradeoffs have been made with this goal in mind.

The most critical tradeoff is that when we read a fax from the queue, the lambda function that's responsible for sending that fax continues to run, polling Twilio for the fax's status, until the fax is sent or fails. The has some advantages over returning quickly and using the Twilio callback URL:

- We get end-to-end retry guarantees: if any part of sending the fax fails, including the Lambda functions, SQS will re-deliver the message and we'll retry. This makes it very unlikely that we'll drop a fax due to a transient error.

- We don't need to configure or secure an API Gateway interface. All network communications are outbound from the Fax Gateway.

- It works better with the SQS FIFO queue: we don't want to acknowledge the message until the fax is sent, because we're using SQS message groups to ensure only one fax is sent to a particular recipient at a time (using the recipient fax number as the message group ID). If the lambda function returned success after sending the fax to Twilio, and relied on Twilio's callbacks, then as soon as one fax was sent to Twilio, the queue could deliver another message from the same message group -- so we'd send another fax to the same number without waiting for the first one to succeed. We could get around this by *always* returning an error from the Lambda function so the SQS-Lambda integration doesn't delete the message automatically, and then calling the `DeleteMessage` SQS API endpoints manually from the Twilio callback handler, but that would mean we don't get a lot of useful information from standard Lambda monitoring tools, because it would be more difficult to differentiate between real errors from the Lambda function, and errors that we're throwing to get around the Lambda-SQS integration behavior.

However, this trade-off has one major disadvantage: *all faxes must take less than 15 minutes to deliver*, or the lambda function will time out, and we'll end up retrying and re-sending the fax. Faxes typically take less than 1 minute per page, so this shouldn't be a problem as long as your faxes are no more than a few pages long.

### Queues

A quick overview of the queues and how messages flow through them.

#### Fax Queue

The primary queue that holds faxes that we want to send. To send a message via the Fax Gateway, upstream applications write to this queue. The is a FIFO queue, with the destination phone number as the message group ID -- so faxes will be delivered in-order and there won't ever be more than one fax to a particular destination number in-flight at a time.

We read messages off this queue in the Fax Processor lambda function. This function sends the fax to Twilio and then polls for the result, not returning until the message is delivered or failed. If the message is delivered successfully, this function queues up a success webhook. If the message is not delivered successfully, the function either writes the message to the Retry Queue and queues up a temporary-failure webhook (if there are retries remaining), or just queues up a permanent-failure webhook (if this fax has exhausted all the retries allowed -- by default, 20 retries).

#### Retry Queue

When a fax is not sent successfully, the Fax Processor moves the message from the Fax Queue to the Retry Queue. We use the DelaySeconds parameter on the message in the Retry Queue to delay retrying sending the fax.

The Retry Processor reads messages from this queue and just moves them back into the Fax Queue.

#### Webhook Queue

When a fax attempt is made (successful or unsuccessful), the Fax Processor writes a webhook notification to the Webhook Queue. The Webhook Processor reads from this queue and delivers the POST request, erroring if it doesn't get a 2xx response code.

This queue is the most likely to end up with messages going to the dead-letter queue -- unlike the Fax Processor and Retry Processor, which only depend on robust external systems like SQS and Twilio, the Webhook Processor will error if the message's `callback_url` returns an error. By default, we retry delivering the webhook 20 times, so messages will only end up in the DLQ if there's a long outage of whatever's handling the `callback_url`.
