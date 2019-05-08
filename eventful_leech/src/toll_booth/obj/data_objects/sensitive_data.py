import logging

from src.toll_booth.obj.data_objects.identifiers import InternalId


class SensitiveData:
    def __init__(self, sensitive_entry, data_name, source_internal_id, internal_id=None):
        """SensitiveData is any information that might be considered relevant to HIPAA

            Any data possibly relevant to HIPAA is not stored directly into the graph or index
            Instead, an opaque pointer is generated and used in place of the data
            The sensitive data itself is stored in a separate location, where it can be retrieved by authorized persons

        Args:
            sensitive_entry:
            data_name:
            source_internal_id:
            internal_id:
        """
        if not internal_id:
            id_string = ''.join([data_name, source_internal_id])
            internal_id = InternalId(id_string).id_value
        self._sensitive_entry = sensitive_entry
        self._source_internal_id = source_internal_id
        self._insensitive = internal_id
        self.update_sensitive()

    @classmethod
    def from_insensitive(cls, insensitive_entry, sensitive_table_name=None):
        import boto3
        from boto3.dynamodb.conditions import Key

        if not sensitive_table_name:
            import os
            sensitive_table_name = os.environ['SENSITIVE_TABLE']
        resource = boto3.resource('dynamodb')
        table = resource.Table(sensitive_table_name)
        results = table.query(
            IndexName='string',
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression=Key('insensitive').eq(insensitive_entry)
        )
        print(results)

    def __str__(self):
        return self._insensitive

    def __get__(self, instance, owner):
        return self._insensitive

    @property
    def sensitive_entry(self):
        return self._sensitive_entry

    def update_sensitive(self, sensitive_table_name=None):
        """Push a sensitive value to remote storage

        Args:
            sensitive_table_name:

        Returns: None

        Raises:
            ClientError: the update operation could not take place

        """
        import boto3
        from botocore.exceptions import ClientError
        if not sensitive_table_name:
            import os
            sensitive_table_name = os.environ['SENSITIVE_TABLE']
        resource = boto3.resource('dynamodb')
        table = resource.Table(sensitive_table_name)
        try:
            table.update_item(
                Key={'insensitive': self._insensitive},
                UpdateExpression='SET sensitive_entry = if_not_exists(sensitive_entry, :s)',
                ExpressionAttributeValues={':s': self._sensitive_entry},
                ReturnValues='NONE'
            )
        except ClientError as e:
            logging.error(f'failed to update a sensitive data entry: {e}')
            raise e
