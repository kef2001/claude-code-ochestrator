#!/usr/bin/env python3
"""Unit tests for security utilities."""

import pytest
import os
import tempfile
from pathlib import Path

from claude_orchestrator.security_utils import (
    validate_api_key,
    sanitize_error_message,
    check_file_permissions,
    perform_security_audit,
    get_safe_error_response
)


class TestSecurityUtils:
    """Test suite for security utilities."""
    
    def test_validate_api_key_valid(self):
        """Test validation of valid API keys."""
        valid_keys = [
            'sk-' + 'a' * 50,
            'sk-abc123def456ghi789jkl012mno345pqr678stu901vwx',
            'sk-1234567890abcdefghijklmnopqrstuvwxyzABCDEF'
        ]
        
        for key in valid_keys:
            assert validate_api_key(key) is True
    
    def test_validate_api_key_invalid(self):
        """Test validation of invalid API keys."""
        invalid_keys = [
            '',
            None,
            'not-an-api-key',
            'sk-',  # Too short
            'sk-abc',  # Too short
            'pk-' + 'a' * 50,  # Wrong prefix
            'sk-' + 'a' * 30,  # Too short
            'sk-abc!@#$%'  # Invalid characters
        ]
        
        for key in invalid_keys:
            assert validate_api_key(key) is False
    
    def test_sanitize_error_message(self):
        """Test error message sanitization."""
        # Test API key sanitization
        msg = "Error with key sk-abc123def456ghi789jkl012mno345pqr678stu901vwx"
        sanitized = sanitize_error_message(msg)
        assert "sk-***" in sanitized
        assert "sk-abc123def456ghi789jkl012mno345pqr678stu901vwx" not in sanitized
        
        # Test user path sanitization
        msg = "File not found: /Users/john/secret/file.txt"
        sanitized = sanitize_error_message(msg)
        assert "/Users/***" in sanitized
        assert "john" not in sanitized
        
        # Test email sanitization
        msg = "Email sent to user@example.com"
        sanitized = sanitize_error_message(msg)
        assert "***@***.***" in sanitized
        assert "user@example.com" not in sanitized
        
        # Test Windows path sanitization
        msg = r"Error in C:\Users\JohnDoe\Documents\file.txt"
        sanitized = sanitize_error_message(msg)
        assert r"C:\Users\***" in sanitized
        assert "JohnDoe" not in sanitized
        
        # Test Slack webhook sanitization
        msg = "Webhook: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX"
        sanitized = sanitize_error_message(msg)
        assert "https://hooks.slack.com/services/***" in sanitized
    
    def test_sanitize_error_message_empty(self):
        """Test sanitization of empty messages."""
        assert sanitize_error_message("") == ""
        assert sanitize_error_message(None) == None
    
    def test_check_file_permissions(self):
        """Test file permission checking."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file = f.name
            f.write("test content")
        
        try:
            # Check existing file
            result = check_file_permissions(test_file)
            assert result['exists'] is True
            assert result['readable'] is True
            assert result['writable'] is True
            
            # Check non-existent file
            result = check_file_permissions('/non/existent/file.txt')
            assert result['exists'] is False
            assert len(result['recommendations']) > 0
        finally:
            os.unlink(test_file)
    
    def test_check_env_file_permissions(self):
        """Test .env file permission recommendations."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            env_file = f.name
            f.write("API_KEY=secret")
        
        try:
            # Make file world-readable
            os.chmod(env_file, 0o644)
            
            result = check_file_permissions(env_file)
            assert result['exists'] is True
            assert result['owner_only'] is False
            assert any('chmod 600' in rec for rec in result['recommendations'])
        finally:
            os.unlink(env_file)
    
    def test_perform_security_audit(self):
        """Test security audit functionality."""
        findings = perform_security_audit()
        
        # Should return a list
        assert isinstance(findings, list)
        
        # Check for common findings
        for finding in findings:
            assert isinstance(finding, str)
    
    def test_get_safe_error_response(self):
        """Test safe error response generation."""
        # Test known error types
        errors = [
            (FileNotFoundError("test"), "Requested file not found"),
            (PermissionError("test"), "Permission denied"),
            (ConnectionError("test"), "Connection failed"),
            (TimeoutError("test"), "Operation timed out"),
            (ValueError("test"), "Invalid input provided"),
            (KeyError("test"), "Required configuration missing")
        ]
        
        for error, expected in errors:
            assert get_safe_error_response(error) == expected
        
        # Test unknown error with sanitization
        error = Exception("Error with key sk-abc123def456ghi789")
        response = get_safe_error_response(error)
        assert "sk-***" in response
        assert "sk-abc123def456ghi789" not in response
    
    @pytest.mark.parametrize("key,expected", [
        ("sk-" + "a" * 50, True),
        ("sk-" + "A" * 50, True),
        ("sk-" + "0" * 50, True),
        ("sk-aA0-" * 10, True),
        ("", False),
        ("sk-", False),
        ("sk-短的", False),  # Non-ASCII
        ("sk_" + "a" * 50, False),  # Wrong separator
    ])
    def test_validate_api_key_parametrized(self, key, expected):
        """Parametrized test for API key validation."""
        assert validate_api_key(key) == expected