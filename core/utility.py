from rest_framework.response import Response
from functools import wraps
from rest_framework import status
from dotenv import load_dotenv
import os
import sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from base64 import b64encode, b64decode
import logging
import traceback

sys.path.append(os.getcwd())
os.environ['DJANGO_SETTINGS_MODULE'] = 'CPTBackend.settings'
# django.setup()

load_dotenv()

logger = logging.getLogger("django") 

def catch_exceptions(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            logging.error(f"An error occurred in {filename} at line {line}: {e}")
            return Response({'error': "这是一个程序错误。请通知管理员联系开发者"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return wrapper

key = b64decode(os.getenv('AES_KEY'))
def encrypt(plaintext):
    while len(plaintext) % 16 != 0:
        plaintext += ' '  # Padding with spaces

    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(plaintext.encode('utf-8')) + encryptor.finalize()
    return b64encode(ct).decode('utf-8') 

def decrypt(ciphertext):
    ct = b64decode(ciphertext)
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(ct) + decryptor.finalize()
    return decrypted_data.decode('utf-8').strip() 