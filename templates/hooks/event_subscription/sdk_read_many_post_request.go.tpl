
// sdk_read_many_post_request hook
//
// Map ResourceNotFoundFault to NotFound error so ACK can trigger createResource
// correctly.
if err != nil {
    var awsErr smithy.APIError
    if errors.As(err, &awsErr) && awsErr.ErrorCode() == "ResourceNotFoundFault" {
        rm.metrics.RecordAPICall("READ_MANY", "DescribeEventSubscriptions", err)
        return nil, ackerr.NotFound
    }
}
