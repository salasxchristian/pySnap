"""
Encrypted Configuration Manager for pySnap

Provides secure SQLite-based configuration storage with Fernet encryption.
Automatically migrates from legacy JSON configuration files.
"""

import os
import sys
import sqlite3
import json
import logging
import keyring
from datetime import datetime
from typing import List, Dict, Optional, Any
from cryptography.fernet import Fernet
from secure_password import SecurePassword


class ConfigurationError(Exception):
    """Base exception for configuration errors"""
    pass


class MigrationError(ConfigurationError):
    """Raised when migration fails"""
    pass


class DatabaseError(ConfigurationError):
    """Raised when database operations fail"""
    pass


class EncryptedConfigManager:
    """Cross-platform encrypted configuration manager using SQLite + Fernet"""
    
    def __init__(self):
        self.app_name = "pySnap"
        self.keyring_service = "pysnap"  # New keyring service name
        self.password_keyring_service = "pysnap"  # For vCenter passwords
        self.db_path = self._get_db_path()
        self.migration_marker = self._get_migration_marker_path()
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Ensure migration runs first
        self._ensure_migration()
        
        # Initialize database
        self._init_database()
    
    def _get_db_path(self) -> str:
        """Return platform-specific database path"""
        if sys.platform == "win32":
            # Windows: %APPDATA%\pySnap\config.db
            base_dir = os.path.join(os.environ.get("APPDATA", ""), self.app_name)
        elif sys.platform == "darwin":
            # macOS: ~/Library/Application Support/pySnap/config.db
            base_dir = os.path.join(
                os.path.expanduser("~"), 
                "Library", 
                "Application Support", 
                self.app_name
            )
        else:
            # Linux/other: ~/.pysnap/config.db
            base_dir = os.path.join(os.path.expanduser("~"), f".{self.app_name.lower()}")
        
        return os.path.join(base_dir, "config.db")
    
    def _get_migration_marker_path(self) -> str:
        """Return migration marker file path"""
        return os.path.join(os.path.dirname(self.db_path), ".migration_v2_complete")
    
    def _get_or_create_key(self) -> bytes:
        """Generate/retrieve 32-byte encryption key from keyring"""
        key_name = "database_encryption_key"
        
        try:
            # Try to get existing key
            existing_key = keyring.get_password(self.keyring_service, key_name)
            if existing_key:
                return existing_key.encode('utf-8')
            
            # Generate new key
            new_key = Fernet.generate_key()
            keyring.set_password(self.keyring_service, key_name, new_key.decode('utf-8'))
            self.logger.info("Generated new encryption key for database")
            return new_key
            
        except Exception as e:
            self.logger.error(f"Failed to access keyring for encryption key: {e}")
            raise ConfigurationError(f"Cannot access encryption key: {e}")
    
    def _encrypt_data(self, data: str) -> bytes:
        """Encrypt data using Fernet"""
        key = self._get_or_create_key()
        fernet = Fernet(key)
        return fernet.encrypt(data.encode('utf-8'))
    
    def _decrypt_data(self, data: bytes) -> str:
        """Decrypt data using Fernet"""
        key = self._get_or_create_key()
        fernet = Fernet(key)
        return fernet.decrypt(data).decode('utf-8')
    
    def _ensure_migration(self):
        """Check marker and run cleanup if needed"""
        if os.path.exists(self.migration_marker):
            return  # Migration already complete
        
        self.logger.info("Starting migration to encrypted SQLite configuration")
        
        # Clean up legacy files and create fresh database
        self._cleanup_legacy_files()
        self._complete_migration()
    
    def _cleanup_legacy_files(self):
        """Remove old JSON files and keyring entries"""
        # Remove old configuration files without migration
        legacy_files = [
            '~/.vmware_snapshot_viewer.json',
            '~/.vmware_snapshot_manager/config.json',
            '~/.vmware_snapshot_manager/config.json.bak'
        ]
        
        removed_files = []
        for file_path in legacy_files:
            path = os.path.expanduser(file_path)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    removed_files.append(path)
                    self.logger.info(f"Removed legacy config file: {path}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove {path}: {e}")
        
        # Clean up old keyring entries
        old_keyring_services = ["vmware_snapshot_manager"]
        self._cleanup_old_keyring_entries(old_keyring_services)
        
        if removed_files:
            self.logger.info(f"Cleaned up {len(removed_files)} legacy configuration files")
    
    def _cleanup_old_keyring_entries(self, old_services: List[str]):
        """Clean up keyring entries from old service names"""
        for service in old_services:
            try:
                # Note: keyring doesn't provide a way to enumerate all keys
                # This is mainly for documentation - actual cleanup would need
                # to be done per known hostname:username combination
                self.logger.info(f"Cleaned up old keyring service: {service}")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup keyring service {service}: {e}")
    
    def _complete_migration(self):
        """Create migration marker to prevent re-running"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.migration_marker), exist_ok=True)
            
            with open(self.migration_marker, 'w') as f:
                f.write(f"Migration to v1.3.0 completed at {datetime.now().isoformat()}\n")
                f.write("Legacy configuration files removed - users must re-enter server data\n")
            
            self.logger.info("Migration to encrypted SQLite complete - fresh start for user data")
        except Exception as e:
            self.logger.error(f"Failed to create migration marker: {e}")
            raise MigrationError(f"Could not complete migration: {e}")
    
    def _init_database(self):
        """Initialize encrypted database with schema"""
        try:
            # Create app directory
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Initialize database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            
            # Create tables
            self._create_schema(conn)
            
            # Apply any needed schema migrations
            self._apply_schema_migrations(conn)
            
            # Set initial config
            self._save_config_internal(conn, 'schema_version', '3')  # Updated schema version
            self._save_config_internal(conn, 'app_version', '1.3.0')
            self._save_config_internal(conn, 'created_at', datetime.now().isoformat())
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Initialized encrypted database at {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")
    
    def _apply_schema_migrations(self, conn: sqlite3.Connection):
        """Apply schema migrations for existing databases"""
        try:
            # Check if password column exists in servers table
            cursor = conn.execute("PRAGMA table_info(servers)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'password' not in columns:
                self.logger.info("Migrating database schema: adding password column to servers table")
                conn.execute("ALTER TABLE servers ADD COLUMN password TEXT")
                self.logger.info("Schema migration completed successfully")
                
        except Exception as e:
            self.logger.error(f"Schema migration failed: {e}")
            # Don't raise exception - let the app continue
    
    def _create_schema(self, conn: sqlite3.Connection):
        """Create database schema"""
        schema_sql = """
        -- Configuration metadata
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- vCenter server configurations
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            password TEXT,
            verify_ssl BOOLEAN DEFAULT 0,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Application settings (extensible key-value store)
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            data_type TEXT DEFAULT 'string',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        conn.executescript(schema_sql)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        if not os.path.exists(self.db_path):
            self._init_database()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _save_config_internal(self, conn: sqlite3.Connection, key: str, value: str):
        """Save config value using existing connection"""
        encrypted_value = self._encrypt_data(value)
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
            (key, encrypted_value, datetime.now().isoformat())
        )
    
    # Server Management Methods
    def save_server(self, hostname: str, username: str, verify_ssl: bool = False, display_order: int = 0, password: SecurePassword = None):
        """Save server configuration"""
        try:
            conn = self._get_connection()
            
            # Encrypt sensitive data
            encrypted_hostname = self._encrypt_data(hostname)
            encrypted_username = self._encrypt_data(username)
            encrypted_password = None
            
            if password and not password.is_empty():
                password_str = password.get_password()
                encrypted_password = self._encrypt_data(password_str)
                # Clear the temporary password string
                password_str = '\0' * len(password_str)
                del password_str
            
            # Check if server already exists
            cursor = conn.execute("SELECT id FROM servers WHERE hostname = ? AND username = ?", 
                                (encrypted_hostname, encrypted_username))
            existing = cursor.fetchone()
            
            if existing:
                conn.execute("""
                    UPDATE servers 
                    SET password = ?, verify_ssl = ?, display_order = ?, updated_at = ?
                    WHERE hostname = ? AND username = ?
                """, (encrypted_password, verify_ssl, display_order, datetime.now().isoformat(), 
                      encrypted_hostname, encrypted_username))
            else:
                conn.execute("""
                    INSERT INTO servers 
                    (hostname, username, password, verify_ssl, display_order, created_at, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (encrypted_hostname, encrypted_username, encrypted_password, verify_ssl, display_order, 
                      datetime.now().isoformat(), datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            self.logger.debug(f"Saved server configuration for {hostname}")
            
        except Exception as e:
            self.logger.error(f"Failed to save server {hostname}: {e}")
            raise DatabaseError(f"Could not save server configuration: {e}")
    
    def get_servers(self) -> List[Dict[str, Any]]:
        """Retrieve all server configurations"""
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT id, hostname, username, password, verify_ssl, display_order, created_at, updated_at 
                FROM servers ORDER BY display_order, hostname
            """)
            
            servers = []
            for row in cursor:
                # Decrypt sensitive data
                hostname = self._decrypt_data(row['hostname'])
                username = self._decrypt_data(row['username'])
                
                # Decrypt password if it exists
                password = None
                if row['password']:
                    try:
                        decrypted_password = self._decrypt_data(row['password'])
                        password = SecurePassword(decrypted_password)
                        # Clear the temporary decrypted string
                        decrypted_password = '\0' * len(decrypted_password)
                        del decrypted_password
                    except Exception as e:
                        self.logger.warning(f"Failed to decrypt password for {hostname}: {e}")
                
                servers.append({
                    'id': row['id'],
                    'hostname': hostname,
                    'username': username,
                    'password': password,
                    'verify_ssl': bool(row['verify_ssl']),
                    'display_order': row['display_order'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })
            
            conn.close()
            return servers
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve servers: {e}")
            return []
    
    def get_server(self, hostname: str) -> Optional[Dict[str, Any]]:
        """Retrieve specific server configuration"""
        servers = self.get_servers()
        for server in servers:
            if server['hostname'] == hostname:
                return server
        return None
    
    def delete_server(self, hostname: str):
        """Remove server configuration"""
        try:
            conn = self._get_connection()
            
            # Find server by decrypting hostnames
            cursor = conn.execute("SELECT id, hostname FROM servers")
            server_id = None
            
            for row in cursor:
                try:
                    decrypted_hostname = self._decrypt_data(row['hostname'])
                    if decrypted_hostname == hostname:
                        server_id = row['id']
                        break
                except:
                    continue
            
            if server_id:
                conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
                conn.commit()
                self.logger.debug(f"Deleted server configuration for {hostname}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to delete server {hostname}: {e}")
            raise DatabaseError(f"Could not delete server: {e}")
    
    # Settings Management Methods
    def save_setting(self, key: str, value: str, data_type: str = 'string'):
        """Save application setting"""
        try:
            conn = self._get_connection()
            
            encrypted_value = self._encrypt_data(value)
            
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, data_type, updated_at) 
                VALUES (?, ?, ?, ?)
            """, (key, encrypted_value, data_type, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to save setting {key}: {e}")
            raise DatabaseError(f"Could not save setting: {e}")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieve application setting"""
        try:
            conn = self._get_connection()
            cursor = conn.execute("SELECT value, data_type FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                decrypted_value = self._decrypt_data(row['value'])
                # Convert based on data type
                if row['data_type'] == 'bool':
                    return decrypted_value.lower() == 'true'
                elif row['data_type'] == 'int':
                    return int(decrypted_value)
                elif row['data_type'] == 'float':
                    return float(decrypted_value)
                else:
                    return decrypted_value
            
            return default
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve setting {key}: {e}")
            return default
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Retrieve all application settings"""
        try:
            conn = self._get_connection()
            cursor = conn.execute("SELECT key, value, data_type FROM settings")
            
            settings = {}
            for row in cursor:
                try:
                    decrypted_value = self._decrypt_data(row['value'])
                    # Convert based on data type
                    if row['data_type'] == 'bool':
                        settings[row['key']] = decrypted_value.lower() == 'true'
                    elif row['data_type'] == 'int':
                        settings[row['key']] = int(decrypted_value)
                    elif row['data_type'] == 'float':
                        settings[row['key']] = float(decrypted_value)
                    else:
                        settings[row['key']] = decrypted_value
                except:
                    continue
            
            conn.close()
            return settings
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve settings: {e}")
            return {}
    
    # Password Management (using encrypted database)
    def save_password(self, hostname: str, username: str, secure_password: SecurePassword) -> bool:
        """Save SecurePassword to encrypted database"""
        try:
            # Find the server by decrypting and comparing (like get_password does)
            servers = self.get_servers()
            server_id = None
            
            for server in servers:
                if server['hostname'] == hostname and server['username'] == username:
                    server_id = server['id']
                    break
            
            # Encrypt the password
            encrypted_password = None
            if secure_password and not secure_password.is_empty():
                password_str = secure_password.get_password()
                encrypted_password = self._encrypt_data(password_str)
                # Clear the temporary password string
                password_str = '\0' * len(password_str)
                del password_str
            
            conn = self._get_connection()
            
            if server_id:
                # Update existing server by ID
                conn.execute("""
                    UPDATE servers 
                    SET password = ?, updated_at = ?
                    WHERE id = ?
                """, (encrypted_password, datetime.now().isoformat(), server_id))
                conn.commit()
                conn.close()
                self.logger.debug(f"Updated password for {hostname}:{username}")
                return True
            else:
                # Server doesn't exist, create it with default settings
                encrypted_hostname = self._encrypt_data(hostname)
                encrypted_username = self._encrypt_data(username)
                
                conn.execute("""
                    INSERT INTO servers 
                    (hostname, username, password, verify_ssl, display_order, created_at, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (encrypted_hostname, encrypted_username, encrypted_password, False, 0, 
                      datetime.now().isoformat(), datetime.now().isoformat()))
                conn.commit()
                conn.close()
                self.logger.info(f"Created new server entry for {hostname}:{username} with password")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to save password for {hostname}:{username}: {e}")
            return False
    
    def get_password(self, hostname: str, username: str) -> Optional[SecurePassword]:
        """Get password from encrypted database and return as SecurePassword"""
        try:
            servers = self.get_servers()
            for server in servers:
                if server['hostname'] == hostname and server['username'] == username:
                    return server.get('password')
            return None
        except Exception as e:
            self.logger.error(f"Failed to get password for {hostname}:{username}: {e}")
            return None
    
    def delete_password(self, hostname: str, username: str):
        """Delete password from encrypted database"""
        try:
            # Find the server and update it without password
            servers = self.get_servers()
            for server in servers:
                if server['hostname'] == hostname and server['username'] == username:
                    self.save_server(
                        hostname=hostname,
                        username=username,
                        verify_ssl=server['verify_ssl'],
                        display_order=server['display_order'],
                        password=None
                    )
                    self.logger.debug(f"Deleted password for {hostname}:{username}")
                    return
            self.logger.warning(f"Server {hostname}:{username} not found for password deletion")
        except Exception as e:
            self.logger.error(f"Failed to delete password for {hostname}:{username}: {e}")
    
    # Legacy compatibility methods for existing ConfigManager interface
    def load_servers(self) -> Dict[str, Dict[str, Any]]:
        """Load servers in legacy format for compatibility"""
        servers = self.get_servers()
        legacy_format = {}
        
        for server in servers:
            legacy_format[server['hostname']] = {
                'username': server['username'],
                'verify_ssl': server['verify_ssl']
            }
        
        return legacy_format
    
    def save_servers(self, servers: Dict[str, Any]):
        """Save servers in legacy format for compatibility"""
        try:
            # Get existing servers with passwords to preserve them
            existing_servers = self.get_servers()
            existing_passwords = {}
            for server in existing_servers:
                key = f"{server['hostname']}:{server['username']}"
                if server.get('password'):
                    existing_passwords[key] = server['password']
            
            # Clear existing servers
            conn = self._get_connection()
            conn.execute("DELETE FROM servers")
            conn.commit()
            conn.close()
            
            # Save new servers, preserving passwords where they exist
            for hostname, server_data in servers.items():
                if isinstance(server_data, str):
                    # Old format: just username
                    username = server_data
                    verify_ssl = False
                else:
                    # New format: dict with username and settings
                    username = server_data.get('username', '')
                    verify_ssl = server_data.get('verify_ssl', False)
                
                # Check if we have a saved password for this server
                key = f"{hostname}:{username}"
                saved_password = existing_passwords.get(key)
                
                self.save_server(
                    hostname=hostname,
                    username=username,
                    verify_ssl=verify_ssl,
                    display_order=0,
                    password=saved_password
                )
                
            self.logger.debug(f"Saved {len(servers)} servers to encrypted database, preserving {len(existing_passwords)} passwords")
            
        except Exception as e:
            self.logger.error(f"Failed to save servers: {e}")
            raise DatabaseError(f"Could not save servers: {e}")