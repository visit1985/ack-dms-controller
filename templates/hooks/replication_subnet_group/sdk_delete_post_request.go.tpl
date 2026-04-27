
// sdk_delete_post_request hook
//
// Wait for the replication subnet group to be deleted before setResourceUnmanaged.
if err != nil {
    return nil, err
}
r.ko.Status.SubnetGroupStatus = aws.String(replicationSubnetGroupStatusDeleting)
return r, ackrequeue.NeededAfter(errors.New("Waiting for ReplicationSubnetGroup deletion to complete"), 10*time.Second)
