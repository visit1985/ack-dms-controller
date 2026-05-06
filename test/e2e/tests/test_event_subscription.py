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

"""Integration tests for the DMS API EventSubscription resource.

Test scenarios
--------------
* test_crud
    Create an EventSubscription against a bootstrapped SNS topic, verify it
    becomes active in the DMS API, verify the initial ``environment=dev`` tag,
    toggle the ``enabled`` flag to False, update tags to ``environment=prod``,
    and let the fixture handle deletion.
"""

import logging
import time

import pytest

from acktest.aws import identity
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_dms_resource
from e2e import condition
from e2e import event_subscription as aws_api
from e2e import tag
from e2e.replacement_values import REPLACEMENT_VALUES

RESOURCE_PLURAL = "eventsubscriptions"
MAX_WAIT_FOR_SYNCED_PERIODS = 30
MODIFY_WAIT_AFTER_SECONDS = 10


@pytest.fixture
def event_subscription(request):
    """Creates an EventSubscription CR and tears it down after the test."""
    ref = None
    subscription_name = None

    def _cleanup():
        """Deletes any resources created by this fixture.

        Registered as a finalizer so it runs even if fixture setup fails after
        creating the Kubernetes EventSubscription resource.
        """
        if ref is not None:
            try:
                if k8s.get_resource_exists(ref):
                    _, deleted = k8s.delete_custom_resource(ref, 3, 10)
                    assert deleted
            except Exception as e:
                logging.warning(f"failed to delete event subscription CR: {e}")

        if subscription_name is not None:
            try:
                aws_api.wait_until_deleted(subscription_name)
            except Exception as e:
                logging.warning(
                    f"failed waiting for event subscription deletion: {e}"
                )

    request.addfinalizer(_cleanup)

    subscription_name = random_suffix_name("my-event-subscription", 27)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["EVENT_SUBSCRIPTION_NAME"] = subscription_name

    resource_data = load_dms_resource(
        "event_subscription",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        subscription_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    assert k8s.wait_on_condition(
        ref, "ACK.ResourceSynced", "True",
        wait_periods=MAX_WAIT_FOR_SYNCED_PERIODS,
    )

    yield ref, cr, subscription_name



@service_marker
@pytest.mark.canary
class TestEventSubscription:
    def test_crud(self, event_subscription):
        """Verifies the Create → Read → Update → Delete lifecycle.

        Checks:
        1.  The EventSubscription becomes visible in the DMS API and reaches the
            ``active`` status.
        2.  The controller-derived ARN matches the expected DMS ARN format.
        3.  The initial ``environment=dev`` tag is present in the AWS API.
        4.  The ``enabled`` field can be updated from True → False.
        5.  Tags can be updated from ``environment=dev`` → ``environment=prod``.
        """
        ref, _, subscription_name = event_subscription

        aws_api.wait_until(subscription_name, aws_api.status_matches("active"))

        latest = aws_api.get(subscription_name)
        assert latest is not None
        assert latest['CustSubscriptionId'] == subscription_name
        assert latest['SnsTopicArn'] == REPLACEMENT_VALUES['SNS_TOPIC_ARN']
        assert latest['Enabled'] is True
        assert latest['Status'] == 'active'

        cr = k8s.get_resource(ref)
        assert cr is not None
        condition.assert_synced(ref)

        account = identity.get_account_id()
        region = identity.get_region()
        expected_arn = f"arn:aws:dms:{region}:{account}:es:{subscription_name}"

        assert 'status' in cr
        assert 'ackResourceMetadata' in cr['status']
        assert cr['status']['ackResourceMetadata']['arn'] == expected_arn

        latest_tags = tag.clean(aws_api.get_tags(expected_arn))
        assert latest_tags == [{"Key": "environment", "Value": "dev"}]

        k8s.patch_custom_resource(ref, {"spec": {"enabled": False}})
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        assert k8s.wait_on_condition(
            ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_PERIODS,
        )

        latest = aws_api.get(subscription_name)
        assert latest is not None
        assert latest['Enabled'] is False

        k8s.patch_custom_resource(
            ref,
            {"spec": {"tags": [{"key": "environment", "value": "prod"}]}},
        )
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        assert k8s.wait_on_condition(
            ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_PERIODS,
        )

        latest_tags = tag.clean(aws_api.get_tags(expected_arn))
        assert latest_tags == [{"Key": "environment", "Value": "prod"}]
