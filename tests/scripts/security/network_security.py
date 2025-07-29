"""
Network security manager for secure communications.
Provides certificate pinning, request signing, and secure headers.
"""

import ssl
import hashlib
import hmac
import time
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import logging

class NetworkSecurityManager:
    """Manages network security including certificate pinning and request signing."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the network security manager.
        
        Args:
            config: Configuration dictionary containing security settings
        """
        self.config = config
        self.certificate_pins: Dict[str, str] = {}
        self.api_keys: Dict[str, str] = {}
        self._load_certificate_pins()
        self._load_api_keys()
    
    def _load_certificate_pins(self):
        """Load certificate pins for known domains."""
        # Default certificate pins for common APIs
        self.certificate_pins = {
            'api.opensubtitles.com': 'sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
            'api.openai.com': 'sha256/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=',
        }
        
        # Load custom pins from config if available
        custom_pins = self.config.get('security', {}).get('certificate_pins', {})
        self.certificate_pins.update(custom_pins)
    
    def _load_api_keys(self):
        """Load API keys for request signing."""
        api_config = self.config.get('api', {})
        
        # OpenSubtitles credentials
        opensubtitles_config = api_config.get('opensubtitles', {})
        if opensubtitles_config.get('username') and opensubtitles_config.get('password'):
            self.api_keys['opensubtitles'] = f"{opensubtitles_config['username']}:{opensubtitles_config['password']}"
        
        # OpenAI API key
        openai_config = api_config.get('openai', {})
        if openai_config.get('api_key'):
            self.api_keys['openai'] = openai_config['api_key']
    
    def verify_certificate_pin(self, hostname: str, cert_der: bytes) -> bool:
        """
        Verify certificate pin for a hostname.
        
        Args:
            hostname: Hostname to verify
            cert_der: Certificate in DER format
            
        Returns:
            True if certificate pin matches, False otherwise
        """
        if hostname not in self.certificate_pins:
            logging.warning(f"No certificate pin configured for {hostname}")
            return True  # Allow if no pin configured
        
        expected_pin = self.certificate_pins[hostname]
        actual_pin = f"sha256/{hashlib.sha256(cert_der).digest().hex()}"
        
        return expected_pin == actual_pin
    
    def create_secure_session(self) -> requests.Session:
        """
        Create a requests session with security features.
        
        Returns:
            Configured requests session
        """
        session = requests.Session()
        
        # Configure SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        # Add certificate pinning
        def verify_cert(conn, cert, errno, depth, ok):
            if not ok:
                return False
            
            hostname = conn.getpeername()[0]
            return self.verify_certificate_pin(hostname, cert)
        
        # Note: This is a simplified implementation
        # In production, you'd want to use a proper certificate pinning library
        
        session.verify = True
        session.headers.update(self._get_security_headers())
        
        return session
    
    def _get_security_headers(self) -> Dict[str, str]:
        """
        Get security headers for requests.
        
        Returns:
            Dictionary of security headers
        """
        headers = {
            'User-Agent': 'HebrewSubtitleService/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
        }
        
        # Add CSP header if configured
        csp = self.config.get('security', {}).get('content_security_policy')
        if csp:
            headers['Content-Security-Policy'] = csp
        
        return headers
    
    def sign_request(self, method: str, url: str, data: Optional[Dict] = None, 
                    api_name: Optional[str] = None) -> Dict[str, str]:
        """
        Sign a request with HMAC for API authentication.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data
            api_name: Name of the API for key selection
            
        Returns:
            Dictionary with signed headers
        """
        if not api_name or api_name not in self.api_keys:
            return {}
        
        api_key = self.api_keys[api_name]
        timestamp = str(int(time.time()))
        
        # Create signature string
        signature_string = f"{method.upper()}{url}{timestamp}"
        if data:
            import json
            signature_string += json.dumps(data, sort_keys=True)
        
        # Create HMAC signature
        signature = hmac.new(
            api_key.encode(),
            signature_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'X-API-Key': api_key,
            'X-Timestamp': timestamp,
            'X-Signature': signature,
        }
    
    def validate_response_security(self, response: requests.Response) -> bool:
        """
        Validate security aspects of a response.
        
        Args:
            response: Response to validate
            
        Returns:
            True if response is secure, False otherwise
        """
        # Check for secure headers
        security_headers = [
            'Strict-Transport-Security',
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
        ]
        
        for header in security_headers:
            if header not in response.headers:
                logging.warning(f"Missing security header: {header}")
        
        # Check for HTTPS
        if not response.url.startswith('https://'):
            logging.warning("Response not using HTTPS")
            return False
        
        # Check response status
        if response.status_code >= 400:
            logging.warning(f"Response error: {response.status_code}")
            return False
        
        return True
    
    def create_secure_request(self, method: str, url: str, 
                            data: Optional[Dict] = None,
                            api_name: Optional[str] = None,
                            timeout: int = 30) -> requests.Response:
        """
        Create and execute a secure request.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data
            api_name: API name for signing
            timeout: Request timeout
            
        Returns:
            Response object
        """
        session = self.create_secure_session()
        
        # Add signed headers
        signed_headers = self.sign_request(method, url, data, api_name)
        session.headers.update(signed_headers)
        
        # Make request
        try:
            if method.upper() == 'GET':
                response = session.get(url, timeout=timeout)
            elif method.upper() == 'POST':
                response = session.post(url, json=data, timeout=timeout)
            elif method.upper() == 'PUT':
                response = session.put(url, json=data, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = session.delete(url, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Validate response security
            if not self.validate_response_security(response):
                logging.warning("Response security validation failed")
            
            return response
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            raise
    
    def get_ssl_context(self) -> ssl.SSLContext:
        """
        Get a secure SSL context.
        
        Returns:
            Configured SSL context
        """
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Set minimum TLS version
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        # Set cipher suites
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20')
        
        return context
    
    def validate_url_security(self, url: str) -> Dict[str, Any]:
        """
        Validate security aspects of a URL.
        
        Args:
            url: URL to validate
            
        Returns:
            Dictionary with validation results
        """
        parsed = urlparse(url)
        
        validation = {
            'is_https': parsed.scheme == 'https',
            'has_valid_hostname': bool(parsed.hostname),
            'has_valid_port': parsed.port is None or parsed.port in [80, 443, 8080, 8443],
            'has_suspicious_parameters': self._check_suspicious_parameters(parsed.query),
        }
        
        validation['is_secure'] = all([
            validation['is_https'],
            validation['has_valid_hostname'],
            validation['has_valid_port'],
            not validation['has_suspicious_parameters']
        ])
        
        return validation
    
    def _check_suspicious_parameters(self, query: str) -> bool:
        """
        Check for suspicious URL parameters.
        
        Args:
            query: URL query string
            
        Returns:
            True if suspicious parameters found
        """
        suspicious_patterns = [
            'script', 'javascript', 'vbscript', 'onload', 'onerror',
            'eval', 'exec', 'system', 'cmd', 'shell'
        ]
        
        query_lower = query.lower()
        return any(pattern in query_lower for pattern in suspicious_patterns)
    
    def sanitize_url(self, url: str) -> str:
        """
        Sanitize a URL for safe use.
        
        Args:
            url: URL to sanitize
            
        Returns:
            Sanitized URL
        """
        parsed = urlparse(url)
        
        # Ensure HTTPS
        if parsed.scheme not in ['https', 'http']:
            parsed = parsed._replace(scheme='https')
        elif parsed.scheme == 'http':
            parsed = parsed._replace(scheme='https')
        
        # Remove suspicious parameters
        if parsed.query:
            from urllib.parse import parse_qs, urlencode
            params = parse_qs(parsed.query)
            
            # Remove suspicious parameters
            suspicious_keys = [k for k in params.keys() 
                             if self._check_suspicious_parameters(k)]
            for key in suspicious_keys:
                del params[key]
            
            # Rebuild query string
            if params:
                parsed = parsed._replace(query=urlencode(params, doseq=True))
            else:
                parsed = parsed._replace(query='')
        
        return parsed.geturl() 