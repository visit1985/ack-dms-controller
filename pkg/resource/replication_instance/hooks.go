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

package replication_instance

import (
	"context"
	"slices"

	svcapitypes "github.com/aws-controllers-k8s/dms-controller/apis/v1alpha1"
	"github.com/aws-controllers-k8s/dms-controller/pkg/util"
	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
	ackrtlog "github.com/aws-controllers-k8s/runtime/pkg/runtime/log"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/databasemigrationservice"
	svcsdktypes "github.com/aws/aws-sdk-go-v2/service/databasemigrationservice/types"
)

const (
	replicationInstanceStatusAvailable = "available"
	//replicationInstanceStatusCreating  = "creating"
	replicationInstanceStatusDeleting = "deleting"
	//replicationInstanceStatusModifying = "modifying"
	//replicationInstanceStatusUpgrading = "upgrading"
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
		rlog.Debug("removing tags from replication instance", "tags", toDelete)
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
		rlog.Debug("adding tags to replication instance", "tags", toAdd)
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

// hasPendingModifiedValues returns true if the ReplicationInstance has any
// pending modifications that have not yet been applied.
func hasPendingModifiedValues(ko *svcapitypes.ReplicationInstance) bool {
	pmv := ko.Status.PendingModifiedValues
	if pmv == nil {
		return false
	}
	return pmv.AllocatedStorage != nil ||
		pmv.EngineVersion != nil ||
		pmv.MultiAZ != nil ||
		pmv.NetworkType != nil ||
		pmv.ReplicationInstanceClass != nil
}

// hasSteadyState is a custom function to determine if a ReplicationInstance
// is in a steady state.
func hasSteadyState(ko *svcapitypes.ReplicationInstance) bool {
	return ko.Status.InstanceStatus != nil && slices.Contains(
		[]string{
			replicationInstanceStatusAvailable,
		},
		*ko.Status.InstanceStatus,
	)
}
