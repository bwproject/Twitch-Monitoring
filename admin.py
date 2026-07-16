# admin.py (fixed pathlib + per streamer json)

import json
from pathlib import Path

from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext


# ============================================================
#   PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
STREAMERS_FILE = BASE_DIR / "streamers.json"


# ============================================================
#   Работа с файлами
# ============================================================

def get_streamer_file(name: str) -> Path:
    return BASE_DIR / f"{name}.json"


def load_streamers():
    if not STREAMERS_FILE.exists():
        return []

    try:
        with STREAMERS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        result = []

        for streamer in data:
            name = streamer.get("name")

            if not name:
                continue

            streamer_file = get_streamer_file(name)

            if streamer_file.exists():
                try:
                    with streamer_file.open("r", encoding="utf-8") as sf:
                        custom = json.load(sf)

                    if isinstance(custom, dict):
                        result.append(custom)
                        continue

                except Exception as e:
                    print(f"[ADMIN] read {streamer_file.name}: {e}")

            result.append(streamer)

        return result

    except Exception:
        return []


def save_streamer(streamer):
    try:
        streamer_file = get_streamer_file(streamer["name"])

        with streamer_file.open("w", encoding="utf-8") as f:
            json.dump(
                streamer,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:
        print(f"[ADMIN] save_streamer error: {e}")


# ============================================================
#   FSM
# ============================================================

class EditStreamMessages(StatesGroup):
    editing_start = State()
    editing_title_change = State()
    editing_game_change = State()
    editing_end = State()


# ============================================================
#   HANDLERS
# ============================================================

def register_admin_handlers(dp):


    # ---------------------------------------------------------
    # /streamerslist
    # ---------------------------------------------------------
    @dp.message(Command("streamerslist"))
    async def cmd_streamerslist(message: types.Message):

        if not STREAMERS_FILE.exists():
            await message.answer(
                "streamers.json не найден."
            )
            return


        try:
            with STREAMERS_FILE.open(
                "r",
                encoding="utf-8"
            ) as f:
                streamers = json.load(f)

        except Exception as e:
            await message.answer(
                f"Ошибка чтения streamers.json:\n{e}"
            )
            return


        if not isinstance(streamers, list) or not streamers:
            await message.answer(
                "В streamers.json нет стримеров."
            )
            return


        lines = [
            "<b>📺 Список стримеров</b>\n"
        ]


        for streamer in streamers:

            name = streamer.get("name")

            if not name:
                continue


            streamer_file = get_streamer_file(name)


            if streamer_file.exists():

                status = "✅ отдельный файл"

            else:

                status = "📄 только streamers.json"


            lines.append(
                f"<b>{name}</b> — {status}"
            )


        await message.answer(
            "\n".join(lines),
            parse_mode="HTML"
        )
        
    # ---------------------------------------------------------
    # /edit
    # ---------------------------------------------------------
    @dp.message(Command("edit"))
    async def cmd_edit(message: types.Message, state: FSMContext):
        streamers = load_streamers()

        user_streamers = [
            s for s in streamers
            if s.get("tg_id") == message.from_user.id
        ]

        if not user_streamers:
            await message.answer(
                "У вас нет каналов для редактирования."
            )
            return

        await state.update_data(
            streamers=user_streamers,
            index=0
        )

        streamer = user_streamers[0]

        await message.answer(
            f"Вы редактируете: {streamer['name']}\n"
            f"START:\n"
            f"{streamer['messages']['start']}\n\n"
            f"Введите новое или /skip"
        )

        await state.set_state(
            EditStreamMessages.editing_start
        )
    # ---------------------------------------------------------
    @dp.message(EditStreamMessages.editing_start, F.text)
    async def edit_start(message: types.Message, state: FSMContext):
        data = await state.get_data()

        streamers = data["streamers"]
        idx = data["index"]

        streamer = streamers[idx]

        if message.text != "/skip":
            streamer["messages"]["start"] = message.text

        await message.answer(
            f"TITLE_CHANGE:\n"
            f"{streamer['messages']['title_change']}\n\n"
            f"Введите новое или /skip"
        )

        await state.set_state(
            EditStreamMessages.editing_title_change
        )


    # ---------------------------------------------------------
    @dp.message(EditStreamMessages.editing_title_change, F.text)
    async def edit_title_change(message: types.Message, state: FSMContext):
        data = await state.get_data()

        streamers = data["streamers"]
        idx = data["index"]

        streamer = streamers[idx]

        if message.text != "/skip":
            streamer["messages"]["title_change"] = message.text

        await message.answer(
            f"GAME_CHANGE:\n"
            f"{streamer['messages']['game_change']}\n\n"
            f"Введите новое или /skip"
        )

        await state.set_state(
            EditStreamMessages.editing_game_change
        )


    # ---------------------------------------------------------
    @dp.message(EditStreamMessages.editing_game_change, F.text)
    async def edit_game_change(message: types.Message, state: FSMContext):
        data = await state.get_data()

        streamers = data["streamers"]
        idx = data["index"]

        streamer = streamers[idx]

        if message.text != "/skip":
            streamer["messages"]["game_change"] = message.text

        await message.answer(
            f"END:\n"
            f"{streamer['messages']['end']}\n\n"
            f"Введите новое или /skip"
        )

        await state.set_state(
            EditStreamMessages.editing_end
        )


    # ---------------------------------------------------------
    @dp.message(EditStreamMessages.editing_end, F.text)
    async def edit_end(message: types.Message, state: FSMContext):
        data = await state.get_data()

        streamers = data["streamers"]
        idx = data["index"]

        streamer = streamers[idx]

        if message.text != "/skip":
            streamer["messages"]["end"] = message.text


        # =====================================================
        # Сохранение теперь в nik.json
        # =====================================================

        save_streamer(streamer)


        await message.answer(
            f"Сохранено: {streamer['name']}"
        )


        # следующий стример
        idx += 1

        if idx < len(streamers):

            await state.update_data(
                index=idx
            )

            next_s = streamers[idx]

            await message.answer(
                f"Вы редактируете: {next_s['name']}\n"
                f"START:\n"
                f"{next_s['messages']['start']}\n\n"
                f"Введите новое или /skip"
            )

            await state.set_state(
                EditStreamMessages.editing_start
            )

        else:

            await state.clear()

            await message.answer(
                "Редактирование завершено."
            )


    # ---------------------------------------------------------
    # /test
    # ---------------------------------------------------------
    @dp.message(Command("test"))
    async def cmd_test(message: types.Message):

        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            await message.reply(
                "Использование: /test ИМЯ"
            )
            return


        name = parts[1].strip().lower()

        streamers = load_streamers()


        streamer = next(
            (
                s for s in streamers
                if s["name"].lower() == name
            ),
            None
        )


        if not streamer:
            await message.reply(
                "Стример не найден."
            )
            return


        url = f"https://twitch.tv/{streamer['name']}"

        preview = streamer.get(
            "preview",
            True
        )


        msgs = [
            streamer["messages"]["start"].format(
                name=streamer["name"],
                title="T",
                game="G",
                url=url
            ),

            streamer["messages"]["title_change"].format(
                name=streamer["name"],
                old_title="A",
                title="B",
                url=url
            ),

            streamer["messages"]["game_change"].format(
                name=streamer["name"],
                old_game="A",
                game="B",
                url=url
            ),

            streamer["messages"]["end"].format(
                name=streamer["name"],
                title="T",
                duration="1ч",
                peak_viewers=100,
                url=url
            ),
        ]


        for m in msgs:
            await message.answer(
                m,
                parse_mode="HTML",
                disable_web_page_preview=not preview
            )
    # ---------------------------------------------------------
    # /notify
    # ---------------------------------------------------------
    @dp.message(Command("notify"))
    async def cmd_notify(message: types.Message):

        streamers = load_streamers()

        tg_id = message.from_user.id


        streamer = next(
            (
                s for s in streamers
                if s.get("tg_id") == tg_id
            ),
            None
        )


        if not streamer:
            await message.reply(
                "Нет стримеров."
            )
            return


        lines = [
            f"<b>{streamer['name']}</b>\n"
        ]


        for ch in streamer["channels"]:

            cid = str(ch["chat_id"])


            if cid == "-4558073157":

                lines.append(
                    f"{cid} (protected)"
                )

                continue


            lines.append(
                f"{cid}:\n"
                f"start: {ch.get('notify_start', True)}\n"
                f"title: {ch.get('notify_title_change', True)}\n"
                f"game: {ch.get('notify_game_change', True)}\n"
                f"end: {ch.get('notify_end', True)}\n"
            )


        await message.answer(
            "\n".join(lines),
            parse_mode="HTML"
        )



    # ---------------------------------------------------------
    # /notify_set
    # ---------------------------------------------------------
    @dp.message(Command("notify_set"))
    async def cmd_notify_set(message: types.Message):

        parts = message.text.split()


        if len(parts) != 4:

            await message.reply(
                "Использование: /notify_set chat_id field true/false"
            )

            return



        _, chat_id, field, value = parts



        if value.lower() not in (
            "true",
            "false"
        ):

            await message.reply(
                "true/false"
            )

            return



        value = value.lower() == "true"



        allowed = {
            "notify_start",
            "notify_title_change",
            "notify_game_change",
            "notify_end",
        }



        if field not in allowed:

            await message.reply(
                "bad field"
            )

            return



        streamers = load_streamers()

        tg_id = message.from_user.id



        streamer = next(
            (
                s for s in streamers
                if s["tg_id"] == tg_id
            ),
            None
        )



        if not streamer:

            await message.reply(
                "no streamer"
            )

            return



        channel = next(
            (
                c for c in streamer["channels"]
                if str(c["chat_id"]) == chat_id
            ),
            None
        )



        if not channel:

            await message.reply(
                "not found"
            )

            return



        if chat_id == "-4558073157":

            await message.reply(
                "protected"
            )

            return



        channel[field] = value



        # =====================================================
        # сохраняем в ben25890.json
        # =====================================================

        save_streamer(streamer)



        await message.reply(
            f"ok {field}={value}"
        )
