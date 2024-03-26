import json
import os
import pathlib
import re
import time
import logging
import functools
import typing
import asyncio
from datetime import datetime, timedelta, timezone

import requests
from discord.ext import commands
import discord
from openai import OpenAI
import tiktoken


headers = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'authorization': '',
    'sec-ch-ua': '"Brave";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 '
                  'Safari/537.36',
}
config = {"bot_token": "", "openai_key": "", "message_timeframe_minutes": "120", "user_auths": {}, "channels": {}}


WRK_DIR = pathlib.Path(__file__).parent.resolve()

# logging config
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(WRK_DIR, "bot.log"))
console_handler = logging.StreamHandler()
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

session = requests.Session()
session.headers = headers

intents: discord.Intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True, help_command=None)
CONFIG_FILEPATH = os.path.join(WRK_DIR, "auth.json")


def read_config():
    global config
    with open(CONFIG_FILEPATH, "r", encoding="utf-8") as fp:
        config = json.load(fp)
    logger.debug(f"Loaded config from {CONFIG_FILEPATH}")
    return True


def write_config():
    with open(CONFIG_FILEPATH, "w", encoding="utf-8") as fp:
        json.dump(config, fp, indent=2)
    logger.debug(f"Saved config to {CONFIG_FILEPATH}")
    return True


def get_response(url, auth):
    session.headers["Authorization"] = auth
    return session.get(url)


def to_thread(func: typing.Callable) -> typing.Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


@to_thread
def get_messages(channel_id, auth_token, limit=None, before=60):
    logger.debug(f"Getting messages for channel {channel_id} with timeframe {before} and limit of {limit}")
    api = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    all_messages = []

    ctime = datetime.now(timezone.utc)
    diff = ctime - timedelta(minutes=before)
    last_message_id = None
    temp_dict = []
    while True:

        url = api + "?limit=50"
        if last_message_id:
            url = url + "&before=" + str(last_message_id)

        logger.debug(f"Requesting data {url}")
        response = get_response(url, auth_token)

        if response.status_code == 401:
            logger.error(f"Received 401 error {url} auth_token {True if auth_token else False}")
            raise NotAuthorizedException

        if not response.ok:
            logger.error(f"Error, requesting data. Status code: {str(response.status_code)} {url}")
            raise AttributeError

        last_timestamp = None
        first_timestamp = None
        for message in response.json():
            if before and not first_timestamp:
                first_timestamp = message["timestamp"]
                fs_ts = datetime.fromisoformat(first_timestamp)
                if fs_ts < diff:
                    logger.info(f"No new messages since last {before} minutes.")
                    return
            all_messages.append(message["content"])
            last_timestamp = message["timestamp"]
            last_message_id = message["id"]
            temp_dict.append({"time": message["timestamp"], "content": message["content"]})

        timestamp_dt = datetime.fromisoformat(last_timestamp)
        if (before and timestamp_dt < diff) or (limit and len(all_messages) > limit):
            logger.debug(f"Break condition meet {limit and len(all_messages) > limit} -- {before and timestamp_dt < diff}")
            break
        time.sleep(0.5)

    logger.debug(f"Current timestamp {ctime} and last timestamp {last_timestamp} and diff is {diff}")
    return all_messages


def clean_discord_messages(messages):
    cleaned_messages = []
    for msg in messages:
        msg = re.sub(r"http\S+", "", msg)
        msg = re.sub(r"<@!?(\d+)>", "", msg)
        msg = re.sub(r"<#!?(\d+)>", "", msg)
        msg = re.sub(r"<@&(\d+)>", "", msg)
        msg = re.sub(r"<:\w*:\d+>", "", msg)
        msg = re.sub(r"[*_`~>]", "", msg)
        msg = re.sub(r"\s+", " ", msg)
        msg = msg.strip()
        msg = msg.replace("\n", " ")
        if msg:
            cleaned_messages.append(msg)
    return cleaned_messages


@to_thread
def get_overview(messages):
    encoded_msg = tokenizer.encode(messages)
    if len(encoded_msg) > 15_000:
        messages = tokenizer.decode(encoded_msg[:15_000])
        logger.info(f"token size is {len(encoded_msg)}, only taking latest 15000 tokens.")
    completion = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "You are a chat summarization assist, skilled in reading chats happening in discord channels "
                        "and analysing each messages and providing a summary of the entire chat, so that i don't miss "
                        "out the important details in the chat. Please make sure "
                        "that you extract the important points from topics and give precise and insightful summary "
                        "of the chats whenever you see || treat it as a message or chat seperator."},
            {"role": "user", "content": f"###chats : ''{messages}''"}
        ],
    )
    logger.debug(f"Overview of the message is {completion.choices[0].message.content}")
    return completion.choices[0].message.content


class NotAuthorizedException(Exception):
    """Exception raised for errors in the authorization process.
    """

    def __init__(self, message="Not Authorized!"):
        self.message = message
        super().__init__(self.message)


# create file if not exists
if not os.path.exists(CONFIG_FILEPATH):
    write_config()

read_config()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_APIKEY", config.get("openai_key"))
openai_client = OpenAI()
tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
BOT_TOKEN = os.getenv("BOT_TOKEN", config.get("bot_token"))


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    await bot.change_presence(status=discord.Status.online)


@bot.command(name="help")
async def bot_help(ctx):
    message = """
        **🤖 Bot Help Guide**
        
        Find below the list of available commands to interact with the bot:
        
        - `!help` 
          Display the help message with all available commands.
        
        - `!authorize <token>` Authorize your account by providing your account authorization token. This allows the 
        bot to access your channel messages. Be sure to add channel once token is added.
        
        - `!add_channel <channel_id> <channel_name>` Add a new channel to the list of channels the bot is monitoring. 
        Provide the channel's ID and assign a unique name to it.
        
        - `!summarize <channel_name> <timeframe: Optional>`
          Get a summary of the conversation from the specified channel. Timeframe is optional and defaults to 2 hrs.
        
        Please replace `<token>`, `<channel_id>`, and `<channel_name>` with your actual authorization token, the channel
        's ID, and the chosen name for your channel, respectively.
    """
    await ctx.send(message)


@bot.command(name="authorize")
async def authorize(ctx, token):

    if not token:
        return await ctx.send("Please provide your authorization token.")

    author = ctx.message.author.name
    config["user_auths"][author.lower()] = token
    write_config()
    read_config()
    logger.info(f"User Authorization Token added successfully for user {author}")

    await ctx.message.delete()
    await ctx.send("User Authorization Token added successfully!")


@bot.command(name="add_channel")
async def add_channel(ctx, channel_id, channel_name):

    if not channel_id or not channel_name:
        return await ctx.send("Please provide channel_id and channel_name.")

    config["channels"][channel_name.lower()] = channel_id
    write_config()
    read_config()
    logger.info(f"Channel added to the bot, ID: {channel_id} and name: {channel_name}")

    await ctx.send(f"Channel added to the bot. To get the summary of the chat use !summarize {channel_name.lower()}")


@bot.command(name="summarize")
async def summarize(ctx, channel_name, timeframe=None):

    if not channel_name:
        return await ctx.send("Please provide channel_name.")

    channel_id = config["channels"].get(channel_name.lower(), None)
    author = ctx.message.author.name.lower()
    if not channel_id:
        logger.warning(f"Channel id not found in config, user {author} needs to add the channel first.")
        return await ctx.send(f"channel with the name {channel_name} not added. Please type !help to see how to add "
                              f"channel to bot")

    async with ctx.typing():
        before = timeframe or config["message_timeframe_minutes"]
        before = int(before)
        auth_token = config["user_auths"].get(author)
        if not auth_token:
            logger.warning(f"Authorization token not found! user {author} needs to add the authorization token first.")
            return await ctx.send("Authorization token not found! Please add your authorization token first using "
                                  "!authorize command")

        logger.info(f"Getting summery for {channel_name} with id {channel_id}")
        await ctx.send(f"Let me read the messages past {before/60 :.0f} hrs from {channel_name} and create a summery!")

        try:
            messages = await get_messages(str(channel_id), auth_token=auth_token, before=before)
        except NotAuthorizedException:
            logger.error(f"User is not authorized to access this channel. {channel_id}")
            return await ctx.send(f"Seems like you don't have permission to read the messages from channel"
                                  f" {channel_name} or your token expired!")
        except AttributeError:
            logger.error(f"API returned unexpected response. {channel_id}")
            return await ctx.send(f"Something went wrong while reading the messages from {channel_name}, "
                                  f"try again or check the logs!")

        if not messages:
            logger.debug(f"No new messages past {before/60} hrs from {channel_name}!")
            return await ctx.send(f"No new messages past {before/60} hrs from {channel_name}!")

        cleaned_messages = clean_discord_messages(messages)
        text = "||".join(cleaned_messages)

        try:
            overview_message = await get_overview(text)
        except Exception as e:
            logger.error(f"Exception occurred while getting overview, {e}")
            return await ctx.send(f"Something went wrong while generating overview, please try again!")

        await ctx.send(overview_message)


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
