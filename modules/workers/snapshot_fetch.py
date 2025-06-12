"""
Snapshot Fetch Worker Thread

This module contains the worker thread for fetching snapshots from vCenter servers.
"""

import logging
import re
from PyQt6.QtCore import QThread, pyqtSignal
from pyVmomi import vim


from ..core import format_vmware_time, ProgressTracker


class SnapshotFetchWorker(QThread):
    """Worker thread for fetching snapshots"""
    finished = pyqtSignal()
    progress = pyqtSignal(int, int, str)  # completed, total, message
    snapshot_found = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, vcenter_connections):
        super().__init__()
        self.vcenter_connections = vcenter_connections
        self.logger = logging.getLogger('pySnap')

    def run(self):
        try:
            total_vcenters = len(self.vcenter_connections)
            completed_vcenters = 0
            
            for hostname, si in self.vcenter_connections.items():
                container = None
                try:
                    ProgressTracker.emit_progress(
                        self.progress, completed_vcenters, total_vcenters,
                        "Connecting", f"{hostname}"
                    )
                    
                    content = si.RetrieveContent()
                    container = content.viewManager.CreateContainerView(
                        content.rootFolder, [vim.VirtualMachine], True
                    )
                    self.logger.info(f"Created container view for {hostname}")
                    
                    # Count VMs with snapshots for more detailed progress
                    snapshot_vms = 0
                    processed_vms = 0
                    
                    # First count VMs with snapshots
                    for vm in container.view:
                        if vm.snapshot:
                            snapshot_vms += 1
                    
                    if snapshot_vms > 0:
                        # Now process VMs with progress updates
                        for vm in container.view:
                            if vm.snapshot:
                                processed_vms += 1
                                ProgressTracker.emit_progress(
                                    self.progress, processed_vms, snapshot_vms,
                                    "Processing", f"{vm.name}"
                                )
                                
                                for snapshot in self.get_snapshots(vm.snapshot.rootSnapshotList):
                                    # Get creator information from snapshot description
                                    # VMware snapshots don't have a built-in createdBy property
                                    created_by = self.extract_creator_from_description(snapshot.description)
                                    
                                    self.snapshot_found.emit({
                                        'vm_name': vm.name,
                                        'vcenter': hostname,
                                        'name': snapshot.name,
                                        'created': format_vmware_time(snapshot.createTime),
                                        'created_by': created_by,
                                        'description': snapshot.description or '',
                                        'snapshot': snapshot,
                                        'vm': vm,
                                        'has_children': bool(snapshot.childSnapshotList),
                                        'is_child': hasattr(snapshot, 'parent') and snapshot.parent is not None
                                    })
                    
                    completed_vcenters += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing vCenter {hostname}: {str(e)}")
                    self.error.emit(f"Error processing {hostname}: {str(e)}")
                    
                finally:
                    # CRITICAL: Always destroy the container view to prevent resource leaks
                    if container:
                        try:
                            container.Destroy()
                            self.logger.info(f"Destroyed container view for {hostname}")
                        except Exception as destroy_error:
                            self.logger.error(f"Failed to destroy container view for {hostname}: {str(destroy_error)}")
                            # Don't re-raise - we don't want destroy failure to mask original error
            
            # Final progress update
            ProgressTracker.emit_progress(
                self.progress, total_vcenters, total_vcenters,
                "Complete", "Snapshots retrieved"
            )
            self.finished.emit()
            
        except Exception as e:
            self.logger.error(f"Fatal error in snapshot fetch worker: {str(e)}")
            self.error.emit(str(e))

    def get_snapshots(self, snapshots):
        result = []
        for snapshot in snapshots:
            result.append(snapshot)
            result.extend(self.get_snapshots(snapshot.childSnapshotList))
        return result
    
    def extract_creator_from_description(self, description):
        """
        Extract creator information from snapshot description.
        VMware snapshots don't have a built-in 'createdBy' property,
        so we need to parse it from the description field.
        """
        if not description:
            return 'Unknown'
        
        # Look for patterns like "Created by: username" or "(Created by: username)"
        patterns = [
            r'\(Created by:\s*([^)]+)\)',  # (Created by: username)
            r'Created by:\s*([^\n,;]+)',   # Created by: username
            r'\[Created by:\s*([^\]]+)\]', # [Created by: username]
            r'User:\s*([^\n,;]+)',         # User: username
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return 'Unknown'
    
    def extract_creator_from_description(self, description):
        """
        Extract creator information from snapshot description.
        
        VMware snapshots don't have a built-in createdBy property,
        so we look for creator information in the description field.
        
        Args:
            description (str): The snapshot description
            
        Returns:
            str: The username who created the snapshot, or 'Unknown'
        """
        if not description:
            return 'Unknown'
        
        import re
        
        # Look for patterns like "Created by: username" or "(Created by: username)"
        patterns = [
            r'Created by:\s*(\w+)',
            r'\(Created by:\s*(\w+)\)',
            r'User:\s*(\w+)',
            r'By:\s*(\w+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return 'Unknown'