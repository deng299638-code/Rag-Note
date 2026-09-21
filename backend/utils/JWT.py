from datetime import datetime, timezone, timedelta
import os
from fastapi import Depends, HTTPException
from jose import jwt, JWTError
from dotenv import load_dotenv
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials



load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
security = HTTPBearer()

def create_access_token(user_id: int) -> str:

    if not SECRET_KEY or not ALGORITHM:
        raise ValueError("请检查是否已经配置 SECRET_KEY , ALGORITHM")

    expire_time = datetime.now(timezone.utc) + timedelta(hours=24)

    payload = {
        "user_id" :user_id,
        "exp":expire_time
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm= ALGORITHM,
    )


def get_current_user_id(credentials : HTTPAuthorizationCredentials = Depends(security)) -> int:
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=ALGORITHM,
        )

        user_id = payload.get("user_id")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Token 中没有用户信息",
            )

        return int(user_id)
    except(JWTError,ValueError):
        raise HTTPException(
                status_code=401,
                detail="Token 无效或已过期 ",
            )
