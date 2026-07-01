from github_storage import get_payment_text_sync
from utils import DELIVERY_LABELS, STATUS_LABELS, code, escape_html, format_price


def build_client_payment_text(order: dict) -> str:
    return (
        f"Заказ #{order['orderNumber']} создан.\n\n"
        f"Сумма к оплате: {code(format_price(order['totalPrice']))}\n\n"
        f"Реквизиты:\n{code(get_payment_text_sync())}\n\n"
        "После оплаты нажмите кнопку ОТПРАВИТЬ ЧЕК и отправьте фото перевода."
    )


def build_admin_order_text(order: dict) -> str:
    lines = [
        f"🧾 Новый заказ #{order['orderNumber']}",
        "",
        f"Клиент: @{escape_html(order.get('username') or 'без username')}",
        f"Telegram ID: {code(order['telegramId'])}",
        "",
        "🛍 Товары:",
    ]

    for index, item in enumerate(order.get("items") or [], start=1):
        lines.extend(
            [
                f"{index}. {code(item.get('brand', ''))}",
                f"   {code(item.get('name', ''))}",
                f"   Размер: {code(item.get('size', ''))}",
                f"   Цена: {code(format_price(item.get('price', 0)))}",
                "",
            ]
        )

    delivery = order.get("deliveryData", {}) or {}
    lines.extend(
        [
            f"Итого: {code(format_price(order.get('totalPrice', 0)))}",
            "",
            f"Доставка: {code(DELIVERY_LABELS.get(order.get('deliveryMethod'), order.get('deliveryMethod')))}",
            "",
            f"ФИО: {code(delivery.get('fullName', ''))}",
            f"Телефон: {code(delivery.get('phone', ''))}",
            f"Город: {code(delivery.get('city', ''))}",
            f"ПВЗ / адрес: {code(delivery.get('address', ''))}",
            "",
            "Комментарий:",
            code(order.get("comment") or "—"),
            "",
            f"Статус: {code(STATUS_LABELS.get(order.get('status'), order.get('status')))}",
        ]
    )
    return "\n".join(lines)
