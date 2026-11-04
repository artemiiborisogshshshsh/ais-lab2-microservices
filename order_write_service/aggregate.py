
from copy import deepcopy


def apply_event(state, event):
    """Применить одно событие к состоянию заказа."""

    event_type = event["eventType"]
    order_id = event["orderId"]
    version = event["version"]
    payload = event["payload"]

    # Первое событие обязательно создаёт заказ
    if state is None:
        if event_type != "OrderCreated":
            raise ValueError(
                "Первым событием должно быть OrderCreated"
            )

        if version != 1:
            raise ValueError(
                "Первое событие должно иметь версию 1"
            )

        return {
            "orderId": order_id,
            "status": "CREATED",
            "totalAmount": payload["totalAmount"],
            "items": deepcopy(payload.get("items", [])),
            "version": version,
        }

    # Проверяем принадлежность события заказу
    if order_id != state["orderId"]:
        raise ValueError(
            "События принадлежат разным заказам"
        )

    # Проверяем правильный порядок версий
    if version != state["version"] + 1:
        raise ValueError(
            "Нарушена последовательность версий"
        )

    new_state = deepcopy(state)

    if event_type == "OrderPaid":

        if state["status"] != "CREATED":
            raise ValueError(
                "Можно оплатить только созданный заказ"
            )

        new_state["status"] = "PAID"

    elif event_type == "OrderCancelled":

        if state["status"] == "CANCELLED":
            raise ValueError(
                "Заказ уже отменён"
            )

        new_state["status"] = "CANCELLED"

    else:
        raise ValueError(
            f"Неизвестное событие: {event_type}"
        )

    new_state["version"] = version

    return new_state


def rehydrate_order(events):
    """Восстановить состояние заказа из истории событий."""

    state = None

    for event in events:
        state = apply_event(state, event)

    return state
