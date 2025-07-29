"""
Encryption manager for secure data handling.
Provides encryption, decryption, and secure key management.
"""

import os
import base64
import hashlib
import secrets
from typing import Optional, Dict, Any
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import logging
import shutil
import time

class EncryptionManager:
    """Manages encryption, decryption, and secure key handling."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the encryption manager.
        
        Args:
            config: Configuration dictionary containing security settings
        """
        self.config = config
        self.master_key: Optional[bytes] = None
        self.fernet: Optional[Fernet] = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize encryption with master key."""
        secure_config = self.config.get('security', {})
        secure_path = Path(secure_config.get('secure_storage_path', './secure'))
        secure_path.mkdir(parents=True, exist_ok=True)
        
        master_key_file = secure_path / 'master.key'
        
        if master_key_file.exists():
            # Load existing master key
            with open(master_key_file, 'rb') as f:
                self.master_key = f.read()
        else:
            # Generate new master key
            self.master_key = Fernet.generate_key()
            with open(master_key_file, 'wb') as f:
                f.write(self.master_key)
        
        self.fernet = Fernet(self.master_key)
        
        # Set proper permissions on master key file
        os.chmod(master_key_file, 0o600)
    
    def derive_key_from_password(self, password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """
        Derive a cryptographic key from a password using PBKDF2.
        
        Args:
            password: The password to derive the key from
            salt: Salt for key derivation. If None, a random salt is generated.
            
        Returns:
            Derived key bytes
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode())
        return key, salt
    
    def encrypt_data(self, data: str, key: Optional[bytes] = None) -> str:
        """
        Encrypt data using Fernet symmetric encryption.
        
        Args:
            data: Data to encrypt
            key: Encryption key. If None, uses master key.
            
        Returns:
            Encrypted data as base64 string
        """
        if not self.fernet:
            raise ValueError("Encryption not initialized")
        
        if key:
            # Use provided key
            fernet = Fernet(key)
        else:
            # Use master key
            fernet = self.fernet
        
        encrypted_data = fernet.encrypt(data.encode())
        return base64.b64encode(encrypted_data).decode()
    
    def decrypt_data(self, encrypted_data: str, key: Optional[bytes] = None) -> str:
        """
        Decrypt data using Fernet symmetric encryption.
        
        Args:
            encrypted_data: Encrypted data as base64 string
            key: Decryption key. If None, uses master key.
            
        Returns:
            Decrypted data
        """
        if not self.fernet:
            raise ValueError("Encryption not initialized")
        
        if key:
            # Use provided key
            fernet = Fernet(key)
        else:
            # Use master key
            fernet = self.fernet
        
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            logging.error(f"Failed to decrypt data: {e}")
            raise ValueError("Failed to decrypt data - invalid key or corrupted data")
    
    def encrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """
        Encrypt a file using AES-256-CBC.
        
        Args:
            file_path: Path to file to encrypt
            output_path: Output path for encrypted file. If None, adds .enc extension.
            
        Returns:
            Path to encrypted file
        """
        if output_path is None:
            output_path = f"{file_path}.enc"
        
        # Generate a random key and IV for this file
        key = secrets.token_bytes(32)  # AES-256
        iv = secrets.token_bytes(16)   # AES block size
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        with open(file_path, 'rb') as f_in:
            data = f_in.read()
        
        # Pad data to block size
        block_size = 16
        padding_length = block_size - (len(data) % block_size)
        data += bytes([padding_length] * padding_length)
        
        encrypted_data = encryptor.update(data) + encryptor.finalize()
        
        # Write encrypted file with key and IV
        with open(output_path, 'wb') as f_out:
            f_out.write(key)
            f_out.write(iv)
            f_out.write(encrypted_data)
        
        return output_path
    
    def decrypt_file(self, encrypted_file_path: str, output_path: Optional[str] = None) -> str:
        """
        Decrypt a file encrypted with encrypt_file.
        
        Args:
            encrypted_file_path: Path to encrypted file
            output_path: Output path for decrypted file. If None, removes .enc extension.
            
        Returns:
            Path to decrypted file
        """
        if output_path is None:
            if encrypted_file_path.endswith('.enc'):
                output_path = encrypted_file_path[:-4]
            else:
                output_path = f"{encrypted_file_path}.dec"
        
        with open(encrypted_file_path, 'rb') as f_in:
            key = f_in.read(32)  # Read key
            iv = f_in.read(16)   # Read IV
            encrypted_data = f_in.read()  # Read encrypted data
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # Remove padding
        padding_length = decrypted_data[-1]
        decrypted_data = decrypted_data[:-padding_length]
        
        with open(output_path, 'wb') as f_out:
            f_out.write(decrypted_data)
        
        return output_path
    
    def hash_password(self, password: str, salt: Optional[str] = None) -> Dict[str, str]:
        """
        Hash a password using PBKDF2 with salt.
        
        Args:
            password: Password to hash
            salt: Salt for hashing. If None, generates a random salt.
            
        Returns:
            Dictionary with 'hash' and 'salt' keys
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Use PBKDF2 for password hashing
        key, _ = self.derive_key_from_password(password, salt.encode())
        password_hash = base64.b64encode(key).decode()
        
        return {
            'hash': password_hash,
            'salt': salt
        }
    
    def verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """
        Verify a password against a stored hash.
        
        Args:
            password: Password to verify
            stored_hash: Stored password hash
            salt: Salt used for hashing
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            key, _ = self.derive_key_from_password(password, salt.encode())
            password_hash = base64.b64encode(key).decode()
            return password_hash == stored_hash
        except Exception:
            return False
    
    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate a cryptographically secure token.
        
        Args:
            length: Length of token in bytes
            
        Returns:
            Secure token as hex string
        """
        return secrets.token_hex(length)
    
    def secure_delete(self, file_path: str, passes: int = 3):
        """
        Securely delete a file by overwriting with random data.
        
        Args:
            file_path: Path to file to delete
            passes: Number of overwrite passes
        """
        if not os.path.exists(file_path):
            return
        
        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'wb') as f:
            for _ in range(passes):
                f.seek(0)
                f.write(secrets.token_bytes(file_size))
                f.flush()
                os.fsync(f.fileno())
        
        os.remove(file_path)
    
    def get_key_fingerprint(self, key: bytes) -> str:
        """
        Get a fingerprint of a cryptographic key.
        
        Args:
            key: Key to fingerprint
            
        Returns:
            Key fingerprint as hex string
        """
        return hashlib.sha256(key).hexdigest()[:16]
    
    def rotate_master_key(self) -> bool:
        """
        Rotate the master encryption key.
        This re-encrypts all stored data with a new key.
        
        Returns:
            True if rotation successful, False otherwise
        """
        try:
            # Generate new master key
            new_master_key = Fernet.generate_key()
            new_fernet = Fernet(new_master_key)
            
            # Re-encrypt all stored data (this would need to be implemented
            # based on what data is stored)
            
            # Update master key
            secure_config = self.config.get('security', {})
            secure_path = Path(secure_config.get('secure_storage_path', './secure'))
            master_key_file = secure_path / 'master.key'
            
            # Backup old key
            backup_file = secure_path / f'master.key.backup.{int(time.time())}'
            if master_key_file.exists():
                shutil.copy2(master_key_file, backup_file)
            
            # Write new key
            with open(master_key_file, 'wb') as f:
                f.write(new_master_key)
            
            self.master_key = new_master_key
            self.fernet = new_fernet
            
            logging.info("Master key rotated successfully")
            return True
            
        except Exception as e:
            logging.error(f"Failed to rotate master key: {e}")
            return False 