# twitch_api.py
# bot3 Twitch Monitor

import os
import json
import time
import logging
import requests

from pathlib import Path
from dotenv import load_dotenv


load_dotenv()


logger = logging.getLogger("twitch_monitor")


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CACHE_FILE = BASE_DIR / "twitch_cache.json"

STREAMERS_FILE = BASE_DIR / "streamers.json"


# ============================================================
# SINGLETON
# ============================================================

_twitch = None



# ============================================================
# CACHE
# ============================================================


def load_cache():

    if not CACHE_FILE.exists():

        return {}


    try:

        with CACHE_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)


        if isinstance(data, dict):

            return data


    except Exception as e:

        logger.error(
            f"CACHE LOAD ERROR: {e}"
        )


    return {}




def save_cache(data):

    try:

        with CACHE_FILE.open(
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )


    except Exception as e:

        logger.error(
            f"CACHE SAVE ERROR: {e}"
        )




# ============================================================
# STREAMERS LIST
# ============================================================


def load_streamer_names():

    if not STREAMERS_FILE.exists():

        return []


    try:

        with STREAMERS_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)


        result = []


        if isinstance(data, list):

            for item in data:

                if isinstance(item, dict):

                    name = (
                        item.get("name")
                        or
                        item.get("login")
                        or
                        item.get("username")
                    )


                    if name:

                        result.append(
                            name.lower()
                        )


        return result


    except Exception as e:

        logger.error(
            f"STREAMERS LOAD ERROR: {e}"
        )


    return []




# ============================================================
# NORMALIZE TWITCH DATA
# ============================================================


def normalize_stream(data):


    if not data:

        return {

            "online": False,

            "viewer_count": 0

        }



    return {

        "user_login":
            data.get(
                "user_login",
                ""
            ),


        "user_name":
            data.get(
                "user_name",
                ""
            ),


        "title":
            data.get(
                "title",
                ""
            ),


        "game_name":
            data.get(
                "game_name",
                ""
            ),


        "viewer_count":
            data.get(
                "viewer_count",
                0
            ),


        "started_at":
            data.get(
                "started_at",
                ""
            ),


        "thumbnail_url":
            data.get(
                "thumbnail_url",
                ""
            ),


        "online":
            True,


        "offline":
            False,


        "last_online":
            time.time()

    }




# ============================================================
# CACHE UPDATE
# ============================================================


def update_cache_online(
    name,
    stream
):


    cache = load_cache()


    old = cache.get(
        name,
        {}
    )


    current_viewers = stream.get(
        "viewer_count",
        0
    )


    old_peak = old.get(
        "peak_viewers",
        0
    )


    stream["peak_viewers"] = max(
        old_peak,
        current_viewers
    )


    cache[name] = stream


    save_cache(
        cache
    )


    return stream




def get_cache_stream(name):


    cache = load_cache()


    data = cache.get(
        name.lower()
    )


    if not data:

        return None


    result = data.copy()


    result["online"] = False

    result["offline"] = True

    result["viewer_count"] = 0


    return result
# ============================================================
# TWITCH API CLASS
# ============================================================


class TwitchAPI:


    def __init__(
        self,
        client_id=None,
        client_secret=None
    ):


        self.client_id = (
            client_id
            or
            os.getenv(
                "TWITCH_CLIENT_ID"
            )
        )


        self.client_secret = (
            client_secret
            or
            os.getenv(
                "TWITCH_CLIENT_SECRET"
            )
        )


        self.token = None

        self.token_expiry = 0


        self.get_token()




    # ========================================================
    # TOKEN
    # ========================================================


    def get_token(self):


        if not self.client_id or not self.client_secret:


            logger.error(
                "TWITCH CLIENT DATA MISSING"
            )

            return None



        try:

            response = requests.post(

                "https://id.twitch.tv/oauth2/token",

                params={

                    "client_id":
                        self.client_id,

                    "client_secret":
                        self.client_secret,

                    "grant_type":
                        "client_credentials"

                },

                timeout=10

            )


        except Exception as e:

            logger.exception(
                f"TOKEN ERROR: {e}"
            )

            return None




        if response.status_code != 200:


            logger.error(
                response.text
            )

            return None




        data = response.json()


        self.token = data.get(
            "access_token"
        )


        self.token_expiry = (

            time.time()

            +

            data.get(
                "expires_in",
                3600
            )

        )


        logger.info(
            "Twitch token получен"
        )


        return self.token




    def ensure_token(self):


        if (

            not self.token

            or

            time.time()
            >=
            self.token_expiry - 60

        ):

            self.get_token()




    # ========================================================
    # HEADERS
    # ========================================================


    def headers(self):


        self.ensure_token()


        return {

            "Client-ID":
                self.client_id,

            "Authorization":
                f"Bearer {self.token}"

        }




    # ========================================================
    # STREAMS
    # ========================================================


    def fetch_streams(
        self,
        names
    ):


        if not names:

            return {}



        try:

            params = []


            for name in names:

                params.append(

                    (
                        "user_login",
                        name.lower()
                    )

                )



            response = requests.get(

                "https://api.twitch.tv/helix/streams",

                headers=self.headers(),

                params=params,

                timeout=10

            )


        except Exception as e:


            logger.exception(
                f"STREAM REQUEST ERROR: {e}"
            )


            return {}




        if response.status_code != 200:


            logger.error(
                response.text
            )


            return {}




        result = {}



        for item in response.json().get(
            "data",
            []
        ):


            login = item.get(
                "user_login"
            )


            if not login:

                continue



            login = login.lower()



            result[login] = normalize_stream(
                item
            )



        return result




    # ========================================================
    # USERS
    # ========================================================


    def fetch_users(
        self,
        names
    ):


        if not names:

            return {}



        try:

            params = []


            for name in names:

                params.append(

                    (
                        "login",
                        name.lower()
                    )

                )



            response = requests.get(

                "https://api.twitch.tv/helix/users",

                headers=self.headers(),

                params=params,

                timeout=10

            )


        except Exception as e:


            logger.exception(
                f"USERS REQUEST ERROR: {e}"
            )


            return {}




        if response.status_code != 200:


            logger.error(
                response.text
            )


            return {}




        users = {}



        for user in response.json().get(
            "data",
            []
        ):


            login = user.get(
                "login"
            )


            if login:

                users[
                    login.lower()
                ] = user



        return users
# ============================================================
# CACHE BUILDER
# ============================================================


    def build_initial_cache(self):


        names = load_streamer_names()


        if not names:

            logger.warning(
                "NO STREAMERS FOUND"
            )

            return {}



        logger.info(
            "BUILD INITIAL TWITCH CACHE"
        )


        cache = load_cache()



        # получаем профили пользователей

        users = self.fetch_users(
            names
        )



        for name in names:


            user = users.get(
                name
            )


            if user:


                cache[name] = {

                    "user_login":
                        name,


                    "user_name":
                        user.get(
                            "display_name",
                            name
                        ),


                    "profile_image_url":
                        user.get(
                            "profile_image_url",
                            ""
                        ),


                    "offline_image_url":
                        user.get(
                            "offline_image_url",
                            ""
                        ),


                    "title":
                        "",


                    "game_name":
                        "",


                    "viewer_count":
                        0,


                    "peak_viewers":
                        0,


                    "started_at":
                        "",


                    "online":
                        False,


                    "offline":
                        True,


                    "last_update":
                        time.time()

                }




        # если кто-то сейчас онлайн

        online = self.fetch_streams(
            names
        )



        for name, stream in online.items():

            cache[name] = stream



        save_cache(
            cache
        )


        logger.info(
            "INITIAL CACHE CREATED"
        )


        return cache





    # ========================================================
    # REFRESH
    # ========================================================


    def refresh(
        self,
        names=None
    ):


        if not names:

            names = load_streamer_names()



        if not names:

            return {}



        cache = load_cache()



        if not cache:


            cache = self.build_initial_cache()




        online = self.fetch_streams(
            names
        )



        result = {}



        for name in names:


            name = name.lower()



            if name in online:


                # ==========================
                # ONLINE
                # ==========================


                stream = online[name]


                old = cache.get(
                    name,
                    {}
                )


                stream["peak_viewers"] = max(

                    old.get(
                        "peak_viewers",
                        0
                    ),

                    stream.get(
                        "viewer_count",
                        0
                    )

                )


                cache[name] = stream


                result[name] = stream




            else:


                # ==========================
                # OFFLINE
                # ==========================


                old = cache.get(
                    name
                )


                if old:


                    offline = old.copy()


                    offline["online"] = False

                    offline["offline"] = True

                    offline["viewer_count"] = 0


                    result[name] = offline


                else:


                    result[name] = {

                        "user_login":
                            name,

                        "online":
                            False,

                        "offline":
                            True,

                        "viewer_count":
                            0

                    }



        save_cache(
            cache
        )


        return result





    # ========================================================
    # SINGLE STREAM
    # ========================================================


    def get_stream(
        self,
        name
    ):


        name = name.lower()


        data = self.refresh(
            [
                name
            ]
        )


        return data.get(
            name,
            {

                "user_login":
                    name,

                "online":
                    False,

                "offline":
                    True,

                "viewer_count":
                    0

            }
        )





    # ========================================================
    # MULTI STREAM
    # ========================================================


    def get_streams(
        self,
        names
    ):


        return self.refresh(
            names
        )





# ============================================================
# SINGLETON
# ============================================================


def get_twitch_api(
    client_id=None,
    client_secret=None
):


    global _twitch



    real_client_id = (

        client_id

        or

        os.getenv(
            "TWITCH_CLIENT_ID"
        )

    )


    real_client_secret = (

        client_secret

        or

        os.getenv(
            "TWITCH_CLIENT_SECRET"
        )

    )



    if (

        _twitch is None

        or

        _twitch.client_id != real_client_id

        or

        _twitch.client_secret != real_client_secret

    ):


        _twitch = TwitchAPI(

            real_client_id,

            real_client_secret

        )



    return _twitch





# ============================================================
# PUBLIC FUNCTIONS
# ============================================================


def get_streamer_status(
    name
):


    twitch = get_twitch_api()


    return twitch.get_stream(
        name
    )




def get_streamers_status(
    names
):


    twitch = get_twitch_api()


    return twitch.get_streams(
        names
    )