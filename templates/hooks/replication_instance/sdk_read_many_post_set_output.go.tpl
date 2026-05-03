
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
        aws.String("ReplicationInstance not in steady state"), nil)
    return &resource{ko}, nil
}
