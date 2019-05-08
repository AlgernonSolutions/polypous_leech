import logging
import os
import re
import sys
from zipfile import ZipFile
import shutil

import boto3

os.environ['AWS_PROFILE'] = 'dev'


def generate_new_upload_key():
    resource = boto3.resource('s3')
    layer_bucket = resource.Bucket('algernonsolutions-layer-dev')
    all_objects = layer_bucket.objects.all()
    versions = set()
    for entry in all_objects:
        key = entry.key
        pieces = key.split('/')
        folder_name = pieces[0]
        version_pattern = re.compile(r"(?P<number>[\d*])")
        version_search = version_pattern.search(folder_name)
        version = version_search.group('number')
        versions.add(int(version))
    new_max = max(versions) + 1
    new_folder_name = f'v{new_max}'
    return new_folder_name


def run_build():
    package_command = 'sam build --use-container'
    os.system(package_command)


def create_build_directory(version_key, build_location):
    target_path = os.path.join(build_location, version_key)
    try:
        os.mkdir(target_path)
    except FileExistsError:
        shutil.rmtree(target_path)
        os.mkdir(target_path)
    return target_path


def zip_layer(version_key, build_location, layer_location=None):
    if not layer_location:
        layer_location = os.path.join('.aws-sam')
    version_directory = create_build_directory(version_key, build_location)
    zip_logger = logging.Logger('zip_logger')
    zip_logger.setLevel(logging.DEBUG)
    zip_logger.addHandler(logging.StreamHandler(stream=sys.stdout))
    zip_location = os.path.join(version_directory, 'layer')
    shutil.make_archive(
        zip_location,
        format='zip',
        root_dir=os.path.join(layer_location, 'build'),
        base_dir='python',
        logger=zip_logger)
    return zip_location


def upload_layer(bucket_name, layer_version, layer_zip_location):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    file_key = f'{layer_version}/layer.zip'
    bucket.upload_file(layer_zip_location, file_key)
    return file_key


def publish_lambda_layer(layer_name, bucket_name, file_key, layer_description=None):
    layer_description_param = ''
    if layer_description:
        layer_description_param = f'--description "{layer_description}"'
    layer_name_param = f'--layer-name {layer_name}'
    run_time = '--compatible-runtimes "python3.6"'
    content = f'--content S3Bucket={bucket_name},S3Key={file_key}'
    optionals = f'{layer_description_param} {content} {run_time}'
    publish_command = f'aws lambda publish-layer-version {layer_name_param} {optionals}'
    os.system(publish_command)


def update_aws_cli():
    os.system('pip install awscli --upgrade')


def run():
    bucket_name = 'algernonsolutions-layer-dev'
    build_location_path = os.path.join('.build')
    layer_name = 'AlgernonLayer'
    run_build()
    layer_description = 'the compiled base layer for algernon functions'
    layer_version = generate_new_upload_key()
    zip_location = zip_layer(layer_version, build_location=build_location_path)
    file_key = upload_layer(bucket_name, layer_version, f'{zip_location}.zip')
    publish_lambda_layer(layer_name, bucket_name, file_key, layer_description)


if __name__ == '__main__':
    run()
