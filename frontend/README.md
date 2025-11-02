# WMS Dismantle - Frontend Web Dashboard

## 🎨 Frontend Overview

Simple web dashboard untuk Admin dan Admin Regional mengelola Work Orders.

### ✅ Features

- **Login System** - JWT authentication
- **Work Orders Table** - Pagination, filter, search
- **Upload Excel** - Upload WO dan User data
- **View Details** - Lihat detail WO dengan foto-foto
- **Role-based View**:
  - **Admin**: Lihat semua WO
  - **Admin Regional**: Lihat WO per region (exclude Scheduled)

---

## 📂 File Structure

```
frontend/
├── index.html       # Landing page
├── login.html       # Login page
└── dashboard.html   # Main dashboard
```

---

## 🚀 Cara Menggunakan

### 1. Pastikan Backend Running

Backend harus jalan di http://127.0.0.1:8000

```bash
cd d:\wms-dismantle
python -m uvicorn app.main:app --reload
```

### 2. Buka Frontend

**Option A: Open file langsung di browser**
```
Double-click index.html atau login.html
```

**Option B: Gunakan Simple HTTP Server**
```bash
cd d:\wms-dismantle\frontend
python -m http.server 8080
```

Kemudian buka: http://localhost:8080

---

## 🔐 Default Login

**Admin:**
- Username: `admin`
- Password: `admin123`

---

## 📸 Screenshots

### Login Page
- Simple login form
- Auto redirect ke dashboard setelah login

### Dashboard
- Upload Excel (Admin only)
- Filter WO by status, vendor, city
- Table dengan pagination
- View detail WO + photos

---

## ⚠️ Important Notes

### CORS Issue Fix

Jika ada CORS error, pastikan backend sudah ada CORS middleware (sudah diset di `app/main.py`):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Di production, ganti dengan domain spesifik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### File Upload Path

Foto yang diupload tersimpan di:
```
d:\wms-dismantle\uploads\photos\
```

Format nama file:
```
WO{id}_{tipe_foto}_{timestamp}.ext
```

Example: `WO123_rumah_20251101_143052.jpg`

---

## 🎯 Features Breakdown

### Admin Features
✅ Upload Excel WO
✅ Upload Excel Users
✅ View ALL Work Orders
✅ Filter & Pagination
✅ View WO Details with Photos

### Admin Regional Features
✅ View WO in their region only
✅ Filter exclude "Scheduled" status
✅ View WO Details with Photos
❌ Cannot upload Excel

---

## 🔧 Customization

### Change API URL

Edit di setiap HTML file, ubah:
```javascript
const API_URL = 'http://127.0.0.1:8000';
```

Ganti dengan URL production API.

### Styling

Menggunakan **Tailwind CSS CDN**. Untuk production, recommended pakai:
- Next.js
- React + Vite
- Vue.js

---

## 📱 Mobile App (Coming Soon!)

Mobile app untuk teknisi akan dibuat dengan:
- **Flutter** atau **React Native**
- Camera integration
- Barcode scanner
- Offline mode
- GPS tracking

---

## 🐛 Troubleshooting

### Error: Failed to fetch
- Pastikan backend running di port 8000
- Check CORS settings di backend

### Login Error
- Check username & password
- Check API endpoint `/login`

### Upload tidak berhasil
- Check file format (.xlsx atau .xls)
- Check file size
- Check API endpoint `/upload/excel` atau `/upload/users`

---

## 🚀 Next Steps

1. ✅ **Backend API** - DONE!
2. ✅ **Web Dashboard** - DONE!
3. 🔄 **Mobile App** - In Progress
4. ⏳ **OCR Implementation** - TODO
5. ⏳ **Advanced Analytics** - TODO

---

**Frontend Web Dashboard: ✅ COMPLETE!**
