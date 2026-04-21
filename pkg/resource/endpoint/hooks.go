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

package endpoint

import (
	commonutil "github.com/aws-controllers-k8s/dms-controller/pkg/util"
	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
)

const (
	endpointStatusDeleting = "deleting"
)

// customPreCompare contains logic that help compare two iam Roles. This
// function is injected in newResourceDelta function.
func customPreCompare(
	delta *ackcompare.Delta,
	a *resource,
	b *resource,
) {
	compareTags(delta, a, b)
	compareExtraArchivedLogDestIDs(delta, a, b)
}

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

// compareExtraArchivedLogDestIDs is a custom comparison function for comparing
// lists of ExtraArchivedLogDestID where the order of the values in the list
// and any duplicate values are not important.
func compareExtraArchivedLogDestIDs(
	delta *ackcompare.Delta,
	a *resource,
	b *resource,
) {
	if a.ko.Spec.OracleSettings == nil || b.ko.Spec.OracleSettings == nil {
		return
	}
	if ackcompare.HasNilDifference(a.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs,
		b.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs) {
		delta.Add("Spec.OracleSettings.ExtraArchivedLogDestIDs",
			a.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs, b.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs)
		return
	}
	if a.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs == nil { // both nil
		return
	}
	if len(a.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs) != len(b.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs) {
		delta.Add("Spec.OracleSettings.ExtraArchivedLogDestIDs",
			a.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs, b.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs)
	} else if len(a.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs) > 0 {
		aMap := make(map[int64]bool)
		for _, val := range a.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs {
			if val != nil {
				aMap[*val] = true
			}
		}
		aDiff := false
		for _, val := range b.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs {
			if val == nil || !aMap[*val] {
				aDiff = true
				break
			}
		}
		if aDiff {
			delta.Add("Spec.OracleSettings.ExtraArchivedLogDestIDs",
				a.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs, b.ko.Spec.OracleSettings.ExtraArchivedLogDestIDs)
		}
	}
}
