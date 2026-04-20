
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
        // Requeue because we enter "stopping" state now
        return latest, ackrequeue.NeededAfter(nil, 10*time.Second)
    }
} else {
    return nil, ackrequeue.NeededAfter(nil, 10*time.Second)
}
