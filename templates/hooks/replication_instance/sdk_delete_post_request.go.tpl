
// sdk_delete_post_request hook
//
// Wait for the replication instance to be deleted before setResourceUnmanaged.
if err != nil {
    return nil, err
}
r.ko.Status.InstanceStatus = aws.String(replicationInstanceStatusDeleting)
return r, ackrequeue.NeededAfter(
    errors.New(fmt.Sprintf("ReplicationInstance is in %v state", *r.ko.Status.InstanceStatus)),
    60*time.Second)
