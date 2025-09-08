# main.py
import string
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional

import config
from logger import Log


app = FastAPI(
    title="URL Shortener Microservice",
    description="A service to create and manage short URLs with integrated logging."
)

url_db = {}

class URLShortenRequest(BaseModel):
    url: HttpUrl  
    validity: int = Field(
        default=config.DEFAULT_VALIDITY_MINUTES,
        gt=0, 
        description="Duration in minutes for which the short link is valid."
    )
    shortcode: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=12,
        pattern="^[a-zA-Z0-9_\\-]+$",
        description="Optional custom shortcode (alphanumeric, underscore, hyphen)."
    )

class URLShortenResponse(BaseModel):
    shortlink: str
    expiry: str 

def generate_unique_shortcode() -> str:
    """Generates a random, unique shortcode that is not already in use."""
    Log("backend", "info", "service", "Generating a new unique shortcode.")
    while True:
        chars = string.ascii_letters + string.digits
        shortcode = ''.join(secrets.choice(chars) for _ in range(config.SHORTCODE_LENGTH))
        if shortcode not in url_db:
            Log("backend", "debug", "service", f"Generated shortcode '{shortcode}' is unique.")
            return shortcode


@app.post(
    "/shorturls",
    response_model=URLShortenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["URL Shortener"]
)
def create_short_url(request_data: URLShortenRequest):
    """
    Creates a new shortened URL.
    """
    Log("backend", "info", "handler", f"Received request to shorten URL: {request_data.url}")

    shortcode = request_data.shortcode
    
    if shortcode:
        Log("backend", "debug", "handler", f"Custom shortcode '{shortcode}' was provided.")
        if shortcode in url_db:
            Log("backend", "warn", "handler", f"Custom shortcode '{shortcode}' is unavailable. Generating a new one.")
            shortcode = generate_unique_shortcode()
    else:
        Log("backend", "debug", "handler", "No custom shortcode provided. Generating a new one.")
        shortcode = generate_unique_shortcode()

    expiry_datetime_utc = datetime.now(timezone.utc) + timedelta(minutes=request_data.validity)
    Log("backend", "debug", "service", f"Calculated expiry for '{shortcode}': {expiry_datetime_utc.isoformat()}")

    url_db[shortcode] = {
        "long_url": str(request_data.url),
        "expiry_utc": expiry_datetime_utc
    }
    Log("backend", "info", "db", f"Successfully stored mapping for shortcode '{shortcode}'.")

    return URLShortenResponse(
        shortlink=f"{config.BASE_SHORT_URL}/{shortcode}",
        expiry=expiry_datetime_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    )

@app.get("/{shortcode}", tags=["URL Shortener"])
def redirect_to_long_url(shortcode: str):
    """
    Redirects a short URL to its original long URL if it exists and has not expired.
    This is the core functionality that makes the short links work.
    """
    Log("backend", "info", "handler", f"Redirect request received for shortcode: '{shortcode}'.")

    url_data = url_db.get(shortcode)

    if not url_data:
        Log("backend", "error", "handler", f"Shortcode '{shortcode}' not found in database.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found.")

    if datetime.now(timezone.utc) > url_data["expiry_utc"]:
        Log("backend", "warn", "handler", f"Shortcode '{shortcode}' has expired. Removing from DB.")
        del url_db[shortcode] 
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This Short URL has expired.")

    long_url = url_data["long_url"]
    Log("backend", "info", "handler", f"Successfully redirecting '{shortcode}' to its destination.")
    return RedirectResponse(url=long_url)

@app.get("/", tags=["Health"])
def health_check():
    """A simple endpoint to check if the service is running."""
    Log("backend", "info", "route", "Health check endpoint was hit.")
    return {"status": "URL Shortener service is running"}