import boto3

from algernon import ajson
from src.algernon import Bullhorn

from src.toll_booth import Schema

session = boto3.Session(profile_name='dev')
sns = session.client('sns')
listener_arn = 'arn:aws:sns:us-east-1:726075243133:leech-dev-Listener-1EV4D8VOW7L37'
bull_horn = Bullhorn(sns)
schema = Schema.retrieve()
schema_entry = schema['ExternalId']
message = ajson.dumps({
    'task_name': 'generate_source_vertex',
    'task_args': None,
    'task_kwargs': {
        'schema': schema,
        'schema_entry': schema_entry,
        'extracted_data': {
            'source': {
                'id_source': 'Algernon',
                'id_type': 'Employees',
                'id_name': 'emp_id',
                'id_value': 1001
            }
        }
    }
})
message_id = bull_horn.publish('new_event', listener_arn, message)
print()
