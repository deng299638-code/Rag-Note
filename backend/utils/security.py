from passlib.context import CryptContext

# 创建加密上下文对象
pwd_content = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt", "django_pbkdf2_sha256"],#加密算法
    deprecated="auto",#标记旧的加密过的密码
)
def hash_password(password:str) -> str:
    return pwd_content.hash(password, scheme="bcrypt_sha256")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_content.verify(plain_password,hashed_password)

