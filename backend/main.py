from fastapi import FastAPI
from dotenv import load_dotenv
load_dotenv()

from backend.services import spotify, deezer

app = FastAPI()

app.include_router(spotify.router, prefix="/spotify")
app.include_router(deezer.router, prefix="/deezer")

@app.get("/")
def root():
    return {"Backend ok"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

