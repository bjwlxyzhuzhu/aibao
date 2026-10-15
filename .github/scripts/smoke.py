"""Offline image checks: no school roster, local secrets, or model calls."""
import os
import sys

sys.path.insert(0, os.getcwd())
from fastapi.testclient import TestClient

if sys.argv[1] == 'api':
    from app.main import app
    with TestClient(app) as client:
        response = client.get('/api/health')
        assert response.status_code == 200, response.text
        assert response.json()['ok'] is True
        assert response.json()['demo_mode'] is False
        response = client.post('/api/auth/login', json={'login': 'admin', 'password': 'wrong'})
        assert response.status_code in (400, 401), response.text
    print('API: clean database startup and health checks passed')
else:
    import torch
    import torchaudio
    from funasr import AutoModel
    from server import app
    with TestClient(app) as client:
        response = client.get('/health')
        assert response.status_code == 200 and response.json()['ok'] is True
    print('ASR: CPU dependencies and health checks passed (model weights are not downloaded in CI)')
