# twitch_api.py

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
# STREAMER FILE SAVE
# ============================================================

def save_streamer_data(
    name,
    data
):

    try:

        file = BASE_DIR / f"{name}.json"


        old = {}


        if file.exists():

            try:

                with file.open(
                    "r",
                    encoding="utf-8"
                ) as f:

                    old = json.load(f)

            except Exception:

                old = {}



        if not isinstance(
            old,
            dict
        ):

            old = {}



        old["twitch_data"] = data


        old["old_title"] = data.get(
            "title",
            ""
        )


        old["old_game"] = data.get(
            "game_name",
            ""
        )


        old["peak_viewers"] = data.get(
            "viewer_count",
            0
        )


        old["last_update"] = time.time()



        with file.open(
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                old,
                f,
                ensure_ascii=False,
                indent=2
            )


        logger.info(
            f"STREAMER DATA SAVED: {name}.json"
        )


    except Exception as e:

        logger.exception(
            f"SAVE STREAMER DATA ERROR {name}: {e}"
        )




# ============================================================
# TWITCH API
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

            resp = requests.post(

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




        if resp.status_code != 200:


            logger.error(
                resp.text
            )


            return None



        data = resp.json()



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

            time.time() >= self.token_expiry - 60

        ):

            self.get_token()




    # ========================================================
    # STREAMS
    # ========================================================

    def get_streams(
        self,
        streamer_names
    ):


        if not streamer_names:

            return {}



        self.ensure_token()



        if not self.token:

            return {}



        headers = {

            "Client-ID":
                self.client_id,

            "Authorization":
                f"Bearer {self.token}"

        }




        params = [

            (
                "user_login",
                name.lower()
            )

            for name in streamer_names

        ]



        try:

            resp = requests.get(

                "https://api.twitch.tv/helix/streams",

                headers=headers,

                params=params,

                timeout=10

            )


        except Exception as e:

            logger.exception(
                f"STREAM ERROR: {e}"
            )

            return {}




        if resp.status_code != 200:


            logger.error(
                resp.text
            )


            return {}




        streams = resp.json().get(
            "data",
            []
        )



        cache = load_cache()


        result = {}



        for stream in streams:


            login = stream.get(
                "user_login"
            )



            if not login:

                continue



            login = login.lower()



            result[login] = stream



            cache[login] = stream



            # сохраняем последний стрим

            save_streamer_data(
                login,
                stream
            )




        save_cache(
            cache
        )



        logger.info(
            f"ONLINE USERS: {list(result.keys())}"
        )



        return result




    # ========================================================
    # SINGLE STREAM
    # ========================================================

    def get_stream(
        self,
        streamer_name
    ):


        name = streamer_name.lower()



        online = self.get_streams(
            [
                name
            ]
        )



        if name in online:

            return online[name]




        # ====================================================
        # OFFLINE -> streamer.json
        # ====================================================

        streamer_file = BASE_DIR / f"{name}.json"



        if streamer_file.exists():


            try:

                with streamer_file.open(
                    "r",
                    encoding="utf-8"
                ) as f:

                    data = json.load(f)



                twitch_data = data.get(
                    "twitch_data"
                )



                if twitch_data:


                    result = twitch_data.copy()


                    result["viewer_count"] = 0


                    result["offline"] = True



                    logger.info(
                        f"USE STREAMER FILE: {name}"
                    )


                    return result



            except Exception as e:

                logger.error(
                    f"STREAMER FILE ERROR {name}: {e}"
                )





        # ====================================================
        # OFFLINE -> CACHE
        # ====================================================

        cache = load_cache()



        if name in cache:


            data = cache[name].copy()


            data["viewer_count"] = 0


            data["offline"] = True



            logger.info(
                f"USE CACHE: {name}"
            )



            return data





        # ====================================================
        # USER DATA
        # ====================================================


        users = self.get_users(
            [
                name
            ]
        )



        if name in users:


            user = users[name]



            return {

                "user_login":
                    name,

                "user_name":
                    user.get(
                        "display_name",
                        name
                    ),

                "title":
                    "",

                "game_name":
                    "",

                "viewer_count":
                    0,

                "started_at":
                    "",

                "thumbnail_url":
                    user.get(
                        "profile_image_url",
                        ""
                    ),

                "offline":
                    True

            }




        return {

            "user_login":
                name,

            "title":
                "",

            "game_name":
                "",

            "viewer_count":
                0,

            "offline":
                True

        }




    # ========================================================
    # USERS
    # ========================================================

    def get_users(
        self,
        usernames
    ):


        if not usernames:

            return {}



        self.ensure_token()



        if not self.token:

            return {}



        headers = {

            "Client-ID":
                self.client_id,

            "Authorization":
                f"Bearer {self.token}"

        }



        params = [

            (
                "login",
                name.lower()
            )

            for name in usernames

        ]



        try:

            resp = requests.get(

                "https://api.twitch.tv/helix/users",

                headers=headers,

                params=params,

                timeout=10

            )


        except Exception as e:

            logger.exception(
                f"USERS ERROR: {e}"
            )

            return {}




        if resp.status_code != 200:

            return {}



        return {

            user["login"].lower():

            user

            for user in resp.json().get(
                "data",
                []
            )

        }





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
