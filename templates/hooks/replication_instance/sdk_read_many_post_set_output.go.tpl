
// sdk_read_many_post_set_output hook
//
// Merge PendingModifiedValues back into Spec so the delta does not trigger a
// redundant ModifyReplicationInstance call while the change is still being
// applied.
pmv := ko.Status.PendingModifiedValues
if pmv == nil {
    if pmv.MultiAZ != nil {
        ko.Spec.MultiAZ = pmv.MultiAZ
    }
    if pmv.ReplicationInstanceClass != nil {
        ko.Spec.InstanceClass = pmv.ReplicationInstanceClass
    }
    if pmv.AllocatedStorage != nil {
        ko.Spec.AllocatedStorage = pmv.AllocatedStorage
    }
    if pmv.EngineVersion != nil {
        ko.Spec.EngineVersion = pmv.EngineVersion
    }
    if pmv.NetworkType != nil {
        ko.Spec.NetworkType = pmv.NetworkType
    }
}

// sdk_read_many_post_set_output hook
//
// Retrieves the latest tags
if ko.ObjectMeta.GetDeletionTimestamp() == nil {
    if ko.Status.ACKResourceMetadata != nil && ko.Status.ACKResourceMetadata.ARN != nil {
        resourceARN := (*string)(ko.Status.ACKResourceMetadata.ARN)
        tags, err := rm.getTags(ctx, *resourceARN)
        if err != nil {
            return nil, err
        }
        ko.Spec.Tags = tags
    }
}

// sdk_read_many_post_set_output hook
//
// If the replication instance is not in a steady state, requeue more frequently.
if !hasSteadyState(ko) {
    ackcondition.SetSynced(&resource{ko}, corev1.ConditionFalse,
        aws.String(fmt.Sprintf("ReplicationInstance is in %v state", ko.Status.InstanceStatus)), nil)
    return &resource{ko}, nil
}

// sdk_read_many_post_set_output hook
//
// Requeue if there are pending modified values. Even though we pass
// ApplyImmediately the resource may stay in status `available` for a short
// period of time before switching to `modifying`.
if hasPendingModifiedValues(ko) {
    ackcondition.SetSynced(&resource{ko}, corev1.ConditionFalse,
        aws.String("ReplicationInstance has pending modified values"), nil)
    return &resource{ko}, nil
}
