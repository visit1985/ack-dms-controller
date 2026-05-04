
// sdk_delete_pre_build_request hook
//
// Make sure replication instance is in a steady state before deleting it.
if !hasSteadyState(r.ko){
    return r, ackrequeue.NeededAfter(
        errors.New(fmt.Sprintf("ReplicationInstance is in %v state", *r.ko.Status.InstanceStatus),
    ), 10*time.Second)
}
