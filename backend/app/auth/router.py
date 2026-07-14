from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth.dependencies import require_admin
from app.auth import users as auth_users

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


class InviteRequest(BaseModel):
    email: EmailStr
    nome: str
    role: str = "engineer"
    redirect_to: str


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("")
async def get_users(_=Depends(require_admin)):
    return await auth_users.list_auth_users()


@router.post("/invite")
async def invite_user(req: InviteRequest, _=Depends(require_admin)):
    try:
        return await auth_users.invite_auth_user(req.email, req.nome, req.role, req.redirect_to)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{user_id}/role")
async def update_role(user_id: str, req: UpdateRoleRequest, _=Depends(require_admin)):
    try:
        return await auth_users.update_auth_user(user_id, req.role)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(user_id: str, _=Depends(require_admin)):
    try:
        await auth_users.delete_auth_user(user_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
