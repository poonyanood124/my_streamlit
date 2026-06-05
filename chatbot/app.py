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
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT_SECRETS_PATH = PROJECT_ROOT / ".streamlit" / "secrets.toml"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
AI_FALLBACK_TOPIC = "AI fallback"
OUT_OF_SCOPE_TOPIC = "out_of_scope"
NON_CANONICAL_TOPICS = {"fallback", AI_FALLBACK_TOPIC, OUT_OF_SCOPE_TOPIC}
SOCIAL_SECURITY_AI_INSTRUCTIONS = """
คุณเป็นผู้ช่วยตอบคำถามเรื่องประกันสังคมของไทย
- ตอบเป็นภาษาไทยที่เข้าใจง่าย กระชับ และสุภาพ
- ตอบเรื่องประกันสังคม สิทธิประโยชน์ ขั้นตอน เอกสาร หรือคำแนะนำที่เกี่ยวข้องเป็นหลัก
- ถ้าคำถามไม่ได้พูดคำว่า "ประกันสังคม" ตรง ๆ แต่มีแนวโน้มถามเรื่องสิทธิ สวัสดิการ การสมัคร เอกสาร การเบิก การส่งเงินสมทบ ลูกหรือบุตร การรักษา การว่างงาน การคลอด หรือค่าใช้จ่ายที่ผู้ใช้สงสัยว่าเบิกได้ไหม ให้พยายามตีความในกรอบประกันสังคมก่อน อย่าเพิ่งปฏิเสธเร็วเกินไป
- ถ้าผู้ใช้ถามว่าสิ่งหนึ่ง "ได้สิทธิ์ไหม", "เบิกได้ไหม", "สมัครยังไง", "ต้องใช้เอกสารอะไร", หรือ "ครอบคลุมไหม" ให้ตอบว่าตามหลักประกันสังคมเกี่ยวข้องกับสิทธิใด หรือถ้าโดยทั่วไปไม่ใช่สิทธิของประกันสังคมก็ควรบอกตรง ๆ ว่าโดยหลักมักไม่ครอบคลุม พร้อมเสนอคำถามต่อยอดที่ควรถาม
- ถ้าคำถามเป็นเรื่องลูก บุตร ค่าเทอม หรือค่าเล่าเรียน ให้พิจารณาสิทธิกรณีสงเคราะห์บุตรก่อน และอย่าแต่งเงื่อนไขเฉพาะ เช่น ต้องรอครบกี่ปี ต้องจ่ายเป็นรายเดือนแบบใด หรือเบิกย้อนหลังได้เท่าไร ถ้าไม่แน่ใจ
- ถ้าคำถามชัดเจนว่าไม่เกี่ยวกับประกันสังคมจริง ๆ เช่น เรื่องอากาศ หุ้น เขียนโปรแกรม หรือข่าวทั่วไป ให้บอกสุภาพว่าระบบนี้ออกแบบมาสำหรับคำถามด้านประกันสังคม
- ถ้าไม่มั่นใจในรายละเอียดที่เปลี่ยนแปลงตามเวลา ให้ระบุว่านี่เป็นคำแนะนำเบื้องต้น และแนะนำให้ตรวจสอบกับสำนักงานประกันสังคมหรือสายด่วน 1506
- ห้ามแต่งตัวเลข อัตราเงิน หรือเงื่อนไขเฉพาะที่ไม่แน่ใจ
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


st.set_page_config(page_title="ประกันสังคม Chatbot", page_icon="💬", layout="wide")

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Noto+Sans+Thai:wght@400;500;600;700&display=swap');

        :root {
            --bg: #f5f7fb;
            --surface: rgba(255, 255, 255, 0.86);
            --surface-strong: #ffffff;
            --border: rgba(15, 23, 42, 0.08);
            --border-strong: rgba(15, 23, 42, 0.12);
            --text: #0f172a;
            --muted: #5b6475;
            --accent: #0f766e;
            --accent-soft: rgba(15, 118, 110, 0.08);
            --shadow: 0 18px 50px rgba(15, 23, 42, 0.06);
        }

        .stApp {
            font-family: "Manrope", "Noto Sans Thai", sans-serif;
            background:
                radial-gradient(circle at top left, rgba(15, 118, 110, 0.08), transparent 26%),
                radial-gradient(circle at 80% 0%, rgba(59, 130, 246, 0.06), transparent 22%),
                linear-gradient(180deg, #f7f9fc 0%, #f4f7fb 100%);
            color: var(--text);
        }

        .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp div, .stApp span, .stApp label {
            font-family: "Manrope", "Noto Sans Thai", sans-serif;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
            padding-bottom: 2.2rem;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8fafc 0%, #f2f5f9 100%);
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 1.6rem;
        }

        .sidebar-note {
            padding: 0.95rem 1rem;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid var(--border);
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.55;
        }

        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 1.1rem 1.25rem;
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(255, 255, 255, 0.78);
            box-shadow: var(--shadow);
            backdrop-filter: blur(18px);
        }

        .product-label {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            font-size: 0.83rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #0b1220;
        }

        .product-dot {
            width: 0.72rem;
            height: 0.72rem;
            border-radius: 999px;
            background: linear-gradient(135deg, #111827, #0f766e);
            box-shadow: 0 0 0 6px rgba(15, 118, 110, 0.09);
        }

        .status-tag {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.55rem 0.8rem;
            border-radius: 999px;
            background: var(--accent-soft);
            border: 1px solid rgba(15, 118, 110, 0.12);
            color: #0f5c56;
            font-size: 0.86rem;
            font-weight: 600;
        }

        .hero-card, .meta-card {
            background: var(--surface);
            border: 1px solid rgba(255, 255, 255, 0.8);
            box-shadow: var(--shadow);
            backdrop-filter: blur(18px);
        }

        .hero-card {
            padding: 1.55rem;
            border-radius: 32px;
        }

        .hero-kicker {
            display: inline-flex;
            align-items: center;
            padding: 0.38rem 0.72rem;
            border-radius: 999px;
            background: #eef2f7;
            color: #334155;
            font-size: 0.82rem;
            font-weight: 600;
        }

        .hero-title {
            margin: 1rem 0 0.7rem;
            font-size: clamp(2rem, 3vw, 3.1rem);
            line-height: 0.98;
            letter-spacing: -0.04em;
            color: #0f172a;
            max-width: 720px;
        }

        .hero-copy {
            margin: 0;
            max-width: 640px;
            color: var(--muted);
            font-size: 1.01rem;
            line-height: 1.7;
        }

        .prompt-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
            margin-top: 1.25rem;
        }

        .prompt-pill {
            padding: 0.62rem 0.9rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.88);
            color: #334155;
            font-size: 0.9rem;
            font-weight: 500;
        }

        .meta-card {
            border-radius: 28px;
            padding: 1.35rem;
            display: grid;
            gap: 1rem;
        }

        .meta-label {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #64748b;
            font-weight: 700;
        }

        .meta-value {
            margin-top: 0.35rem;
            font-size: 1.25rem;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: -0.03em;
        }

        .meta-copy {
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.6;
        }

        .meta-divider {
            height: 1px;
            background: var(--border);
        }

        .section-header {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            margin-top: 0.2rem;
            margin-bottom: 0.75rem;
        }

        .section-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #111827;
            letter-spacing: -0.02em;
            margin: 0;
        }

        .section-copy {
            color: var(--muted);
            font-size: 0.92rem;
        }

        [data-testid="stChatMessage"] {
            border-radius: 22px;
            padding: 0.12rem;
        }

        [data-testid="stChatMessageContent"] {
            border-radius: 22px;
            padding: 1rem 1.05rem;
            box-shadow: none;
        }

        [data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) [data-testid="stChatMessageContent"] {
            background: #ffffff;
            border: 1px solid var(--border);
            color: #172033;
        }

        [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] {
            background: #111827;
            color: #f8fafc;
            border: 1px solid rgba(17, 24, 39, 0.16);
        }

        .stButton > button {
            border-radius: 14px;
            border: 1px solid var(--border-strong);
            background: #ffffff;
            color: #111827;
            font-weight: 600;
            min-height: 2.8rem;
            box-shadow: none;
            transition: all 0.18s ease;
        }

        .stButton > button:hover {
            border-color: rgba(15, 118, 110, 0.26);
            color: #0f5c56;
            background: #fbfffe;
        }

        .stButton > button[kind="primary"] {
            background: #111827;
            color: #f8fafc;
            border-color: #111827;
        }

        [data-testid="stChatInput"] {
            background: rgba(255, 255, 255, 0.92);
            border-radius: 22px;
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.05);
        }

        .hint-banner {
            padding: 1rem 1.08rem;
            border-radius: 20px;
            background: linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(255, 255, 255, 0.95));
            border: 1px solid var(--border);
            color: #465164;
            font-size: 0.94rem;
            line-height: 1.6;
        }

        @media (max-width: 980px) {
            .topbar {
                align-items: flex-start;
                flex-direction: column;
            }
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
                "content": (
                    "สวัสดี ถามเรื่องประกันสังคมได้เลย เช่น มาตรา 33, 39, 40, "
                    "สิทธิรักษาพยาบาล, ว่างงาน, คลอดบุตร, ชราภาพ หรือการตรวจสอบสิทธิ"
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


def render_hero(db_status: bool) -> None:
    db_text = "MongoDB Connected" if db_status else "MongoDB Unavailable"
    st.markdown(
        f"""
        <div class="topbar">
            <div class="product-label">
                <span class="product-dot"></span>
                Social Security Assistant
            </div>
            <div class="status-tag">{db_text}</div>
        </div>
        <div class="hero-card">
            <div class="hero-kicker">Thailand Social Security</div>
            <h1 class="hero-title">ตอบคำถามสิทธิประกันสังคม</h1>
            <div class="prompt-row">
                <span class="prompt-pill">มาตรา 33</span>
                <span class="prompt-pill">มาตรา 39</span>
                <span class="prompt-pill">มาตรา 40</span>
                <span class="prompt-pill">ว่างงาน</span>
                <span class="prompt-pill">สิทธิรักษาพยาบาล</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_meta_panel(db_status: bool) -> None:
    total_messages = len(
        [message for message in st.session_state.messages if message["role"] == "assistant" and message.get("record_id")]
    )
    feedback_count = len(
        [message for message in st.session_state.messages if message["role"] == "assistant" and message.get("feedback")]
    )
    db_text = "พร้อมใช้งาน" if db_status else "รอตรวจสอบการเชื่อมต่อ"

    st.markdown(
        f"""
        <div class="meta-card">
            <div>
                <div class="meta-label">Log Status</div>
                <div class="meta-value">{db_text}</div>
                <div class="meta-copy">บันทึกคำถาม คำตอบ วันที่ และ feedback ได้ใน collection เดียวกัน</div>
            </div>
            <div class="meta-divider"></div>
            <div>
                <div class="meta-label">Saved Responses</div>
                <div class="meta-value">{total_messages}</div>
                <div class="meta-copy">จำนวนคำตอบที่มี record ใน session ปัจจุบัน</div>
            </div>
            <div class="meta-divider"></div>
            <div>
                <div class="meta-label">Feedback Captured</div>
                <div class="meta-value">{feedback_count}</div>
                <div class="meta-copy">จำนวนครั้งที่ผู้ใช้กดถูกใจหรือไม่ถูกใจใน session นี้</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feedback_actions(message: dict, index: int) -> None:
    if not message.get("record_id"):
        return

    if message.get("feedback"):
        if message["feedback"] == "liked":
            st.caption("บันทึกแล้ว: ผู้ใช้ถูกใจกับคำตอบนี้")
        elif message["feedback"] == "disliked":
            st.caption("บันทึกแล้ว: ผู้ใช้ไม่ถูกใจกับคำตอบนี้")
        else:
            st.caption("บันทึก feedback แล้ว")
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.button("ถูกใจ", key=f"like_{index}", use_container_width=True):
            if update_feedback(message["record_id"], "liked"):
                st.session_state.messages[index]["feedback"] = "liked"
                st.rerun()
            st.warning("บันทึก feedback ไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
    with col2:
        if st.button("ไม่ถูกใจ", key=f"dislike_{index}", use_container_width=True):
            if update_feedback(message["record_id"], "disliked"):
                st.session_state.messages[index]["feedback"] = "disliked"
                st.rerun()
            st.warning("บันทึก feedback ไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")


def render_popular_questions(popular_questions: list[dict[str, Any]], db_status: bool) -> None:
    st.markdown(
        """
        <div class="section-header">
            <div class="section-title">Popular Questions</div>
            <div class="section-copy">ดึงจากคำถามที่ถูกบันทึกใน MongoDB และอัปเดตตามข้อมูลจริง</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if popular_questions:
        cols = st.columns(min(3, len(popular_questions)))
        for index, item in enumerate(popular_questions):
            with cols[index % len(cols)]:
                st.markdown(
                    f"""
                    <div class="meta-card">
                        <div>
                            <div class="meta-label">{item['group_label']}</div>
                            <div class="meta-copy">{item['question']}</div>
                        </div>
                        <div class="meta-divider"></div>
                        <div>
                            <div class="meta-label">Asked</div>
                            <div class="meta-value">{item['count']} ครั้ง</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("ถามคำถามนี้", key=f"popular_main_{index}", use_container_width=True):
                    st.session_state.pending_prompt = item["question"]
                    st.rerun()
        return

    if db_status:
        st.info("ตอนนี้ยังไม่มีข้อมูลคำถามมากพอในฐานข้อมูล ลองถามสัก 2-3 คำถามก่อน แล้วส่วนนี้จะเริ่มแสดงคำถามยอดฮิต")
        return

    st.warning("ยังดึงคำถามยอดฮิตไม่ได้ เพราะระบบยังเชื่อมต่อฐานข้อมูลไม่สำเร็จ")


def main() -> None:
    bootstrap_state()
    popular_questions: list[dict[str, Any]] = []

    with st.sidebar:
        st.subheader("Control Panel")
        if st.button("เริ่มบทสนทนาใหม่", use_container_width=True):
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": (
                        "สวัสดีครับ ถามเรื่องประกันสังคมได้เลย เช่น มาตรา 33, 39, 40, "
                        "สิทธิรักษาพยาบาล, ว่างงาน, คลอดบุตร, ชราภาพ หรือการตรวจสอบสิทธิ"
                    ),
                    "record_id": None,
                    "feedback": None,
                    "topic": None,
                    "source": None,
                    "model": None,
                }
            ]
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()
        st.markdown("---")
        st.subheader("Stored Fields")
        st.write("คำถามของผู้ใช้")
        st.write("คำตอบที่ระบบตอบกลับ")
        st.write("วันที่และเวลา")
        st.write("แหล่งที่มาของคำตอบ")
        st.write("feedback ถูกใจหรือไม่ถูกใจ")
        st.caption("ข้อมูลเวลาถูกเก็บทั้ง UTC และเวลาไทย")
        st.markdown("---")
        st.subheader("AI Fallback")
        st.caption(f"Model ปัจจุบัน: {get_ollama_model()}")
        st.caption(f"Endpoint: {get_ollama_base_url()}")
        st.info("Ollama")

    db_status = True
    try:
        from bson import ObjectId

        st.session_state.object_id_factory = ObjectId
        get_collection()
    except RuntimeError:
        db_status = False
        st.error("ไม่พบค่า MONGODB_URI ใน Streamlit secrets หรือ environment variables")
    except ServerSelectionTimeoutError:
        db_status = False
        st.error("เชื่อมต่อ MongoDB ไม่สำเร็จ กรุณาตรวจสอบ connection string และ network")
    except Exception as exc:
        db_status = False
        st.error(f"เกิดปัญหาในการเชื่อมต่อฐานข้อมูล: {exc}")

    if db_status:
        backfill_question_groups()
        popular_questions = get_popular_questions()

    with st.sidebar:
        st.markdown("---")
        st.subheader("คำถามยอดฮิต")
        if popular_questions:
            st.caption("ดึงจากคำถามที่ถูกบันทึกในฐานข้อมูล")
            for index, item in enumerate(popular_questions):
                label = f"{item['group_label']} ({item['count']})"
                if st.button(label, key=f"popular_question_{index}", use_container_width=True):
                    st.session_state.pending_prompt = item["question"]
                    st.rerun()
        elif db_status:
            st.markdown(
                """
                <div class="sidebar-note">
                    ยังไม่มีข้อมูลคำถามมากพอในฐานข้อมูล ลองเริ่มถามสัก 2-3 คำถามก่อน แล้วส่วนนี้จะเริ่มแสดงคำถามยอดฮิตให้เอง
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="sidebar-note">
                    ยังดึงคำถามยอดฮิตไม่ได้ เพราะระบบยังเชื่อมต่อฐานข้อมูลไม่สำเร็จ
                </div>
                """,
                unsafe_allow_html=True,
            )

    hero_col, meta_col = st.columns([1.65, 0.95], gap="large")
    with hero_col:
        render_hero(db_status)
    with meta_col:
        render_meta_panel(db_status)
    render_popular_questions(popular_questions, db_status)
    st.markdown(
        """
        <div class="section-header">
            <div class="section-title">Conversation</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="hint-banner">
            พิมพ์คำถามเป็นภาษาธรรมชาติได้เลย เช่น "ลาออกจากงานแล้วต้องทำมาตรา 39 ยังไง" หรือ "สิทธิรักษาพยาบาลใช้ยังไง"
        </div>
        """,
        unsafe_allow_html=True,
    )

    for index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("topic"):
                st.caption(f"หัวข้อที่จับคู่ได้: {message['topic']}")
            if message.get("source") == "ollama" and message.get("model"):
                st.caption(f"คำตอบนี้มาจาก Ollama fallback: {message['model']}")
            elif message.get("status_text"):
                st.caption(message["status_text"])
            if message["role"] == "assistant":
                render_feedback_actions(message, index)

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

    answer_payload = find_best_answer(prompt)
    answer_payload.setdefault("source", "knowledge_base")
    answer_payload.setdefault("model", None)
    if not answer_payload.get("matched"):
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
        st.caption(f"หัวข้อที่จับคู่ได้: {answer_payload['topic']}")
        if answer_payload.get("source") == "ollama" and answer_payload.get("model"):
            st.caption(f"คำตอบนี้มาจาก Ollama fallback: {answer_payload['model']}")
        elif answer_payload.get("status_text"):
            st.caption(answer_payload["status_text"])
        if db_status and record_id:
            st.info("เลือกได้เลยว่าคำตอบนี้ถูกใจหรือไม่ถูกใจ ระบบจะบันทึก feedback ลงฐานข้อมูล")
        elif db_status:
            st.warning("ตอบคำถามได้ แต่บันทึกลงฐานข้อมูลไม่สำเร็จในรอบนี้")
        else:
            st.warning("ตอบคำถามได้ แต่ยังไม่สามารถบันทึกลงฐานข้อมูลได้")

    st.rerun()


if __name__ == "__main__":
    main()
