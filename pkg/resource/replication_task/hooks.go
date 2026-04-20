// Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"). You may
// not use this file except in compliance with the License. A copy of the
// License is located at
//
//     http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file. This file is distributed
// on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
// express or implied. See the License for the specific language governing
// permissions and limitations under the License.

package replication_task

import (
	"slices"

	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
	"github.com/aws/aws-sdk-go-v2/aws"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/databasemigrationservice"
	svcsdktypes "github.com/aws/aws-sdk-go-v2/service/databasemigrationservice/types"

	svcapitypes "github.com/aws-controllers-k8s/dms-controller/apis/v1alpha1"
	commonutil "github.com/aws-controllers-k8s/dms-controller/pkg/util"
)

const (
	connectionStatusSuccessful = "successful"
	//connectionStatusTesting    = "testing"
	//connectionStatusFailed     = "failed"

	//replicationTaskStatusCreating  = "creating"
	//replicationTaskStatusDeleting  = "deleting"
	replicationTaskStatusFailed = "failed"
	//replicationTaskStatusModifying = "modifying"
	//replicationTaskStatusMoving    = "moving"
	replicationTaskStatusReady    = "ready"
	replicationTaskStatusStopped  = "stopped"
	replicationTaskStatusStopping = "stopping"
	replicationTaskStatusRunning  = "running"
	replicationTaskStatusStarting = "starting"
)

// compareTags is a custom comparison function for comparing lists of Tag
// structs where the order of the structs in the list is not important.
func compareTags(
	delta *ackcompare.Delta,
	a *resource,
	b *resource,
) {
	if len(a.ko.Spec.Tags) != len(b.ko.Spec.Tags) {
		delta.Add("Spec.Tags", a.ko.Spec.Tags, b.ko.Spec.Tags)
	} else if len(a.ko.Spec.Tags) > 0 {
		if !commonutil.EqualTags(a.ko.Spec.Tags, b.ko.Spec.Tags) {
			delta.Add("Spec.Tags", a.ko.Spec.Tags, b.ko.Spec.Tags)
		}
	}
}

// hasSteadyState is a custom function to determine if a ReplicationTask
// is in a steady state.
func hasSteadyState(ko *svcapitypes.ReplicationTask) bool {
	return ko.Status.TaskStatus != nil && slices.Contains(
		[]string{
			replicationTaskStatusFailed,
			replicationTaskStatusReady,
			replicationTaskStatusRunning,
			replicationTaskStatusStopped,
		},
		*ko.Status.TaskStatus,
	)
}

// endpointConnectionsTested is a custom function to determine if a
// ReplicationTasks source and target endpoints have successful
// connection tests.
func endpointConnectionsTested(ko *svcapitypes.ReplicationTask) bool {
	return ko.Status.SourceEndpointConnectionStatus != nil &&
		*ko.Status.SourceEndpointConnectionStatus == connectionStatusSuccessful &&
		ko.Status.TargetEndpointConnectionStatus != nil &&
		*ko.Status.TargetEndpointConnectionStatus == connectionStatusSuccessful
}

// deleteRequested is a custom function to determine if a ReplicationTask is
// requested to be deleted
func deleteRequested(ko *svcapitypes.ReplicationTask) bool {
	return ko.ObjectMeta.GetDeletionTimestamp() != nil
}

// startRequested is a custom function to determine if a ReplicationTask is
// requested to be started
func startRequested(ko *svcapitypes.ReplicationTask) bool {
	return ko.Spec.StartReplicationTask != nil && *ko.Spec.StartReplicationTask
}

// updateRequiresStop is a custom function to determine if a ReplicationTask
// update requires the task to be stopped first.
func updateRequiresStop(delta *ackcompare.Delta) bool {
	return delta.DifferentExcept("Spec.StartReplicationTask", "Spec.Tags")
}

// updateInProgress is a custom function to determine if a ReplicationTask
// update is in progress by checking UpdateInProgress status attribute.
func updateInProgress(ko *svcapitypes.ReplicationTask) bool {
	return ko.Status.UpdateInProgress != nil && *ko.Status.UpdateInProgress
}

// alreadyStarted is a custom function to determine if a ReplicationTask
// is already started.
func alreadyStarted(ko *svcapitypes.ReplicationTask) bool {
	return ko.Status.TaskStatus != nil && slices.Contains(
		[]string{
			replicationTaskStatusRunning,
			replicationTaskStatusStarting,
		},
		*ko.Status.TaskStatus,
	)
}

// alreadyStopped is a custom function to determine if a ReplicationTask
// is already stopped.
func alreadyStopped(ko *svcapitypes.ReplicationTask) bool {
	return ko.Status.TaskStatus != nil && slices.Contains(
		[]string{
			replicationTaskStatusFailed,
			replicationTaskStatusStopping,
			replicationTaskStatusStopped,
		},
		*ko.Status.TaskStatus,
	)
}

// shouldStartReplicationTask is a custom function to determine if a
// ReplicationTask should be started.
func shouldStartReplicationTask(ko *svcapitypes.ReplicationTask) bool {
	return !updateInProgress(ko) && !deleteRequested(ko) && startRequested(ko) &&
		endpointConnectionsTested(ko) && !alreadyStarted(ko)
}

// shouldStopReplicationTask is a custom function to determine if a
// ReplicationTask should be stopped.
func shouldStopReplicationTask(ko *svcapitypes.ReplicationTask, delta *ackcompare.Delta) bool {
	return (deleteRequested(ko) || !startRequested(ko) || updateRequiresStop(delta)) &&
		!alreadyStopped(ko)
}

// newStartReplicationTaskRequestPayload is a custom function to
// constructs the input for the StartReplicationTask operation based
// on the current state of the ReplicationTask.
func newStartReplicationTaskRequestPayload(ko *svcapitypes.ReplicationTask) *svcsdk.StartReplicationTaskInput {
	startReplicationTaskType := svcsdktypes.StartReplicationTaskTypeValueStartReplication
	if ko.Status.TaskStatus != nil && *ko.Status.TaskStatus == replicationTaskStatusReady {
		startReplicationTaskType = svcsdktypes.StartReplicationTaskTypeValueResumeProcessing
	}
	return &svcsdk.StartReplicationTaskInput{
		ReplicationTaskArn:       aws.String(string(*ko.Status.ACKResourceMetadata.ARN)),
		StartReplicationTaskType: startReplicationTaskType,
	}
}

// newStopReplicationTaskRequestPayload is a custom function to
// constructs the input for the StopReplicationTask operation.
func newStopReplicationTaskRequestPayload(ko *svcapitypes.ReplicationTask) *svcsdk.StopReplicationTaskInput {
	return &svcsdk.StopReplicationTaskInput{
		ReplicationTaskArn: aws.String(string(*ko.Status.ACKResourceMetadata.ARN)),
	}
}
