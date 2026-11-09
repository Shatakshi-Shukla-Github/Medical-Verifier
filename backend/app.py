from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel, Field
from pipeline import MedicalFactCheckerPipeline, SourceSearchError

app = FastAPI(title="Medical Myth & Health Misinformation Verifier API")

# Enable CORS for React Frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = MedicalFactCheckerPipeline()

class ClaimRequest(BaseModel):
    claim: str = Field(min_length=1, max_length=1000)

@app.get("/")
def read_root():
    return {"message": "Medical Myth Verifier API is active"}

@app.post("/api/analyze")
def analyze_claim(request: ClaimRequest):
    try:
        return pipeline.analyze_claim(request.claim)
    except SourceSearchError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

@app.get("/api/dashboard-metrics")
def get_dashboard_metrics():
    return pipeline.get_dashboard_metrics()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)