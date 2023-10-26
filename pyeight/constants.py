CLIENT_API_URL = "https://client-api.8slp.net/"
APP_API_URL = "https://app-api.8slp.net/"
AUTH_URL = "https://auth-api.8slp.net/v1/tokens"

TOKEN_TIME_BUFFER_SECONDS = 120



DEFAULT_API_HEADERS = {
    "content-type": "application/json",
    "connection": "keep-alive",
    "user-agent": "Android App",
    "accept-encoding": "gzip",
    "accept": "application/json",
    "host": "app-api.8slp.net",
    "authorization": f"Bearer ADD",
}

DEFAULT_AUTH_HEADERS = {
    "content-type": "application/json",
    "user-agent": "Android App",
    "accept-encoding": "gzip",
    "accept": "application/json",
}
DEFAULT_TIMEOUT = 2400


TEMPERATURE_JSON = """{"currentLevel":{level}}"""
CURRENT_STATE_JSON = """
        {
          "currentState": {
            "type": "smart"
          }
        }"""