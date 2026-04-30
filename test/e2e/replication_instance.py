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

"""Utilities for working with DMS ReplicationInstance resources"""

import datetime
import time
import typing

import boto3
import pytest

DEFAULT_WAIT_UNTIL_TIMEOUT_SECONDS = 60 * 30
DEFAULT_WAIT_UNTIL_INTERVAL_SECONDS = 15
DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS = 60 * 20
DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS = 15

InstanceMatchFunc = typing.NewType(
    'InstanceMatchFunc',
    typing.Callable[[dict], bool],
)


class StatusMatcher:
    """Callable that returns True when a ReplicationInstance record matches
    the expected status string."""

    def __init__(self, status: str):
        self.match_on = status

    def __call__(self, record: dict) -> bool:
        return (
            record is not None
            and 'ReplicationInstanceStatus' in record
            and record['ReplicationInstanceStatus'] == self.match_on
        )


def status_matches(status: str) -> InstanceMatchFunc:
    """Returns a match function that checks for the given status string."""
    return StatusMatcher(status)


def wait_until(
    replication_instance_id: str,
    match_fn: InstanceMatchFunc,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_INTERVAL_SECONDS,
) -> None:
    """Waits until a ReplicationInstance with the supplied ID is returned from
    the DMS API and the matching functor returns True.

    Usage::

        from e2e.replication_instance import wait_until, status_matches

        wait_until(instance_id, status_matches("available"))

    Raises:
        pytest.fail upon timeout.
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while not match_fn(get(replication_instance_id)):
        if datetime.datetime.now() >= timeout:
            pytest.fail("Failed to match ReplicationInstance before timeout")
        time.sleep(interval_seconds)


def wait_until_deleted(
    replication_instance_id: str,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS,
) -> None:
    """Waits until a ReplicationInstance with the supplied ID is no longer
    returned from the DMS API.

    Usage::

        from e2e.replication_instance import wait_until_deleted

        wait_until_deleted(instance_id)

    Raises:
        pytest.fail upon timeout or if the instance enters any status other
        than "deleting" while being removed.
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while True:
        if datetime.datetime.now() >= timeout:
            pytest.fail(
                "Timed out waiting for ReplicationInstance to be "
                "deleted in DMS API"
            )
        time.sleep(interval_seconds)

        latest = get(replication_instance_id)
        if latest is None:
            break

        if latest['ReplicationInstanceStatus'] != "deleting":
            pytest.fail(
                "Status is not 'deleting' for ReplicationInstance that was "
                "deleted. Status is " + latest['ReplicationInstanceStatus']
            )


def get(replication_instance_id: str) -> dict | None:
    """Returns a dict containing the ReplicationInstance record from the DMS API.

    If no such replication instance exists, returns None.
    """
    c = boto3.client('dms')
    try:
        resp = c.describe_replication_instances(
            Filters=[
                {
                    'Name': 'replication-instance-id',
                    'Values': [replication_instance_id],
                }
            ]
        )
        instances = resp.get('ReplicationInstances', [])
        if not instances:
            return None
        assert len(instances) == 1
        return instances[0]
    except c.exceptions.ResourceNotFoundFault:
        return None


def get_tags(replication_instance_arn: str) -> list | None:
    """Returns the TagList for a ReplicationInstance from the DMS API.

    If no such replication instance exists, returns None.
    """
    c = boto3.client('dms')
    try:
        resp = c.list_tags_for_resource(ResourceArn=replication_instance_arn)
        return resp['TagList']
    except c.exceptions.ResourceNotFoundFault:
        return None

