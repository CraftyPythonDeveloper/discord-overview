import logging
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

import requests
import pathlib
from openai import OpenAI
import tiktoken

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
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
WRK_DIR = pathlib.Path(__file__).parent.resolve()


# logging config
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(WRK_DIR, "bot.log"))
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False


DISCORD_AUTH = os.environ['DISCORD_TOKEN']

session = requests.Session()
headers["Authorization"] = DISCORD_AUTH
session.headers = headers

DISCORD_TOKEN = os.environ['DISCORD_TOKEN']

openai_client = OpenAI()
tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")


def get_messages(channel_id, before=60, limit=None):
    logger.debug(f"Getting messages for channel {channel_id} with timeframe {before} and limit of {limit}")
    api = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    all_messages = []

    ctime = datetime.now(timezone.utc)
    diff = ctime - timedelta(minutes=before)
    last_message_id = None
    temp_dict = []
    progress_bar = tqdm(total=None, desc='Retrieved 0 records', leave=True)
    while True:

        url = api + "?limit=100"
        if last_message_id:
            url = url + "&before=" + str(last_message_id)

        logger.debug(f"Requesting data {url}")
        response = session.get(url)

        if response.status_code == 401:
            logger.error(f"Received 401 error {url}")
            return

        if not response.ok:
            logger.error(f"Error, requesting data. Status code: {str(response.status_code)} {url}")
            return

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
            progress_bar.update()

        timestamp_dt = datetime.fromisoformat(last_timestamp)
        if (before and timestamp_dt < diff) or (limit and len(all_messages) > limit):
            logger.debug(f"Break condition meet {limit and len(all_messages) > limit} -- {before and timestamp_dt < diff}")
            break
        progress_bar.set_description(f'Retrieved {len(all_messages)} messages')
        progress_bar.update()
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
    cleaned_messages = "||".join(cleaned_messages)
    return cleaned_messages


def get_overview(message):
    completion = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "You are a chat summarization assist, skilled in reading chats happening in discord channels "
                        "and analysing each messages and providing a summary of the entire chat, so that i don't miss "
                        "out the important details in the chat. Please make sure "
                        "that you extract the important points from topics and give precise and insightful summary "
                        "of the chats whenever you see || treat it as a message seperator."},
            {"role": "user", "content": f"###chats : ''{message}''"}
        ],
    )
    logger.debug(f"Overview of the message is {completion.choices[0].message.content}")
    return completion.choices[0].message.content


if __name__ == "__main__":
    channel_id = input("Enter your channel ID: ")
    timeframe = int(input("Enter your timeframe in minutes: "))
    logger.info(f"Getting messages for past {timeframe} minutes")
    messages = get_messages(channel_id, before=timeframe)
    cleaned_msg = clean_discord_messages(messages)
    logger.info("Cleaned messages, getting overview of all the messages.")
    chunked_msg = []
    encoded_msg = tokenizer.encode(cleaned_msg)
    if len(encoded_msg) > 15_000:
        for i in range(0, len(encoded_msg), 15_000):
            chunked_msg.append(tokenizer.decode(encoded_msg[i:i+15_000]))
        logger.info(f"token size is {len(encoded_msg)}, and max token accepted by OpenAI is ~16000. Chunking the output")
    else:
        chunked_msg.append(cleaned_msg)

    overviews = []
    for chunk in chunked_msg:
        overview = get_overview(chunk)
        overviews.append(overview)

    print(overviews)

    with open(os.path.join(WRK_DIR, "output.txt"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(overviews))

    subprocess.run(["notepad", os.path.join(WRK_DIR, "output.txt")])

    logger.info("Script execution complete successfully and results saved to output.txt file.")
    input("Press any key to exit...")
