
"""Lambda handler for forwarding messages from SQS to Kinesis Firehose."""
import logging
import os

import boto3
from src.algernon import lambda_logged

fire_hose = boto3.client('firehose')
stream_name = os.environ['FIREHOSE_DELIVERY_STREAM_NAME']


@lambda_logged
def handler(event, context):
    """Forward SQS messages to Kinesis Firehose Delivery Stream."""
    logging.debug('Received event: %s', event)
    if 'Records' not in event:
        logging.info('No records in event')
        return

    for record in event['Records']:
        response = fire_hose.put_record(
            DeliveryStreamName=stream_name,
            Record={'Data': record['body'] + "\n"}
        )
        logging.debug('Firehose response: %s', response)
