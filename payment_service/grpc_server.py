
import os
from concurrent import futures
from uuid import uuid4
from observability.operation_metrics import OperationMetrics
import grpc

from proto import payment_pb2, payment_pb2_grpc

metrics = OperationMetrics(
    counter_name="grpc_requests_total",
    duration_name="grpc_request_duration_seconds",
)
class PaymentGrpcService(
    payment_pb2_grpc.PaymentServiceServicer
):
    @metrics.instrument("CheckPaymentStatus")
    def CheckPaymentStatus(self, request, context):
        order_id = request.order_id
        amount = request.amount

        print(
            f"gRPC: получен запрос для заказа {order_id}, "
            f"сумма: {amount}",
            flush=True
        )

        if not order_id:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Не указан идентификатор заказа"
            )

        # Имитация недоступности Payment Service
        if request.simulate_failure:
            print(
                f"gRPC: имитация ошибки для заказа {order_id}",
                flush=True
            )

            context.abort(
                grpc.StatusCode.UNAVAILABLE,
                "Payment Service временно недоступен"
            )

        transaction_id = str(uuid4())

        print(
            f"gRPC: платёж заказа {order_id} подтверждён",
            flush=True
        )

        return payment_pb2.PaymentResponse(
            transaction_id=transaction_id,
            status="SUCCESS",
            message="Платёж успешно подтверждён"
        )


def serve():
    metrics.start(port=9100)
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10)
    )

    payment_pb2_grpc.add_PaymentServiceServicer_to_server(
        PaymentGrpcService(),
        server
    )

    port = int(os.getenv("GRPC_PORT", "50051"))
    bound_port = server.add_insecure_port(f"[::]:{port}")

    if bound_port == 0:
        raise RuntimeError("Не удалось открыть gRPC-порт")

    server.start()

    print(
        f"Payment gRPC Server запущен на порту {port}",
        flush=True
    )

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=5)


if __name__ == "__main__":
    serve()
