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
	"context"
	"slices"

	svcapitypes "github.com/aws-controllers-k8s/dms-controller/apis/v1alpha1"
	"github.com/aws-controllers-k8s/dms-controller/pkg/util"
	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
	ackrtlog "github.com/aws-controllers-k8s/runtime/pkg/runtime/log"
	"github.com/aws/aws-sdk-go-v2/aws"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/databasemigrationservice"
	svcsdktypes "github.com/aws/aws-sdk-go-v2/service/databasemigrationservice/types"
)

const (
	connectionStatusSuccessful = "successful"
	//connectionStatusTesting    = "testing"
	//connectionStatusFailed     = "failed"

	//replicationTaskStatusCreating  = "creating"
	replicationTaskStatusDeleting = "deleting"
	replicationTaskStatusFailed   = "failed"
	//replicationTaskStatusModifying = "modifying"
	//replicationTaskStatusMoving    = "moving"
	replicationTaskStatusReady    = "ready"
	replicationTaskStatusRunning  = "running"
	replicationTaskStatusStarting = "starting"
	replicationTaskStatusStopped  = "stopped"
	replicationTaskStatusStopping = "stopping"
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
		if !util.EqualTags(a.ko.Spec.Tags, b.ko.Spec.Tags) {
			delta.Add("Spec.Tags", a.ko.Spec.Tags, b.ko.Spec.Tags)
		}
	}
}

// getTags retrieves the resource's associated tags
func (rm *resourceManager) getTags(
	ctx context.Context,
	resourceARN string,
) ([]*svcapitypes.Tag, error) {
	resp, err := rm.sdkapi.ListTagsForResource(
		ctx,
		&svcsdk.ListTagsForResourceInput{
			ResourceArn: &resourceARN,
		},
	)
	rm.metrics.RecordAPICall("GET", "ListTagsForResource", err)
	if err != nil {
		return nil, err
	}
	tags := make([]*svcapitypes.Tag, 0, len(resp.TagList))
	for _, tag := range resp.TagList {
		tags = append(tags, &svcapitypes.Tag{
			Key:   tag.Key,
			Value: tag.Value,
		})
	}
	return tags, nil
}

// syncTags keeps the resource's tags in sync
func (rm *resourceManager) syncTags(
	ctx context.Context,
	desired *resource,
	latest *resource,
) (err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.syncTags")
	defer func() { exit(err) }()

	arn := (*string)(latest.ko.Status.ACKResourceMetadata.ARN)

	toAdd, toDelete := util.ComputeTagsDelta(
		desired.ko.Spec.Tags, latest.ko.Spec.Tags,
	)

	if len(toDelete) > 0 {
		rlog.Debug("removing tags from replication task", "tags", toDelete)
		_, err = rm.sdkapi.RemoveTagsFromResource(
			ctx,
			&svcsdk.RemoveTagsFromResourceInput{
				ResourceArn: arn,
				TagKeys:     toDelete,
			},
		)
		rm.metrics.RecordAPICall("UPDATE", "RemoveTagsFromResource", err)
		if err != nil {
			return err
		}
	}

	if len(toAdd) > 0 {
		rlog.Debug("adding tags to replication task", "tags", toAdd)
		_, err = rm.sdkapi.AddTagsToResource(
			ctx,
			&svcsdk.AddTagsToResourceInput{
				ResourceArn: arn,
				Tags:        sdkTagsFromResourceTags(toAdd),
			},
		)
		rm.metrics.RecordAPICall("UPDATE", "AddTagsToResource", err)
		if err != nil {
			return err
		}
	}
	return nil
}

// sdkTagsFromResourceTags transforms a *svcapitypes.Tag array to a *svcsdk.Tag
// array.
func sdkTagsFromResourceTags(
	rTags []*svcapitypes.Tag,
) []svcsdktypes.Tag {
	tags := make([]svcsdktypes.Tag, len(rTags))
	for i := range rTags {
		tags[i] = svcsdktypes.Tag{
			Key:   rTags[i].Key,
			Value: rTags[i].Value,
		}
	}
	return tags
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
// was already started.
func alreadyStarted(ko *svcapitypes.ReplicationTask) bool {
	if ko.Status.TaskStatus == nil {
		return false
	}
	// if status is running or starting
	c1 := *ko.Status.TaskStatus == replicationTaskStatusRunning ||
		*ko.Status.TaskStatus == replicationTaskStatusStarting
	// if status is stopping or stopped and migration type is full-load
	c2 := (*ko.Status.TaskStatus == replicationTaskStatusStopping ||
		*ko.Status.TaskStatus == replicationTaskStatusStopped) &&
		*ko.Spec.MigrationType == string(svcsdktypes.MigrationTypeValueFullLoad)
	return c1 || c2
}

// alreadyStopped is a custom function to determine if a ReplicationTask
// is already stopped.
func alreadyStopped(ko *svcapitypes.ReplicationTask) bool {
	if ko.Status.TaskStatus == nil {
		return true
	}
	// if status is not running or starting
	return *ko.Status.TaskStatus != replicationTaskStatusRunning &&
		*ko.Status.TaskStatus != replicationTaskStatusStarting
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
	if ko.Status.TaskStatus != nil && *ko.Status.TaskStatus != replicationTaskStatusReady {
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
