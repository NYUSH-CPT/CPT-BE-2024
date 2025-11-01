"""
Comprehensive test suite for core/utility.py

Tests cover:
- Encryption and decryption functions
- Exception handling in catch_exceptions decorator
- Edge cases and error conditions
"""

import os
import base64
from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock
from rest_framework.response import Response
from rest_framework import status

from core.utility import encrypt, decrypt, catch_exceptions


class TestEncryptionDecryption(TestCase):
    """Tests for encrypt() and decrypt() functions"""
    
    def setUp(self):
        """Set up test AES key"""
        # Generate a 32-byte key for testing
        test_key = b'0123456789abcdef0123456789abcdef'  # 32 bytes
        self.test_key_b64 = base64.b64encode(test_key).decode('utf-8')
        
        # Patch the AES_KEY environment variable
        with patch.dict(os.environ, {'AES_KEY': self.test_key_b64}):
            # Reload the utility module to pick up the new key
            import importlib
            import core.utility
            importlib.reload(core.utility)
            self.encrypt = core.utility.encrypt
            self.decrypt = core.utility.decrypt
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypt and decrypt work correctly together"""
        plaintext = "13800138000"
        
        ciphertext = self.encrypt(plaintext)
        decrypted = self.decrypt(ciphertext)
        
        self.assertEqual(decrypted, plaintext)
    
    def test_encrypt_adds_padding(self):
        """Test encrypt adds padding for non-16-byte lengths"""
        plaintext = "short"  # 5 bytes, needs padding to 16
        
        ciphertext = self.encrypt(plaintext)
        decrypted = self.decrypt(ciphertext)
        
        self.assertEqual(decrypted.strip(), plaintext)
    
    def test_encrypt_exact_16_bytes(self):
        """Test encrypt works for exactly 16-byte strings"""
        plaintext = "1234567890123456"  # Exactly 16 bytes
        
        ciphertext = self.encrypt(plaintext)
        decrypted = self.decrypt(ciphertext)
        
        self.assertEqual(decrypted.strip(), plaintext)
    
    def test_encrypt_long_string(self):
        """Test encrypt works for long strings"""
        plaintext = "This is a very long phone number that exceeds 16 bytes"
        
        ciphertext = self.encrypt(plaintext)
        decrypted = self.decrypt(ciphertext)
        
        self.assertEqual(decrypted.strip(), plaintext)
    
    def test_encrypt_special_characters(self):
        """Test encrypt works with special characters"""
        plaintext = "138-0013-8000@example.com"
        
        ciphertext = self.encrypt(plaintext)
        decrypted = self.decrypt(ciphertext)
        
        self.assertEqual(decrypted.strip(), plaintext)
    
    def test_encrypt_empty_string(self):
        """Test encrypt handles empty string"""
        plaintext = ""
        
        ciphertext = self.encrypt(plaintext)
        decrypted = self.decrypt(ciphertext)
        
        self.assertEqual(decrypted.strip(), plaintext)
    
    def test_encrypt_returns_base64(self):
        """Test encrypt returns base64-encoded string"""
        plaintext = "test123"
        
        ciphertext = self.encrypt(plaintext)
        
        # Should be valid base64
        try:
            base64.b64decode(ciphertext)
        except Exception:
            self.fail("encrypt() did not return valid base64")
    
    def test_decrypt_invalid_base64(self):
        """Test decrypt raises error for invalid base64"""
        invalid_ciphertext = "not_valid_base64!!!"
        
        with self.assertRaises(Exception):
            self.decrypt(invalid_ciphertext)
    
    def test_encrypt_different_inputs_different_outputs(self):
        """Test encrypt produces different output for different inputs"""
        plaintext1 = "13800138000"
        plaintext2 = "13800138001"
        
        ciphertext1 = self.encrypt(plaintext1)
        ciphertext2 = self.encrypt(plaintext2)
        
        # Should be different (even with padding)
        self.assertNotEqual(ciphertext1, ciphertext2)


class TestCatchExceptionsDecorator(TestCase):
    """Tests for catch_exceptions decorator"""
    
    def test_catch_exceptions_success(self):
        """Test catch_exceptions doesn't interfere with successful execution"""
        
        @catch_exceptions
        def successful_view(request):
            return Response({"success": True}, status=status.HTTP_200_OK)
        
        mock_request = MagicMock()
        response = successful_view(mock_request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], True)
    
    def test_catch_exceptions_catches_exception(self):
        """Test catch_exceptions catches and logs exceptions"""
        
        @catch_exceptions
        def failing_view(request):
            raise ValueError("Test error")
        
        mock_request = MagicMock()
        
        with patch('core.utility.logging.error') as mock_log:
            response = failing_view(mock_request)
            
            # Should return 500 error
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertIn('错误', response.data['error'])
            
            # Should log the error
            mock_log.assert_called_once()
            self.assertIn("Test error", str(mock_log.call_args))
    
    def test_catch_exceptions_preserves_function_metadata(self):
        """Test catch_exceptions preserves function name and docstring"""
        
        @catch_exceptions
        def test_function(request):
            """Test docstring"""
            pass
        
        self.assertEqual(test_function.__name__, "test_function")
        self.assertEqual(test_function.__doc__, "Test docstring")
    
    def test_catch_exceptions_passes_arguments(self):
        """Test catch_exceptions passes arguments correctly"""
        
        @catch_exceptions
        def arg_view(request, arg1, arg2, kwarg1=None):
            return Response({"arg1": arg1, "arg2": arg2, "kwarg1": kwarg1})
        
        mock_request = MagicMock()
        response = arg_view(mock_request, "value1", "value2", kwarg1="value3")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["arg1"], "value1")
        self.assertEqual(response.data["arg2"], "value2")
        self.assertEqual(response.data["kwarg1"], "value3")
    
    def test_catch_exceptions_logs_traceback(self):
        """Test catch_exceptions logs traceback information"""
        
        @catch_exceptions
        def error_view(request):
            raise RuntimeError("Runtime error message")
        
        mock_request = MagicMock()
        
        with patch('core.utility.logging.error') as mock_log:
            response = error_view(mock_request)
            
            # Verify error was logged
            mock_log.assert_called_once()
            call_args = str(mock_log.call_args)
            
            # Should contain error message
            self.assertIn("Runtime error message", call_args)
            # Should contain file/line information
            self.assertIn("test_utility.py", call_args or "")
    
    def test_catch_exceptions_handles_different_exception_types(self):
        """Test catch_exceptions handles different exception types"""
        
        @catch_exceptions
        def type_error_view(request):
            raise TypeError("Type error")
        
        @catch_exceptions
        def key_error_view(request):
            raise KeyError("Key error")
        
        @catch_exceptions
        def attribute_error_view(request):
            raise AttributeError("Attribute error")
        
        mock_request = MagicMock()
        
        # All should return 500
        response1 = type_error_view(mock_request)
        response2 = key_error_view(mock_request)
        response3 = attribute_error_view(mock_request)
        
        self.assertEqual(response1.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response2.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response3.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestUtilityEdgeCases(TestCase):
    """Tests for edge cases in utility functions"""
    
    def setUp(self):
        """Set up test AES key"""
        test_key = b'0123456789abcdef0123456789abcdef'
        self.test_key_b64 = base64.b64encode(test_key).decode('utf-8')
        
        with patch.dict(os.environ, {'AES_KEY': self.test_key_b64}):
            import importlib
            import core.utility
            importlib.reload(core.utility)
            self.encrypt = core.utility.encrypt
            self.decrypt = core.utility.decrypt
    
    def test_encrypt_newlines(self):
        """Test encrypt handles strings with newlines"""
        plaintext = "Line 1\nLine 2\nLine 3"
        
        ciphertext = self.encrypt(plaintext)
        decrypted = self.decrypt(ciphertext)
        
        self.assertEqual(decrypted.strip(), plaintext)
    
    def test_encrypt_numeric_strings(self):
        """Test encrypt handles numeric-only strings (phone numbers)"""
        plaintext = "13800138000"
        
        ciphertext = self.encrypt(plaintext)
        decrypted = self.decrypt(ciphertext)
        
        self.assertEqual(decrypted.strip(), plaintext)
        # Verify it's still numeric
        self.assertTrue(decrypted.strip().isnumeric())
    
    def test_decrypt_strips_padding(self):
        """Test decrypt correctly strips padding"""
        # Encrypt a short string
        plaintext = "short"
        ciphertext = self.encrypt(plaintext)
        
        # Decrypt should strip trailing spaces added by padding
        decrypted = self.decrypt(ciphertext)
        self.assertEqual(decrypted, plaintext)
    
    def test_encrypt_consistency(self):
        """Test encrypt produces consistent output for same input"""
        plaintext = "consistent_test"
        
        ciphertext1 = self.encrypt(plaintext)
        ciphertext2 = self.encrypt(plaintext)
        
        # Same input should produce same output with ECB mode
        self.assertEqual(ciphertext1, ciphertext2)
    
    def test_decrypt_corrupted_data(self):
        """Test decrypt handles corrupted ciphertext"""
        # Valid base64 but invalid ciphertext
        corrupted = base64.b64encode(b'invalid_ciphertext').decode('utf-8')
        
        with self.assertRaises(Exception):
            self.decrypt(corrupted)

