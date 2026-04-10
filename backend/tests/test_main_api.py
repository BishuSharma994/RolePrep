import unittest
import importlib
import os
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient


class MainApiTests(unittest.TestCase):
    def test_buildz_returns_deployment_marker(self):
        sys.modules.pop("backend.services.db", None)
        sys.modules.pop("backend.main", None)

        with patch.dict(os.environ, {"MONGO_URI": "mongodb://localhost:27017"}):
            with patch("pymongo.MongoClient"):
                main_module = importlib.import_module("backend.main")

        with patch.object(main_module, "init_db"):
            with TestClient(main_module.app) as client:
                response = client.get("/buildz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "deployment": "github-actions",
            },
        )


if __name__ == "__main__":
    unittest.main()
