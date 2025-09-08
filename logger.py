import requests
import threading
from typing import Literal, Optional

import config


token_lock = threading.Lock()

auth_token_storage: Optional[dict] = None

LogStack = Literal["backend", "frontend"]
LogLevel = Literal["debug", "info", "warn", "error", "fatal"]
BackendPackage = Literal[
    "cache", "controller", "cron_job", "db", "domain",
    "handler", "repository", "route", "service"
]
LogPackage = BackendPackage 



def get_auth_token() -> Optional[str]:
    """
    Fetches and caches the authorization token from the test server.
    It's thread-safe and only fetches a new token when necessary.
    """
    global auth_token_storage

    with token_lock:
        if auth_token_storage:
            return auth_token_storage.get('token')

        print("Attempting to get a new authorization token...")
        payload = {
            "email": config.EMAIL,
            "name": config.NAME,
            "rollNo": config.ROLL_NO,
            "accessCode": config.ACCESS_CODE,
            "clientID": config.CLIENT_ID,
            "clientSecret": config.CLIENT_SECRET
        }
        try:
            response = requests.post(config.AUTH_ENDPOINT, json=payload, timeout=10)
            response.raise_for_status()  

            token_data = response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                print("Error: 'access_token' not found in the authentication response.")
                return None

            auth_token_storage = {'token': access_token}
            print("Successfully obtained and cached a new auth token.")
            return access_token

        except requests.exceptions.RequestException as e:
            print(f"FATAL: Could not fetch auth token. Error: {e}")
            return None

def Log(stack: LogStack, level: LogLevel, package: LogPackage, message: str):
    """
    A reusable function that sends a log message to the test server API.
    This is the central logging function to be used throughout the application.
    """
    token = get_auth_token()
    if not token:
        print(f"LOG FAILED (No Auth Token): [{level.upper()}] {package} - {message}")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "stack": stack,
        "level": level,
        "package": package,
        "message": message
    }

    try:
        response = requests.post(config.LOG_ENDPOINT, headers=headers, json=payload, timeout=5)
        if response.status_code != 200:
            print(f"Warning: Log submission failed with status {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending log to the test server: {e}")