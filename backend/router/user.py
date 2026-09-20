from utils.security import hash_password,verify_password
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.db_config import get_db
from utils.JWT import create_access_token,get_current_user_id
from schemas.user_schemas import (
    RegisterRequest, LoginRequest, UserResponse
)
from models.user import (
    User
)

def _user_to_response(user:User):
    return UserResponse(
        id = user.id,
        username=user.username,
        email=user.email,
    )



user_router = APIRouter(tags=["user"],prefix="/user")



@user_router.post("/register/")
async def register(rep: RegisterRequest,db : AsyncSession = Depends(get_db)):
    """用户注册"""
    if rep.password != rep.confirm_password:
        raise HTTPException(
            status_code=400,
            detail = {"confirm_password":"密码和确认的密码不一致"}
        )

    result = await db.execute(select(User).where(User.email == rep.email , User.username == rep.username))

    existing_user = result.scalar_one_or_none()


    if existing_user:
        raise HTTPException(
            status_code=400,
            detail={
                "email": "该邮箱或用户名已被注册"
            }
        )

    user = User(
        username=rep.username,
        email=rep.email,
        password=hash_password(rep.password),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "message": "注册校验通过",
        "user": _user_to_response(user).model_dump()
    }


@user_router.post("/login/")
async def login(req: LoginRequest,db:AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where((User.email == req.email) | (User.username == req.username)))
    existing_user = result.scalar_one_or_none()
    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="邮箱或密码错误",
        )

    password_vaild = verify_password(req.password,existing_user.password,)

    if not password_vaild:
        raise HTTPException(
            status_code=401,
            detail="邮箱或密码错误",
        )

    token = create_access_token(existing_user.id)
    return{
        "message": "登录成功",
        "token":token,
        "user": _user_to_response(existing_user).model_dump()
    }

@user_router.get("/me")
async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="用户不存在",
        )

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }
