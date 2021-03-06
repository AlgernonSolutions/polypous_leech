import os

import boto3
import jsonref

from src.algernon import AlgDecoder


class SchemaSnek:
    def __init__(self, bucket_name=None, **kwargs):
        folder_name = kwargs.get('folder_name', None)
        if not bucket_name:
            bucket_name = os.getenv('LEECH_BUCKET_NAME', 'the-leech')
        if not folder_name:
            folder_name = os.getenv('SCHEMA_FOLDER', 'schemas')
        self._bucket_name = bucket_name
        self._folder_name = folder_name

    def get_validation_schema(self, schema_name=None):
        if not schema_name:
            schema_name = 'master_schema.json'
        return self.get_schema(schema_name=schema_name)

    def put_validation_schema(self, file_path, master_schema_name=None):
        if not master_schema_name:
            master_schema_name = 'master_schema.json'
        return self.put_schema(file_path, master_schema_name)

    def get_schema(self, **kwargs):
        schema_name = kwargs.get('schema_name', 'schema.json')
        s3 = boto3.resource('s3')
        object_key = f'{self._folder_name}/{schema_name}'
        stored_object = s3.Object(self._bucket_name, object_key).get()
        stored_schema_string = stored_object['Body'].read()
        schema = jsonref.loads(stored_schema_string, cls=AlgDecoder)
        return schema

    def put_schema(self, file_path, schema_name=None):
        if not schema_name:
            schema_name = 'schema.json'
        file_name = f'{self._folder_name}/{schema_name}'
        s3 = boto3.resource('s3')
        s3.Bucket(self._bucket_name).upload_file(file_path, file_name)
