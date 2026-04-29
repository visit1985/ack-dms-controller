# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Utilities for working with DMS replication subnet resources"""

import datetime
import time

import boto3
import pytest

DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS = 60*10
DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS = 15


def get(subnet_group_id):
    """Returns a dict containing the DMS replication_subnet_group record from the DMS API.

    If no such DMS replication_subnet_group exists, returns None.
    """
    c = boto3.client('dms')
    try:
        resp = c.describe_replication_subnet_groups(
            Filters=[
                {
                    'Name': 'replication-subnet-group-id',
                    'Values': [
                        subnet_group_id,
                    ]
                },
            ],
        )
        assert len(resp['ReplicationSubnetGroups']) == 1
        return resp['ReplicationSubnetGroups'][0]
    except c.exceptions.ResourceNotFoundFault:
        return None


def get_tags(subnet_group_arn):
    """Returns a dict containing the DMS replication subnet group's tag records from the DMS
    API.

    If no such DMS replication subnet group exists, returns None.
    """
    c = boto3.client('dms')
    try:
        resp = c.list_tags_for_resource(
            ResourceArn=subnet_group_arn,
        )
        return resp['TagList']
    except c.exceptions.ResourceNotFoundFault:
        return None
