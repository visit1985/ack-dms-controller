
// sdk_update_pre_set_output hook
//
if latest.ko.ObjectMeta.GetDeletionTimestamp() == nil {
    if delta.DifferentAt("Spec.Tags") {
        if err = rm.syncTags(ctx, desired, latest); err != nil {
            return nil, err
        }
    }
}
