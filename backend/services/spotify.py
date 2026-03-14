import os
import base64
import requests
from urllib.parse import urlencode
from fastapi import APIRouter, Request

router = APIRouter()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8000/spotify/callback"

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"


@router.get("/auth")
def spotify_auth():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "user-read-email user-read-private"
    }
    url = f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"
    return {"auth_url": url}


@router.get("/callback")
def spotify_callback(code: str):
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    return response.json()

