
// sdk_delete_post_request hook
//
// Wait for the replication task to be deleted before setResourceUnmanaged.
if err != nil {
    return nil, err
}
r.ko.Status.TaskStatus = aws.String(replicationTaskStatusDeleting)
return r, ackrequeue.NeededAfter(errors.New("Waiting for ReplicationTask deletion to complete"), 10*time.Second)
