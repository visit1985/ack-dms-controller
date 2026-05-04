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

"""DMS-specific bootstrapping helpers.

These wrappers keep account-specific test bootstrap behavior local to the DMS
controller test suite without modifying shared ``acktest`` helpers.
"""

import json
import os
import time

from dataclasses import dataclass

from acktest.bootstrapping import Bootstrappable
from acktest.bootstrapping.iam import Role, ROLE_CREATE_WAIT_IN_SECONDS

PERMISSIONS_BOUNDARY_ENV_VAR = "ACK_TEST_IAM_PERMISSIONS_BOUNDARY"


def get_permissions_boundary(
    env_var: str = PERMISSIONS_BOUNDARY_ENV_VAR,
) -> str:
    """Returns an optional IAM permissions boundary ARN from the environment."""
    return os.environ.get(env_var, "")


@dataclass
class RoleWithPermissionsBoundary(Role):
    """A DMS-local IAM role bootstrapper that optionally applies a permissions
    boundary when creating the role.
    """

    permissions_boundary: str = ""

    def bootstrap(self):
        """Creates an IAM role with an auto-generated name.

        This mirrors ``acktest.bootstrapping.iam.Role.bootstrap`` but injects
        ``PermissionsBoundary`` only when one is configured.
        """
        Bootstrappable.bootstrap(self)

        create_role_args = {
            "RoleName": self.name,
            "AssumeRolePolicyDocument": json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": self.principal_service},
                            "Action": ["sts:AssumeRole", "sts:TagSession"],
                        }
                    ],
                }
            ),
            "Description": self.description,
        }
        if self.permissions_boundary:
            create_role_args["PermissionsBoundary"] = self.permissions_boundary

        self.iam_client.create_role(**create_role_args)

        for policy in self.managed_policies:
            self.iam_client.attach_role_policy(
                RoleName=self.name,
                PolicyArn=policy,
            )

        if self.user_policies is not None:
            for arn in self.user_policies.arns:
                self.iam_client.attach_role_policy(
                    RoleName=self.name,
                    PolicyArn=arn,
                )

        iam_resource = self.iam_client.get_role(RoleName=self.name)
        self.arn = iam_resource["Role"]["Arn"]

        # There appears to be a delay in role availability after role creation
        # resulting in failure that role is not present. So adding a delay
        # to allow for the role to become available.
        time.sleep(ROLE_CREATE_WAIT_IN_SECONDS)
