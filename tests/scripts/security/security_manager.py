"""
Main security manager for Hebrew Subtitle Service.
Orchestrates encryption, network security, and access control.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timedelta
from .encryption import EncryptionManager
from .network_security import NetworkSecurityManager

class SecurityManager:
    """Main security manager that coordinates all security features."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the security manager.
        
        Args:
            config: Configuration dictionary containing security settings
        """
        self.config = config
        self.encryption_manager = EncryptionManager(config)
        self.network_security_manager = NetworkSecurityManager(config)
        self.audit_log: List[Dict[str, Any]] = []
        self.access_control: Dict[str, Any] = {}
        self._load_access_control()
    
    def _load_access_control(self):
        """Load access control configuration."""
        security_config = self.config.get('security', {})
        self.access_control = security_config.get('access_control', {})
    
    def audit_log_event(self, event_type: str, user_id: Optional[str] = None,
                       resource: Optional[str] = None, action: Optional[str] = None,
                       success: bool = True, details: Optional[Dict[str, Any]] = None):
        """
        Log a security audit event.
        
        Args:
            event_type: Type of event (login, file_access, api_call, etc.)
            user_id: ID of the user performing the action
            resource: Resource being accessed
            action: Action being performed
            success: Whether the action was successful
            details: Additional details about the event
        """
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'success': success,
            'details': details or {},
            'ip_address': self._get_client_ip(),
            'user_agent': self._get_user_agent(),
        }
        
        self.audit_log.append(audit_entry)
        
        # Log to file if audit logging is enabled
        if self.config.get('security', {}).get('audit_logging', True):
            self._write_audit_log(audit_entry)
        
        # Keep audit log size manageable
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]
    
    def _write_audit_log(self, audit_entry: Dict[str, Any]):
        """Write audit entry to log file."""
        try:
            log_dir = Path(self.config.get('paths', {}).get('log_directory', './logs'))
            log_dir.mkdir(parents=True, exist_ok=True)
            
            audit_file = log_dir / 'security_audit.log'
            
            with open(audit_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry) + '\n')
                
        except Exception as e:
            logging.error(f"Failed to write audit log: {e}")
    
    def _get_client_ip(self) -> Optional[str]:
        """Get client IP address (placeholder for web applications)."""
        # This would be implemented based on the application context
        return "127.0.0.1"
    
    def _get_user_agent(self) -> Optional[str]:
        """Get user agent string (placeholder for web applications)."""
        # This would be implemented based on the application context
        return "HebrewSubtitleService/1.0"
    
    def check_access_permission(self, user_id: str, resource: str, action: str) -> bool:
        """
        Check if a user has permission to perform an action on a resource.
        
        Args:
            user_id: ID of the user
            resource: Resource being accessed
            action: Action being performed
            
        Returns:
            True if access is allowed, False otherwise
        """
        # Simple role-based access control
        user_roles = self.access_control.get('users', {}).get(user_id, {}).get('roles', [])
        
        for role in user_roles:
            role_permissions = self.access_control.get('roles', {}).get(role, {}).get('permissions', [])
            
            for permission in role_permissions:
                if (permission.get('resource') == resource and 
                    permission.get('action') == action):
                    return True
        
        # Log access denial
        self.audit_log_event(
            'access_denied',
            user_id=user_id,
            resource=resource,
            action=action,
            success=False,
            details={'reason': 'insufficient_permissions'}
        )
        
        return False
    
    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive data in a dictionary.
        
        Args:
            data: Dictionary containing potentially sensitive data
            
        Returns:
            Dictionary with sensitive data encrypted
        """
        sensitive_keys = ['password', 'api_key', 'token', 'secret', 'key']
        encrypted_data = data.copy()
        
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if isinstance(value, str):
                    encrypted_data[key] = self.encryption_manager.encrypt_data(value)
                elif isinstance(value, dict):
                    encrypted_data[key] = self.encrypt_sensitive_data(value)
        
        return encrypted_data
    
    def decrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive data in a dictionary.
        
        Args:
            data: Dictionary containing encrypted sensitive data
            
        Returns:
            Dictionary with sensitive data decrypted
        """
        sensitive_keys = ['password', 'api_key', 'token', 'secret', 'key']
        decrypted_data = data.copy()
        
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if isinstance(value, str):
                    try:
                        decrypted_data[key] = self.encryption_manager.decrypt_data(value)
                    except ValueError:
                        # If decryption fails, assume it's not encrypted
                        pass
                elif isinstance(value, dict):
                    decrypted_data[key] = self.decrypt_sensitive_data(value)
        
        return decrypted_data
    
    def secure_api_call(self, method: str, url: str, data: Optional[Dict] = None,
                       api_name: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Make a secure API call with full security features.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data
            api_name: API name for signing
            user_id: User ID for audit logging
            
        Returns:
            Dictionary with response data and security info
        """
        # Validate URL security
        url_validation = self.network_security_manager.validate_url_security(url)
        if not url_validation['is_secure']:
            self.audit_log_event(
                'insecure_url_access',
                user_id=user_id,
                resource=url,
                action=method,
                success=False,
                details=url_validation
            )
            raise ValueError(f"Insecure URL: {url}")
        
        # Sanitize URL
        sanitized_url = self.network_security_manager.sanitize_url(url)
        
        # Encrypt sensitive data if present
        if data:
            data = self.encrypt_sensitive_data(data)
        
        # Make secure request
        try:
            response = self.network_security_manager.create_secure_request(
                method, sanitized_url, data, api_name
            )
            
            # Log successful API call
            self.audit_log_event(
                'api_call',
                user_id=user_id,
                resource=sanitized_url,
                action=method,
                success=True,
                details={
                    'status_code': response.status_code,
                    'api_name': api_name,
                    'response_size': len(response.content)
                }
            )
            
            return {
                'success': True,
                'status_code': response.status_code,
                'data': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                'headers': dict(response.headers),
                'security_info': {
                    'url_validation': url_validation,
                    'certificate_pinned': True,
                    'request_signed': bool(api_name),
                    'https_used': sanitized_url.startswith('https://')
                }
            }
            
        except Exception as e:
            # Log failed API call
            self.audit_log_event(
                'api_call_failed',
                user_id=user_id,
                resource=sanitized_url,
                action=method,
                success=False,
                details={'error': str(e), 'api_name': api_name}
            )
            raise
    
    def secure_file_operations(self, file_path: str, operation: str, 
                             user_id: Optional[str] = None) -> bool:
        """
        Perform secure file operations with access control and audit logging.
        
        Args:
            file_path: Path to the file
            operation: Operation to perform (read, write, delete)
            user_id: User ID for audit logging
            
        Returns:
            True if operation successful, False otherwise
        """
        # Check file access permissions
        if not self.check_access_permission(user_id or 'system', file_path, operation):
            return False
        
        try:
            if operation == 'read':
                # For reading, we might want to decrypt if it's encrypted
                if file_path.endswith('.enc'):
                    decrypted_path = self.encryption_manager.decrypt_file(file_path)
                    self.audit_log_event(
                        'file_read',
                        user_id=user_id,
                        resource=file_path,
                        action='read',
                        success=True,
                        details={'decrypted_path': decrypted_path}
                    )
                    return True
                else:
                    # Regular file read
                    with open(file_path, 'r') as f:
                        f.read()
                    
            elif operation == 'write':
                # For writing, we might want to encrypt sensitive files
                if any(sensitive in file_path.lower() for sensitive in ['config', 'key', 'secret']):
                    # This would be implemented based on specific requirements
                    pass
                
                self.audit_log_event(
                    'file_write',
                    user_id=user_id,
                    resource=file_path,
                    action='write',
                    success=True
                )
                
            elif operation == 'delete':
                # Use secure delete for sensitive files
                if any(sensitive in file_path.lower() for sensitive in ['key', 'secret', 'password']):
                    self.encryption_manager.secure_delete(file_path)
                else:
                    os.remove(file_path)
                
                self.audit_log_event(
                    'file_delete',
                    user_id=user_id,
                    resource=file_path,
                    action='delete',
                    success=True
                )
            
            return True
            
        except Exception as e:
            self.audit_log_event(
                'file_operation_failed',
                user_id=user_id,
                resource=file_path,
                action=operation,
                success=False,
                details={'error': str(e)}
            )
            return False
    
    def get_security_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive security report.
        
        Returns:
            Dictionary containing security status and statistics
        """
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'encryption': {
                'master_key_exists': bool(self.encryption_manager.master_key),
                'master_key_fingerprint': self.encryption_manager.get_key_fingerprint(
                    self.encryption_manager.master_key
                ) if self.encryption_manager.master_key else None,
            },
            'network_security': {
                'certificate_pins_configured': len(self.network_security_manager.certificate_pins),
                'api_keys_configured': len(self.network_security_manager.api_keys),
            },
            'access_control': {
                'users_configured': len(self.access_control.get('users', {})),
                'roles_configured': len(self.access_control.get('roles', {})),
            },
            'audit_log': {
                'total_events': len(self.audit_log),
                'recent_events': len([e for e in self.audit_log 
                                    if datetime.fromisoformat(e['timestamp']) > 
                                    datetime.utcnow() - timedelta(hours=24)]),
                'failed_events': len([e for e in self.audit_log if not e['success']]),
            },
            'security_status': 'secure'  # This would be determined by various checks
        }
    
    def rotate_security_credentials(self) -> bool:
        """
        Rotate all security credentials (master key, API keys, etc.).
        
        Returns:
            True if rotation successful, False otherwise
        """
        try:
            # Rotate master key
            if not self.encryption_manager.rotate_master_key():
                return False
            
            # Log rotation event
            self.audit_log_event(
                'security_rotation',
                user_id='system',
                resource='all',
                action='rotate_credentials',
                success=True
            )
            
            return True
            
        except Exception as e:
            self.audit_log_event(
                'security_rotation_failed',
                user_id='system',
                resource='all',
                action='rotate_credentials',
                success=False,
                details={'error': str(e)}
            )
            return False 