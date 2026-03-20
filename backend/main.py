from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from backend.services import spotify, deezer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # sert si on loge le site (remplacer "*" par l'url du site)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spotify.router, prefix="/spotify")
app.include_router(deezer.router, prefix="/deezer")

@app.get("/")
def root():
    return {"Backend ok"}

@app.get("/health")
def health_check():
    return {"status": "ok"}