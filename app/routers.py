from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from typing import Optional, List
import pandas as pd
import io
import warnings
import numpy as np
from sqlalchemy.orm import Session
from app.database import engine
from app import models
from app.auth import get_current_user, require_role
import os
from datetime import datetime
import shutil

# Abaikan warning dari openpyxl
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

router = APIRouter(tags=["WMS Dismantle"])

# Folder untuk menyimpan foto
UPLOAD_FOLDER = "uploads/photos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@router.get("/", tags=["Info"], summary="Home")
async def read_root():
    """
    Endpoint utama yang menampilkan informasi umum tentang WMS Dismantle API
    """
    return {
        "message": "WMS Dismantle API is running 🚀",
        "version": "0.1.0",
        "description": "API untuk mengelola data dismantle Work Orders",
        "endpoints": {
            "GET /": "Homepage - Informasi umum API",
            "GET /work-orders": "Mendapatkan daftar semua Work Orders",
            "POST /upload/excel": "Upload file Excel untuk data dismantle"
        }
    }

from fastapi import Query

@router.get("/work-orders", tags=["Work Orders"], summary="List Work Orders (Role-based)")
async def get_work_orders(
    skip: int = Query(0, description="Jumlah data yang dilewati (untuk pagination)"),
    limit: int = Query(10, description="Jumlah maksimum data yang ditampilkan"),
    status: Optional[str] = Query(None, description="Filter berdasarkan status WO"),
    vendor: Optional[str] = Query(None, description="Filter berdasarkan vendor"),
    city: Optional[str] = Query(None, description="Filter berdasarkan kota"),
    current_user: models.User = Depends(get_current_user)
):
    """
    Mendapatkan daftar Work Orders berdasarkan role:
    - **Admin**: Lihat semua WO
    - **Admin Regional**: Lihat WO per region (exclude status Scheduled)
    - **Teknisi**: Lihat WO per area mereka
    
    Fitur: Pagination, Filter status, vendor, kota
    """
    with Session(engine) as session:
        # Buat query dasar
        query = session.query(models.DismantleData)
        
        # Filter berdasarkan role user
        if current_user.role == "teknisi":
            # Teknisi hanya lihat WO di area mereka
            query = query.filter(models.DismantleData.city_simplified == current_user.area)
        elif current_user.role == "admin_regional":
            # Admin Regional lihat per city_simplified (area), exclude status "Scheduled"
            query = query.filter(
                models.DismantleData.city_simplified == current_user.area,
                models.DismantleData.status_wo != "Scheduled"
            )
        # Admin lihat semua (tidak ada filter tambahan)
        
        # Terapkan filter tambahan jika ada
        if status:
            query = query.filter(models.DismantleData.status_wo == status)
        if vendor:
            query = query.filter(models.DismantleData.vendor == vendor)
        if city:
            query = query.filter(models.DismantleData.city_simplified == city)
            
        # Hitung total data setelah filter
        total_records = query.count()
        
        # Terapkan pagination
        work_orders = query.offset(skip).limit(limit).all()
        
        # Dapatkan nilai unik untuk filter (sesuai role)
        status_query = session.query(models.DismantleData.status_wo.distinct())
        vendor_query = session.query(models.DismantleData.vendor.distinct())
        city_query = session.query(models.DismantleData.city_simplified.distinct())
        
        if current_user.role == "teknisi":
            status_query = status_query.filter(models.DismantleData.city_simplified == current_user.area)
            vendor_query = vendor_query.filter(models.DismantleData.city_simplified == current_user.area)
            city_query = city_query.filter(models.DismantleData.city_simplified == current_user.area)
        elif current_user.role == "admin_regional":
            status_query = status_query.filter(models.DismantleData.city_simplified == current_user.area, models.DismantleData.status_wo != "Scheduled")
            vendor_query = vendor_query.filter(models.DismantleData.city_simplified == current_user.area, models.DismantleData.status_wo != "Scheduled")
            city_query = city_query.filter(models.DismantleData.city_simplified == current_user.area, models.DismantleData.status_wo != "Scheduled")
        
        all_statuses = [r[0] for r in status_query.all() if r[0]]
        all_vendors = [r[0] for r in vendor_query.all() if r[0]]
        all_cities = [r[0] for r in city_query.all() if r[0]]

        return {
            "status": "success",
            "user_role": current_user.role,
            "user_area": current_user.area,
            "data": {
                "total_records": total_records,
                "page_info": {
                    "current_page": skip // limit + 1,
                    "records_per_page": limit,
                    "total_pages": (total_records + limit - 1) // limit
                },
                "filter_options": {
                    "status": all_statuses,
                    "vendors": all_vendors,
                    "cities": all_cities
                },
                "records": [
                    {
                        "id": wo.id,
                        "customer_id": wo.customer_id,
                        "wo_id_xl": wo.wo_id_xl,
                        "city": wo.city_simplified,
                        "region": wo.region,
                        "product_name": wo.product_name,
                        "status_wo": wo.status_wo,
                        "approval_status": wo.approval_status,
                        "vendor": wo.vendor,
                        "updated_by": wo.updated_by,
                        "updated_at": wo.updated_at.strftime("%Y-%m-%d %H:%M:%S") if wo.updated_at else None
                    }
                    for wo in work_orders
                ]
            }
        }

from fastapi import HTTPException

@router.post("/upload/excel", tags=["Upload"], summary="Upload Excel File")
async def upload_excel(file: UploadFile = File(...)):
    """
    Upload dan proses file Excel yang berisi data Work Orders.
    
    ## Format File Excel
    File harus memiliki kolom-kolom berikut:
    - Customer iD
    - WO ID XL
    - City (Simplified)
    - Product Name
    - STATUS WO
    - Vendor
    
    ## Proses yang dilakukan:
    1. Validasi format file
    2. Baca dan proses data
    3. Simpan ke database
    4. Return preview data
    """
    # Validasi tipe file
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File harus berformat Excel (.xlsx atau .xls)")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Debug: Print kolom yang ada di file Excel
        print("Kolom yang ada di Excel:", df.columns.tolist())
        
        # Validasi kolom yang diperlukan (case-insensitive)
        required_columns = ["Customer iD", "WO ID XL", "City (Simplified)", 
                          "Product Name", "STATUS WO", "Vendor"]
        # Ubah semua kolom ke lowercase untuk pengecekan
        df.columns = [col.strip() for col in df.columns]  # Hapus spasi di awal/akhir
        available_columns = {col.lower(): col for col in df.columns}
        missing_columns = [col for col in required_columns if col.lower() not in available_columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Kolom yang diperlukan tidak ditemukan: {', '.join(missing_columns)}"
            )

        # Bersihkan data
        df = df.replace([np.inf, -np.inf, np.nan], None)
        
        # Simpan ke database
        new_records = 0
        with Session(engine) as session:
            for _, row in df.iterrows():
                # Cek apakah WO sudah ada
                existing_wo = session.query(models.DismantleData).filter_by(
                    wo_id_xl=row.get("WO ID XL")
                ).first()
                
                if not existing_wo:
                    # Gunakan case-insensitive lookup
                    # Cari kolom region di Excel
                    region_col = [col for col in df.columns if col.lower() == "region"]
                    region_value = row.get(region_col[0]) if region_col else None
                    
                    data = models.DismantleData(
                        customer_id=row.get([col for col in df.columns if col.lower() == "customer id"][0]),
                        wo_id_xl=row.get([col for col in df.columns if col.lower() == "wo id xl"][0]),
                        city_simplified=row.get([col for col in df.columns if col.lower() == "city (simplified)"][0]),
                        product_name=row.get([col for col in df.columns if col.lower() == "product name"][0]),
                        status_wo=row.get([col for col in df.columns if col.lower() == "status wo"][0]),
                        vendor=row.get([col for col in df.columns if col.lower() == "vendor"][0]),
                        region=region_value
                    )
                    session.add(data)
                    new_records += 1
            
            session.commit()

        preview = df.head().replace({np.nan: None}).to_dict(orient="records")

        return {
            "status": "success",
            "message": f"File {file.filename} berhasil diproses",
            "detail": {
                "total_rows": len(df),
                "new_records": new_records,
                "duplicate_records": len(df) - new_records,
                "preview": preview[:5]  # Batasi preview hanya 5 data
            }
        }
        
    except Exception as e:
        print(f"Error detail: {str(e)}")  # Debug print
        import traceback
        print(f"Full error: {traceback.format_exc()}")  # Print full error trace
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/work-orders/{wo_id}", tags=["Work Orders"], summary="Update WO dengan Upload Foto")
async def update_work_order(
    wo_id: int,
    status_wo: Optional[str] = Form(None),
    foto_rumah: Optional[UploadFile] = File(None),
    foto_fat: Optional[UploadFile] = File(None),
    foto_cabut_port: Optional[UploadFile] = File(None),
    foto_ont: Optional[UploadFile] = File(None),
    foto_adapter: Optional[UploadFile] = File(None),
    foto_kabel_lan: Optional[UploadFile] = File(None),
    foto_customer: Optional[UploadFile] = File(None),
    foto_sn: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update Work Order - Upload foto dan update status
    
    **Role:** Teknisi atau Admin
    
    **Foto yang bisa diupload:**
    - foto_rumah: Foto rumah customer
    - foto_fat: Foto FAT
    - foto_cabut_port: Foto cabut port FAT
    - foto_ont: Foto ONT
    - foto_adapter: Foto adapter
    - foto_kabel_lan: Foto kabel LAN
    - foto_customer: Foto customer
    - foto_sn: Foto Serial Number (akan di-OCR otomatis)
    """
    
    # Helper function untuk save file
    async def save_upload_file(upload_file: UploadFile, wo_id: int, photo_type: str) -> str:
        if not upload_file:
            return None
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(upload_file.filename)[1]
        filename = f"WO{wo_id}_{photo_type}_{timestamp}{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save file
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        
        return filepath
    
    with Session(engine) as session:
        # Cari WO
        wo = session.query(models.DismantleData).filter(models.DismantleData.id == wo_id).first()
        
        if not wo:
            raise HTTPException(status_code=404, detail="Work Order tidak ditemukan")
        
        # Cek permission: teknisi hanya bisa update WO di area mereka
        if current_user.role == "teknisi" and wo.city_simplified != current_user.area:
            raise HTTPException(
                status_code=403,
                detail="Anda tidak memiliki akses ke Work Order ini"
            )
        
        # Update status jika ada
        if status_wo:
            wo.status_wo = status_wo
        
        # Upload dan simpan foto
        foto_paths = {}
        
        if foto_rumah:
            wo.foto_rumah = await save_upload_file(foto_rumah, wo_id, "rumah")
            foto_paths["foto_rumah"] = wo.foto_rumah
        
        if foto_fat:
            wo.foto_fat = await save_upload_file(foto_fat, wo_id, "fat")
            foto_paths["foto_fat"] = wo.foto_fat
        
        if foto_cabut_port:
            wo.foto_cabut_port = await save_upload_file(foto_cabut_port, wo_id, "cabut_port")
            foto_paths["foto_cabut_port"] = wo.foto_cabut_port
        
        if foto_ont:
            wo.foto_ont = await save_upload_file(foto_ont, wo_id, "ont")
            foto_paths["foto_ont"] = wo.foto_ont
        
        if foto_adapter:
            wo.foto_adapter = await save_upload_file(foto_adapter, wo_id, "adapter")
            foto_paths["foto_adapter"] = wo.foto_adapter
        
        if foto_kabel_lan:
            wo.foto_kabel_lan = await save_upload_file(foto_kabel_lan, wo_id, "kabel_lan")
            foto_paths["foto_kabel_lan"] = wo.foto_kabel_lan
        
        if foto_customer:
            wo.foto_customer = await save_upload_file(foto_customer, wo_id, "customer")
            foto_paths["foto_customer"] = wo.foto_customer
        
        if foto_sn:
            filepath = await save_upload_file(foto_sn, wo_id, "sn")
            wo.foto_sn = filepath
            foto_paths["foto_sn"] = filepath
            
            # TODO: Implement OCR untuk barcode/SN
            # try:
            #     import pytesseract
            #     from PIL import Image
            #     image = Image.open(filepath)
            #     sn_text = pytesseract.image_to_string(image)
            #     wo.sn_ocr_result = sn_text.strip()
            # except Exception as ocr_error:
            #     print(f"OCR Error: {ocr_error}")
        
        # Update tracking
        wo.updated_by = current_user.username
        wo.updated_at = datetime.now()
        
        session.commit()
        session.refresh(wo)
        
        return {
            "status": "success",
            "message": "Work Order berhasil diupdate",
            "data": {
                "id": wo.id,
                "wo_id_xl": wo.wo_id_xl,
                "status_wo": wo.status_wo,
                "updated_by": wo.updated_by,
                "updated_at": wo.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                "uploaded_photos": foto_paths
            }
        }

@router.get("/work-orders/{wo_id}", tags=["Work Orders"], summary="Get Detail WO")
async def get_work_order_detail(
    wo_id: int,
    current_user: models.User = Depends(get_current_user)
):
    """
    Mendapatkan detail lengkap Work Order termasuk semua foto
    """
    with Session(engine) as session:
        wo = session.query(models.DismantleData).filter(models.DismantleData.id == wo_id).first()
        
        if not wo:
            raise HTTPException(status_code=404, detail="Work Order tidak ditemukan")
        
        # Cek permission
        if current_user.role == "teknisi" and wo.city_simplified != current_user.area:
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke Work Order ini")
        
        return {
            "status": "success",
            "data": {
                "id": wo.id,
                "customer_id": wo.customer_id,
                "wo_id_xl": wo.wo_id_xl,
                "city": wo.city_simplified,
                "region": wo.region,
                "product_name": wo.product_name,
                "status_wo": wo.status_wo,
                "vendor": wo.vendor,
                "updated_by": wo.updated_by,
                "updated_at": wo.updated_at.strftime("%Y-%m-%d %H:%M:%S") if wo.updated_at else None,
                "approval_status": wo.approval_status,
                "approval_by": wo.approval_by,
                "approval_date": wo.approval_date.strftime("%Y-%m-%d %H:%M:%S") if wo.approval_date else None,
                "approval_notes": wo.approval_notes,
                "photos": {
                    "foto_rumah": wo.foto_rumah,
                    "foto_fat": wo.foto_fat,
                    "foto_cabut_port": wo.foto_cabut_port,
                    "foto_ont": wo.foto_ont,
                    "foto_adapter": wo.foto_adapter,
                    "foto_kabel_lan": wo.foto_kabel_lan,
                    "foto_customer": wo.foto_customer,
                    "foto_sn": wo.foto_sn,
                    "sn_ocr_result": wo.sn_ocr_result
                }
            }
        }

@router.get("/work-orders/pending-approval", tags=["Work Orders"], summary="WO Pending Approval")
async def get_pending_approval_wo(
    skip: int = Query(0, description="Pagination offset"),
    limit: int = Query(10, description="Records per page"),
    current_user: models.User = Depends(require_role(["admin", "admin_regional"]))
):
    """
    Mendapatkan daftar WO yang pending approval
    
    **Admin Regional:** Hanya WO di region mereka dengan status != Scheduled
    **Admin:** Semua WO pending
    """
    with Session(engine) as session:
        query = session.query(models.DismantleData)
        
        # Filter WO yang sudah diupdate oleh teknisi tapi belum di-approve
        query = query.filter(
            models.DismantleData.updated_by.isnot(None),
            models.DismantleData.approval_status.in_([None, 'pending'])
        )
        
        # Filter berdasarkan role
        if current_user.role == "admin_regional":
            query = query.filter(
                models.DismantleData.city_simplified == current_user.area,
                models.DismantleData.status_wo != "Scheduled"
            )
        
        total_records = query.count()
        work_orders = query.offset(skip).limit(limit).all()
        
        return {
            "status": "success",
            "data": {
                "total_records": total_records,
                "page_info": {
                    "current_page": skip // limit + 1,
                    "records_per_page": limit,
                    "total_pages": (total_records + limit - 1) // limit
                },
                "records": [
                    {
                        "id": wo.id,
                        "customer_id": wo.customer_id,
                        "wo_id_xl": wo.wo_id_xl,
                        "city": wo.city_simplified,
                        "region": wo.region,
                        "product_name": wo.product_name,
                        "status_wo": wo.status_wo,
                        "vendor": wo.vendor,
                        "updated_by": wo.updated_by,
                        "updated_at": wo.updated_at.strftime("%Y-%m-%d %H:%M:%S") if wo.updated_at else None,
                        "approval_status": wo.approval_status or "pending"
                    }
                    for wo in work_orders
                ]
            }
        }

@router.put("/work-orders/{wo_id}/approve", tags=["Work Orders"], summary="Approve/Reject WO")
async def approve_work_order(
    wo_id: int,
    action: str = Form(..., description="approved atau rejected"),
    notes: Optional[str] = Form(None, description="Catatan approval/rejection"),
    current_user: models.User = Depends(require_role(["admin", "admin_regional"]))
):
    """
    Approve atau Reject Work Order
    
    **Admin Regional:** Hanya bisa approve WO di region mereka
    **Admin:** Bisa approve semua WO
    
    **Actions:**
    - `approved`: Approve WO
    - `rejected`: Reject WO (perlu notes)
    """
    if action not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Action harus 'approved' atau 'rejected'")
    
    if action == "rejected" and not notes:
        raise HTTPException(status_code=400, detail="Notes wajib diisi saat reject WO")
    
    with Session(engine) as session:
        wo = session.query(models.DismantleData).filter(models.DismantleData.id == wo_id).first()
        
        if not wo:
            raise HTTPException(status_code=404, detail="Work Order tidak ditemukan")
        
        # Cek permission: Admin Regional hanya bisa approve WO di city (area) mereka
        if current_user.role == "admin_regional":
            if wo.city_simplified != current_user.area:
                raise HTTPException(
                    status_code=403,
                    detail="Anda tidak memiliki akses untuk approve WO ini"
                )
            if wo.status_wo == "Scheduled":
                raise HTTPException(
                    status_code=403,
                    detail="WO dengan status Scheduled tidak bisa di-approve"
                )
        
        # Cek apakah WO sudah diupdate oleh teknisi
        if not wo.updated_by:
            raise HTTPException(
                status_code=400,
                detail="WO ini belum diupdate oleh teknisi"
            )
        
        # Update approval status
        wo.approval_status = action
        wo.approval_by = current_user.username
        wo.approval_date = datetime.now()
        wo.approval_notes = notes
        
        session.commit()
        session.refresh(wo)
        
        return {
            "status": "success",
            "message": f"Work Order berhasil di-{action}",
            "data": {
                "id": wo.id,
                "wo_id_xl": wo.wo_id_xl,
                "approval_status": wo.approval_status,
                "approval_by": wo.approval_by,
                "approval_date": wo.approval_date.strftime("%Y-%m-%d %H:%M:%S"),
                "approval_notes": wo.approval_notes
            }
        }

@router.get("/work-orders/statistics", tags=["Work Orders"], summary="WO Statistics")
async def get_wo_statistics(
    current_user: models.User = Depends(get_current_user)
):
    """
    Mendapatkan statistik Work Orders
    
    **Per Role:**
    - Admin: Semua statistik
    - Admin Regional: Statistik per city (area)
    - Teknisi: Statistik per area
    """
    with Session(engine) as session:
        query = session.query(models.DismantleData)
        
        # Filter berdasarkan role
        if current_user.role == "teknisi":
            query = query.filter(models.DismantleData.city_simplified == current_user.area)
        elif current_user.role == "admin_regional":
            query = query.filter(
                models.DismantleData.city_simplified == current_user.area,
                models.DismantleData.status_wo != "Scheduled"
            )
        
        total = query.count()
        
        # Status breakdown
        status_stats = {}
        for status in ["Scheduled", "In Progress", "Completed", "Full Collected", "Not Collected", "Partial Collected"]:
            count = query.filter(models.DismantleData.status_wo == status).count()
            status_stats[status] = count
        
        # Approval stats (for Admin Regional & Admin)
        approval_stats = {}
        if current_user.role in ["admin", "admin_regional"]:
            approval_stats = {
                "pending": query.filter(
                    models.DismantleData.updated_by.isnot(None),
                    models.DismantleData.approval_status.in_([None, 'pending'])
                ).count(),
                "approved": query.filter(models.DismantleData.approval_status == 'approved').count(),
                "rejected": query.filter(models.DismantleData.approval_status == 'rejected').count()
            }
        
        return {
            "status": "success",
            "data": {
                "total_wo": total,
                "status_breakdown": status_stats,
                "approval_stats": approval_stats
            }
        }


