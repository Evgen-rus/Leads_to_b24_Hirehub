"""
Вывод всех полей лида Bitrix24 по ID (JSON по умолчанию).

Использование:
    python get_lead_by_id.py 12345
    python get_lead_by_id.py 12345 --pretty
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from setup import get_logger


load_dotenv()

logger = get_logger(__file__)


def get_env_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Переменная окружения {name} не задана или пуста")
    return value


def build_api_method_url(webhook_url: str, method: str) -> str:
    return f"{webhook_url.rstrip('/')}/{method}"


def build_lead_url(webhook_url: str, lead_id: str | int) -> str:
    portal_url = webhook_url.split("/rest/", maxsplit=1)[0].rstrip("/")
    return f"{portal_url}/crm/lead/details/{lead_id}/"


def call_bitrix_api(
    webhook_url: str,
    method: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    method_url = build_api_method_url(webhook_url, method)
    response = requests.post(
        method_url,
        json=payload or {},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )

    try:
        result = response.json()
    except ValueError:
        result = {}

    if not response.ok:
        error_text = result.get("error_description") or result.get("error") or response.text
        raise RuntimeError(f"HTTP {response.status_code}: {error_text}")

    if result.get("error"):
        error_text = result.get("error_description") or result.get("error")
        raise RuntimeError(str(error_text))

    return result


def fetch_lead(webhook_url: str, lead_id: int) -> Dict[str, Any]:
    result = call_bitrix_api(
        webhook_url,
        "crm.lead.get",
        {"id": lead_id},
    )
    lead = result.get("result")
    if not lead:
        raise ValueError(f"Лид с ID {lead_id} не найден")
    return lead


def fetch_lead_field_titles(webhook_url: str) -> Dict[str, str]:
    """Человекочитаемые названия полей из crm.lead.fields."""
    result = call_bitrix_api(webhook_url, "crm.lead.fields")
    fields = result.get("result", {})
    return {
        field_id: str(field_info.get("title") or field_id)
        for field_id, field_info in fields.items()
    }


def format_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def print_lead_fields(
    lead: Dict[str, Any],
    field_titles: Dict[str, str],
    lead_url: str,
) -> None:
    print(f"\nЛид ID: {lead.get('ID', '?')}")
    print(f"Ссылка: {lead_url}\n")
    print("-" * 60)

    for field_id in sorted(lead.keys()):
        title = field_titles.get(field_id, field_id)
        value = format_value(lead[field_id])
        print(f"{field_id} ({title}):")
        if "\n" in value:
            print(value)
        else:
            print(f"  {value}")
        print("-" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Вывести все поля лида Bitrix24 по ID",
    )
    parser.add_argument(
        "lead_id",
        type=int,
        help="ID лида в Bitrix24 (число из URL или ответа API)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Вывести поля списком с русскими названиями вместо JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        webhook_url = get_env_required("BITRIX_WEBHOOK_URL")
    except ValueError as error:
        print(f"Ошибка: {error}")
        sys.exit(1)

    lead_id = args.lead_id
    logger.info("Запрос лида ID=%s", lead_id)

    try:
        lead = fetch_lead(webhook_url, lead_id)
        lead_url = build_lead_url(webhook_url, lead_id)
    except (requests.RequestException, RuntimeError, ValueError) as error:
        print(f"Не удалось получить лид {lead_id}: {error}")
        logger.error("Ошибка получения лида ID=%s: %s", lead_id, error)
        sys.exit(1)

    if not args.pretty:
        print(json.dumps(lead, ensure_ascii=False, indent=2))
        return

    try:
        field_titles = fetch_lead_field_titles(webhook_url)
    except (requests.RequestException, RuntimeError) as error:
        logger.warning("Не удалось загрузить названия полей: %s", error)
        field_titles = {}

    print_lead_fields(lead, field_titles, lead_url)


if __name__ == "__main__":
    main()
