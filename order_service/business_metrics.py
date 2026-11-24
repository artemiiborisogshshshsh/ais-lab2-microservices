from prometheus_client import CollectorRegistry, Counter


ORDER_REGISTRY = CollectorRegistry()


ORDERS_CREATED = Counter(
    "orders_created_total",
    "Количество созданных заказов",
    registry=ORDER_REGISTRY,
)


ORDERS_PAID = Counter(
    "orders_paid_total",
    "Количество успешно оплаченных заказов",
    registry=ORDER_REGISTRY,
)


ORDERS_CANCELLED = Counter(
    "orders_cancelled_total",
    "Количество отмененных заказов",
    registry=ORDER_REGISTRY,
)