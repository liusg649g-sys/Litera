"""Replaceable secret vault; never fall back to plaintext or machine-wide DPAPI."""
import ctypes
from ctypes import wintypes
import os
from .ai_service import ModelFailure

class WindowsSecretVault:
    scheme = 'windows-dpapi-current-user-v1'
    @property
    def available(self): return os.name == 'nt'

    def _operate(self, owner, value, encrypt):
        if not self.available:
            raise ModelFailure('MODEL_VAULT_UNAVAILABLE', '此服务器未配置安全密钥存储，无法保存或调用用户模型')
        class Blob(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
        def blob(data):
            buffer = ctypes.create_string_buffer(data)
            return Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer
        source, source_buffer = blob(value)
        entropy, entropy_buffer = blob(('litera/user-model/v1/' + owner).encode())
        output = Blob()
        crypt = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        protect = crypt.CryptProtectData if encrypt else crypt.CryptUnprotectData
        protect.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        protect.restype = wintypes.BOOL
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        # UI_FORBIDDEN only: no LOCAL_MACHINE flag; OS account master key stays outside DB.
        try:
            if not protect(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(output)):
                raise ModelFailure('MODEL_VAULT_UNAVAILABLE', '无法解锁用户模型密钥，请在当前服务器重新配置') from None
            return ctypes.string_at(output.data, output.size)
        finally:
            if output.data:
                ctypes.memset(output.data, 0, output.size)
                kernel.LocalFree(output.data)
            ctypes.memset(source_buffer, 0, len(source_buffer))

    def encrypt(self, owner, secret): return self._operate(owner, secret.encode('utf-8'), True)
    def decrypt(self, owner, encrypted): return self._operate(owner, encrypted, False).decode('utf-8')

vault = WindowsSecretVault()
class UnavailableSecretVault:
    available=False
    scheme='unavailable'
    def encrypt(self,*args):raise vault_error()
    def decrypt(self,*args):raise vault_error()


def vault_error():
    return ModelFailure('MODEL_VAULT_UNAVAILABLE','安全密钥存储不可用，请检查独立主密钥文件或重新配置密钥')


class AesGcmFileVault:
    """Portable vault. No automatic conversion/rotation of existing ciphertext.

    The administrator supplies a secret outside the DB/image/repository. POSIX
    permissions must deny group/other access. Keys are never returned in errors.
    """
    scheme='aes256gcm-file-v1'
    prefix=b'LITERA-AESGCM-1\x00'
    def __init__(self,path):self.path=path

    def _key(self):
        import base64,stat
        from pathlib import Path
        try:
            path=Path(self.path)
            if not self.path or not path.is_absolute() or path.is_symlink():raise ValueError()
            flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0)
            with os.fdopen(os.open(path,flags),'rb') as stream:
                info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size>128:raise ValueError()
                if os.name!='nt' and stat.S_IMODE(info.st_mode)&0o077:raise ValueError()
                key=base64.b64decode(stream.read(129).strip(),altchars=b'-_',validate=True)
            if len(key)!=32:raise ValueError()
            return key
        except (OSError,ValueError,TypeError):raise vault_error() from None

    @property
    def available(self):
        try:self._key();return True
        except ModelFailure:return False

    def encrypt(self,owner,secret):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        try:
            nonce=os.urandom(12)
            aad=b'litera/user-model/aesgcm/v1\x00'+owner.encode('utf-8')
            return self.prefix+nonce+AESGCM(self._key()).encrypt(nonce,secret.encode('utf-8'),aad)
        except ModelFailure:raise
        except (ValueError,TypeError):raise vault_error() from None

    def decrypt(self,owner,value):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
        try:
            if not isinstance(value,bytes) or not value.startswith(self.prefix) or len(value)<len(self.prefix)+29:raise ValueError()
            raw=value[len(self.prefix):]
            aad=b'litera/user-model/aesgcm/v1\x00'+owner.encode('utf-8')
            return AESGCM(self._key()).decrypt(raw[:12],raw[12:],aad).decode('utf-8')
        except ModelFailure:raise
        except (InvalidTag,ValueError,TypeError):raise vault_error() from None


def get_secret_vault():
    from .config import get_settings
    settings=get_settings();mode=settings.user_model_secret_backend
    if mode=='windows_dpapi' or (mode=='auto' and os.name=='nt'):return vault
    if mode in ('auto','aesgcm_file') and settings.user_model_master_key_file:
        return AesGcmFileVault(settings.user_model_master_key_file)
    return UnavailableSecretVault()
