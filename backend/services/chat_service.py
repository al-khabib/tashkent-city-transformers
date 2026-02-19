import json
from datetime import date
from typing import Any, Dict

from backend.state import RuntimeState
from backend.utils import safe_json_parse



def extract_prediction_params(query: str, state: RuntimeState) -> Dict[str, str]:
    parser_prompt = (
        "Extract district and target_date from the request.\n"
        "Known districts: " + ", ".join(state.known_districts) + ".\n"
        "target_date format: YYYY-MM-DD (or infer reasonable next-month date if absent).\n\n"
        f"Request: {query}\n"
        "Return JSON only: {\"district\":\"...\", \"target_date\":\"YYYY-MM-DD\"}"
    )
    raw = state.llm.invoke(parser_prompt)
    parsed = safe_json_parse(str(raw)) or {}
    district = str(parsed.get("district", "")).strip().lower()
    target_date = str(parsed.get("target_date", "")).strip()
    if not district:
        for item in state.known_districts:
            if item in query.lower():
                district = item
                break
    if not target_date:
        target_date = date.today().replace(day=1).isoformat()
    if not district:
        district = state.known_districts[0]
    return {"district": district, "target_date": target_date}



def translate_to_english(text: str, source_lang: str, state: RuntimeState) -> str:
    if source_lang == "en":
        return text
    prompt = (
        "Translate the following text to English.\n"
        "Return only the translated text, no comments.\n\n"
        f"Source language: {source_lang}\n"
        f"Text: {text}"
    )
    return str(state.llm.invoke(prompt)).strip()



def translate_from_english(text: str, target_lang: str, state: RuntimeState) -> str:
    if target_lang == "en":
        return text
    prompt = (
        f"Translate the following text from English to {target_lang}.\n"
        "Keep structure and bullet points.\n"
        "Return only translated text.\n\n"
        f"Text: {text}"
    )
    return str(state.llm.invoke(prompt)).strip()



def explain_prediction_for_mayor(query: str, prediction: Dict[str, Any], state: RuntimeState) -> str:
    brief_prompt = (
        "You are briefing the Mayor of Tashkent.\n"
        "Turn the prediction numbers into a concise operational warning in English.\n"
        "Use exactly 4 bullet points with clear labels:\n"
        "- Forecast\n"
        "- Capacity Gap\n"
        "- Risk Score (1-10)\n"
        "- TP Action Plan\n"
        "Tone: executive, direct, actionable.\n\n"
        f"Original question: {query}\n"
        f"Prediction data: {json.dumps(prediction, ensure_ascii=True)}"
    )
    return str(state.llm.invoke(brief_prompt)).strip()
