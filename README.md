# Streamlit Apps

Repo นี้มีหลายแอป Streamlit ที่ใช้ MongoDB เป็น backend

## Shared setup

สร้าง `.streamlit/secrets.toml`

```toml
MONGODB_URI = "your-mongodb-uri"
MONGODB_DB = "chamber_booking"
MONGODB_COLLECTION = "bookings"
```

ติดตั้ง dependencies

```bash
pip install -r requirements.txt
```

## Chamber Booking

รัน local

```bash
streamlit run chamber.py
```

สิ่งที่แอปรองรับ

- เก็บ booking ลง MongoDB แทน Excel
- ถ้า collection ยังว่างและมี `booking.xlsx` อยู่ ระบบจะ import ข้อมูลเดิมเข้า MongoDB ให้อัตโนมัติหนึ่งครั้ง
- เปลี่ยนชื่อ database/collection ได้ผ่าน `MONGODB_DB` และ `MONGODB_COLLECTION`

Deploy บน Streamlit Community Cloud

1. เลือกไฟล์ entrypoint เป็น `chamber.py`
2. ใส่ `MONGODB_URI` ใน App secrets
3. ถ้าต้องการเปลี่ยน database หรือ collection ให้ใส่ `MONGODB_DB` และ `MONGODB_COLLECTION` เพิ่ม

## Mini Airbnb Dashboard

รัน local

```bash
streamlit run app.py
```

Deploy บน Streamlit Community Cloud โดยตั้งค่า `MONGODB_URI` ใน app secrets
