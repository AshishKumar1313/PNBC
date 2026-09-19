from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix='/auth', tags=['Authentication'])


@router.post('/register', response_model=UserResponse)
async def register_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    statement = select(User).where(User.email == payload.email)
    result = await db.execute(statement)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='User already exists')

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post('/login', response_model=TokenResponse)
async def login_user(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    statement = select(User).where(User.email == payload.email)
    result = await db.execute(statement)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid credentials',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    access_token = create_access_token(str(user.id))
    return TokenResponse(access_token=access_token, token_type='bearer')


@router.get('/me', response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user
