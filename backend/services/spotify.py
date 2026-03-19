import os
import base64
import requests
import time
from urllib.parse import urlencode
from fastapi import APIRouter, Request
from supabase import create_client, Client

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

# Auto refresh token endpoint (to be called by frontend before making Spotify API calls)

@router.get("/refresh")
def refresh_spotify_token():
    # 1. récupérer le refresh token
    data = supabase.table("spotify_tokens").select("*").eq("id", "user_1").single().execute()
    refresh_token = data.data["refresh_token"]

    # 2. appel Spotify
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_header}"}

    response = requests.post(SPOTIFY_TOKEN_URL, data=payload, headers=headers)
    new_token = response.json()

    # 3. mettre à jour Supabase
    expires_at = int(time.time()) + new_token["expires_in"]

    supabase.table("spotify_tokens").update({
        "access_token": new_token["access_token"],
        "expires_at": expires_at
    }).eq("id", "user_1").execute()

    return new_token
