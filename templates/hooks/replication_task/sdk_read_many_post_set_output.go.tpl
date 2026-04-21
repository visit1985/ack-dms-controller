
// sdk_read_many_post_set_output hook
//
// Fetch connection Status and LastFailureMessage for Endpoints.
// Clear the failure message if the connections are successful,
// otherwise set them to the latest failure message.
describeConnectionsInput := &svcsdk.DescribeConnectionsInput{
    Filters: []svcsdktypes.Filter{
        {
            Name:   aws.String("endpoint-arn"),
            Values: []string{
                string(*ko.Spec.SourceEndpointARN),
                string(*ko.Spec.TargetEndpointARN),
            },
        },
        {
            Name:   aws.String("replication-instance-arn"),
            Values: []string{string(*ko.Spec.ReplicationInstanceARN)},
        },
    },
}
respDescribeConnections, err := rm.sdkapi.DescribeConnections(ctx, describeConnectionsInput)
rm.metrics.RecordAPICall("READ_MANY", "DescribeConnections", err)
if err != nil {
    var awsErr smithy.APIError
    if errors.As(err, &awsErr) && awsErr.ErrorCode() == "ResourceNotFoundFault" {
        ackcondition.SetSynced(&resource{ko}, corev1.ConditionFalse,
            aws.String("connection status not found"), nil)
        return &resource{ko}, nil
    }
    return &resource{ko}, err
}
for _, elem := range respDescribeConnections.Connections {
    if *elem.EndpointArn == *ko.Spec.SourceEndpointARN {
        if elem.Status != nil {
            ko.Status.SourceEndpointConnectionStatus = elem.Status
        }
        ko.Status.SourceEndpointConnectionLastFailureMessage = elem.LastFailureMessage
    }
    if *elem.EndpointArn == *ko.Spec.TargetEndpointARN {
        if elem.Status != nil {
            ko.Status.TargetEndpointConnectionStatus = elem.Status
        }
        ko.Status.TargetEndpointConnectionLastFailureMessage = elem.LastFailureMessage
    }
}

// sdk_read_many_post_set_output hook
//
// Start the replication task if the custom StartReplicationTask field in
// the Spec is set to true and the task is not already started and is in a
// steady state.
if shouldStartReplicationTask(ko) {
    if hasSteadyState(ko) {
        startReplicationTaskInput := newStartReplicationTaskRequestPayload(ko)
        _, err := rm.sdkapi.StartReplicationTask(ctx, startReplicationTaskInput)
        rm.metrics.RecordAPICall("UPDATE", "StartReplicationTask", err)
        if err != nil {
            return &resource{ko}, err
        }
        ko.Status.TaskStatus = aws.String(replicationTaskStatusStarting)
        ackcondition.SetSynced(&resource{ko}, corev1.ConditionFalse,
            aws.String("task entered starting state"), nil)
        return &resource{ko}, nil
    }
}

// sdk_read_many_post_set_output hook
//
// If the replication task is not in a steady state, requeue more frequently.
if !hasSteadyState(ko) {
    ackcondition.SetSynced(&resource{ko}, corev1.ConditionFalse,
        aws.String("task not in steady state"), nil)
    return &resource{ko}, nil
}
