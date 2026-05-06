# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Utilities for working with DMS ReplicationTask resources."""

import datetime
import time
import typing

import boto3
import pytest

DEFAULT_WAIT_UNTIL_TIMEOUT_SECONDS = 60 * 5
DEFAULT_WAIT_UNTIL_INTERVAL_SECONDS = 10
DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS = 60 * 10
DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS = 10
DEFAULT_WAIT_TASK_RUNNING_TIMEOUT_SECONDS = 60 * 10  # Task can take time to start
DEFAULT_WAIT_TASK_RUNNING_INTERVAL_SECONDS = 15
DEFAULT_WAIT_TASK_STOPPED_TIMEOUT_SECONDS = 60 * 15  # Full load + migration can take time
DEFAULT_WAIT_TASK_STOPPED_INTERVAL_SECONDS = 15

TaskMatchFunc = typing.Callable[[dict | None], bool]


class StatusMatcher:
    """Callable that returns True when a ReplicationTask matches a given status."""

    def __init__(self, status: str):
        self.match_on = status

    def __call__(self, record: dict | None) -> bool:
        return (
            record is not None
            and 'Status' in record
            and record['Status'] == self.match_on
        )


def status_matches(status: str) -> TaskMatchFunc:
    """Returns a match function that checks for the given status string."""
    return StatusMatcher(status)


def wait_until(
    task_arn: str,
    match_fn: TaskMatchFunc,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_INTERVAL_SECONDS,
) -> None:
    """Waits until a DMS ReplicationTask matches the supplied predicate.

    Args:
        task_arn: The ARN of the replication task
        match_fn: Callable that returns True when condition is met
        timeout_seconds: Maximum time to wait before failing
        interval_seconds: Time between polls

    Raises:
        pytest.fail upon timeout.
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while not match_fn(get(task_arn)):
        if datetime.datetime.now() >= timeout:
            pytest.fail(f"Failed to match ReplicationTask {task_arn} before timeout")
        time.sleep(interval_seconds)


def wait_until_deleted(
    task_arn: str,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS,
) -> None:
    """Waits until a DMS ReplicationTask is no longer returned by the API.

    Args:
        task_arn: The ARN of the replication task
        timeout_seconds: Maximum time to wait before failing
        interval_seconds: Time between polls

    Raises:
        pytest.fail upon timeout.
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while True:
        if datetime.datetime.now() >= timeout:
            pytest.fail(
                f"Timed out waiting for ReplicationTask {task_arn} to be deleted"
            )

        latest = get(task_arn)
        if latest is None:
            break

        time.sleep(interval_seconds)


def wait_until_running(
    task_arn: str,
    timeout_seconds: int = DEFAULT_WAIT_TASK_RUNNING_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_TASK_RUNNING_INTERVAL_SECONDS,
) -> None:
    """Waits until a DMS ReplicationTask reaches running status.

    Args:
        task_arn: The ARN of the replication task
        timeout_seconds: Maximum time to wait before failing
        interval_seconds: Time between polls

    Raises:
        pytest.fail upon timeout.
    """
    wait_until(
        task_arn,
        status_matches("running"),
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
    )


def wait_until_stopped(
    task_arn: str,
    timeout_seconds: int = DEFAULT_WAIT_TASK_STOPPED_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_TASK_STOPPED_INTERVAL_SECONDS,
) -> None:
    """Waits until a DMS ReplicationTask reaches stopped status.

    Args:
        task_arn: The ARN of the replication task
        timeout_seconds: Maximum time to wait before failing
        interval_seconds: Time between polls

    Raises:
        pytest.fail upon timeout.
    """
    wait_until(
        task_arn,
        status_matches("stopped"),
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
    )


def get(task_arn: str) -> dict | None:
    """Returns the DMS ReplicationTask record for the supplied task ARN.

    Args:
        task_arn: The ARN of the replication task

    Returns:
        dict containing the task record, or None if task doesn't exist
    """
    c = boto3.client('dms')
    try:
        resp = c.describe_replication_tasks(
            Filters=[
                {
                    'Name': 'replication-task-arn',
                    'Values': [task_arn],
                }
            ]
        )
        tasks = resp.get('ReplicationTasks', [])
        if not tasks:
            return None
        assert len(tasks) == 1
        return tasks[0]
    except c.exceptions.ResourceNotFoundFault:
        return None


def get_tags(task_arn: str) -> list | None:
    """Returns the tag list for a DMS ReplicationTask.

    Args:
        task_arn: The ARN of the replication task

    Returns:
        List of tags, or None if task doesn't exist
    """
    c = boto3.client('dms')
    try:
        resp = c.list_tags_for_resource(ResourceArn=task_arn)
        return resp['TagList']
    except c.exceptions.ResourceNotFoundFault:
        return None
