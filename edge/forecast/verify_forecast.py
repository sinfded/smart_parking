import time
import httpx
import threading
import uvicorn
import sys
from api.index import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8888, log_level="error")

def run_tests():
    # 1. Start server in background thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    
    # Wait for server to boot
    time.sleep(2.0)
    
    client = httpx.Client(base_url="http://127.0.0.1:8888")
    
    # Test Health Endpoint
    print("Testing /health endpoint...")
    try:
        res = client.get("/health")
        print(f"Health Response: {res.status_code} - {res.json()}")
        assert res.status_code == 200
        assert res.json()["model_loaded"] is True
    except Exception as e:
        print(f"Health check failed: {e}")
        sys.exit(1)
        
    # Test Forecast Endpoint
    print("Testing /api/forecast endpoint...")
    try:
        payload = {
            "hour": 14,
            "day_of_week": 4, # Friday
            "previous_occupancy": 15
        }
        res = client.post("/api/forecast", json=payload)
        print(f"Forecast Response: {res.status_code} - {res.json()}")
        assert res.status_code == 200
        assert "predicted_occupied_slots" in res.json()
        val = res.json()["predicted_occupied_slots"]
        print(f"Verified! Predicted occupied slots: {val}")
    except Exception as e:
        print(f"Forecast endpoint failed: {e}")
        sys.exit(1)

    print("\nAll integration verification tests passed successfully!")
    sys.exit(0)

if __name__ == "__main__":
    run_tests()
