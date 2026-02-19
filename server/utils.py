import json
import re
from datetime import date, datetime
from typing import Any, Dict, Optional



def safe_json_parse(raw_text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None



def detect_language_fast(text: str) -> str:
    if re.search(r"[А-Яа-яЁё]", text):
        return "ru"
    lowered = text.lower()
    uz_markers = ("qanday", "bo'yicha", "uchun", "tuman", "yil", "kerak", "salom")
    if any(marker in lowered for marker in uz_markers):
        return "uz"
    return "en"



def parse_target_date(target_date: str) -> date:
    if not target_date:
        raise ValueError("target_date is required")
    target_date = target_date.strip().lower()
    if target_date in {"next month", "1 month"}:
        today = date.today()
        month = today.month + 1
        year = today.year + (1 if month > 12 else 0)
        month = 1 if month > 12 else month
        return date(year, month, 1)
    if target_date in {"next year", "1 year"}:
        return date(date.today().year + 1, date.today().month, 1)
    if re.fullmatch(r"\d{4}-\d{2}", target_date):
        return datetime.strptime(f"{target_date}-01", "%Y-%m-%d").date()
    return datetime.strptime(target_date, "%Y-%m-%d").date()
