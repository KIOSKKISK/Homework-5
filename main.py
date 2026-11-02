"""Сервис учёта заказов кофейни (домашнее задание к уроку №5)."""

from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Настройки приложения
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    app_name: str = "Учёт заказов кофейни"
    default_page_size: int = 10
    max_page_size: int = 50

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]


# ---------------------------------------------------------------------------
# Перечисления
# ---------------------------------------------------------------------------

class DrinkSize(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


class OrderStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    completed = "completed"


class SortField(str, Enum):
    id = "id"
    created_at = "created_at"
    drink = "drink"


# ---------------------------------------------------------------------------
# Модели данных
# ---------------------------------------------------------------------------

class OrderCreate(BaseModel):
    """Данные, которые присылает бариста при создании заказа."""

    drink: str = Field(
        min_length=1,
        max_length=100,
        description="Название напитка из меню",
        examples=["Латте"],
    )
    size: DrinkSize = Field(
        description="Размер напитка",
        examples=[DrinkSize.medium],
    )
    quantity: int = Field(
        gt=0,
        description="Количество порций",
        examples=[2],
    )
    customer_name: str | None = Field(
        default=None,
        max_length=50,
        description="Имя клиента (необязательно)",
        examples=["Ирина"],
    )


class OrderUpdate(BaseModel):
    """Частичное обновление: None означает «поле не прислали, не трогаем»."""

    drink: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Новое название напитка",
        examples=["Капучино"],
    )
    size: DrinkSize | None = Field(
        default=None,
        description="Новый размер напитка",
        examples=[DrinkSize.large],
    )
    quantity: int | None = Field(
        default=None,
        gt=0,
        description="Новое количество порций",
        examples=[3],
    )
    customer_name: str | None = Field(
        default=None,
        max_length=50,
        description="Новое имя клиента",
        examples=["Олег"],
    )
    status: OrderStatus | None = Field(
        default=None,
        description="Новый статус заказа",
        examples=[OrderStatus.ready],
    )


class Order(BaseModel):
    """Заказ, который отдаётся клиенту в ответе."""

    id: int = Field(description="Идентификатор заказа", examples=[1])
    drink: str = Field(description="Название напитка из меню", examples=["Латте"])
    size: DrinkSize = Field(description="Размер напитка", examples=[DrinkSize.medium])
    quantity: int = Field(description="Количество порций", examples=[2])
    customer_name: str | None = Field(
        default=None, description="Имя клиента", examples=["Ирина"]
    )
    status: OrderStatus = Field(
        description="Статус заказа", examples=[OrderStatus.pending]
    )
    created_at: datetime = Field(
        description="Момент создания заказа", examples=["2026-07-10T09:15:00"]
    )


# ---------------------------------------------------------------------------
# Приложение и хранилище в памяти
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Учёт заказов кофейни",
    description=(
        "Сервис для бариста одной точки: создание заказов, просмотр списка, "
        "смена статуса (pending → ready → completed) и отмена. "
        "Данные хранятся в памяти процесса и пропадают при перезапуске."
    ),
    version="1.0.0",
)

# Словарь id -> заказ. Счётчик не уменьшается при удалении,
# поэтому id никогда не повторяются (в отличие от len(orders) + 1).
orders: dict[int, dict] = {}
next_order_id = 1


def find_order_or_404(order_id: int) -> dict:
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заказ с id={order_id} не найден",
        )
    return order


# ---------------------------------------------------------------------------
# Сервисные эндпоинты
# ---------------------------------------------------------------------------

@app.get("/", tags=["Сервис"], summary="Приветствие")
def read_root(settings: SettingsDep):
    return {"message": f"Сервис «{settings.app_name}» на связи"}


@app.get("/info", tags=["Сервис"], summary="Информация о сервисе")
def get_info(settings: SettingsDep):
    return {"app_name": settings.app_name, "orders_count": len(orders)}


# ---------------------------------------------------------------------------
# Заказы
# ---------------------------------------------------------------------------

@app.post(
    "/orders",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    tags=["Заказы"],
    summary="Создать заказ",
)
def create_order(order: OrderCreate):
    global next_order_id
    new_order = order.model_dump()
    new_order["id"] = next_order_id
    new_order["status"] = OrderStatus.pending
    new_order["created_at"] = datetime.now()
    orders[next_order_id] = new_order
    next_order_id += 1
    return new_order


@app.get(
    "/orders",
    response_model=list[Order],
    tags=["Заказы"],
    summary="Список заказов",
)
def list_orders(
    settings: SettingsDep,
    status_filter: Annotated[
        OrderStatus | None,
        Query(alias="status", description="Показать только заказы с этим статусом"),
    ] = None,
    limit: Annotated[
        int | None,
        Query(ge=1, description="Сколько заказов вернуть (по умолчанию из настроек)"),
    ] = None,
    offset: Annotated[
        int, Query(ge=0, description="Сколько заказов пропустить с начала")
    ] = 0,
    sort_by: Annotated[
        SortField, Query(description="Поле для сортировки")
    ] = SortField.id,
    descending: Annotated[
        bool, Query(description="Сортировать по убыванию")
    ] = False,
):
    if limit is None:
        limit = settings.default_page_size
    if limit > settings.max_page_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"limit не может быть больше {settings.max_page_size}",
        )

    result = list(orders.values())
    if status_filter is not None:
        result = [o for o in result if o["status"] == status_filter]

    result.sort(key=lambda o: o[sort_by.value], reverse=descending)
    return result[offset : offset + limit]


@app.get(
    "/orders/{order_id}",
    response_model=Order,
    tags=["Заказы"],
    summary="Заказ по идентификатору",
)
def get_order(order_id: Annotated[int, Path(ge=1, description="Идентификатор заказа")]):
    return find_order_or_404(order_id)


@app.patch(
    "/orders/{order_id}",
    response_model=Order,
    tags=["Заказы"],
    summary="Частично обновить заказ",
)
def update_order(
    order_id: Annotated[int, Path(ge=1, description="Идентификатор заказа")],
    update: OrderUpdate,
):
    order = find_order_or_404(order_id)
    # exclude_unset=True — берём только те поля, которые клиент реально прислал;
    # exclude_none=True — явный null не затрёт обязательное поле (обнуление не рассматриваем)
    order.update(update.model_dump(exclude_unset=True, exclude_none=True))
    return order


@app.delete(
    "/orders/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Заказы"],
    summary="Отменить заказ",
)
def delete_order(order_id: Annotated[int, Path(ge=1, description="Идентификатор заказа")]):
    find_order_or_404(order_id)
    del orders[order_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)
