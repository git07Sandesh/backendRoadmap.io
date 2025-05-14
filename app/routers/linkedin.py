from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

class LinkedInCode(BaseModel):
    code: str
    state: str

@router.post("/exchange-code")
async def exchange_code(data: LinkedInCode):
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    userinfo_url = "https://api.linkedin.com/v2/userinfo"  # ← this is the OIDC endpoint

    payload = {
        "grant_type": "authorization_code",
        "code": data.code,
        "redirect_uri": os.getenv("LINKEDIN_REDIRECT_URI"),
        "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
        "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
    }

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_res = await client.post(
            token_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_res.status_code != 200:
            print("Token Error:", token_res.text)
            raise HTTPException(status_code=token_res.status_code, detail="Failed to exchange code")

        token_data = token_res.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=401, detail="Access token not found")

        print("Access token:", access_token)
        print("Userinfo headers:", {"Authorization": f"Bearer {access_token}"})
        print("Userinfo URL:", userinfo_url)

        # Fetch userinfo
        userinfo_res = await client.get(
            userinfo_url,
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )

        if userinfo_res.status_code != 200:
            print("Userinfo Error:", userinfo_res.text)
            raise HTTPException(status_code=userinfo_res.status_code, detail="Failed to fetch userinfo")

        return userinfo_res.json()
