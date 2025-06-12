"""
Snapshot Create Worker Thread

This module contains the worker thread for creating snapshots in bulk.
"""

import time
import getpass
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from pyVmomi import vim
from ..core import ProgressTracker, format_vmware_time


class SnapshotCreateWorker(QThread):
    progress = pyqtSignal(int, int, str)  # completed, total, message
    finished = pyqtSignal()
    error = pyqtSignal(str)
    snapshot_created = pyqtSignal(dict)  # Changed from str to dict to include snapshot details for caching

    def __init__(self, vcenter_connections, servers, description, memory=False, vcenter_username=None):
        super().__init__()
        self.vcenter_connections = vcenter_connections
        self.servers = servers
        self.description = description
        self.memory = memory
        self.vcenter_username = vcenter_username or getpass.getuser()  # Fallback to system user
        self.batch_size = 5  # Process 5 servers per vCenter at a time

    def run(self):
        total = len(self.servers)
        completed = 0
        failed = []
        
        # Show initial progress
        ProgressTracker.emit_progress(
            self.progress, 0, total,
            "Locating", "VMs"
        )
        
        # Group servers by vCenter
        servers_by_vcenter = {}
        for i, server in enumerate(self.servers, 1):
            # Update progress during VM discovery
            ProgressTracker.emit_progress(
                self.progress, i-1, total,
                "Finding", f"{server}"
            )
            
            # Find which vCenter the VM belongs to
            found = False
            for si in self.vcenter_connections.values():
                vm = self.find_vm_in_vcenter(si, server)
                if vm:
                    vcenter = si._stub.host
                    if vcenter not in servers_by_vcenter:
                        servers_by_vcenter[vcenter] = []
                    servers_by_vcenter[vcenter].append((vm, server))
                    found = True
                    break
            if not found:
                failed.append(f"Server not found: {server}")

        if not servers_by_vcenter:
            self.error.emit("No VMs were found in any connected vCenter")
            self.finished.emit()
            return

        # Show how many VMs were found
        found_count = sum(len(servers) for servers in servers_by_vcenter.values())
        ProgressTracker.emit_progress(
            self.progress, 0, total,
            "Creating", f"Found {found_count}"
        )

        # Process each vCenter's servers in batches
        active_tasks = {}  # {task: (server_name, vcenter_name)}
        
        for vcenter, server_list in servers_by_vcenter.items():
            ProgressTracker.emit_progress(
                self.progress, completed, total,
                "Creating", f"{vcenter}"
            )
            
            for i in range(0, len(server_list), self.batch_size):
                batch = server_list[i:i + self.batch_size]
                batch_servers = [s[1] for s in batch]
                ProgressTracker.emit_progress(
                    self.progress, completed, total,
                    "Batch", f"{len(batch_servers)} VMs"
                )
                
                # Start snapshot creation for batch
                for vm, server in batch:
                    try:
                        # Add creator information to description using vCenter username
                        description_with_creator = f"{self.description} (Created by: {self.vcenter_username})"
                        
                        task = vm.CreateSnapshot_Task(
                            name=f"Monthly OS Patching",
                            description=description_with_creator,
                            memory=self.memory,
                            quiesce=False
                        )
                        active_tasks[task] = (server, vcenter)
                    except Exception as e:
                        failed.append(f"Error creating snapshot for {server}: {str(e)}")

                # Monitor tasks
                while active_tasks:
                    for task in list(active_tasks.keys()):
                        server, vcenter = active_tasks[task]
                        try:
                            if task.info.state == vim.TaskInfo.State.success:
                                completed += 1
                                # Get the snapshot we just created
                                snapshot_obj = None
                                if vm.snapshot:
                                    # Find the snapshot that was just created
                                    for snapshot in self.get_snapshots(vm.snapshot.rootSnapshotList):
                                        if snapshot.name == "Monthly OS Patching" and format_vmware_time(snapshot.createTime)[:10] == datetime.now().strftime('%Y-%m-%d'):
                                            snapshot_obj = snapshot
                                            break
                                
                                if snapshot_obj:
                                    # Get creator information from description
                                    # VMware snapshots don't have a built-in createdBy property
                                    created_by = self.extract_creator_from_description(snapshot_obj.description)
                                    
                                    # Emit snapshot details in the same format as SnapshotFetchWorker
                                    # This enables caching by directly adding to the tree without refetching
                                    self.snapshot_created.emit({
                                        'vm_name': vm.name,
                                        'vcenter': vcenter,
                                        'name': snapshot_obj.name,
                                        'created': format_vmware_time(snapshot_obj.createTime),
                                        'created_by': created_by,
                                        'description': snapshot_obj.description or '',
                                        'snapshot': snapshot_obj,
                                        'vm': vm,
                                        'has_children': bool(snapshot_obj.childSnapshotList),
                                        'is_child': hasattr(snapshot_obj, 'parent') and snapshot_obj.parent is not None
                                    })
                                else:
                                    # If we can't find the snapshot object, just emit the server name
                                    # This ensures backward compatibility
                                    self.snapshot_created.emit({'vm_name': server})
                                
                                ProgressTracker.emit_progress(
                                    self.progress, completed, total,
                                    "Created", f"{(completed/total)*100:.1f}%"
                                )
                                del active_tasks[task]
                            elif task.info.state == vim.TaskInfo.State.error:
                                failed.append(f"Failed: {server}: {task.info.error.msg}")
                                del active_tasks[task]
                            else:
                                # Show individual task progress
                                task_progress = task.info.progress or 0
                                active_count = len(active_tasks)
                                ProgressTracker.emit_progress(
                                    self.progress, completed, total,
                                    "Working", f"{server} ({task_progress}%)"
                                )
                        except Exception as e:
                            failed.append(f"Error monitoring {server}: {str(e)}")
                            del active_tasks[task]
                    time.sleep(0.5)

        # Final status
        if failed:
            self.error.emit("\n".join(failed))
        ProgressTracker.emit_progress(
            self.progress, completed, total,
            "Complete", f"{completed} done" + (f", {len(failed)} failed" if failed else "")
        )
        self.finished.emit()

    def find_vm_in_vcenter(self, si, name):
        """Find VM by name in a specific vCenter"""
        content = si.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )
        for vm in container.view:
            if vm.name.lower() == name.lower():
                return vm
        container.Destroy()
        return None

    def find_vm(self, name):
        """Find VM by name across all connected vCenters"""
        for si in self.vcenter_connections.values():
            vm = self.find_vm_in_vcenter(si, name)
            if vm:
                return vm
        return None
        
    def get_snapshots(self, snapshots):
        """Helper method to traverse snapshot tree"""
        result = []
        for snapshot in snapshots:
            result.append(snapshot)
            result.extend(self.get_snapshots(snapshot.childSnapshotList))
        return result
    
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