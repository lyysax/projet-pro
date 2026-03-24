import os
import base64
import requests
import time
from urllib.parse import urlencode
from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


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

PARIS_TZ = ZoneInfo("Europe/Paris")


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
    print("TOKEN DATA:", token_data)

    expires_at = int(time.time()) + token_data["expires_in"]

    supabase.table("spotify_token").upsert({
        "id": "user_1",
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_at": expires_at
    }).execute()

    return RedirectResponse(url="http://127.0.0.1:5500/frontend/dashboard.html")

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

@router.get("/me")
def get_me():
    # Récupère le token stocké
    data = supabase.table("spotify_token").select("access_token").eq("id", "user_1").single().execute()
    token_row = data.data if data else None

    if not token_row or "access_token" not in token_row:
        return {"error": 401, "detail": "Token Spotify introuvable. Reconnecte ton compte."}

    access_token = token_row["access_token"]

    # Appel Spotify /me
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{SPOTIFY_API_URL}/me", headers=headers)

    if response.status_code != 200:
        return {"error": response.status_code, "detail": response.text}

    me = response.json()
    return {
        "id": me.get("id"),
        "name": me.get("display_name") or me.get("id") or "utilisateur",
        "email": me.get("email")
    }

# Endpoints pour récupérer les données Spotify

@router.get("/top-artists")
def get_top_artists(
    time_range: str = Query("short_term"),
    limit: int = Query(50, ge=1, le=50)
):
    data = supabase.table("spotify_token").select("access_token").eq("id", "user_1").single().execute()
    access_token = data.data["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"{SPOTIFY_API_URL}/me/top/artists",
        headers=headers,
        params={"time_range": time_range, "limit": limit}
    )

    if response.status_code != 200:
        return {"error": response.status_code, "detail": response.text}

    return response.json()


@router.get("/top-tracks")
def get_top_tracks(
    time_range: str = Query("short_term"),
    limit: int = Query(50, ge=1, le=50)
):
    data = supabase.table("spotify_token").select("access_token").eq("id", "user_1").single().execute()
    access_token = data.data["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"{SPOTIFY_API_URL}/me/top/tracks",
        headers=headers,
        params={"time_range": time_range, "limit": limit}
    )

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
    token_data = (
        supabase.table("spotify_token")
        .select("access_token")
        .eq("id", "user_1")
        .single()
        .execute()
    )
    access_token = token_data.data["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"{SPOTIFY_API_URL}/me/player/recently-played",
        headers=headers,
        params={"limit": 50},
    )

    if response.status_code != 200:
        return {"error": response.status_code, "detail": response.text}

    items = response.json().get("items", [])
    rows = []

    for item in items:
        track = item.get("track", {})
        track_id = track.get("id")
        played_at = item.get("played_at")

        if not track_id or not played_at:
            continue

        rows.append({
            "track_id": track_id,
            "track_name": track.get("name"),
            "artist_name": (track.get("artists") or [{}])[0].get("name"),
            "duration_ms": track.get("duration_ms") or 0,
            "played_at": played_at,
        })

    if rows:
        supabase.table("listening_history").upsert(
            rows,
            on_conflict="track_id,played_at",
        ).execute()

    return {"saved": len(rows)}

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

def _release_window_utc(now_paris: datetime):
    today_21 = now_paris.replace(hour=21, minute=0, second=0, microsecond=0)
    if now_paris >= today_21:
        release_paris = today_21
    else:
        release_paris = today_21 - timedelta(days=1)

    start_paris = release_paris - timedelta(hours=24)

    return (
        start_paris.astimezone(timezone.utc),
        release_paris.astimezone(timezone.utc),
        today_21 if now_paris < today_21 else today_21 + timedelta(days=1),
        release_paris
    )

@router.get("/daily-stats")
def daily_stats():
    now_paris = datetime.now(PARIS_TZ)
    start_utc, end_utc, next_release_paris, release_paris = _release_window_utc(now_paris)

    # On lit la fenêtre 24h qui se termine à 21h (snapshot quotidien)
    data = (
        supabase.table("listening_history")
        .select("*")
        .gte("played_at", start_utc.isoformat().replace("+00:00", "Z"))
        .lt("played_at", end_utc.isoformat().replace("+00:00", "Z"))
        .execute()
    )

    tracks = data.data or []

    # Top artistes (top 5)
    artist_count = {}
    for t in tracks:
        artist = t.get("artist_name") or "Inconnu"
        artist_count[artist] = artist_count.get(artist, 0) + 1
    top_artists = sorted(artist_count.items(), key=lambda x: x[1], reverse=True)[:5]

    # Top tracks (top 5)
    track_count = {}
    for t in tracks:
        key = (
            t.get("track_name") or "Inconnu",
            t.get("artist_name") or "Inconnu"
        )
        track_count[key] = track_count.get(key, 0) + 1
    top_tracks = sorted(track_count.items(), key=lambda x: x[1], reverse=True)[:5]

    total_ms = sum((t.get("duration_ms") or 0) for t in tracks)
    total_minutes = round(total_ms / 60000)

    return {
        "release_at": release_paris.isoformat(),
        "next_release_at": next_release_paris.isoformat(),
        "window_start_utc": start_utc.isoformat(),
        "window_end_utc": end_utc.isoformat(),
        "total_minutes": total_minutes,
        "total_plays": len(tracks),
        "top_artists": [{"name": name, "count": count} for name, count in top_artists],
        "top_tracks": [{"name": name, "artist": artist, "count": count} for (name, artist), count in top_tracks]
    }

@router.get("/listening-minutes")
def get_listening_minutes(time_range: str = Query("short_term")):
    now_utc = datetime.now(timezone.utc)

    if time_range == "short_term":
        start_utc = now_utc - timedelta(days=28)
    elif time_range == "medium_term":
        start_utc = now_utc - timedelta(days=183)
    elif time_range == "long_term":
        start_utc = None
    else:
        return {"error": 400, "detail": "time_range invalide"}

    query = supabase.table("listening_history").select("duration_ms")
    if start_utc is not None:
        query = query.gte("played_at", start_utc.isoformat().replace("+00:00", "Z"))

    data = query.execute()
    rows = data.data or []

    total_ms = sum((row.get("duration_ms") or 0) for row in rows)
    total_minutes = round(total_ms / 60000)

    return {
        "time_range": time_range,
        "total_minutes": total_minutes,
        "total_ms": total_ms,
        "plays_count": len(rows)
    }


@router.get("/history-diagnostics")
def history_diagnostics():
    now_utc = datetime.now(timezone.utc)
    short_start = now_utc - timedelta(days=28)
    medium_start = now_utc - timedelta(days=183)

    all_rows = (
        supabase.table("listening_history")
        .select("played_at")
        .order("played_at", desc=False)
        .execute()
        .data
        or []
    )

    if not all_rows:
        return {
            "total_rows": 0,
            "oldest_played_at": None,
            "latest_played_at": None,
            "short_term_rows": 0,
            "medium_term_rows": 0,
            "long_term_rows": 0,
        }

    played_ats = [row.get("played_at") for row in all_rows if row.get("played_at")]

    def _count_since(start_iso: str) -> int:
        rows = (
            supabase.table("listening_history")
            .select("played_at")
            .gte("played_at", start_iso)
            .execute()
            .data
            or []
        )
        return len(rows)

    short_rows = _count_since(short_start.isoformat().replace("+00:00", "Z"))
    medium_rows = _count_since(medium_start.isoformat().replace("+00:00", "Z"))

    return {
        "total_rows": len(played_ats),
        "oldest_played_at": played_ats[0],
        "latest_played_at": played_ats[-1],
        "short_term_start_utc": short_start.isoformat(),
        "medium_term_start_utc": medium_start.isoformat(),
        "short_term_rows": short_rows,
        "medium_term_rows": medium_rows,
        "long_term_rows": len(played_ats),
    }

