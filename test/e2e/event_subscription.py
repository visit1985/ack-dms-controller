# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Utilities for working with DMS EventSubscription resources."""

import datetime
import time
import typing

import boto3
import pytest

DEFAULT_WAIT_UNTIL_TIMEOUT_SECONDS = 60 * 10
DEFAULT_WAIT_UNTIL_INTERVAL_SECONDS = 10
DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS = 60 * 10
DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS = 10

SubscriptionMatchFunc = typing.Callable[[dict | None], bool]


class StatusMatcher:
    """Callable that returns True when an EventSubscription matches a status."""

    def __init__(self, status: str):
        self.match_on = status

    def __call__(self, record: dict | None) -> bool:
        return (
            record is not None
            and 'Status' in record
            and record['Status'] == self.match_on
        )


def status_matches(status: str) -> SubscriptionMatchFunc:
    """Returns a match function that checks for the given status string."""
    return StatusMatcher(status)


def wait_until(
    subscription_name: str,
    match_fn: SubscriptionMatchFunc,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_INTERVAL_SECONDS,
) -> None:
    """Waits until a DMS event subscription matches the supplied predicate."""
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while not match_fn(get(subscription_name)):
        if datetime.datetime.now() >= timeout:
            pytest.fail("Failed to match EventSubscription before timeout")
        time.sleep(interval_seconds)


def wait_until_deleted(
    subscription_name: str,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS,
) -> None:
    """Waits until a DMS event subscription is no longer returned by the API."""
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while True:
        if datetime.datetime.now() >= timeout:
            pytest.fail(
                "Timed out waiting for EventSubscription to be deleted in DMS API"
            )

        latest = get(subscription_name)
        if latest is None:
            break

        time.sleep(interval_seconds)


def get(subscription_name: str) -> dict | None:
    """Returns the DMS EventSubscription record for the supplied name."""
    c = boto3.client('dms')
    try:
        resp = c.describe_event_subscriptions(
            SubscriptionName=subscription_name,
        )
        subscriptions = resp.get('EventSubscriptionsList', [])
        if not subscriptions:
            return None
        assert len(subscriptions) == 1
        return subscriptions[0]
    except c.exceptions.ResourceNotFoundFault:
        return None


def get_tags(subscription_arn: str) -> list | None:
    """Returns the tag list for a DMS EventSubscription."""
    c = boto3.client('dms')
    try:
        resp = c.list_tags_for_resource(ResourceArn=subscription_arn)
        return resp['TagList']
    except c.exceptions.ResourceNotFoundFault:
        return None
