import logging
import os

import boto3
from src.algernon import lambda_logged, Bullhorn
from src.algernon import queued
from botocore.exceptions import ClientError

from src.toll_booth import CredibleFrontEndDriver
from src.algernon import ajson


@lambda_logged
@queued
def task(event, context):
    logging.info(f'started a call for a credible task, event: {event}')
    task_name = event['task_name']
    task_args = event.get('task_args', ())
    if task_args is None:
        task_args = ()
    task_kwargs = event.get('task_kwargs', {})
    if task_kwargs is None:
        task_kwargs = {}
    task_function = getattr(CredibleTasks, f'_{task_name}')
    id_source = task_kwargs['id_source']
    existing_credentials = CredibleTasks.get_credentials(**task_kwargs)
    driver = CredibleFrontEndDriver(id_source, credentials=existing_credentials)
    if driver.credentials != existing_credentials:
        CredibleTasks.push_credentials(id_source=id_source, credentials=driver.credentials)
    results = task_function(*task_args, **task_kwargs, driver=driver)
    logging.info(f'completed a call for a credible task, event: {event}, results: {results}')
    return results


class CredibleTasks:
    @staticmethod
    def get_credentials(**kwargs):
        id_source = kwargs['id_source']
        try:
            credentials = _download_object(os.environ['STORAGE_BUCKET'], id_source, 'credentials')
        except ClientError:
            return None
        return credentials

    @staticmethod
    def push_credentials(**kwargs):
        id_source = kwargs['id_source']
        _upload_object(os.environ['STORAGE_BUCKET'], id_source, 'credentials', kwargs['credentials'])

    @staticmethod
    def _get_encounter(**kwargs):
        driver = kwargs['driver']
        encounter_id = kwargs['encounter_id']
        id_source = kwargs['id_source']
        client_id = kwargs['client_id']
        encounter_text = driver.retrieve_client_encounter(encounter_id)
        folder_name = f'{id_source}/{client_id}'
        encounter = {
            'client_id': client_id,
            'id_source': id_source,
            'encounter_id': encounter_id,
            'encounter_text': encounter_text
        }
        _upload_object(os.environ['STORAGE_BUCKET'], folder_name, f'{encounter_id}.json', encounter)
        return encounter

    @staticmethod
    def _get_client_encounter_ids(**kwargs):
        client_id = kwargs['client_id']
        encounter_search_data = {
            'clientvisit_id': 1,
            'client_id': client_id,
            'service_type': 1,
            'non_billable': 1,
            'consumer_name': 1,
            'staff_name': 1,
            'client_int_id': 1,
            'emp_int_id': 1,
            'non_billable1': 3,
            'visittype': 1,
            'orig_rate_amount': 1,
            'timein': 1,
            'data_dict_ids': 83
        }
        driver = kwargs['driver']
        try:
            results = driver.process_advanced_search('ClientVisit', encounter_search_data)
        except RuntimeError as e:
            logging.error(f'runtime error retrieving values for client_id: {client_id}: {e}')
            results = []
        encounter_ids = [x['Service ID'] for x in results]
        bullhorn = Bullhorn()
        for encounter_id in encounter_ids:
            new_task = {
                'task_name': 'get_encounter',
                'task_kwargs': {
                    'encounter_id': encounter_id,
                    'client_id': client_id,
                    'id_source': kwargs['id_source']
                }
            }
            bullhorn.publish('new_event', os.environ['CREDIBLE_MANAGER_ARN'], ajson.dumps(new_task))
        return encounter_ids

    @staticmethod
    def _get_client_ids(**kwargs):
        client_search_data = {
            'teams': 1,
            'client_id': 1,
            'last_name': 1,
            'first_name': 1,
            'text28': 1,
            'dob': 1,
            'ssn': 1,
            'primary_assigned': 1,
            'client_status_f': 'ALL ACTIVE'
        }
        id_source = kwargs['id_source']
        driver = kwargs['driver']
        results = driver.process_advanced_search('Clients', client_search_data)
        client_ids = [x[' Id'] for x in results]
        bullhorn = Bullhorn()
        for client_id in client_ids:
            new_task = {
                'task_name': 'get_client_encounter_ids',
                'task_kwargs': {
                    'client_id': client_id,
                    'id_source': id_source
                }
            }
            bullhorn.publish('new_event', os.environ['CREDIBLE_MANAGER_ARN'], ajson.dumps(new_task))
        return client_ids


def _upload_object(bucket_name, folder_name, object_name, obj):
    resource = boto3.resource('s3')
    object_key = f'{folder_name}/{object_name}'
    resource.Object(bucket_name, object_key).put(Body=ajson.dumps(obj))


def _download_object(bucket_name, folder_name, object_name):
    resource = boto3.resource('s3')
    object_key = f'{folder_name}/{object_name}'
    stored_object = resource.Object(bucket_name, object_key).get()
    string_body = stored_object['Body'].read()
    return ajson.loads(string_body)
