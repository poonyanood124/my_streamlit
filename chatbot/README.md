# Social Security Chatbot

Streamlit chatbot สำหรับถามตอบเรื่องประกันสังคม พร้อมบันทึกคำถาม คำตอบ วันที่ และ feedback ลง MongoDB

## Run

```bash
streamlit run chatbot/app.py
```

## Secrets

ใส่ค่าใน `.streamlit/secrets.toml`

```toml
MONGODB_URI = "your-mongodb-uri"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"
```

ติดตั้งและเปิด Ollama ก่อน จากนั้น pull โมเดลที่ต้องการ เช่น

```bash
ollama pull llama3.2
```

ถ้า Ollama ยังไม่รัน หรือยังไม่ได้ pull โมเดล ระบบจะยังตอบจาก knowledge base ได้ตามปกติ แต่จะไม่สามารถใช้ AI fallback สำหรับคำถามนอกชุดคำตอบได้

AI fallback ถูกตั้งค่าให้ช่วยตีความคำถามที่ไม่พูดคำว่า "ประกันสังคม" ตรง ๆ แต่ยังน่าจะเกี่ยวกับสิทธิหรือสวัสดิการ เช่น คำถามเรื่องลูก บุตร การสมัคร เอกสาร การเบิก หรือค่าใช้จ่ายที่สงสัยว่าเบิกได้หรือไม่ โดยถ้าคำถามไม่เกี่ยวจริง ระบบจะปฏิเสธอย่างสุภาพ

## Database fields

- `session_id`
- `question`
- `answer`
- `topic`
- `match_score`
- `matched`
- `answer_source`
- `model`
- `feedback`
- `created_at_utc`
- `created_at_local`
- `created_date`
- `created_time`
- `feedback_at_utc`
- `feedback_at_local`
