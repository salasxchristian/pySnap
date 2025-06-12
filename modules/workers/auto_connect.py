"""
Auto-Connect Worker Thread

This module contains the worker thread for auto-connecting to saved vCenters.
"""

import ssl
import socket
import urllib3
from PyQt6.QtCore import QThread, pyqtSignal
from pyVim.connect import SmartConnect


class AutoConnectWorker(QThread):
    """Worker thread for auto-connecting to saved vCenters"""
    progress = pyqtSignal(str)  # status message
    connection_made = pyqtSignal(str, object, dict)  # hostname, service_instance, credentials
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, saved_servers, config_manager):
        super().__init__()
        self.saved_servers = saved_servers
        self.config_manager = config_manager

    def run(self):
        try:
            # Set socket timeout for all connections in this thread
            socket.setdefaulttimeout(10.0)  # Increased to 10 seconds
            
            servers = list(self.saved_servers.items())
            total = len(servers)
            connected = 0
            
            for hostname, server_data in servers:
                # Handle both old format (string) and new format (dict)
                if isinstance(server_data, str):
                    username = server_data
                    verify_ssl = False
                else:
                    username = server_data.get('username', '')
                    verify_ssl = server_data.get('verify_ssl', False)
                
                secure_password = self.config_manager.get_password(hostname, username)
                if secure_password and not secure_password.is_empty():
                    try:
                        connected += 1
                        self.progress.emit(f"Auto-connecting to {hostname}... ({connected}/{total})")
                        
                        # Create SSL context based on saved preference
                        context = ssl.create_default_context()
                        if not verify_ssl:
                            context.check_hostname = False
                            context.verify_mode = ssl.CERT_NONE
                            # Disable SSL verification warnings
                            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                        
                        # Get password string briefly for connection
                        password_str = secure_password.get_password()
                        try:
                            si = SmartConnect(
                                host=hostname,
                                user=username,
                                pwd=password_str,
                                sslContext=context,
                                disableSslCertValidation=not verify_ssl
                            )
                        finally:
                            # Clear the temporary password string
                            password_str = '\0' * len(password_str)
                            del password_str
                        
                        if si:
                            credentials = {
                                'username': username, 
                                'password': secure_password,
                                'verify_ssl': verify_ssl
                            }
                            self.connection_made.emit(hostname, si, credentials)
                        else:
                            self.error.emit(f"Failed to connect to {hostname}: No service instance returned")
                    except socket.timeout:
                        self.error.emit(f"Connection to {hostname} timed out after 10 seconds")
                        # Continue with next server
                    except socket.gaierror as e:
                        self.error.emit(f"Cannot resolve hostname {hostname}: {str(e)}")
                        # Continue with next server
                    except ConnectionRefusedError as e:
                        self.error.emit(f"Connection refused by {hostname}: {str(e)}")
                        # Continue with next server
                    except Exception as e:
                        # Log but don't crash - continue with next server
                        self.error.emit(f"Failed to auto-connect to {hostname}: {type(e).__name__}: {str(e)}")
                        # Continue with next server
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(f"Auto-connect error: {str(e)}")
        finally:
            # Reset socket timeout to default
            socket.setdefaulttimeout(None)