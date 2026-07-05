import base64
import getpass
import hashlib
import os

ITERATIONS = 260000

password = getpass.getpass("Nova senha: ")
confirm = getpass.getpass("Confirmar senha: ")

if password != confirm:
    raise SystemExit("As senhas não conferem.")

salt = os.urandom(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
print(f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}")
