import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import AnalyzeResponse, DeviceResult, app


class FakeRedis:
    def __init__(self, entries):
        self.entries = entries
        self.added = []

    def xrevrange(self, stream_name, count=50):
        self.stream_name = stream_name
        self.count = count
        return self.entries

    def xadd(self, stream_name, fields, maxlen=None, approximate=True):
        self.added.append(
            {
                "stream_name": stream_name,
                "fields": fields,
                "maxlen": maxlen,
                "approximate": approximate,
            }
        )
        return "1749045600000-0"


class PredictEventRouteTest(unittest.TestCase):
    def tearDown(self):
        from app.main import _stop_predict_pipeline

        _stop_predict_pipeline()

    def test_predict_event_returns_recent_prediction_events_from_redis_stream(self):
        payload = {
            "anomaly_score": 0.82,
            "risk_level": "critical",
            "model": "chronos-per-sensor+threshold",
            "per_device": {
                "pump-1": {
                    "anomaly_score": 0.82,
                    "per_sensor": {"temperature_c": 0.82, "threshold": 0.2},
                }
            },
            "event_id": "event-1",
            "alert_id": "alert-1",
            "work_order_id": "wo-1",
            "timestamp": "2026-06-04T14:00:00+00:00",
        }
        redis_client = FakeRedis(
            [
                (
                    "1749045600000-0",
                    {
                        "payload": json.dumps(payload),
                        "device_id": "pump-1",
                        "anomaly_score": "0.82",
                    },
                )
            ]
        )

        with patch("app.main._get_predict_stream_client", return_value=redis_client):
            response = TestClient(app).get("/predict/event")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "items": [
                    {
                        "stream_id": "1749045600000-0",
                        **payload,
                    }
                ]
            },
        )

    def test_publish_prediction_event_writes_analyze_response_to_redis_stream(self):
        redis_client = FakeRedis([])
        response = AnalyzeResponse(
            anomaly_score=0.61,
            risk_level="high",
            model="chronos-per-sensor+threshold",
            per_device={
                "pump-1": DeviceResult(
                    anomaly_score=0.61,
                    per_sensor={"vibration_rms": 0.61},
                )
            },
            event_id="event-1",
            alert_id="alert-1",
            work_order_id="wo-1",
        )

        with patch("app.main._get_predict_stream_client", return_value=redis_client):
            with patch("app.main._predict_stream_name", "test:predict"):
                from app.main import _publish_prediction_event

                stream_id = _publish_prediction_event(response)

        self.assertEqual(stream_id, "1749045600000-0")
        self.assertEqual(redis_client.added[0]["stream_name"], "test:predict")
        self.assertEqual(redis_client.added[0]["maxlen"], 1000)
        payload = json.loads(redis_client.added[0]["fields"]["payload"])
        self.assertEqual(payload["anomaly_score"], 0.61)
        self.assertEqual(payload["risk_level"], "high")
        self.assertEqual(payload["per_device"]["pump-1"]["per_sensor"]["vibration_rms"], 0.61)
        self.assertIn("timestamp", payload)

    def test_run_predict_pipeline_fetches_ms2_readings_and_queues_one_task_per_device(self):
        class FakeTask:
            id = "task-1"

        sent_tasks = []

        def fake_send_task(name, args):
            sent_tasks.append({"name": name, "args": args})
            task = FakeTask()
            task.id = f"task-{len(sent_tasks)}"
            return task

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return [
                    {"device_id": "pump-1", "timestamp": "2026-06-04T14:00:00+00:00", "temperature_c": 80.0, "vibration_rms": 5.0},
                    {"device_id": "pump-2", "timestamp": "2026-06-04T14:00:01+00:00", "temperature_c": 70.0, "vibration_rms": 3.0},
                    {"device_id": "pump-1", "timestamp": "2026-06-04T14:00:02+00:00", "temperature_c": 82.0, "vibration_rms": 5.5},
                ]

        with patch("app.main.httpx.get", return_value=FakeResponse()) as get_mock:
            with patch("app.main.celery_app.send_task", side_effect=fake_send_task):
                from app.main import _run_predict_pipeline_once

                result = _run_predict_pipeline_once(limit=100)

        get_mock.assert_called_once_with("http://localhost:8002/readings", params={"limit": 100}, timeout=5.0)
        self.assertEqual(result["queued_devices"], 2)
        self.assertEqual(result["source_readings"], 3)
        self.assertEqual([task["name"] for task in sent_tasks], ["app.tasks.run_device_prediction"] * 2)
        self.assertEqual(sent_tasks[0]["args"][0], "pump-1")
        self.assertEqual(len(sent_tasks[0]["args"][1]), 2)
        self.assertEqual(sent_tasks[1]["args"][0], "pump-2")
        self.assertEqual(len(sent_tasks[1]["args"][1]), 1)

    def test_stop_predict_pipeline_marks_pipeline_stopped(self):
        from app.main import _pipeline_status, _stop_predict_pipeline

        _pipeline_status["running"] = True
        result = _stop_predict_pipeline()

        self.assertFalse(result["running"])
        self.assertFalse(_pipeline_status["running"])

    def test_auto_start_predict_pipeline_starts_when_enabled(self):
        with patch("app.main._pipeline_auto_start", True):
            with patch("app.main._start_predict_pipeline", return_value={"running": True}) as start_mock:
                from app.main import _auto_start_predict_pipeline

                result = _auto_start_predict_pipeline()

        start_mock.assert_called_once()
        self.assertTrue(result["running"])

    def test_auto_start_predict_pipeline_skips_when_disabled(self):
        with patch("app.main._pipeline_auto_start", False):
            with patch("app.main._start_predict_pipeline") as start_mock:
                from app.main import _auto_start_predict_pipeline

                result = _auto_start_predict_pipeline()

        start_mock.assert_not_called()
        self.assertFalse(result["running"])

    def test_device_prediction_records_high_risk_event_before_publish(self):
        records = [
            {
                "device_id": "pump-1",
                "timestamp": "2026-06-04T14:00:00+00:00",
                "temperature_c": 100.0,
            }
        ]

        with patch("app.tasks.run_inference_sensor", return_value={"score": 0.8}):
            with patch(
                "app.tasks._record_high_risk_event",
                return_value=("event-1", "alert-1", "wo-1"),
            ) as record_mock:
                with patch("app.tasks._publish_device_prediction_event", return_value="stream-1") as publish_mock:
                    from app.tasks import run_device_prediction

                    result = run_device_prediction("pump-1", records)

        record_mock.assert_called_once_with("pump-1", "critical", 0.8)
        publish_mock.assert_called_once()
        published_payload = publish_mock.call_args.args[0]
        self.assertEqual(published_payload["event_id"], "event-1")
        self.assertEqual(published_payload["alert_id"], "alert-1")
        self.assertEqual(published_payload["work_order_id"], "wo-1")
        self.assertEqual(result["stream_id"], "stream-1")


if __name__ == "__main__":
    unittest.main()
