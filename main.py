import asyncio
import base64
import openai
import re
import sqlite3

from aiogram import Bot, Dispatcher, executor, types
from datetime import datetime
from io import BytesIO
from logger import Logger
from typing import Dict, Union, List
from yaml import load, Loader

log = Logger()
config = load(open("config.yml"), Loader=Loader)
bot = Bot(config["bot_token"])
dp = Dispatcher(bot)
openai.api_key = config["openai_token"]

system_message = None
chats: Dict[int, list] = {}
escaped = ['[', ']', '(', ')', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
commands = {
    "help": "Help message",
    "start": "Start message",
    "reset": "Clear current chat",
    "delete": "Delete last to messages",
    "regen": "Regenerate last message"
    # "sql": "Raw SQL command"
}

# model -> [in, out]
pricing = { 
    "gpt-4-vision-preview": [0.01, 0.03],
    "gpt-4-turbo-preview": [0.01, 0.03],
    "gpt-4": [0.03, 0.06],
    "gpt-4-32k": [0.06, 0.12],
    "gpt-3.5-turbo-0125": [0.0005, 0.0015], # better use this instead of just gpt-3.5-turbo
    "gpt-3.5-turbo-instruct": [0.0015, 0.0020]
}
model = "gpt-4-vision-preview"

def truncate_text(text, limit=50):
    if text is None:
        return None
    return text[:limit] + "..." if len(text) > limit else text


def chunks(lst: list, n: int) -> list:
    return list([lst[i:i + n] for i in range(0, len(lst), n)])


def to_html(markdown_text: str) -> str:
    html_text = markdown_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html_text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<b><i>\1</i></b>', html_text)  # bold and italic sim.
    html_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_text)  # bold
    html_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', html_text)  # italic
    
    def replace_code_blocks(match):
        language = match.group(1) or ''
        code = match.group(2)
        return f'<pre><code class="language-{language}">{code}</code></pre>'    
    html_text = re.sub(r'```(\w+)?\n(.*?)\n```', replace_code_blocks, html_text, flags=re.DOTALL)  # code block
    
    html_text = re.sub(r'`(.*?)`', r'<code>\1</code>', html_text)  # inline code

    html_text = re.sub(r'^> (.*?)$', r'<blockquote>\1</blockquote>', html_text, flags=re.MULTILINE)  # quote
    #html_text = re.sub(r'!\[(.*?)\]\((.*?)\)', r'<img src="\2" alt="\1">', html_text)
    html_text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html_text)  # link
    return html_text


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
    for command, description in commands.items():
        text += f"/{command} - {description}\n"
    await message.answer(text)


@dp.message_handler(commands=["start"])
async def on_start(message: types.Message):
    await message.reply("Hello! I'm GPT4 client developed and maintained by @thed1mas")


@dp.message_handler(commands=["delete", "regen"])
async def on_wip(message: types.Message):
    await message.reply("Work in progress!")


@dp.message_handler(commands=["reset"])
async def on_reset(message: types.Message):
    if message.from_id in chats.keys():
        chats[message.from_id] = []
    await message.reply("Message history has been cleared")


@dp.message_handler(content_types=["text", "photo"])
async def on_message(message: types.Message):
    if message.get_command():
        return

    if message.from_id not in config["whitelist"]:
        await message.answer("Access denied!")

    if message.from_id not in chats.keys():
        chats[message.from_id] = []
        if system_message is not None:
            chats[message.from_id].append({"role": "system", "content": system_message})

    new = await message.answer("🧠 Starting generating...")

    if len(message.photo):
        for photo in message.photo:
            buffer = BytesIO()
            await photo.download(destination_file=buffer)
            img_str = str(base64.b64encode(buffer.getvalue()), encoding="utf8")
            chats[message.from_id].append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                ]
            })

    if message.text:
        chats[message.from_id].append({"role": "user", "content": message.text})
    if message.caption:
        chats[message.from_id].append({"role": "user", "content": message.caption})

    log.info(f"Starting generation with from [bold]{message.from_user.id}[/] with prompt [bold]{truncate_text(message.text)}[/]")
    try:
        start = datetime.now()
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=chats[message.from_id],
            max_tokens=2048
        )
        spent = str(round((datetime.now() - start).total_seconds(), 2))
        tokens_total = response["usage"]["total_tokens"]
        tokens_prompt = response["usage"]["prompt_tokens"]
        tokens_completion = tokens_total - tokens_prompt
        price = round((tokens_prompt * pricing[model][0] + tokens_completion * pricing[model][1]) / 1000, 2)
        log.success(
            f"Generation of [bold]{truncate_text(message.text)}[/] finished. Used [bold]{tokens_total}[/] tokens. Spent [bold]{spent}s[/]")
        if tokens_completion == 0:
            await new.edit_text("📭 Model returned nothing (zero-length text)")
        else:
            result = to_html(response["choices"][0]["message"]["content"])
            if len(result) > 3500:
                chunked = chunks(result, 3500)
                await new.edit_text(chunked[0], parse_mode="html")
                for chunk in chunked[1:]:
                    await new.answer(chunk, parse_mode="html")
            else:
                await new.edit_text(result, parse_mode="html")
        await message.answer(
            f"📊 Used tokens *{tokens_total}* \(*{tokens_prompt}* prompt, *{tokens_completion}* completion\)\n" + \
            f"⌛ Time spent *{escape(spent)}s*\n" + \
            f"💸 Approximate price: *{price}$*",
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
