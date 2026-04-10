
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
            return nil, err
        }
    } else {
        return &resource{ko}, ackrequeue.NeededAfter(nil, 10*time.Second)
    }
}
