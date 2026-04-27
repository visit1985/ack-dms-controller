
// sdk_delete_post_request hook
//
// Wait for the event subscription to be deleted before setResourceUnmanaged.
if err != nil {
    return nil, err
}
r.ko.Status.SubscriptionStatus = aws.String(eventSubscriptionStatusDeleting)
return r, ackrequeue.NeededAfter(errors.New("Waiting for EventSubscription deletion to complete"), 10*time.Second)
