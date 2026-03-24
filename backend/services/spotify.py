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
        "scope": "user-read-email user-read-private user-top-read user-read-recently-played"
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
    token_data = response.json()

    # Sauvegarde dans Supabase
    expires_at = int(time.time()) + token_data["expires_in"]

    supabase.table("spotify_token").upsert({
        "id": "user_1",
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_at": expires_at
    }).execute()

    return token_data

# Auto refresh token endpoint (to be called by frontend before making Spotify API calls)

@router.get("/refresh")
def refresh_spotify_token():
    # 1. récupérer le refresh token
    data = supabase.table("spotify_token").select("*").eq("id", "user_1").single().execute()
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

    supabase.table("spotify_token").update({
        "access_token": new_token["access_token"],
        "expires_at": expires_at
    }).eq("id", "user_1").execute()

    return new_token

# Endpoints pour récupérer les données Spotify

@router.get("/top-artists")
def get_top_artists():
    data = supabase.table("spotify_token").select("access_token").eq("id", "user_1").single().execute()
    access_token = data.data["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{SPOTIFY_API_URL}/me/top/artists", headers=headers, params={"time_range": "short_term", "limit": 10})
    
    if response.status_code != 200:
        return {"error": response.status_code, "detail": response.text}
    
    return response.json()


@router.get("/top-tracks")
def get_top_tracks():
    data = supabase.table("spotify_token").select("access_token").eq("id", "user_1").single().execute()
    access_token = data.data["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{SPOTIFY_API_URL}/me/top/tracks", headers=headers, params={"time_range": "short_term", "limit": 10})
    
    if response.status_code != 200:
        return {"error": response.status_code, "detail": response.text}

    return response.json()

## Endpoint pour récupérer l'historique d'écoute récent

@router.get("/recently-played")
def get_recently_played():
    data = supabase.table("spotify_token").select("access_token").eq("id", "user_1").single().execute()
    access_token = data.data["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{SPOTIFY_API_URL}/me/player/recently-played", headers=headers, params={"limit": 50})
    
    if response.status_code != 200:
        return {"error": response.status_code, "detail": response.text}

    return response.json()

# Endpoint pour sauvegarder l'historique d'écoute dans Supabase
@router.post("/save-history")
def save_listening_history():
    data = supabase.table("spotify_token").select("access_token").eq("id", "user_1").single().execute()
    access_token = data.data["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{SPOTIFY_API_URL}/me/player/recently-played", headers=headers, params={"limit": 50})
    
    if response.status_code != 200:
        return {"error": response.status_code, "detail": response.text}
    
    tracks = response.json()["items"]
    
    for track in tracks:
        supabase.table("listening_history").upsert({
            "track_id": track["track"]["id"],
            "track_name": track["track"]["name"],
            "artist_name": track["track"]["artists"][0]["name"],
            "duration_ms": track["track"]["duration_ms"],
            "played_at": track["played_at"]
        }).execute()
    
    return {"saved": len(tracks)}

from datetime import datetime, timezone

@router.get("/daily-recap")
def daily_recap():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    data = supabase.table("listening_history").select("*").gte("played_at", f"{today}T00:00:00Z").execute()
    
    tracks = data.data
    
    if not tracks:
        return {"message": "Aucune écoute aujourd'hui"}
    
    total_ms = sum(t["duration_ms"] for t in tracks)
    total_minutes = round(total_ms / 60000)
    
    artist_count = {}
    for t in tracks:
        artist = t["artist_name"]
        artist_count[artist] = artist_count.get(artist, 0) + 1
    
    top_artist = max(artist_count, key=artist_count.get)
    
    return {
        "date": today,
        "total_tracks": len(tracks),
        "total_minutes": total_minutes,
        "top_artist": top_artist,
        "tracks": tracks
    }