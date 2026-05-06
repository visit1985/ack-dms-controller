
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
		r.ko.Status.TaskStatus = aws.String(replicationTaskStatusStopping)
        return r, ackrequeue.NeededAfter(
            errors.New(fmt.Sprintf("ReplicationTask is in %v state", *r.ko.Status.TaskStatus)),
            30*time.Second)
    }
} else {
    return r, ackrequeue.NeededAfter(
        errors.New(fmt.Sprintf("ReplicationTask is in %v state", *r.ko.Status.TaskStatus)),
        30*time.Second)
}
