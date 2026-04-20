
// sdk_update_post_set_output hook
//
// Reset Status.UpdateInProgress so the next sync can start the
// task again if needed.
ko.Status.UpdateInProgress = nil
