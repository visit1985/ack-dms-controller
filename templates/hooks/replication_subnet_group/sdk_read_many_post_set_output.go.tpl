
// sdk_read_many_post_set_output hook
//
// The API does not return the ARN so we build it ourselves.
if ko.Status.ACKResourceMetadata == nil {
    ko.Status.ACKResourceMetadata = &ackv1alpha1.ResourceMetadata{}
}
if ko.Status.ACKResourceMetadata.ARN == nil {
    arn := ackv1alpha1.AWSResourceName(fmt.Sprintf(
        "arn:%s:dms:%s:%s:subgrp:%s",
        partitionFromRegion(string(rm.awsRegion)),
        rm.awsRegion,
        rm.awsAccountID,
        *ko.Spec.Name,
    ))
    ko.Status.ACKResourceMetadata.ARN = &arn
}
