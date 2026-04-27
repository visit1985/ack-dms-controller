
// sdk_delete_post_request hook
//
// Wait for the replication instance to be deleted before setResourceUnmanaged.
if err != nil {
    return nil, err
}
r.ko.Status.ReplicationInstanceStatus = aws.String(replicationInstanceStatusDeleting)
return r, ackrequeue.NeededAfter(errors.New("Waiting for ReplicationInstance deletion to complete"), 10*time.Second)
