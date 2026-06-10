from __future__ import annotations

import re
from typing import Any


CONTACT_MESSAGE = (
    "หากเป็นข้อมูลเฉพาะเคส แนะนำตรวจสอบเพิ่มเติมกับสำนักงานประกันสังคม "
    "หรือโทรสายด่วน 1506 เพื่อยืนยันสิทธิอีกครั้ง"
)


KNOWLEDGE_BASE: list[dict[str, Any]] = [
    {
        "topic": "ประกันสังคมคืออะไร",
        "keywords": ["ประกันสังคม", "ประกันสังคมคือ", "socialsecurity"],
        "answer": (
            "ประกันสังคมคือระบบหลักประกันที่ช่วยดูแลผู้ประกันตนเมื่อเกิดกรณีต่าง ๆ เช่น เจ็บป่วย คลอดบุตร ทุพพลภาพ "
            "เสียชีวิต สงเคราะห์บุตร ชราภาพ และว่างงาน โดยสิทธิที่ได้รับจะต่างกันตามประเภทผู้ประกันตน เช่น มาตรา 33, 39 และ 40 "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "มาตรา 33",
        "keywords": ["มาตรา33", "ม33", "ลูกจ้าง", "นายจ้าง", "หักเงินเดือน"],
        "answer": (
            "ผู้ประกันตนมาตรา 33 คือผู้ที่เป็นลูกจ้างในสถานประกอบการและมีนายจ้างนำส่งเงินสมทบให้ทุกเดือน "
            "สิทธิหลักที่มักได้รับได้แก่ เจ็บป่วย คลอดบุตร ทุพพลภาพ เสียชีวิต สงเคราะห์บุตร ชราภาพ และว่างงาน "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "มาตรา 39",
        "keywords": ["มาตรา39", "ม39", "ลาออก", "ออกจากงาน", "ต่อประกันสังคม"],
        "answer": (
            "มาตรา 39 เหมาะกับผู้ที่เคยเป็นผู้ประกันตนมาตรา 33 และลาออกจากงานแล้ว แต่ต้องการส่งเงินสมทบต่อเอง "
            "โดยทั่วไปต้องเคยส่งเงินสมทบตามเงื่อนไขที่กฎหมายกำหนด และสมัครต่อภายในระยะเวลาที่กำหนดหลังออกจากงาน "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "มาตรา 40",
        "keywords": ["มาตรา40", "ม40", "อาชีพอิสระ", "ฟรีแลนซ์", "ค้าขาย", "ไม่มีนายจ้าง"],
        "answer": (
            "มาตรา 40 สำหรับผู้ประกอบอาชีพอิสระหรือผู้ที่ไม่มีนายจ้าง เช่น ฟรีแลนซ์ ค้าขาย หรือรับจ้างทั่วไป "
            "สิทธิประโยชน์จะขึ้นกับทางเลือกการส่งเงินสมทบที่สมัครไว้ จึงควรตรวจสอบแผนที่เลือกก่อนทุกครั้ง "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "ค่ารักษาพยาบาล",
        "keywords": ["รักษา", "เจ็บป่วย", "โรงพยาบาล", "ค่ารักษา", "ป่วย", "สิทธิรักษา"],
        "answer": (
            "สิทธิรักษาพยาบาลของประกันสังคมโดยมากจะผูกกับโรงพยาบาลตามสิทธิของผู้ประกันตน "
            "กรณีเจ็บป่วยทั่วไปควรเข้ารับบริการที่โรงพยาบาลตามสิทธิก่อน ยกเว้นกรณีฉุกเฉินสามารถเข้ารับการรักษาได้ตามความจำเป็น "
            "แล้วค่อยตรวจสอบขั้นตอนการใช้สิทธิย้อนหลังตามเงื่อนไขของสำนักงานประกันสังคม "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "คลอดบุตร",
        "keywords": ["คลอด", "คลอดบุตร", "ตั้งครรภ์", "ฝากครรภ์", "ค่าคลอด"],
        "answer": (
            "กรณีคลอดบุตร ผู้ประกันตนสามารถมีสิทธิได้รับค่าคลอดบุตรและเงินสงเคราะห์การหยุดงานเพื่อการคลอดบุตร "
            "ตามเงื่อนไขจำนวนเดือนที่ส่งเงินสมทบและหลักเกณฑ์ที่ใช้ในช่วงเวลานั้น "
            "ควรเตรียมเอกสาร เช่น ใบรับรองแพทย์ ใบเสร็จ และเอกสารยืนยันการคลอดให้พร้อมก่อนยื่นเรื่อง "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "สงเคราะห์บุตร",
        "keywords": ["สงเคราะห์บุตร", "ค่าเทอม", "ค่าเล่าเรียน", "ค่าเรียนลูก", "สิทธิลูก", "สิทธิบุตร"],
        "answer": (
            "ถ้าถามในกรอบประกันสังคม โดยหลักจะเป็นสิทธิกรณีสงเคราะห์บุตร ไม่ใช่สิทธิค่าเทอมโดยตรง "
            "ดังนั้นคำถามเรื่องค่าเทอมมักต้องเช็กก่อนว่าเข้าข่ายสิทธิสงเคราะห์บุตรหรือไม่ และเงื่อนไขอายุบุตรยังอยู่ในเกณฑ์หรือเปล่า "
            "ถ้าบุตรอายุ 7 ปี มีโอกาสที่อาจเกินช่วงอายุของสิทธิแล้ว จึงควรตรวจสอบเงื่อนไขล่าสุดกับสำนักงานประกันสังคมหรือสายด่วน 1506 ก่อนยื่นเรื่อง "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "ว่างงาน",
        "keywords": ["ว่างงาน", "ตกงาน", "ลาออก", "เลิกจ้าง", "ชดเชยว่างงาน"],
        "answer": (
            "กรณีว่างงาน สิทธิประโยชน์จะต่างกันระหว่างการลาออกเองกับการถูกเลิกจ้าง "
            "โดยทั่วไปต้องขึ้นทะเบียนผู้ว่างงานและยื่นเรื่องตามระยะเวลาที่กำหนด รวมถึงต้องมีประวัติส่งเงินสมทบตามเงื่อนไข "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "ชราภาพ",
        "keywords": ["ชราภาพ", "บำนาญ", "บำเหน็จ", "เกษียณ", "อายุ55"],
        "answer": (
            "สิทธิชราภาพมีได้ทั้งแบบบำเหน็จหรือบำนาญ ขึ้นกับอายุและจำนวนเดือนที่ส่งเงินสมทบสะสมไว้ "
            "หากต้องการทราบว่าตนเองเข้าเกณฑ์แบบใด ควรตรวจสอบประวัติการส่งเงินสมทบย้อนหลังประกอบ "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "ตรวจสอบสิทธิ",
        "keywords": ["ตรวจสอบสิทธิ", "เช็กสิทธิ", "เช็คสิทธิ", "สิทธิประกันสังคม", "เงินสมทบ"],
        "answer": (
            "การตรวจสอบสิทธิประกันสังคมสามารถทำได้ผ่านช่องทางออนไลน์ของสำนักงานประกันสังคมหรือที่สำนักงานประกันสังคมใกล้บ้าน "
            "โดยมักใช้เลขบัตรประชาชนและข้อมูลยืนยันตัวตนในการเข้าสู่ระบบ "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "เปลี่ยนโรงพยาบาล",
        "keywords": ["เปลี่ยนโรงพยาบาล", "ย้ายโรงพยาบาล", "เปลี่ยนสิทธิ", "โรงพยาบาลตามสิทธิ"],
        "answer": (
            "การเปลี่ยนโรงพยาบาลตามสิทธิประกันสังคมมักทำได้ในช่วงเวลาที่สำนักงานประกันสังคมเปิดให้เปลี่ยนสิทธิ "
            "หรือในกรณีที่เข้าเงื่อนไขพิเศษ เช่น ย้ายที่อยู่หรือย้ายสถานที่ทำงาน "
            f"{CONTACT_MESSAGE}"
        ),
    },
    {
        "topic": "เงินสมทบ",
        "keywords": ["เงินสมทบ", "ส่งเงิน", "หักกี่เปอร์เซ็นต์", "หักประกันสังคม", "สมทบ"],
        "answer": (
            "เงินสมทบประกันสังคมขึ้นกับประเภทผู้ประกันตนและฐานค่าจ้างหรือทางเลือกที่สมัครไว้ "
            "สำหรับมาตรา 33 จะมีทั้งส่วนของลูกจ้าง นายจ้าง และรัฐร่วมกันสมทบ ส่วนมาตรา 39 และ 40 ผู้ประกันตนจะเป็นผู้ส่งเองตามเกณฑ์ที่กำหนด "
            f"{CONTACT_MESSAGE}"
        ),
    },
]


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", "", text)
    return text


EARLY_RETIREMENT_ANSWER = (
    "ถ้าหมายถึงสิทธิชราภาพของประกันสังคม อายุ 45 ปียังไม่สามารถรับเงินชราภาพได้ครับ "
    "โดยทั่วไปต้องมีอายุครบ 55 ปีบริบูรณ์ และความเป็นผู้ประกันตนสิ้นสุดลงก่อน จึงจะยื่นขอรับเงินชราภาพได้ "
    "จำนวนเงินที่จะได้รับขึ้นกับมาตรา ประวัติการส่งเงินสมทบ จำนวนเดือนที่ส่ง และฐานค่าจ้างที่ใช้คำนวณ "
    "ดังนั้นตอนอายุ 45 จะยังบอกยอดรับจริงไม่ได้ ควรตรวจประวัติเงินสมทบในระบบประกันสังคมหรือสอบถามสายด่วน 1506 เพื่อประเมินสิทธิครับ"
)


def find_early_retirement_answer(question: str) -> dict[str, Any] | None:
    normalized_question = normalize_text(question)
    retirement_keywords = ["เกษียณ", "ชราภาพ", "บำนาญ", "บำเหน็จ"]
    has_retirement_signal = any(normalize_text(keyword) in normalized_question for keyword in retirement_keywords)
    has_early_age_signal = any(age in normalized_question for age in ["45", "อายุ45", "45ปี"])

    if not (has_retirement_signal and has_early_age_signal):
        return None

    return {
        "topic": "เกษียณก่อนอายุ 55",
        "answer": EARLY_RETIREMENT_ANSWER,
        "score": 99,
        "matched": True,
    }


def score_question_topics(question: str) -> list[dict[str, Any]]:
    normalized_question = normalize_text(question)
    topic_scores: list[dict[str, Any]] = []

    for item in KNOWLEDGE_BASE:
        score = 0
        matched_keywords: list[str] = []
        for keyword in item["keywords"]:
            normalized_keyword = normalize_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_question:
                score += max(1, len(normalized_keyword) // 3)
                matched_keywords.append(normalized_keyword)

        topic_scores.append(
            {
                "topic": item["topic"],
                "answer": item["answer"],
                "score": score,
                "matched_keywords": matched_keywords,
            }
        )

    topic_scores.sort(key=lambda item: item["score"], reverse=True)
    return topic_scores


def is_high_confidence_match(
    normalized_question: str,
    matched_keywords: list[str],
    score: int,
) -> bool:
    if not matched_keywords:
        return False

    longest_keyword = max((len(keyword) for keyword in matched_keywords), default=0)
    has_exact_keyword = any(normalized_question == keyword for keyword in matched_keywords)
    has_strong_phrase = any(
        len(keyword) >= 6 and normalized_question.startswith(keyword) for keyword in matched_keywords
    )
    has_multiple_signals = len(matched_keywords) >= 2 and score >= 4

    if has_exact_keyword:
        return True
    if has_strong_phrase and len(normalized_question) <= longest_keyword + 12:
        return True
    if has_multiple_signals:
        return True

    return False


def infer_topic_for_question(question: str) -> str | None:
    early_retirement_answer = find_early_retirement_answer(question)
    if early_retirement_answer:
        return early_retirement_answer["topic"]

    normalized_question = normalize_text(question)
    topic_scores = score_question_topics(question)
    if not topic_scores:
        return None

    best_match = topic_scores[0]
    best_score = best_match["score"]
    matched_keywords = best_match["matched_keywords"]
    second_best_score = topic_scores[1]["score"] if len(topic_scores) > 1 else 0

    if not matched_keywords or best_score <= 0:
        return None

    if is_high_confidence_match(normalized_question, matched_keywords, best_score):
        return best_match["topic"]

    has_multiple_signals = len(matched_keywords) >= 2
    has_long_keyword = any(len(keyword) >= 6 for keyword in matched_keywords)
    has_clear_lead = best_score >= 2 and (best_score - second_best_score) >= 2

    if has_multiple_signals or has_long_keyword or has_clear_lead:
        return best_match["topic"]

    return None


def find_best_answer(question: str) -> dict[str, Any]:
    early_retirement_answer = find_early_retirement_answer(question)
    if early_retirement_answer:
        return early_retirement_answer

    normalized_question = normalize_text(question)
    topic_scores = score_question_topics(question)
    best_match = topic_scores[0] if topic_scores else None
    best_score = best_match["score"] if best_match else 0
    best_matched_keywords = best_match["matched_keywords"] if best_match else []
    second_best_score = topic_scores[1]["score"] if len(topic_scores) > 1 else 0

    has_long_keyword = any(len(keyword) >= 6 for keyword in best_matched_keywords)
    has_clear_lead = best_score >= 2 and (best_score - second_best_score) >= 2

    if best_match and (
        is_high_confidence_match(normalized_question, best_matched_keywords, best_score)
        or (has_long_keyword and has_clear_lead)
    ):
        return {
            "topic": best_match["topic"],
            "answer": best_match["answer"],
            "score": best_score,
            "matched": True,
        }

    return {
        "topic": "fallback",
        "answer": (
            "ตอนนี้ผมยังไม่มีคำตอบที่ตรงพอสำหรับคำถามนี้ในชุดความรู้ประกันสังคมที่เตรียมไว้ "
            "ลองพิมพ์รายละเอียดเพิ่ม เช่น ระบุว่าเป็นมาตรา 33, 39, 40 หรือเป็นเรื่องรักษาพยาบาล คลอดบุตร ว่างงาน หรือชราภาพ "
            f"{CONTACT_MESSAGE}"
        ),
        "score": 0,
        "matched": False,
    }
