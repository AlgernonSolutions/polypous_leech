import boto3


class Bullhorn:
    def __init__(self, client=None):
        if not client:
            client = boto3.client('sns')
        self._client = client

    def publish(self, message_subject, topic_arn, message_body):
        response = self._client.publish(
            TopicArn=topic_arn,
            Subject=message_subject,
            Message=message_body
        )
        return response['MessageId']
