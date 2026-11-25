import json
import os
import unittest

from urllib.request import Request, urlopen


GRAFANA_URL = os.getenv(
    "GRAFANA_URL",
    "http://localhost:3000",
).rstrip("/")

GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN")


class TestGrafana(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not GRAFANA_TOKEN:
            raise RuntimeError(
                "GRAFANA_TOKEN environment variable is required"
            )

    def request(self, path):
        request = Request(
            f"{GRAFANA_URL}{path}",
            headers={
                "Authorization": f"Bearer {GRAFANA_TOKEN}",
                "Accept": "application/json",
            },
        )

        with urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 200)

            return json.loads(
                response.read().decode("utf-8")
            )

    def test_grafana_health(self):
        result = self.request("/api/health")

        self.assertEqual(result["database"], "ok")

    def test_prometheus_datasource(self):
        result = self.request(
            "/api/datasources/uid/prometheus"
        )

        self.assertEqual(result["type"], "prometheus")
        self.assertEqual(
            result["url"],
            "http://prometheus:9090",
        )
        self.assertTrue(result["isDefault"])

    def test_loki_datasource(self):
        result = self.request(
            "/api/datasources/uid/loki"
        )

        self.assertEqual(result["type"], "loki")
        self.assertEqual(
            result["url"],
            "http://loki:3100",
        )

    def test_jaeger_datasource(self):
        result = self.request(
            "/api/datasources/uid/jaeger"
        )

        self.assertEqual(result["type"], "jaeger")
        self.assertEqual(
            result["url"],
            "http://jaeger:16686",
        )

    def test_prometheus_connection(self):
        result = self.request(
            "/api/datasources/uid/prometheus/health"
        )

        self.assertEqual(result["status"], "OK")

    def test_loki_connection(self):
        result = self.request(
            "/api/datasources/uid/loki/health"
        )

        self.assertEqual(result["status"], "OK")

    def test_technical_dashboard(self):
        result = self.request(
            "/api/dashboards/uid/ais-technical"
        )

        self.assertEqual(
            result["dashboard"]["title"],
            "AIS - Technical Monitoring",
        )

        self.assertTrue(
            result["meta"]["provisioned"]
        )

    def test_business_dashboard(self):
        result = self.request(
            "/api/dashboards/uid/ais-business"
        )

        self.assertEqual(
            result["dashboard"]["title"],
            "AIS - Business Monitoring",
        )

        self.assertTrue(
            result["meta"]["provisioned"]
        )

    def test_technical_panels(self):
        result = self.request(
            "/api/dashboards/uid/ais-technical"
        )

        titles = {
            panel["title"]
            for panel in result["dashboard"]["panels"]
        }

        expected = {
            "Available Targets",
            "Unavailable Targets",
            "HTTP Request Rate",
            "HTTP Latency p95",
            "HTTP Errors (last 5 minutes)",
            "RabbitMQ Operations",
        }

        self.assertEqual(titles, expected)

    def test_business_panels(self):
        result = self.request(
            "/api/dashboards/uid/ais-business"
        )

        titles = {
            panel["title"]
            for panel in result["dashboard"]["panels"]
        }

        expected = {
            "Created Orders",
            "Paid Orders",
            "Cancelled Orders",
            "Payment Success Rate",
            "Payment Outcomes",
            "Order Dynamics",
        }

        self.assertEqual(titles, expected)

    def test_prometheus_query(self):
        result = self.request(
            "/api/datasources/proxy/uid/prometheus"
            "/api/v1/query?query=sum%28up%29"
        )

        self.assertEqual(result["status"], "success")

        values = result["data"]["result"]

        self.assertTrue(values)

        available = float(values[0]["value"][1])

        self.assertGreater(available, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)