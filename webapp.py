# webapp.py

print("NEW WEBAPP LOADED UTF8")


import json

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


try:
    from bot3.twitch_api import (
        get_streamer_status
    )

except ImportError:

    from twitch_api import (
        get_streamer_status
    )



# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

STREAMERS_FILE = BASE_DIR / "streamers.json"




# ============================================================
# ROUTER
# ============================================================

router = APIRouter()




# ============================================================
# FILES
# ============================================================

def get_streamer_file(name):

    return BASE_DIR / f"{name}.json"





def load_json(file):

    try:

        with file.open(
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)


    except Exception as e:

        print(
            "[WEBAPP JSON ERROR]",
            file,
            e
        )


        return None






def save_json(file, data):


    with file.open(
        "w",
        encoding="utf-8"
    ) as f:


        json.dump(

            data,

            f,

            ensure_ascii=False,

            indent=2

        )





# ============================================================
# STREAMERS
# ============================================================

def load_streamers():


    if not STREAMERS_FILE.exists():

        return []



    data = load_json(
        STREAMERS_FILE
    )



    if isinstance(
        data,
        list
    ):

        return data



    return []






def load_streamer(name):


    custom = get_streamer_file(
        name
    )



    if custom.exists():


        data = load_json(
            custom
        )


        if isinstance(
            data,
            dict
        ):


            return data





    for item in load_streamers():


        if (

            item.get(
                "name",
                ""
            ).lower()

            ==

            name.lower()

        ):

            return item




    return None





# ============================================================
# TWITCH DATA
# ============================================================

def get_twitch_preview(name):


    result = {


        "title":"",

        "game":"",

        "viewer_count":0,

        "started_at":"",

        "thumbnail_url":"",

        "offline":True

    }



    try:


        data = get_streamer_status(
            name
        )



        if data:


            result["title"] = data.get(
                "title",
                ""
            )


            result["game"] = data.get(
                "game_name",
                ""
            )


            result["viewer_count"] = data.get(
                "viewer_count",
                0
            )


            result["started_at"] = data.get(
                "started_at",
                ""
            )


            result["thumbnail_url"] = data.get(
                "thumbnail_url",
                ""
            )


            result["offline"] = data.get(
                "offline",
                True
            )



    except Exception as e:


        print(
            "[WEBAPP TWITCH ERROR]",
            e
        )



    return result
# ============================================================
# PREVIEW
# ============================================================

@router.get(
    "/preview/{name}"
)
async def preview(name: str):


    streamer = load_streamer(
        name
    )



    if not streamer:


        return JSONResponse(

            {
                "error":"not found"
            },

            status_code=404

        )





    twitch = get_twitch_preview(
        name
    )




    data = {


        "name":

            streamer.get(
                "name",
                name
            ),



        "url":

            f"https://twitch.tv/{name}",



        "title":

            twitch.get(
                "title",
                ""
            ),



        "game":

            twitch.get(
                "game",
                ""
            ),



        "viewer_count":

            twitch.get(
                "viewer_count",
                0
            ),



        "started_at":

            twitch.get(
                "started_at",
                ""
            ),



        "thumbnail_url":

            twitch.get(
                "thumbnail_url",
                ""
            ),



        "offline":

            twitch.get(
                "offline",
                True
            ),



        "old_title":

            streamer.get(
                "old_title",
                ""
            ),



        "old_game":

            streamer.get(
                "old_game",
                ""
            ),



        "duration":

            streamer.get(
                "duration",
                "0"
            ),



        "peak_viewers":

            streamer.get(
                "peak_viewers",
                0
            )

    }



    print(
        "[WEBAPP PREVIEW]",
        data
    )



    return JSONResponse(
        content=data
    )





# ============================================================
# STREAMERS LIST
# ============================================================

@router.get(
    "/streamers"
)
async def streamers():


    result = []



    for s in load_streamers():


        name = s.get(
            "name"
        )


        if not name:

            continue




        result.append(

            {

                "name": name,

                "file":

                    get_streamer_file(name).exists()

            }

        )



    return JSONResponse(
        content=result
    )






# ============================================================
# GET STREAMER
# ============================================================

@router.get(
    "/streamer/{name}"
)
async def get_streamer(name: str):


    streamer = load_streamer(
        name
    )


    if not streamer:


        return JSONResponse(

            {
                "error":"not found"
            },

            status_code=404

        )



    return JSONResponse(
        content=streamer
    )






# ============================================================
# SAVE
# ============================================================

def save_streamer(data):


    name = data.get(
        "name"
    )


    if not name:

        raise Exception(
            "name missing"
        )



    save_json(

        get_streamer_file(name),

        data

    )






# ============================================================
# UPDATE
# ============================================================

@router.post(
    "/streamer/{name}"
)
async def update_streamer(
    name: str,
    request: Request
):


    try:


        data = await request.json()



        if not isinstance(
            data,
            dict
        ):


            return JSONResponse(

                {

                    "ok": False,

                    "error":
                        "JSON must object"

                },

                status_code=400

            )



        data["name"] = name



        save_streamer(
            data
        )



        print(
            "[WEBAPP SAVED]",
            name
        )



        return JSONResponse(

            {

                "ok": True,

                "file":
                    f"{name}.json"

            }

        )



    except Exception as e:


        print(
            "[WEBAPP SAVE ERROR]",
            e
        )



        return JSONResponse(

            {

                "ok": False,

                "error":
                    str(e)

            },

            status_code=500

        )