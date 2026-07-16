# twitch.py

import asyncio
import json
import logging
import os

from pathlib import Path
from datetime import datetime, timezone

from aiogram import Bot, types
from aiogram.filters import Command


try:
    from bot3.twitch_api import get_twitch_api
except ImportError:
    from twitch_api import get_twitch_api



logger = logging.getLogger("twitch_monitor")



# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

STREAMERS_FILE = BASE_DIR / "streamers.json"


STREAMERS = []

_last_mtime = None




# ============================================================
# LOAD STREAMERS
# ============================================================

def load_streamers():

    global STREAMERS


    if not STREAMERS_FILE.exists():

        STREAMERS = []

        logger.warning(
            "streamers.json отсутствует"
        )

        return




    try:

        with STREAMERS_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)



        if not isinstance(
            data,
            list
        ):

            STREAMERS = []

            return




        result = []



        for streamer in data:


            name = streamer.get(
                "name"
            )


            if not name:

                continue



            custom_file = BASE_DIR / f"{name}.json"



            if custom_file.exists():


                try:

                    with custom_file.open(
                        "r",
                        encoding="utf-8"
                    ) as sf:

                        custom = json.load(sf)



                    if isinstance(
                        custom,
                        dict
                    ):

                        result.append(
                            custom
                        )


                        logger.info(
                            f"Используется {custom_file.name}"
                        )


                        continue



                except Exception as e:

                    logger.error(
                        f"{custom_file}: {e}"
                    )



            result.append(
                streamer
            )



        STREAMERS = result



        logger.info(
            f"STREAMERS LOADED: {[x.get('name') for x in STREAMERS]}"
        )



    except Exception as e:

        logger.exception(
            f"LOAD ERROR: {e}"
        )

        STREAMERS = []




# ============================================================
# WATCH FILE
# ============================================================

async def watch_streamers_file(
    interval=5
):

    global _last_mtime



    while True:


        try:

            if STREAMERS_FILE.exists():


                mtime = STREAMERS_FILE.stat().st_mtime



                if (

                    _last_mtime is None

                    or

                    mtime != _last_mtime

                ):


                    _last_mtime = mtime


                    load_streamers()



        except Exception as e:

            logger.exception(
                f"WATCH ERROR: {e}"
            )



        await asyncio.sleep(
            interval
        )





# ============================================================
# MONITOR
# ============================================================

async def monitor(
    bot: Bot,
    client_id,
    client_secret,
    interval=30
):


    twitch = get_twitch_api(
        client_id,
        client_secret
    )



    state = {}



    while True:


        try:


            if not STREAMERS:


                logger.warning(
                    "STREAMERS пустой"
                )


                await asyncio.sleep(
                    interval
                )


                continue




            names = [

                s["name"].lower()

                for s in STREAMERS

            ]



            logger.info(
                f"CHECK: {names}"
            )



            online = twitch.get_streams(
                names
            )



            for streamer in STREAMERS:



                name = streamer["name"].lower()



                messages = streamer.get(
                    "messages",
                    {}
                )



                url = f"https://twitch.tv/{name}"




                if name not in state:


                    state[name] = {


                        "online":False,

                        "title":"",

                        "game":"",

                        "start_time":None,

                        "peak_viewers":0

                    }



                st = state[name]





                # ==================================================
                # ONLINE
                # ==================================================

                if name in online:



                    data = online[name]



                    title = data.get(
                        "title",
                        ""
                    )


                    game = data.get(
                        "game_name",
                        ""
                    )


                    viewers = data.get(
                        "viewer_count",
                        0
                    )



                    if not st["online"]:



                        logger.info(
                            f"START STREAM {name}"
                        )


                        st["online"] = True


                        st["title"] = title


                        st["game"] = game


                        st["start_time"] = datetime.now(
                            timezone.utc
                        )


                        st["peak_viewers"] = viewers





                        for ch in streamer.get(
                            "channels",
                            []
                        ):


                            if ch.get(
                                "notify_start",
                                True
                            ):


                                await bot.send_message(

                                    ch["chat_id"],


                                    messages.get(
                                        "start",
                                        ""
                                    ).format(

                                        name=name,

                                        title=title,

                                        game=game,

                                        url=url

                                    ),


                                    parse_mode="HTML"

                                )



                    else:


                        if viewers > st["peak_viewers"]:

                            st["peak_viewers"] = viewers




                # ==================================================
                # OFFLINE
                # ==================================================

                else:



                    offline = twitch.get_stream(
                        name
                    )



                    if offline:


                        st["title"] = offline.get(
                            "title",
                            st["title"]
                        )


                        st["game"] = offline.get(
                            "game_name",
                            st["game"]
                        )




                    if st["online"]:



                        logger.info(
                            f"END STREAM {name}"
                        )



                        duration = (

                            datetime.now(
                                timezone.utc
                            )

                            -

                            st["start_time"]

                        )



                        sec = int(
                            duration.total_seconds()
                        )


                        hours, rem = divmod(
                            sec,
                            3600
                        )


                        minutes = rem // 60



                        dur = (
                            f"{hours}ч {minutes}мин"
                        )




                        for ch in streamer.get(
                            "channels",
                            []
                        ):


                            if ch.get(
                                "notify_end",
                                True
                            ):


                                await bot.send_message(

                                    ch["chat_id"],


                                    messages.get(
                                        "end",
                                        ""
                                    ).format(

                                        name=name,

                                        title=st["title"],

                                        duration=dur,

                                        peak_viewers=st["peak_viewers"],

                                        url=url

                                    ),


                                    parse_mode="HTML"

                                )




                        st["online"] = False

                        st["title"] = ""

                        st["game"] = ""

                        st["start_time"] = None

                        st["peak_viewers"] = 0




        except Exception as e:

            logger.exception(
                f"MONITOR ERROR: {e}"
            )



        await asyncio.sleep(
            interval
        )





# ============================================================
# /twitchapi
# ============================================================

def register_twitch_api_handler(dp):


    @dp.message(Command("twitchapi"))
    async def twitch_api_test(
        message: types.Message
    ):


        try:


            twitch = get_twitch_api()


            result = twitch.get_streams(
                [
                    "ninja"
                ]
            )



            await message.answer(

                "✅ Twitch API OK\n"
                f"Онлайн: {len(result)}"

            )



        except Exception as e:


            await message.answer(
                f"❌ ERROR: {e}"
            )
