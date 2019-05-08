import json
import os
from os import path
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_generate_source_vertex_event():
    return _generate_leech_event('generate_source_vertex_event')


@pytest.fixture
def mock_bullhorn_boto():
    boto_patch = patch('algernon.aws.Bullhorn')
    mock_boto = boto_patch.start()
    yield mock_boto
    boto_patch.stop()


@pytest.fixture(autouse=True)
def silence_x_ray():
    x_ray_patch_all = 'algernon.aws.lambda_logging.patch_all'
    patch(x_ray_patch_all).start()
    yield
    patch.stopall()


@pytest.fixture
def environment():
    os.environ['LEECH_LISTENER_ARN'] = 'some_arn'


@pytest.fixture
def mock_context():
    from unittest.mock import MagicMock
    context = MagicMock(name='context')
    context.__reduce__ = cheap_mock
    context.function_name = 'test_function'
    context.invoked_function_arn = 'test_function_arn'
    context.aws_request_id = '12344_request_id'
    context.get_remaining_time_in_millis.side_effect = [1000001, 500001, 250000, 0]
    return context


def cheap_mock(*args):
    from unittest.mock import Mock
    return Mock, ()


def _read_test_event(event_name):
    with open(path.join('tests', 'test_events', f'{event_name}.json')) as json_file:
        event = json.load(json_file)
        return event


def _generate_leech_event(event_name):
    event = _read_test_event(event_name)
    event_string = json.dumps(event)
    message_object = {'Message': event_string}
    body_object = {'body': json.dumps(message_object)}
    return {'Records': [body_object]}
