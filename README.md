# Leads_to_b24_Hirehub

Автоматизация загрузки лидов из Google Sheets в Bitrix24 через локальную SQLite-базу.

Основной рабочий контур состоит из двух скриптов:

- `1_save_gsheet_to_sqlite.py` читает Google Sheets и сохраняет свежие лиды в `lr195.db`.
- `2_upload_sqlite_to_bitrix.py` берет из `lr195.db` лиды с пустым `Статус_Б24`, создает лиды в Bitrix24 и записывает ссылку на созданный лид обратно в Google Sheets и SQLite.

## Как работает процесс

1. `1_save_gsheet_to_sqlite.py` подключается к Google Sheets через service account.
2. Скрипт читает вкладку из `GOOGLE_SHEET_NAME`. Если переменная не задана, берется первая вкладка таблицы.
3. Из Google Sheets используются колонки:
   - `ID`
   - `Дата`
   - `Номера`
   - `Канал`
   - `Источник`
   - `Статус_Б24`
4. В SQLite сохраняются только записи за последние `3` дня. Период задается константой `DAYS_LOOKBACK` в `1_save_gsheet_to_sqlite.py`.
5. Поле `Статус_Б24` из таблицы сохраняется в SQLite в колонку `bitrix24_info`.
6. `2_upload_sqlite_to_bitrix.py` выбирает только записи, где `bitrix24_info` пустой.
7. Для каждой такой записи создается лид в Bitrix24:
   - `TITLE`: `Перехват лидов DDMMYYYY`
   - `PHONE`: из колонки `Номера`
   - `COMMENTS`: из колонки `Источник`, если она заполнена
   - `SOURCE_ID`, `STATUS_ID`, `ASSIGNED_BY_ID`, `UF_CRM_ROISTAT`: из `.env` или из значений по умолчанию
8. После успешного создания лида ссылка вида `https://.../crm/lead/details/<id>/` записывается:
   - в Google Sheets в колонку `Статус_Б24`
   - в SQLite в поле `bitrix24_info`

## Структура данных

Основная таблица SQLite:

- база: `lr195.db`
- таблица: `leads`

Поля таблицы:

- `source_id` - уникальный ID строки/лида из Google Sheets, primary key
- `event_dt` - дата лида
- `phone` - телефон
- `channel` - канал
- `source_lead` - источник лида, используется как `COMMENTS` в Bitrix24
- `bitrix24_info` - статус из Google Sheets или ссылка на созданный лид Bitrix24
- `sheet_name` - имя вкладки Google Sheets
- `sheet_row` - номер строки в Google Sheets
- `inserted_at` - время вставки в БД по Москве

При повторной загрузке из Google Sheets запись обновляется по `source_id`. Если в Google Sheets поле `Статус_Б24` непустое, это значение сохраняется в `bitrix24_info`, и такой лид не будет повторно отправлен в Bitrix24.

## Переменные окружения

Проект использует `.env`.

Обязательные переменные:

```env
GOOGLE_CREDENTIALS_FILE=credentials/service-account.json
GOOGLE_SHEET_ID=your_google_sheet_id
BITRIX_WEBHOOK_URL=https://your-portal.bitrix24.ru/rest/1/your_webhook/
```

Опциональные переменные:

```env
GOOGLE_SHEET_NAME=Данные

BITRIX_MAX_RETRIES=3
BITRIX_RETRY_BASE_DELAY=1
BITRIX_SOURCE_ID=UC_M09HMS
BITRIX_STATUS_ID=NEW
BITRIX_ASSIGNED_BY_ID=61
BITRIX_ROISTAT=парсинг
```

`GOOGLE_SHEET_ID` должен быть только ID таблицы, без полного URL.

## Требования

- Python 3.11+
- доступ к Google Sheets API
- service account Google с доступом к нужной таблице
- права service account на редактирование таблицы, потому что второй скрипт пишет ссылку в колонку `Статус_Б24`
- рабочий webhook Bitrix24 с правами на CRM

Установка зависимостей:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Для Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Ручной запуск

Сохранение лидов из Google Sheets в SQLite:

```bash
cd /opt/Leads_to_b24_Hirehub
/opt/Leads_to_b24_Hirehub/venv/bin/python 1_save_gsheet_to_sqlite.py
```

Загрузка лидов из SQLite в Bitrix24:

```bash
cd /opt/Leads_to_b24_Hirehub
/opt/Leads_to_b24_Hirehub/venv/bin/python 2_upload_sqlite_to_bitrix.py
```

Локальный запуск на Windows:

```powershell
python 1_save_gsheet_to_sqlite.py
python 2_upload_sqlite_to_bitrix.py
```

## Cron на Ubuntu

После деплоя на сервер можно добавить расписание через `crontab -e`:

```cron
# ==== Leads_to_b24_Hirehub SCHEDULE ====
CRON_TZ=Europe/Moscow
33 8-17 * * * cd /opt/Leads_to_b24_Hirehub && /opt/Leads_to_b24_Hirehub/venv/bin/python 1_save_gsheet_to_sqlite.py >/dev/null 2>> /opt/Leads_to_b24_Hirehub/logs/cron_save_gsheet.log
35 8-17 * * * cd /opt/Leads_to_b24_Hirehub && /opt/Leads_to_b24_Hirehub/venv/bin/python 2_upload_sqlite_to_bitrix.py >/dev/null 2>> /opt/Leads_to_b24_Hirehub/logs/cron_upload_sqlite.log
```

Текущее расписание означает:

- в `08:33, 09:33, ..., 17:33 MSK` обновляется SQLite из Google Sheets
- в `08:35, 09:35, ..., 17:35 MSK` новые лиды из SQLite отправляются в Bitrix24

После проверки cron можно отключить отдельные cron-логи:

```cron
# ==== Leads_to_b24_Hirehub SCHEDULE ====
CRON_TZ=Europe/Moscow
33 8-17 * * * cd /opt/Leads_to_b24_Hirehub && /opt/Leads_to_b24_Hirehub/venv/bin/python 1_save_gsheet_to_sqlite.py >/dev/null 2>/dev/null
35 8-17 * * * cd /opt/Leads_to_b24_Hirehub && /opt/Leads_to_b24_Hirehub/venv/bin/python 2_upload_sqlite_to_bitrix.py >/dev/null 2>/dev/null
```

## Логи

Основные скрипты пишут логи в папку `logs`:

- `logs/1_save_gsheet_to_sqlite.log`
- `logs/2_upload_sqlite_to_bitrix.log`

Настройка логирования находится в `setup.py`.

Особенности:

- ротация по дням
- время в логах московское
- архивы логов хранятся `14` дней

Если используется проверочный cron-вариант, stderr cron пишется отдельно:

- `logs/cron_save_gsheet.log`
- `logs/cron_upload_sqlite.log`

## Вспомогательные скрипты

- `bitrix24_fields.py` - получение и просмотр полей лидов Bitrix24 через API.
- `util_get_lead_by_id.py` - утилита для получения лида по ID.
- `util_status_id.py` - утилита для просмотра статусов.
- `upload_leads.py` - старый ручной сценарий загрузки лидов из Excel через диалог выбора файла. Он не входит в основной контур Google Sheets -> SQLite -> Bitrix24.

## Важные замечания

- `1_save_gsheet_to_sqlite.py` использует окно выгрузки `DAYS_LOOKBACK = 3`.
- `2_upload_sqlite_to_bitrix.py` не отправляет повторно лиды, у которых уже заполнен `bitrix24_info`.
- Если Bitrix24 недоступен или вернул ошибку после всех ретраев, запись остается незагруженной и будет обработана на следующем запуске.
- Если лид создан в Bitrix24, но обновление Google Sheets не удалось, ссылка уже сохраняется в SQLite, поэтому повторной отправки в Bitrix24 не будет.
