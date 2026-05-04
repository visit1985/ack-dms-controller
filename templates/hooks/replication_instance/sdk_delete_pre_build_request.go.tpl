
// sdk_delete_pre_build_request hook
//
// Make sure replication instance is in a steady state before deleting it.
if !hasSteadyState(r.ko){
    if r.ko.Status.InstanceStatus == aws.String(replicationInstanceStatusDeleting) {
        return r, ackrequeue.NeededAfter(errors.New("Waiting for ReplicationInstance deletion to complete"), 10*time.Second)
    }
    return r, ackrequeue.NeededAfter(errors.New("ReplicationInstance not in a steady state"), 10*time.Second)
}
