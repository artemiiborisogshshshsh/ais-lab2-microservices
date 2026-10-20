
import argparse
import json
import os
import time

import grpc
import pybreaker

from proto import payment_pb2, payment_pb2_grpc


# Настройки отказоустойчивости
GRPC_TIMEOUT = 3
RESET_TIMEOUT = 10
FAIL_MAX = 3


class PaymentBreakerListener(pybreaker.CircuitBreakerListener):
    """Логирование переходов Circuit Breaker."""

    def state_change(self, cb, old_state, new_state):
        print(
            f"Circuit Breaker: "
            f"{old_state.name.upper()} -> {new_state.name.upper()}",
            flush=True
        )


# Один Circuit Breaker на весь процесс клиента
payment_breaker = pybreaker.CircuitBreaker(
    name="payment_service",
    fail_max=FAIL_MAX,
    reset_timeout=RESET_TIMEOUT,
    listeners=[PaymentBreakerListener()]
)


def grpc_check_payment(order_id, amount, simulate_failure=False):
    """Реальный gRPC-вызов Payment Service."""

    target = os.getenv(
        "PAYMENT_GRPC_TARGET",
        "127.0.0.1:50051"
    )

    print(f"gRPC: отправляем запрос для заказа {order_id}")

    with grpc.insecure_channel(target) as channel:
        stub = payment_pb2_grpc.PaymentServiceStub(channel)

        request = payment_pb2.PaymentRequest(
            order_id=order_id,
            amount=amount,
            simulate_failure=simulate_failure
        )

        response = stub.CheckPaymentStatus(
            request,
            timeout=GRPC_TIMEOUT
        )

        return {
            "transaction_id": response.transaction_id,
            "status": response.status,
            "message": response.message
        }


def fallback(order_id):
    """Резервный ответ при недоступности Payment Service."""

    print(f"Fallback для заказа {order_id}")

    return {
        "transaction_id": "",
        "status": "PROCESSING",
        "message": "Платёжная система временно недоступна, попробуйте позже"
    }


def check_payment(order_id, amount, simulate_failure=False):
    """gRPC-вызов, защищённый Circuit Breaker."""

    try:
        return payment_breaker.call(
            grpc_check_payment,
            order_id,
            amount,
            simulate_failure
        )

    except pybreaker.CircuitBreakerError:
        print("Circuit Breaker OPEN: используется Fallback")
        return fallback(order_id)

    except grpc.RpcError as error:
        print(
            f"Ошибка gRPC: {error.code().name}: "
            f"{error.details()}"
        )
        return fallback(order_id)


def show_result(result):
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )


def run_demo(order_id, amount):
    """Демонстрация полного цикла Circuit Breaker."""

    print(f"Начальное состояние: {payment_breaker.current_state.upper()}")

    # Успешный запрос
    print("\n1. Успешный запрос")
    show_result(check_payment(order_id, amount))

    # Три последовательные ошибки
    for number in range(1, FAIL_MAX + 1):
        print(f"\n2. Имитация ошибки №{number}")

        result = check_payment(
            order_id,
            amount,
            simulate_failure=True
        )

        show_result(result)

        print(
            f"Состояние: {payment_breaker.current_state.upper()}"
        )

    # Запрос во время OPEN
    print("\n3. Проверка блокировки запросов")
    show_result(check_payment(order_id, amount))

    # Ждём разрешения пробного запроса
    print(f"\n4. Ожидание {RESET_TIMEOUT + 1} секунд...")
    time.sleep(RESET_TIMEOUT + 1)

    # Успешный запрос восстанавливает соединение
    print("\n5. Проверка восстановления")
    show_result(check_payment(order_id, amount))

    print(
        f"\nИтоговое состояние: "
        f"{payment_breaker.current_state.upper()}"
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--order-id", required=True)
    parser.add_argument("--amount", type=float, required=True)

    parser.add_argument(
        "--simulate-failure",
        action="store_true"
    )

    parser.add_argument(
        "--demo-breaker",
        action="store_true"
    )

    args = parser.parse_args()

    if args.demo_breaker:
        run_demo(args.order_id, args.amount)
    else:
        result = check_payment(
            args.order_id,
            args.amount,
            args.simulate_failure
        )
        show_result(result)


if __name__ == "__main__":
    main()
