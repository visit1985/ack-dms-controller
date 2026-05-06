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

"""Integration tests for the DMS API ReplicationInstance resource.

Test scenarios
--------------
* test_crud
    Create a dms.t3.small instance, wait for it to become *available*, verify
    status in the K8s CR and the AWS API, update a simple field
    (autoMinorVersionUpgrade), verify tags, update tags, toggle the
    ``multiAZ`` flag and let the fixture handle deletion.
"""

import logging
import time

import pytest

from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_dms_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition
from e2e import replication_instance as aws_api
from e2e import replication_subnet_group as sg_aws_api
from e2e import tag

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESOURCE_PLURAL = "replicationinstances"

# DMS replication instances typically take 5-10 minutes to become available.
# We allow 20 minutes total to account for slower regions and retries.
MAX_WAIT_FOR_SYNCED_MINUTES = 20

# Time to pause between patching a resource and re-checking its AWS state.
MODIFY_WAIT_AFTER_SECONDS = 10

SUBNET_GROUP_RESOURCE_PLURAL = "replicationsubnetgroups"
SUBNET_GROUP_DESC = "my-replication-subnet-group description"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def replication_instance_fixture(request):
    """Creates all K8s resources needed for ReplicationInstance tests and
    tears them down in the correct order afterwards.

    Yields:
        tuple: (instance_ref, instance_cr, instance_name, subnet_group_ref,
                subnet_group_name)
    """
    sg_ref = None
    ri_ref = None
    instance_name = None
    subnet_group_name = None

    def _cleanup():
        """Deletes any resources created by this fixture.

        Registered as a finalizer so it runs even if fixture setup fails after
        creating one or more Kubernetes resources.
        """
        if ri_ref is not None:
            try:
                if k8s.get_resource_exists(ri_ref):
                    _, deleted = k8s.delete_custom_resource(ri_ref, 3, 10)
                    assert deleted
            except Exception as e:
                logging.warning(f"failed to delete replication instance CR: {e}")

        if instance_name is not None:
            try:
                aws_api.wait_until_deleted(instance_name)
            except Exception as e:
                logging.warning(
                    f"failed waiting for replication instance deletion: {e}"
                )

        if sg_ref is not None:
            try:
                if k8s.get_resource_exists(sg_ref):
                    _, deleted = k8s.delete_custom_resource(sg_ref, 3, 10)
                    assert deleted
            except Exception as e:
                logging.warning(f"failed to delete subnet group CR: {e}")

        if subnet_group_name is not None:
            try:
                sg_aws_api.wait_until_deleted(subnet_group_name)
                logging.info("Subnet group deleted")
            except Exception as e:
                logging.warning(f"failed waiting for subnet group deletion: {e}")

    request.addfinalizer(_cleanup)

    # -- Subnet group --------------------------------------------------------
    subnet_group_name = random_suffix_name("my-replication-subnet-group", 33)

    sg_replacements = REPLACEMENT_VALUES.copy()
    sg_replacements["REPLICATION_SUBNET_GROUP_NAME"] = subnet_group_name
    sg_replacements["REPLICATION_SUBNET_GROUP_DESC"] = SUBNET_GROUP_DESC

    sg_resource_data = load_dms_resource(
        "replication_subnet_group",
        additional_replacements=sg_replacements,
    )
    logging.debug(sg_resource_data)

    sg_ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, SUBNET_GROUP_RESOURCE_PLURAL,
        subnet_group_name, namespace="default",
    )
    k8s.create_custom_resource(sg_ref, sg_resource_data)
    sg_cr = k8s.wait_resource_consumed_by_controller(sg_ref)

    assert sg_cr is not None
    assert k8s.get_resource_exists(sg_ref)
    # Subnet group provisioning is synchronous in DMS — wait for it to sync.
    condition.assert_synced(sg_ref)

    # -- Replication instance ------------------------------------------------
    instance_name = random_suffix_name("my-replication-instance", 29)

    ri_replacements = REPLACEMENT_VALUES.copy()
    ri_replacements["REPLICATION_INSTANCE_NAME"] = instance_name
    ri_replacements["REPLICATION_SUBNET_GROUP_NAME"] = subnet_group_name

    ri_resource_data = load_dms_resource(
        "replication_instance",
        additional_replacements=ri_replacements,
    )
    logging.debug(ri_resource_data)

    ri_ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        instance_name, namespace="default",
    )
    k8s.create_custom_resource(ri_ref, ri_resource_data)
    ri_cr = k8s.wait_resource_consumed_by_controller(ri_ref)

    assert ri_cr is not None
    assert k8s.get_resource_exists(ri_ref)

    yield ri_ref, ri_cr, instance_name, sg_ref, subnet_group_name


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@service_marker
@pytest.mark.canary
class TestReplicationInstance:

    def test_crud(self, replication_instance_fixture):
        """Verifies the full Create → Read → Update → Delete lifecycle.

        Checks:
        1.  Immediately after creation the K8s CR status is ``creating`` and
            the ``ACK.ResourceSynced`` condition is False.
        2.  After waiting for sync the AWS API reports ``available``.
        3.  The K8s CR status field is also updated to ``available`` on the
            next reconciliation pass.
        4.  ``autoMinorVersionUpgrade`` can be toggled off and back on, with
            each change reflected in the AWS API after re-sync.
        5.  The initial ``environment=dev`` tag is present in the AWS API.
        6.  Tags can be updated to ``environment=prod``.
        7.  ``multiAZ`` can be toggled from False → True; the controller
            transitions through a not-synced state while DMS applies the
            modification, then returns to ``available`` with MultiAZ enabled.
        """
        ri_ref, ri_cr, instance_name, _, _ = replication_instance_fixture

        # Immediately after creation the instance should be in 'creating'.
        assert 'status' in ri_cr
        assert 'instanceStatus' in ri_cr['status']
        assert ri_cr['status']['instanceStatus'] == 'creating'
        condition.assert_not_synced(ri_ref)

        # Wait for the controller to mark the CR as synced (= available).
        assert k8s.wait_on_condition(
            ri_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES * 4, period_length=15,
        )

        # Confirm the AWS-side status is 'available'.
        latest = aws_api.get(instance_name)
        assert latest is not None
        assert latest['ReplicationInstanceStatus'] == 'available'
        assert latest['MultiAZ'] is False

        # The K8s CR's status.replicationInstanceStatus should have been
        # updated from 'creating' to reflect the current state.
        ri_cr = k8s.get_resource(ri_ref)
        assert ri_cr is not None
        assert ri_cr['status']['instanceStatus'] != 'creating'
        condition.assert_synced(ri_ref)

        # ---- Update: toggle autoMinorVersionUpgrade -------------------------
        original_amvu = latest.get('AutoMinorVersionUpgrade', True)
        new_amvu = not original_amvu

        k8s.patch_custom_resource(
            ri_ref,
            {"spec": {"autoMinorVersionUpgrade": new_amvu}},
        )
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        assert k8s.wait_on_condition(
            ri_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES * 4, period_length=15,
        )

        latest = aws_api.get(instance_name)
        assert latest is not None
        assert latest['AutoMinorVersionUpgrade'] == new_amvu

        # Restore original value.
        k8s.patch_custom_resource(
            ri_ref,
            {"spec": {"autoMinorVersionUpgrade": original_amvu}},
        )
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        assert k8s.wait_on_condition(
            ri_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES * 4, period_length=15,
        )

        latest = aws_api.get(instance_name)
        assert latest is not None
        assert latest['AutoMinorVersionUpgrade'] == original_amvu

        # ---- Verify initial tags -------------------------------------------
        arn = latest['ReplicationInstanceArn']
        expect_tags = [{"Key": "environment", "Value": "dev"}]
        latest_tags = tag.clean(aws_api.get_tags(arn))
        assert expect_tags == latest_tags

        # ---- Update tags ---------------------------------------------------
        k8s.patch_custom_resource(
            ri_ref,
            {"spec": {"tags": [{"key": "environment", "value": "prod"}]}},
        )
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        assert k8s.wait_on_condition(
            ri_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES * 4, period_length=15,
        )

        latest_tags = tag.clean(aws_api.get_tags(arn))
        assert latest_tags == [{"Key": "environment", "Value": "prod"}]

        # Confirm MultiAZ is currently disabled.
        latest = aws_api.get(instance_name)
        assert latest is not None
        assert latest['MultiAZ'] is False

        # Apply the MultiAZ change.
        k8s.patch_custom_resource(ri_ref, {"spec": {"multiAZ": True}})
        # Give the controller a moment to start the modify operation before
        # we assert that the resource is temporarily not-synced.
        time.sleep(35)
        condition.assert_not_synced(ri_ref)

        ri_cr = k8s.get_resource(ri_ref)
        assert ri_cr is not None
        assert ri_cr['spec']['multiAZ'] is True

        # Wait for DMS to finish the modification.
        assert k8s.wait_on_condition(
            ri_ref, "ACK.ResourceSynced", "True",
            wait_periods=MAX_WAIT_FOR_SYNCED_MINUTES * 4, period_length=15,
        )

        latest = aws_api.get(instance_name)
        assert latest is not None
        assert latest['ReplicationInstanceStatus'] == 'available'
        assert latest['MultiAZ'] is True
