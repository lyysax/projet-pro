from fastapi import APIRouter
import requests

router = APIRouter()

DEEZER_API_URL = "https://api.deezer.com"


@router.get("/artist")
def search_artist(name: str):
    response = requests.get(f"{DEEZER_API_URL}/search/artist", params={"q": name})
    return response.json()


@router.get("/user")
def get_user(user_id: str):
    response = requests.get(f"{DEEZER_API_URL}/user/{user_id}")
    return response.json()
