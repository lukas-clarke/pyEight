import asyncio
import time
import httpx
import atexit
import logging
from aiohttp.client import ClientError, ClientSession, ClientTimeout
from pyeight.constants import *
from pyeight.structs import Token, User

_LOGGER = logging.getLogger(__name__)
CLIENT_TIMEOUT = ClientTimeout(total=DEFAULT_TIMEOUT)

class EightSleep():
    def __init__(
            self,
            email: str,
            password: str,
            client_id: str,
            client_secret: str):
        self.email = email
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self._api_session = None
        self._token = None
        self._users = []
        # Stop on exit
        atexit.register(self.at_exit)

    def at_exit(self) -> None:
        """Run at exit."""
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(self.stop(), loop).result()
        except RuntimeError:
            asyncio.run(self.stop())

    async def set_heating_level(self, level: int, user_id: str):
        """ set heating level from -100 to 100
        ``user_id`` can either be the name of the user or the side of the bed"""
        await self.turn_on_side(user_id) # Turn on side before setting temperature
        url = APP_API_URL + f"v1/users/{self.match_user(user_id)}/temperature"
        data = {"currentLevel": level}
        await self.api_request("PUT", url, data=data)

    async def set_heating_and_duration_level(self, level: int, duration_seconds, user_id: str):
        """ set heating level from -100 to 100 for a period of time
        ``user_id`` can either be the name of the user or the side of the bed"""
        await self.turn_on_side(user_id)  # Turn on side before setting temperature
        url = APP_API_URL + f"v1/users/{self.match_user(user_id)}/temperature"
        data = {"timeBased": {"level": level, "durationSeconds": duration_seconds}}
        await self.api_request("PUT", url, data=data)

    async def turn_on_side(self, user_id: str):
        """ Turns on the side of the user
        ``user_id`` can either be the name of the user or the side of the bed"""
        url = APP_API_URL + f"v1/users/{self.match_user(user_id)}/temperature"
        data = {"currentState": {"type": "smart"}}
        await self.api_request("PUT", url, data=data)

    async def turn_off_side(self, user_id: str):
        """ Turns off the side of the user
        ``user_id`` can either be the name of the user or the side of the bed"""
        url = APP_API_URL + f"v1/users/{self.match_user(user_id)}/temperature"
        data = {"currentState": {"type": "off"}}
        await self.api_request("PUT", url, data=data)

    async def _get_auth(self) -> Token:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "password",
            "username": self.email,
            "password": self.password
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(AUTH_URL, headers=DEFAULT_AUTH_HEADERS, json=data)
            if response.status_code == 200:
                access_token_str = response.json()["access_token"]
                expiration_seconds_int = float(response.json()["expires_in"]) + time.time()
                main_id = response.json()["userId"]
                return Token(access_token_str, expiration_seconds_int, main_id)
            else:
                raise Exception(f"Auth request failed with status code: {response.status_code}")

    @property
    async def token(self) -> Token:
        """Return session token."""
        if not self._token:
            self._token = await self._get_auth()

        if time.time() + TOKEN_TIME_BUFFER_SECONDS > self._token.expiration:
            self._token = await self._get_auth()

        return self._token

    def match_user(self, user_id: str):
        for user in self._users:
            if user.match(user_id):
                return user.match(user_id)
        raise Exception(f"No users found for {user_id}. Make sure you run the start method prior.")

    async def get_users(self):
        """ get the users linked to account"""
        token = await self.token
        url = APP_API_URL + f"v1/household/users/{token.main_id}/users"
        response_data = await self.api_request("GET", url)
        users = response_data["users"]
        for user in users:
            url = CLIENT_API_URL + f"v1/users/{user['userId']}"
            response_data = await self.api_request("GET", url)
            user_data = response_data["user"]
            self._users.append(User(user_data["firstName"], user_data["userId"], user_data["currentDevice"]["side"]))

    async def start(self):
        """Start api initialization."""
        if not self._api_session:
            self._api_session = ClientSession()
        await self.token
        await self.get_users()

    async def stop(self) -> None:
        """Stop api session."""
        if self._api_session:
            _LOGGER.debug("Closing eight sleep api session.")
            await self._api_session.close()
            self._api_session = None

    async def api_request(
        self,
        method: str,
        url: str,
        params=None,
        data=None,
        input_headers=None
    ):
        """Make api request."""
        if input_headers is not None:
            headers = input_headers
        else:
            headers = DEFAULT_API_HEADERS.copy() # why copy?

        token = await self.token
        if "authorization" in headers:
            headers["authorization"] = f"Bearer {token.bearer_token}"
        else:
            raise Exception("No authorization header found.")
        try:
            assert self._api_session
            resp = await self._api_session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=data,
                timeout=CLIENT_TIMEOUT,
                raise_for_status=True,
            )
            return await resp.json()

        except (ClientError, asyncio.TimeoutError, ConnectionRefusedError) as err:
            _LOGGER.error("Error %sing Eight data. %s", method, err)
            raise err