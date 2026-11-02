# Учёт заказов кофейни — FastAPI

Домашнее задание к уроку №5 «Первое приложение на FastAPI».

Сервис для бариста: создать заказ, посмотреть список, отметить готовым, отменить.
Данные хранятся в памяти процесса.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
fastapi dev main.py
```

Документация: http://127.0.0.1:8000/docs

## Эндпоинты

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/` | Приветствие |
| GET | `/info` | Название сервиса и число заказов |
| POST | `/orders` | Создать заказ (201) |
| GET | `/orders` | Список: фильтр `status`, `limit`, `offset`, `sort_by`, `descending` |
| GET | `/orders/{order_id}` | Заказ по id (404, если нет) |
| PATCH | `/orders/{order_id}` | Частичное обновление (404, если нет) |
| DELETE | `/orders/{order_id}` | Отмена заказа (204 без тела, 404, если нет) |

Сделаны оба бонуса: сортировка `sort_by` и ограничения `limit` (не больше `MAX_PAGE_SIZE`) через `Query()`.
