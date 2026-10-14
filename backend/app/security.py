import hashlib
import hmac
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from .config import get_settings

password_hasher = PasswordHasher()
dummy_hash = password_hasher.hash("litera-dummy-credential-never-used")

def verify_password(hashed, password):
    try:
        return password_hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def csrf_token(session):
    return hmac.new(get_settings().session_secret.encode(), session.id.encode(), hashlib.sha256).hexdigest()
