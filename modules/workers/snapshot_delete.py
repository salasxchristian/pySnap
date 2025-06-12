"""
Snapshot Delete Worker Thread

This module contains the worker thread for deleting snapshots in bulk.
"""

import time
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QTreeWidgetItem
from pyVmomi import vim
from ..core import ProgressTracker


class SnapshotDeleteWorker(QThread):
    """Worker thread for deleting snapshots"""
    progress = pyqtSignal(int, int, str)  # completed, total, message
    finished = pyqtSignal()
    error = pyqtSignal(str)
    item_complete = pyqtSignal(QTreeWidgetItem)

    def __init__(self, items_to_delete):
        super().__init__()
        self.items_to_delete = items_to_delete

    def run(self):
        total = len(self.items_to_delete)
        completed = 0
        active_tasks = {}  # Store active deletion tasks
        
        # Start all deletion tasks
        for item, data in self.items_to_delete:
            try:
                ProgressTracker.emit_progress(
                    self.progress, completed, total,
                    "Deleting", f"{data['vm_name']}"
                )
                
                # Get the VM and snapshot objects
                snapshot = data['snapshot']
                
                # Create deletion task
                task = snapshot.snapshot.RemoveSnapshot_Task(removeChildren=False)
                active_tasks[task] = (item, data)
                
            except Exception as e:
                self.error.emit(f"Error starting deletion of {data['name']}: {str(e)}")
        
        # Monitor all tasks until completion
        while active_tasks:
            total_progress = 0
            
            for task in list(active_tasks.keys()):
                item, data = active_tasks[task]
                try:
                    if task.info.state == vim.TaskInfo.State.success:
                        self.item_complete.emit(item)
                        completed += 1
                        del active_tasks[task]
                    elif task.info.state == vim.TaskInfo.State.error:
                        self.error.emit(f"Failed to delete {data['name']}: {task.info.error.msg}")
                        del active_tasks[task]
                    else:
                        # Task still in progress, add to total progress
                        task_progress = task.info.progress or 0
                        total_progress += task_progress
                except Exception as e:
                    self.error.emit(f"Error monitoring {data['name']}: {str(e)}")
                    del active_tasks[task]
            
            # Calculate and show overall progress
            if active_tasks:
                overall_progress = (completed * 100 + total_progress) / total
                ProgressTracker.emit_progress(
                    self.progress, completed, total,
                    "Deleting", f"{overall_progress:.0f}%"
                )
            
            # Small delay before next check
            time.sleep(0.5)
        
        ProgressTracker.emit_progress(
            self.progress, total, total,
            "Complete", "All deleted"
        )
        self.finished.emit()