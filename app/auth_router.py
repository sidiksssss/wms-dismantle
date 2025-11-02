from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import engine
from app import models
from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    require_role
)
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import io

router = APIRouter(tags=["Authentication"])

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    role: str  # admin, admin_regional, teknisi
    area: Optional[str] = None
    region: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: str
    area: Optional[str]
    region: Optional[str]
    is_active: bool

@router.post("/register", response_model=UserResponse, summary="Register New User")
async def register(user: UserCreate, current_user: models.User = Depends(require_role(["admin"]))):
    """
    Register user baru (hanya bisa dilakukan oleh Admin)
    """
    with Session(engine) as session:
        # Cek apakah username sudah ada
        existing_user = session.query(models.User).filter(
            models.User.username == user.username
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Username already registered"
            )
        
        # Cek email
        existing_email = session.query(models.User).filter(
            models.User.email == user.email
        ).first()
        
        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Buat user baru
        new_user = models.User(
            username=user.username,
            email=user.email,
            password_hash=get_password_hash(user.password),
            full_name=user.full_name,
            role=user.role,
            area=user.area,
            region=user.region
        )
        
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        
        return new_user

@router.post("/login", response_model=Token, summary="Login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login dengan username dan password
    """
    print(f"🔐 Login attempt: username={form_data.username}")
    with Session(engine) as session:
        user = session.query(models.User).filter(
            models.User.username == form_data.username
        ).first()
        
        if not user:
            print(f"❌ User not found: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        print(f"✓ User found: {user.username}, checking password...")
        password_ok = verify_password(form_data.password, user.password_hash)
        print(f"  Password check: {'✓ OK' if password_ok else '❌ FAIL'}")
        
        if not password_ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive"
            )
        
        # Buat access token
        access_token = create_access_token(data={"sub": user.username})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "area": user.area,
                "region": user.region
            }
        }

@router.get("/me", response_model=UserResponse, summary="Get Current User")
async def get_me(current_user: models.User = Depends(get_current_user)):
    """
    Mendapatkan informasi user yang sedang login
    """
    return current_user

@router.post("/upload/users", tags=["Upload"], summary="Upload User Excel")
async def upload_users(
    file: UploadFile = File(...),
    current_user: models.User = Depends(require_role(["admin"]))
):
    """
    Upload file Excel berisi data user/teknisi (hanya Admin)
    
    ## Format File Excel
    Kolom yang diperlukan:
    - username
    - email
    - password
    - full_name
    - role (admin/admin_regional/teknisi)
    - area (untuk teknisi, sesuai City Simplified)
    - region (untuk admin_regional: WEST/CENTRAL/EAST)
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File harus berformat Excel (.xlsx atau .xls)")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        print("Kolom yang ada di Excel:", df.columns.tolist())
        
        # Validasi kolom
        required_columns = ["username", "email", "password", "role"]
        df.columns = [col.strip() for col in df.columns]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Kolom yang diperlukan tidak ditemukan: {', '.join(missing_columns)}"
            )
        
        new_records = 0
        skipped_records = 0
        
        with Session(engine) as session:
            for _, row in df.iterrows():
                username = row.get("username")
                
                # Cek apakah user sudah ada
                existing_user = session.query(models.User).filter_by(username=username).first()
                
                if not existing_user:
                    new_user = models.User(
                        username=username,
                        email=row.get("email"),
                        password_hash=get_password_hash(str(row.get("password"))),
                        full_name=row.get("full_name"),
                        role=row.get("role"),
                        area=row.get("area"),
                        region=row.get("region")
                    )
                    session.add(new_user)
                    new_records += 1
                else:
                    skipped_records += 1
            
            session.commit()
        
        return {
            "status": "success",
            "message": f"File {file.filename} berhasil diproses",
            "detail": {
                "total_rows": len(df),
                "new_records": new_records,
                "skipped_records": skipped_records
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
