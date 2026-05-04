
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
        return r, ackrequeue.NeededAfter(errors.New("ReplicationTask entered stopping state"), 10*time.Second)
    }
} else {
	if r.ko.Status.TaskStatus == aws.String(replicationTaskStatusDeleting) {
        return r, ackrequeue.NeededAfter(errors.New("Waiting for ReplicationTask deletion to complete"), 10*time.Second)
    }
    return r, ackrequeue.NeededAfter(errors.New("ReplicationTask not in a steady state"), 10*time.Second)
}
