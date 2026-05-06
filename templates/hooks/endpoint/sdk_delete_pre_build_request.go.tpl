
// sdk_delete_pre_build_request hook
//
// Stop the replication task and make sure it is in a steady state
// before deleting it.
if r.ko.Status.EndpointStatus != nil && *r.ko.Status.EndpointStatus != endpointStatusDeleted {
    return r, ackrequeue.NeededAfter(
        errors.New(fmt.Sprintf("Endpoint is in %v state", *r.ko.Status.EndpointStatus)),
        10*time.Second)
}
