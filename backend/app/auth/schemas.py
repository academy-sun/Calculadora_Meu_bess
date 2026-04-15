from pydantic import BaseModel


class UserInToken(BaseModel):
    sub: str
    email: str
    role: str  # engineer | admin
