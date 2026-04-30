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

"""Integration tests for the DMS API ReplicationSubnetGroup resource.

Test scenarios
--------------
* test_crud
    Create a ReplicationSubnetGroup, verify it appears in the DMS API with the
    expected description, verify the initial ``environment=dev`` tag, update
    the tag to ``environment=prod``, and confirm the change is reflected in the
    DMS API.  The fixture handles deletion on teardown.
"""

import logging
import time

import pytest

from acktest.aws import identity
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_dms_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition
from e2e import replication_subnet_group
from e2e import tag

RESOURCE_PLURAL = 'replicationsubnetgroups'

DELETE_WAIT_AFTER_SECONDS = 10
MODIFY_WAIT_AFTER_SECONDS = 10

SUBNET_GROUP_DESC = "my-replication-subnet-group description"

@pytest.fixture
def subnet_group():
    """Creates a ReplicationSubnetGroup K8s CR and tears it down afterwards.

    The subnet group is created from the ``replication_subnet_group`` resource
    template using randomly-suffixed names to avoid collisions across parallel
    test runs.

    Yields:
        tuple: (ref, cr, subnet_group_name), where *ref* is the
        ``CustomResourceReference``, *cr* is the initial CR dict returned by
        the controller, and *subnet_group_name* is the identifier used for both
        the K8s object name and the DMS resource name.
    """

    subnet_group_name = random_suffix_name("my-replication-subnet-group", 33)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["REPLICATION_SUBNET_GROUP_NAME"] = subnet_group_name
    replacements["REPLICATION_SUBNET_GROUP_DESC"] = SUBNET_GROUP_DESC

    resource_data = load_dms_resource(
        "replication_subnet_group",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    # Create the k8s resource
    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        subnet_group_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)
    condition.assert_synced(ref)

    yield ref, cr, subnet_group_name

    # Try to delete, if it does exist
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)
    except:
        pass


@service_marker
@pytest.mark.canary
class TestReplicationSubnetGroup:
    def test_crud(self, subnet_group):
        """Verifies the full Create → Read → Update → Delete lifecycle.

        Checks:
        1.  The subnet group is immediately visible in the DMS API after the
            K8s CR is consumed by the controller.
        2.  The ``ReplicationSubnetGroupDescription`` field matches the value
            set in the CR spec.
        3.  The initial ``environment=dev`` tag is present on the resource.
        4.  Tags can be updated to ``environment=prod`` via a CR patch, and
            the DMS API reflects the new value.
        """

        ref, cr, subnet_group_name = subnet_group

        # Let's check that the subnet group appears in DMS
        latest = replication_subnet_group.get(subnet_group_name)
        assert latest is not None
        assert latest['ReplicationSubnetGroupDescription'] == SUBNET_GROUP_DESC

        # Build the ARN for this replication subnet group so we can
        # check its tags.
        account = identity.get_account_id()
        region = identity.get_region()
        arn = f"arn:aws:dms:{region}:{account}:subgrp:{subnet_group_name}"

        # Compare the Tags
        expect_tags = [
            {"Key": "environment", "Value": "dev"}
        ]
        latest_tags = tag.clean(replication_subnet_group.get_tags(arn))
        assert expect_tags == latest_tags

        # OK, now let's update the tag set and check that the tags are
        # updated accordingly.
        new_tags = [
            {
                "key": "environment",
                "value": "prod",
            }
        ]
        updates = {
            "spec": {"tags": new_tags},
        }
        k8s.patch_custom_resource(ref, updates)
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        latest_tags = tag.clean(replication_subnet_group.get_tags(arn))
        after_update_expected_tags = [
            {
                "Key": "environment",
                "Value": "prod",
            }
        ]
        assert latest_tags == after_update_expected_tags
