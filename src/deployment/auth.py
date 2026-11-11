import hashlib
import hmac
import secrets
import time
from collections import deque

from .config import DeploymentError


def create_credentials(password):
    salt = secrets.token_hex(16)
    return {
        "salt": salt,
        "password_hash": hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex(),
        "session_key": secrets.token_hex(32),
    }


def generate_password():
    return secrets.token_urlsafe(18)


class Authentication:
    def __init__(self, credentials):
        self.credentials = credentials
        self.sessions = {}
        self.failures = deque()

    def login(self, password):
        now = time.monotonic()
        while self.failures and self.failures[0] < now - 60:
            self.failures.popleft()
        if len(self.failures) >= 5:
            raise DeploymentError("登录尝试过多，请一分钟后重试", 429)
        hashed = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(self.credentials["salt"]), n=16384, r=8, p=1
        ).hex()
        if not hmac.compare_digest(hashed, self.credentials["password_hash"]):
            self.failures.append(now)
            raise DeploymentError("密码错误", 401)
        self.sessions = {
            key: value for key, value in self.sessions.items() if value["expires"] > time.time()
        }
        if len(self.sessions) >= 100:
            self.sessions.pop(next(iter(self.sessions)))
        nonce = secrets.token_urlsafe(32)
        signature = hmac.new(
            bytes.fromhex(self.credentials["session_key"]), nonce.encode(), hashlib.sha256
        ).hexdigest()
        token = f"{nonce}.{signature}"
        session = {"csrf": secrets.token_urlsafe(32), "expires": time.time() + 8 * 3600}
        self.sessions[token] = session
        return token, session

    def authenticate(self, token):
        session = self.sessions.get(token)
        if not session or session["expires"] <= time.time():
            self.sessions.pop(token, None)
            raise DeploymentError("请先登录", 401)
        return session

    def logout(self, token):
        self.sessions.pop(token, None)
