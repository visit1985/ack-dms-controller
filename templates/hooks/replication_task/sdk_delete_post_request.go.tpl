
// sdk_delete_post_request hook
//
// Wait for the replication task to be deleted before setResourceUnmanaged.
if err != nil {
    return nil, err
}
r.ko.Status.TaskStatus = aws.String(replicationTaskStatusDeleting)
return r, ackrequeue.NeededAfter(
    errors.New(fmt.Sprintf("ReplicationTask is in %v state", *r.ko.Status.TaskStatus)),
    30*time.Second)
