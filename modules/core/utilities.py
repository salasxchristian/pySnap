"""
Utility Functions

This module contains utility functions used throughout the application.
"""

from datetime import timezone


def format_vmware_time(vmware_datetime):
    """
    Convert VMware's UTC datetime to local timezone and format as string.
    
    Args:
        vmware_datetime: VMware createTime datetime object (assumed to be UTC)
        
    Returns:
        str: Formatted datetime string in local timezone ('YYYY-MM-DD HH:MM')
    """
    # VMware createTime appears to be in UTC, convert to local timezone
    if vmware_datetime.tzinfo is None:
        # Treat as UTC if no timezone info
        vmware_datetime = vmware_datetime.replace(tzinfo=timezone.utc)
    
    # Convert to local timezone
    local_time = vmware_datetime.astimezone()
    
    # Format as string
    return local_time.strftime('%Y-%m-%d %H:%M')