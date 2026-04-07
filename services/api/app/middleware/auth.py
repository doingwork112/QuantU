"""
QuantifyU — JWT认证中间件
验证Supabase签发的JWT Token
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from loguru import logger

from app.config import Settings, get_settings

security = HTTPBearer()


class AuthenticatedUser:
    """已认证用户上下文"""

    def __init__(self, user_id: str, email: str, role: str = "authenticated"):
        self.user_id = user_id
        self.email = email
        self.role = role

    def __repr__(self) -> str:
        return f"AuthenticatedUser(id={self.user_id}, email={self.email})"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    从Authorization header中提取并验证JWT
    返回已认证的用户对象
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as e:
        logger.warning(f"JWT验证失败 | error={e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    email = payload.get("email", "")
    role = payload.get("role", "authenticated")

    if not user_id:
        logger.warning("JWT缺少sub字段")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少用户标识",
        )

    return AuthenticatedUser(user_id=user_id, email=email, role=role)


def get_client_ip(request: Request) -> str:
    """获取客户端IP（支持代理）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
