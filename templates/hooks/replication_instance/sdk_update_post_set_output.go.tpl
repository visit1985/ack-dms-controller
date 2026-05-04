
// sdk_update_post_set_output hook
//
// Merge PendingModifiedValues back into Spec so the delta does not trigger a
// redundant ModifyReplicationInstance call while the change is still being
// applied.
pmv := ko.Status.PendingModifiedValues
if pmv != nil {
    if pmv.MultiAZ != nil {
        ko.Spec.MultiAZ = pmv.MultiAZ
    }
    if pmv.ReplicationInstanceClass != nil {
        ko.Spec.InstanceClass = pmv.ReplicationInstanceClass
    }
    if pmv.AllocatedStorage != nil {
        ko.Spec.AllocatedStorage = pmv.AllocatedStorage
    }
    if pmv.EngineVersion != nil {
        ko.Spec.EngineVersion = pmv.EngineVersion
    }
    if pmv.NetworkType != nil {
        ko.Spec.NetworkType = pmv.NetworkType
    }
}
