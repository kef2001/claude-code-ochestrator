#!/usr/bin/env python3
"""Security utilities for Claude Orchestrator.

This module provides security-related functions for API key validation,
error message sanitization, and security checks.
"""

import os
import re
import stat
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


def validate_api_key(key: str) -> bool:
    """Validate API key format and structure.
    
    Args:
        key: API key to validate
        
    Returns:
        True if key appears valid, False otherwise
    """
    if not key:
        return False
    
    # Anthropic keys start with 'sk-'
    if not key.startswith('sk-'):
        return False
    
    # Should be reasonable length
    if len(key) < 40:
        return False
    
    # Should only contain alphanumeric and hyphens
    if not re.match(r'^sk-[a-zA-Z0-9\-]+$', key):
        return False
    
    return True


def sanitize_error_message(message: str) -> str:
    """Remove sensitive data from error messages.
    
    Args:
        message: Error message to sanitize
        
    Returns:
        Sanitized error message
    """
    if not message:
        return message
    
    # Remove API keys
    message = re.sub(r'sk-[a-zA-Z0-9\-]{40,}', 'sk-***', message)
    
    # Remove potential paths with user directories
    message = re.sub(r'/Users/[^/\s]+', '/Users/***', message)
    message = re.sub(r'/home/[^/\s]+', '/home/***', message)
    message = re.sub(r'C:\\Users\\[^\\]+', 'C:\\Users\\***', message)
    
    # Remove email addresses
    message = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '***@***.***', message)
    
    # Remove potential webhook URLs
    message = re.sub(r'https://hooks\.slack\.com/services/[^\s]+', 'https://hooks.slack.com/services/***', message)
    
    return message


def check_file_permissions(filepath: str) -> Dict[str, any]:
    """Check file permissions for security issues.
    
    Args:
        filepath: Path to file to check
        
    Returns:
        Dictionary with security check results
    """
    results = {
        'exists': False,
        'readable': False,
        'writable': False,
        'executable': False,
        'owner_only': False,
        'recommendations': []
    }
    
    if not os.path.exists(filepath):
        results['recommendations'].append(f"File {filepath} does not exist")
        return results
    
    results['exists'] = True
    file_stat = os.stat(filepath)
    mode = file_stat.st_mode
    
    # Check basic permissions
    results['readable'] = bool(mode & stat.S_IRUSR)
    results['writable'] = bool(mode & stat.S_IWUSR)
    results['executable'] = bool(mode & stat.S_IXUSR)
    
    # Check if only owner has access (recommended for .env files)
    results['owner_only'] = not bool(mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | 
                                             stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH))
    
    # Recommendations
    if filepath.endswith('.env') and not results['owner_only']:
        results['recommendations'].append(
            f"Security Warning: {filepath} is accessible by group/others. "
            f"Run: chmod 600 {filepath}"
        )
    
    if results['executable'] and filepath.endswith('.env'):
        results['recommendations'].append(
            f"Security Warning: {filepath} should not be executable. "
            f"Run: chmod 600 {filepath}"
        )
    
    return results


def perform_security_audit() -> List[str]:
    """Perform a basic security audit of the environment.
    
    Returns:
        List of security findings/recommendations
    """
    findings = []
    
    # Check .env file permissions
    env_check = check_file_permissions('.env')
    findings.extend(env_check['recommendations'])
    
    # Check for API key in environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if api_key:
        if not validate_api_key(api_key):
            findings.append("Warning: ANTHROPIC_API_KEY format appears invalid")
    else:
        findings.append("Info: ANTHROPIC_API_KEY not found in environment")
    
    # Check for debug mode
    if os.environ.get('DEBUG', '').lower() in ('true', '1', 'yes'):
        findings.append("Warning: DEBUG mode is enabled - disable in production")
    
    # Check for verbose logging
    if os.environ.get('VERBOSE', '').lower() in ('true', '1', 'yes'):
        findings.append("Info: Verbose logging is enabled - may expose sensitive data")
    
    return findings


def get_safe_error_response(exception: Exception) -> str:
    """Get a safe error response that doesn't expose sensitive information.
    
    Args:
        exception: The exception to process
        
    Returns:
        Safe error message
    """
    error_type = type(exception).__name__
    
    # Map common errors to safe messages
    safe_messages = {
        'FileNotFoundError': 'Requested file not found',
        'PermissionError': 'Permission denied',
        'ConnectionError': 'Connection failed',
        'TimeoutError': 'Operation timed out',
        'ValueError': 'Invalid input provided',
        'KeyError': 'Required configuration missing'
    }
    
    if error_type in safe_messages:
        return safe_messages[error_type]
    
    # For other errors, sanitize the message
    return sanitize_error_message(str(exception))


if __name__ == '__main__':
    # Run security audit if executed directly
    print("🔒 Running Security Audit...")
    findings = perform_security_audit()
    
    if findings:
        print("\nSecurity Findings:")
        for finding in findings:
            print(f"  - {finding}")
    else:
        print("✅ No security issues found")
    
    # Test sanitization
    print("\n🧪 Testing Sanitization...")
    test_message = "Error: API key sk-abc123def456ghi789jkl012mno345pqr678stu901vwx at /Users/john/project failed"
    sanitized = sanitize_error_message(test_message)
    print(f"Original: {test_message}")
    print(f"Sanitized: {sanitized}")