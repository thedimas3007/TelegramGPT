import asyncio
import openai
import sqlite3

from aiogram import Bot, Dispatcher, executor, types
from datetime import datetime
from logger import Logger
from typing import Dict, Union, List
from yaml import load, Loader

log = Logger()
config = load(open("config.yml"), Loader=Loader)
bot = Bot(config["bot_token"])
dp = Dispatcher(bot)
openai.api_key = config["openai_token"]

chats: Dict[int, list] = {}
escaped = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
commands = {
    "help": "Help message",
    "start": "Start message",
    "reset": "Clear current chat",
    "delete": "Delete last to messages",
    "regen": "Regenerate last message"
    # "sql": "Raw SQL command"
}


def chunks(lst: list, n: int) -> list:
    return list([lst[i:i + n] for i in range(0, len(lst), n)])


def escape(string: str, formatting=False) -> str:
    if formatting:
        for s in ["_", "*", "~", "`"]:
            try:
                escaped.remove(s)
            except ValueError:
                pass
    string = str(string)
    for c in escaped:
        string = string.replace(c, f"\\{c}")
    return string


@dp.message_handler(commands=["help"])
async def on_help(message: types.Message):
    text = ""
    for command, description in commands:
        text += f"/{command} - {description}\n"
    await message.answer(text)


@dp.message_handler(commands=["start"])
async def on_start(message: types.Message):
    await message.reply("Hello! I'm GPT4 client developed and maintained by @thed1mas")


@dp.message_handler(commands=["reset", "delete", "regen"])
async def on_wip(message: types.Message):
    await message.reply("Work in progress!")


@dp.message_handler()
async def on_message(message: types.Message):
    if message.get_command():
        return

    if message.from_id not in config["whitelist"]:
        await message.answer("Access denied!")

    if message.from_id not in chats.keys():
        chats[message.from_id] = []

    new = await message.answer("🧠 Starting generating...")
    log.info(f"Starting generation with from [bold]{message.from_user.id}[/] with prompt [bold]{message.text}[/]")
    try:
        start = datetime.now()
        chats[message.from_id].append({"role": "user", "content": message.text})
        response = await openai.ChatCompletion.acreate(
            model="gpt-4-1106-preview",
            # model="gpt-3.5-turbo",
            messages=chats[message.from_id]
        )
        spent = str(round((datetime.now() - start).total_seconds(), 2))
        tokens_total = response["usage"]["total_tokens"]
        tokens_prompt = response["usage"]["prompt_tokens"]
        # tokens_completion = response["usage"]["completion_tokens"]
        tokens_completion = tokens_total - tokens_prompt
        log.success(
            f"Generation of [bold]{message.get_args()}[/] finished. Used [bold]{tokens_total}[/] tokens. Spent [bold]{spent}s[/]")
        if tokens_completion == 0:
            await new.edit_text("📭 Model retuned nothing (zero-length text)")
        else:
            result = response["choices"][0]["message"]["content"]
            if len(result) > 4000:
                chunked = chunks(result, 4000)
                await new.edit_text(chunked[0])
                for chunk in chunked:
                    await new.answer(chunk)
            else:
                await new.edit_text(response["choices"][0]["message"]["content"])
        await message.answer(
            f"📊 Used tokens *{tokens_total}* \(*{tokens_prompt}* prompt, *{tokens_completion}* completion\)\n⌛ Time spent *{escape(spent)}s*",
            parse_mode="MarkdownV2")
        chats[message.from_id].append(response["choices"][0]["message"])
    except Exception as e:
        log.error(
            f"Caught exception [bold]{type(e).__name__}[/] ({'. '.join(e.args)}) on line [bold]{e.__traceback__.tb_lineno}[/]")
        await new.edit_text(f"❌ Error: `{type(e).__name__} ({'. '.join(e.args)})`", parse_mode="MarkdownV2")


def main():
    executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    main()
