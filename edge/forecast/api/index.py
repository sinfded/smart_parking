from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os
import warnings

# Suppress sklearn feature names warning
warnings.filterwarnings("ignore", category=UserWarning)

app = FastAPI(title="Smart Parking Forecasting API", version="1.0")

# Resolve path to the pickle file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(BASE_DIR, "parking_forecast_model.pkl"))

model = None
if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        print(f"Successfully loaded model from {MODEL_PATH}")
    except Exception as e:
        print(f"Error loading model from {MODEL_PATH}: {e}")
else:
    print(f"Model file not found at {MODEL_PATH}")

class ForecastRequest(BaseModel):
    hour: int
    day_of_week: int
    previous_occupancy: int

@app.get("/health")
def health():
    return {
        "status": "ok" if model is not None else "degraded",
        "model_loaded": model is not None
    }

@app.post("/api/forecast")
def predict_occupancy(req: ForecastRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Forecasting model is not loaded on the server")
        
    # Validation
    if not (0 <= req.hour <= 23):
        raise HTTPException(status_code=400, detail="Hour must be between 0 and 23")
    if not (0 <= req.day_of_week <= 6):
        raise HTTPException(status_code=400, detail="Day of week must be between 0 (Monday) and 6 (Sunday)")
    if req.previous_occupancy < 0:
        raise HTTPException(status_code=400, detail="Previous occupancy cannot be negative")

    try:
        # Features: ['hour', 'day_of_week', 'previous_occupancy']
        prediction = model.predict([[req.hour, req.day_of_week, req.previous_occupancy]])[0]
        return {
            "predicted_occupied_slots": round(float(prediction), 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")
