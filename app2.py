from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import certifi
import streamlit as st
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

try:
    from knowledge_base import KNOWLEDGE_BASE, find_best_answer, infer_topic_for_question, normalize_text
except ImportError:
    from chatbot.knowledge_base import KNOWLEDGE_BASE, find_best_answer, infer_topic_for_question, normalize_text


BANGKOK_TZ = ZoneInfo("Asia/Bangkok")
PROJECT_ROOT = Path(__file__).resolve().parent

ROOT_SECRETS_PATH = PROJECT_ROOT / "secret.toml"

DEFAULT_OLLAMA_MODEL = "gemma2:latest"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
AI_FALLBACK_TOPIC = "AI fallback"
OUT_OF_SCOPE_TOPIC = "out_of_scope"
NON_CANONICAL_TOPICS = {"fallback", AI_FALLBACK_TOPIC, OUT_OF_SCOPE_TOPIC}
SOCIAL_SECURITY_AI_INSTRUCTIONS = """
คุณคือเจ้าหน้าที่ให้ข้อมูลประกันสังคมของไทย
ต้องตอบเหมือนเจ้าหน้าที่ประชาสัมพันธ์ที่คุยกับประชาชนจริง ๆ
ใช้ภาษาไทยธรรมชาติ กระชับ เป็นมิตร ไม่เป็นทางการจนเกินไป ไม่ใช่ภาษาหุ่นยนต์

ข้อห้ามในการใช้ภาษา:
- ห้ามใช้ "ค่ะ" "ค่ะ." "นะคะ" โดยเด็ดขาด
- ใช้คำลงท้าย "ครับ" เท่านั้น หรือไม่ต้องลงท้ายถ้าประโยคสั้น
- ห้ามขึ้นต้นประโยคซ้ำ ๆ เช่น "ตามหลักประกันสังคม..." "โดยทั่วไป..." "สามารถตรวจสอบเพิ่มเติมได้..."
- ห้ามใช้คำว่า "สมัครสมาชิก" หรือ "สมัครสมาชิกประกันสังคม" เพราะประกันสังคมไม่มีระบบสมาชิก
- ห้ามใช้ภาษาอื่นปน

วิธีการตอบ:
- ตอบตรงประเด็น สั้น กระชับ ไม่ยืดเยื้อ
- ถ้าถามว่าได้สิทธิไหม เบิกได้ไหม สมัครยังไง ต้องใช้เอกสารอะไร ให้ตอบตรง ๆ
- ถ้าถามเรื่องลูก บุตร ค่าเทอม ให้พิจารณาสิทธิสงเคราะห์บุตรก่อน
- ถ้าถามเรื่องอื่นที่ไม่ใช่ประกันสังคม เช่น อากาศ หุ้น เขียนโปรแกรม ให้บอกว่าออกแบบมาสำหรับคำถามด้านประกันสังคม

สิ่งที่ห้ามทำเด็ดขาด:
- ห้ามแต่งตัวเลข อัตราเงิน หรือเงื่อนไขที่ไม่แน่ใจ
- ห้ามเปลี่ยนมาตรา 33/39/40 ของผู้ถาม
- ห้ามตอบคนละเรื่องกับที่ถาม

ถ้าไม่มั่นใจในข้อมูล:
ให้ตอบว่า "ผมยังไม่สามารถยืนยันข้อมูลส่วนนี้ได้ แนะนำให้สอบถามสำนักงานประกันสังคมหรือสายด่วน 1506"
"""

SOCIAL_SECURITY_SCOPE_KEYWORDS = [
    "ประกันสังคม",
    "มาตรา",
    "ม33",
    "ม39",
    "ม40",
    "ผู้ประกันตน",
    "เงินสมทบ",
    "สิทธิ",
    "ว่างงาน",
    "ชราภาพ",
    "คลอด",
    "โรงพยาบาล",
    "ค่ารักษา",
    "ลาออก",
    "เลิกจ้าง",
    "บำนาญ",
    "บำเหน็จ",
    "เกษียณ",
    "1506",
    "สายด่วน1506",
    "เงินชราภาพ",
    "เงินบำนาญ",
    "เงินบำเหน็จ",
    "อายุ55",
    "เกษียณอายุ",
]
BORDERLINE_SCOPE_KEYWORDS = [
    "สิทธิ",
    "สิทธิ์",
    "สวัสดิการ",
    "สมัคร",
    "ลงทะเบียน",
    "ยื่น",
    "เอกสาร",
    "เบิก",
    "เคลม",
    "ครอบคลุม",
    "ได้ไหม",
    "ยังไง",
    "ขั้นตอน",
    "ลูก",
    "บุตร",
    "เด็ก",
    "ค่าเทอม",
    "ค่าเล่าเรียน",
    "ค่าเรียน",
    "สงเคราะห์บุตร",
    "ค่าคลอด",
    "รักษา",
    "โรงพยาบาล",
]
STRONG_SCOPE_KEYWORDS = {
    "1506",
    "ประกันสังคม",
    "ผู้ประกันตน",
    "ชราภาพ",
    "บำนาญ",
    "บำเหน็จ",
    "เกษียณ",
    "มาตรา33",
    "มาตรา39",
    "มาตรา40",
    "ม33",
    "ม39",
    "ม40",
}
DERIVED_SCOPE_KEYWORDS = {
    normalize_text(keyword)
    for item in KNOWLEDGE_BASE
    for keyword in item["keywords"]
}


st.set_page_config(page_title="ประกันสังคม Chatbot", page_icon="💬", layout="centered")

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@400;500;600;700&family=Sarabun:wght@400;500;600;700&display=swap');

        * {
            font-family: "Prompt", "Sarabun", sans-serif;
        }

        .stApp {
            background: #FAFBFC;
        }

        .block-container {
            max-width: 700px;
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .main-header {
            text-align: center;
            margin-bottom: 0.15rem;
        }

        .main-header .logo-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            margin-bottom: 0.1rem;
        }

        .main-header .logo-icon {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, #FFD6E7, #D9ECFF);
            border-radius: 10px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }

        .main-header .title {
            font-size: 1.6rem;
            font-weight: 700;
            color: #334155;
            margin: 0;
            letter-spacing: -0.02em;
        }

        .main-header .subtitle {
            font-size: 0.88rem;
            color: #64748B;
            margin-top: 0.1rem;
            font-weight: 400;
        }

        .popular-section {
            text-align: center;
            margin: 2rem 0 1.5rem;
        }

        .popular-section .section-label {
            font-size: 0.7rem;
            font-weight: 600;
            letter-spacing: 0.12em;
            color: #94a3b8;
            margin-bottom: 0.75rem;
        }

        .popular-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            justify-content: center;
        }

        .popular-grid .stButton > button {
            border-radius: 999px;
            padding: 0.4rem 1.1rem;
            background: #ffffff;
            border: 1px solid #E7EAF0;
            color: #334155;
            font-size: 0.82rem;
            font-weight: 500;
            min-height: 0;
            height: auto;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }

        .popular-grid .stButton > button:hover {
            border-color: #FFD6E7;
            background: #fff8fb;
            transform: translateY(-2px);
            box-shadow: 0 4px 14px rgba(255, 214, 231, 0.3);
        }

        .popular-grid .stButton > button:active {
            transform: translateY(0);
        }

        [data-testid="stChatMessage"] {
            padding: 0.15rem 0;
        }

        [data-testid="stChatMessageContent"] {
            border-radius: 20px !important;
            padding: 0.85rem 1.1rem !important;
            box-shadow: none !important;
        }

        [data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) [data-testid="stChatMessageContent"] {
            background: #FFD6E7 !important;
            border: 1px solid #f5c8db !important;
            color: #334155 !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
        }

        [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] {
            background: #D9ECFF !important;
            border: 1px solid #c8dff5 !important;
            color: #334155 !important;
        }

        .welcome-message [data-testid="stChatMessageContent"] {
            background: #DDF5E5 !important;
            border: 1px solid #c8e8d4 !important;
        }

        [data-testid="stChatInput"] {
            background: #ffffff;
            border-radius: 999px;
            border: 1px solid #E7EAF0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.02);
            padding: 0.35rem 0.75rem;
        }

        [data-testid="stChatInput"]:focus-within {
            border-color: #D9ECFF;
            box-shadow: 0 0 0 3px rgba(217, 236, 255, 0.35);
        }

        [data-testid="stChatInput"] textarea {
            color: #334155;
        }

        [data-testid="stChatInput"] textarea::placeholder {
            color: #94a3b8;
        }

        div[data-testid="stMarkdownContainer"] p {
            margin-bottom: 0;
        }

        .st-emotion-cache-1v0mbdj {
            display: none;
        }

        hr {
            margin: 0;
            border: none;
            border-top: 1px solid #E7EAF0;
        }

        .main-divider {
            margin: 1rem 0 1rem;
            border: none;
            border-top: 1px solid #E7EAF0;
        }

        [data-testid="stSidebar"] {
            display: none;
        }

        .feedback-row {
            display: flex;
            gap: 0.4rem;
            margin-top: 0.6rem;
        }

        .feedback-row .stButton > button {
            border-radius: 999px;
            padding: 0.1rem 0.55rem;
            min-height: 0;
            height: auto;
            font-size: 0.72rem;
            background: rgba(255,255,255,0.6);
            border: 1px solid rgba(255,255,255,0.8);
            color: #64748B;
            transition: all 0.15s ease;
        }

        .feedback-row .stButton > button:hover {
            border-color: #FFD6E7;
            background: #ffffff;
        }

        .feedback-saved {
            font-size: 0.7rem;
            color: #94a3b8;
            margin-top: 0.35rem;
        }

        .reset-area {
            text-align: center;
            margin-top: 0.5rem;
        }

        .reset-area .stButton > button {
            border-radius: 999px;
            padding: 0.2rem 0.9rem;
            min-height: 0;
            height: auto;
            font-size: 0.72rem;
            background: transparent;
            border: 1px solid #E7EAF0;
            color: #94a3b8;
            transition: all 0.15s ease;
        }

        .reset-area .stButton > button:hover {
            border-color: #FFD6E7;
            background: #fff8fb;
            color: #64748B;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def init_connection() -> MongoClient:
    uri = load_secret_value("MONGODB_URI")
    if not uri:
        raise RuntimeError("Missing MONGODB_URI")

    client = MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
    )
    client.admin.command("ping")
    return client


def load_secret_value(key: str) -> str | None:
    try:
        secret_value = st.secrets.get(key)
        if secret_value:
            return str(secret_value)
    except Exception:
        pass

    env_value = os.getenv(key)
    if env_value:
        return env_value

    if ROOT_SECRETS_PATH.exists():
        try:
            for raw_line in ROOT_SECRETS_PATH.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                parsed_key, value = line.split("=", 1)
                if parsed_key.strip() == key:
                    return value.strip().strip('"').strip("'")
        except Exception:
            return None

    return None


def get_ollama_model() -> str:
    return load_secret_value("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL


def get_ollama_base_url() -> str:
    return (load_secret_value("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def is_social_security_question(question: str) -> bool:
    normalized = normalize_text(question)
    if not normalized:
        return False

    matched_keywords = {
        keyword
        for keyword in {normalize_text(keyword) for keyword in SOCIAL_SECURITY_SCOPE_KEYWORDS}.union(DERIVED_SCOPE_KEYWORDS)
        if keyword and keyword in normalized
    }
    if not matched_keywords:
        return False

    if any(keyword in STRONG_SCOPE_KEYWORDS for keyword in matched_keywords):
        return True

    long_matches = [keyword for keyword in matched_keywords if len(keyword) >= 6]
    if long_matches:
        return True

    return len(matched_keywords) >= 2


def get_scope_signal(question: str) -> dict[str, Any]:
    normalized = normalize_text(question)
    if not normalized:
        return {
            "label": "empty",
            "primary_keywords": [],
            "secondary_keywords": [],
        }

    primary_keywords = sorted(
        {
            keyword
            for keyword in {normalize_text(keyword) for keyword in SOCIAL_SECURITY_SCOPE_KEYWORDS}.union(
                DERIVED_SCOPE_KEYWORDS
            )
            if keyword and keyword in normalized
        }
    )
    secondary_keywords = sorted(
        {
            normalize_text(keyword)
            for keyword in BORDERLINE_SCOPE_KEYWORDS
            if normalize_text(keyword) in normalized
        }
    )

    if any(keyword in STRONG_SCOPE_KEYWORDS for keyword in primary_keywords):
        label = "likely_in_scope"
    elif len(primary_keywords) >= 2:
        label = "likely_in_scope"
    elif primary_keywords and secondary_keywords:
        label = "likely_in_scope"
    elif secondary_keywords and any(
        keyword in secondary_keywords
        for keyword in {"สิทธิ", "สิทธิ์", "สวัสดิการ", "สมัคร", "เบิก", "ลูก", "บุตร", "ค่าเทอม"}
    ):
        label = "borderline_related"
    elif is_social_security_question(question):
        label = "likely_in_scope"
    else:
        label = "unclear"

    return {
        "label": label,
        "primary_keywords": primary_keywords,
        "secondary_keywords": secondary_keywords,
    }


def build_ai_messages(question: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SOCIAL_SECURITY_AI_INSTRUCTIONS.strip()}]
    scope_signal = get_scope_signal(question)
    signal_note = (
        "สัญญาณจากระบบเบื้องต้น: "
        f"{scope_signal['label']} | "
        f"primary={', '.join(scope_signal['primary_keywords']) or '-'} | "
        f"secondary={', '.join(scope_signal['secondary_keywords']) or '-'}"
    )
    messages.append({"role": "system", "content": signal_note})
    history = st.session_state.get("messages", [])

    for message in history[-6:]:
        if message["role"] not in {"user", "assistant"}:
            continue
        messages.append({"role": message["role"], "content": message["content"]})

    if not messages or messages[-1]["role"] != "user" or messages[-1]["content"] != question:
        messages.append({"role": "user", "content": question})
    return messages


def generate_ai_answer(question: str) -> dict[str, Any]:
    scope_signal = get_scope_signal(question)
    model = get_ollama_model()
    base_url = get_ollama_base_url()
    payload = {
        "model": model,
        "messages": build_ai_messages(question),
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.8,
            "num_predict": 300,
        },
    }

    try:
        request = Request(
            url=f"{base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        answer_text = response_payload.get("message", {}).get("content", "").strip()
        if not answer_text:
            raise ValueError("Empty AI response")
        return {
            "topic": AI_FALLBACK_TOPIC,
            "answer": answer_text,
            "score": 0,
            "matched": False,
            "source": "ollama",
            "model": model,
            "status_text": f"Ollama fallback ทำงานสำเร็จ ({scope_signal['label']})",
        }
    except HTTPError as exc:
        error_type = type(exc).__name__
        error_body = exc.read().decode("utf-8", errors="ignore")
        if exc.code == 404 or "model" in error_body.lower():
            answer_text = (
                f"ยังไม่พบโมเดล `{model}` ใน Ollama กรุณารัน `ollama pull {model}` ก่อนใช้งาน"
            )
            status_text = f"Ollama model not found: {model}"
        else:
            answer_text = (
                "ระบบ Ollama ตอบไม่ได้ในรอบนี้ กรุณาตรวจสอบว่า Ollama เปิดอยู่ "
                "และ endpoint ของ Ollama ใช้งานได้ตามปกติ"
            )
            status_text = f"Ollama HTTP error: {exc.code}"
        return {
            "topic": AI_FALLBACK_TOPIC,
            "answer": answer_text,
            "score": 0,
            "matched": False,
            "source": "ai_error",
            "model": model,
            "status_text": status_text,
        }
    except URLError:
        return {
            "topic": AI_FALLBACK_TOPIC,
            "answer": (
                "ยังติดต่อ Ollama ไม่ได้ กรุณาตรวจสอบว่าติดตั้งและเปิด Ollama แล้ว "
                f"และกำลังรันที่ {base_url}"
            ),
            "score": 0,
            "matched": False,
            "source": "ai_unavailable",
            "model": model,
            "status_text": f"Ollama server unavailable: {base_url}",
        }
    except Exception as exc:
        error_type = type(exc).__name__
        answer_text = (
            "ระบบ Ollama ยังตอบไม่ได้ในรอบนี้ กรุณาตรวจสอบว่าได้ pull โมเดลไว้แล้ว "
            "และเซิร์ฟเวอร์ Ollama ทำงานอยู่"
        )
        return {
            "topic": AI_FALLBACK_TOPIC,
            "answer": answer_text,
            "score": 0,
            "matched": False,
            "source": "ai_error",
            "model": model,
            "status_text": f"Ollama error: {error_type}",
        }


def get_collection():
    client = init_connection()
    return client["social_security_chatbot"]["chat_logs"]


def current_timestamps() -> dict[str, str | datetime]:
    now_utc = datetime.now(timezone.utc)
    now_bkk = now_utc.astimezone(BANGKOK_TZ)
    return {
        "created_at_utc": now_utc,
        "created_at_local": now_bkk,
        "created_date": now_bkk.strftime("%Y-%m-%d"),
        "created_time": now_bkk.strftime("%H:%M:%S"),
    }


def canonicalize_question_text(question: str) -> str:
    canonical = normalize_text(question)
    filler_phrases = [
        "ครับ",
        "ค่ะ",
        "คะ",
        "นะครับ",
        "หน่อย",
        "หน่อยครับ",
        "ทีครับ",
        "ทีค่ะ",
        "รบกวน",
        "ช่วย",
    ]
    for phrase in filler_phrases:
        canonical = canonical.replace(normalize_text(phrase), "")
    return canonical


def derive_question_group(question: str, topic: str | None) -> dict[str, str]:
    canonical_topic = topic if topic and topic not in NON_CANONICAL_TOPICS else None
    inferred_topic = canonical_topic or infer_topic_for_question(question)
    if inferred_topic:
        return {
            "question_group": f"topic::{inferred_topic}",
            "question_group_label": inferred_topic,
        }

    canonical_question = canonicalize_question_text(question) or normalize_text(question)
    return {
        "question_group": f"question::{canonical_question}",
        "question_group_label": question.strip(),
    }


def save_chat_log(question: str, answer_payload: dict[str, Any]) -> str | None:
    timestamps = current_timestamps()
    group_info = derive_question_group(question, answer_payload.get("topic"))
    document = {
        "session_id": st.session_state.session_id,
        "question": question,
        "question_normalized": normalize_text(question),
        **group_info,
        "answer": answer_payload["answer"],
        "topic": answer_payload["topic"],
        "match_score": answer_payload["score"],
        "matched": answer_payload["matched"],
        "answer_source": answer_payload.get("source", "knowledge_base"),
        "model": answer_payload.get("model"),
        "feedback": None,
        **timestamps,
    }

    try:
        result = get_collection().insert_one(document)
        return str(result.inserted_id)
    except PyMongoError:
        return None


def update_feedback(record_id: str, feedback: str) -> bool:
    timestamps = current_timestamps()
    try:
        result = get_collection().update_one(
            {"_id": st.session_state.object_id_factory(record_id)},
            {
                "$set": {
                    "feedback": feedback,
                    "feedback_at_utc": timestamps["created_at_utc"],
                    "feedback_at_local": timestamps["created_at_local"],
                }
            },
        )
        return result.modified_count > 0
    except Exception:
        return False


def get_popular_questions(limit: int = 5) -> list[dict[str, Any]]:
    topic_group_prefix = "topic::"
    pipeline = [
        {
            "$match": {
                "question": {
                    "$type": "string",
                    "$ne": "",
                }
            }
        },
        {"$sort": {"created_at_utc": -1}},
        {
            "$addFields": {
                "effective_group": {
                    "$ifNull": [
                        "$question_group",
                        {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$ne": ["$topic", None]},
                                        {"$not": [{"$in": ["$topic", list(NON_CANONICAL_TOPICS)]}]},
                                    ]
                                },
                                {"$concat": [topic_group_prefix, "$topic"]},
                                "$question",
                            ]
                        },
                    ]
                },
                "effective_label": {
                    "$ifNull": [
                        "$question_group_label",
                        {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$ne": ["$topic", None]},
                                        {"$not": [{"$in": ["$topic", list(NON_CANONICAL_TOPICS)]}]},
                                    ]
                                },
                                "$topic",
                                "$question",
                            ]
                        },
                    ]
                },
            }
        },
        {
            "$group": {
                "_id": "$effective_group",
                "count": {"$sum": 1},
                "latest_at": {"$first": "$created_at_utc"},
                "question": {"$first": "$question"},
                "group_label": {"$first": "$effective_label"},
                "topic": {"$first": "$topic"},
            }
        },
        {"$sort": {"count": -1, "latest_at": -1}},
        {"$limit": limit},
    ]

    try:
        results = list(get_collection().aggregate(pipeline))
    except PyMongoError:
        return []

    return [
        {
            "question": item.get("question") or item.get("group_label") or item["_id"],
            "group_label": item.get("group_label") or item.get("question") or item["_id"],
            "count": item["count"],
            "topic": item.get("topic"),
        }
        for item in results
        if item.get("_id")
    ]


def backfill_question_groups(batch_size: int = 200) -> None:
    try:
        collection = get_collection()
        cursor = collection.find(
            {
                "$or": [
                    {"question_group": {"$exists": False}},
                    {"question_group_label": {"$exists": False}},
                ],
                "question": {"$type": "string", "$ne": ""},
            },
            {"question": 1, "topic": 1},
            limit=batch_size,
        )

        operations = []
        for item in cursor:
            group_info = derive_question_group(item["question"], item.get("topic"))
            operations.append(
                UpdateOne(
                    {"_id": item["_id"]},
                    {
                        "$set": {
                            "question_normalized": normalize_text(item["question"]),
                            **group_info,
                        }
                    },
                )
            )

        if operations:
            collection.bulk_write(operations, ordered=False)
    except PyMongoError:
        return


def bootstrap_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "is_welcome": True,
                "content": (
                    "สวัสดีครับ ถามเรื่องประกันสังคมได้เลยครับ "
                    "เช่น มาตรา 33, 39, 40, สิทธิรักษาพยาบาล, ว่างงาน, คลอดบุตร, ชราภาพ"
                ),
                "record_id": None,
                "feedback": None,
                "topic": None,
                "source": None,
                "model": None,
            }
        ]

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None


def main() -> None:
    bootstrap_state()
    popular_questions: list[dict[str, Any]] = []

    db_status = True
    try:
        from bson import ObjectId

        st.session_state.object_id_factory = ObjectId
        get_collection()
    except RuntimeError:
        db_status = False
    except ServerSelectionTimeoutError:
        db_status = False
    except Exception:
        db_status = False

    if db_status:
        backfill_question_groups()
        popular_questions = get_popular_questions()

    st.markdown(
        """
        <div class="main-header">
            <div class="logo-row">
                <span class="logo-icon">⚙️</span>
                <span class="title">ประกันสังคม</span>
            </div>
            <div class="subtitle">ถามเกี่ยวกับสิทธิประกันสังคมของไทย</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if popular_questions:
        st.markdown(
            """
            <div class="popular-section">
                <div class="section-label">POPULAR QUESTIONS</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        pop_cols = st.columns([1] * min(3, len(popular_questions)), gap="small")
        row_size = 3
        for i, item in enumerate(popular_questions):
            col_idx = i % row_size
            with pop_cols[col_idx]:
                label = f"{item['group_label']}  ({item['count']})"
                if st.button(label, key=f"pop_{i}", use_container_width=True):
                    st.session_state.pending_prompt = item["question"]
                    st.rerun()

    st.markdown("<hr class='main-divider'>", unsafe_allow_html=True)

    chat_container = st.container()
    with chat_container:
        for index, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                if message.get("is_welcome"):
                    st.markdown(
                        f'<div class="welcome-message">{message["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(message["content"])
                if message["role"] == "assistant":
                    if not message.get("record_id"):
                        continue
                    if message.get("feedback"):
                        icon = "👍" if message["feedback"] == "liked" else "👎"
                        st.markdown(f"<div class='feedback-saved'>{icon} บันทึกแล้ว</div>", unsafe_allow_html=True)
                        continue
                    st.markdown("<div class='feedback-row'>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("👍", key=f"like_{index}", use_container_width=True):
                            if update_feedback(message["record_id"], "liked"):
                                st.session_state.messages[index]["feedback"] = "liked"
                                st.rerun()
                    with col2:
                        if st.button("👎", key=f"dislike_{index}", use_container_width=True):
                            if update_feedback(message["record_id"], "disliked"):
                                st.session_state.messages[index]["feedback"] = "disliked"
                                st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    prompt = st.chat_input("พิมพ์คำถามเกี่ยวกับประกันสังคม...")
    if not prompt and st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None
    if not prompt:
        return

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
            "record_id": None,
            "feedback": None,
            "topic": None,
            "source": None,
            "model": None,
        }
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    kb_answer = find_best_answer(prompt)

    if kb_answer.get("matched"):
        prompt_with_context = f"""
        ข้อมูลอ้างอิงจากฐานความรู้:

        {kb_answer['answer']}

        กฎ:
        - ใช้ข้อมูลอ้างอิงด้านบนเป็นแหล่งข้อมูลหลัก
        - หากข้อมูลอ้างอิงขัดแย้งกับความรู้เดิมของคุณ ให้เชื่อข้อมูลอ้างอิง
        - ห้ามเพิ่มตัวเลขหรือเงื่อนไขที่ไม่มีในข้อมูลอ้างอิง

        คำถาม:
        {prompt}
        """
        answer_payload = generate_ai_answer(prompt_with_context)
    else:
        answer_payload = generate_ai_answer(prompt)
    record_id = save_chat_log(prompt, answer_payload) if db_status else None

    assistant_message = {
        "role": "assistant",
        "content": answer_payload["answer"],
        "record_id": record_id,
        "feedback": None,
        "topic": answer_payload["topic"],
        "source": answer_payload.get("source"),
        "model": answer_payload.get("model"),
        "status_text": answer_payload.get("status_text"),
    }
    st.session_state.messages.append(assistant_message)

    with st.chat_message("assistant"):
        st.markdown(answer_payload["answer"])

    st.rerun()


if __name__ == "__main__":
    main()
