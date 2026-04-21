
// sdk_update_pre_build_request hook
//
// Stop the replication task and make sure it is in a steady state
// before updating it.
if hasSteadyState(latest.ko) {
    if shouldStopReplicationTask(latest.ko, delta) {
        stopReplicationTaskInput := newStopReplicationTaskRequestPayload(latest.ko)
        _, err := rm.sdkapi.StopReplicationTask(ctx, stopReplicationTaskInput)
        rm.metrics.RecordAPICall("UPDATE", "StopReplicationTask", err)
        if err != nil {
            return nil, err
        }
        // Record that we stopped for an update, not by user request
        latest.ko.Status.UpdateInProgress = aws.Bool(true)
        latest.ko.Status.TaskStatus = aws.String(replicationTaskStatusStopping)
        ackcondition.SetSynced(latest, corev1.ConditionFalse,
            aws.String("task entered stopping state"), nil)
        return latest, nil
    }
} else {
    ackcondition.SetSynced(latest, corev1.ConditionFalse,
        aws.String("task not in steady state"), nil)
    return latest, nil
}
