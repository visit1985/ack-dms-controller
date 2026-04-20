
// sdk_delete_pre_build_request hook
//
// Stop the replication task and make sure it is in a steady state
// before deleting it.
if hasSteadyState(r.ko) {
    if shouldStopReplicationTask(r.ko, nil) {
        stopReplicationTaskInput := newStopReplicationTaskRequestPayload(r.ko)
        _, err := rm.sdkapi.StopReplicationTask(ctx, stopReplicationTaskInput)
        rm.metrics.RecordAPICall("UPDATE", "StopReplicationTask", err)
        if err != nil {
            return nil, err
        }
        // Requeue because we enter "stopping" state now
        return nil, ackrequeue.NeededAfter(nil, 10*time.Second)
    }
} else {
    return nil, ackrequeue.NeededAfter(nil, 10*time.Second)
}
