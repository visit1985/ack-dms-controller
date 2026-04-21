
// sdk_delete_post_request hook
//
// Wait for the endpoint to be deleted before setResourceUnmanaged.
if err != nil {
    return nil, err
}
r.ko.Status.EndpointStatus = aws.String(endpointStatusDeleting)
return r, nil
