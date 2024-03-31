# Business Listing Scraper

### Currently Supported sites are: [Brownbook](https://www.brownbook.net/) <br>

This repo is about scraping data from discord subscribed channels and providing the overview of entire chat using **Python**  and **openai**.
<br><br> This includes below-mentioned features.
* Take channel id as input and scrape all the chats based on the timeframe defined (defaults to 120 minutes).
* Once scraped use openai to get the overview of the chat.
* This also includes a discord bot which can be used to interact with the script using bot

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Support](#support)
- [Contributing](#contributing)

## Installation

* Make sure python is installed and accessable through terminal/cmd by typing ```python --version``` or ```python3 --version```
* (Optional step) Create virtual environment by following tutorial on [How to install virtual environment](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
* Clone the repo locally using ```git clone https://github.com/CraftyPythonDeveloper/discord-overview```
* ```cd discord-overview```
* Install requirements ```pip install -r requirements.txt```
* Rename .env.example to .env
* Get the discord authorization key, follow below steps to get it.
    *  Login to discord from web.
    *  Open developers tool or press F12
    *  Go to networks tab and click on url which ends with limit=50
    *  Then in the headers find the authorization key.
* Once you have the authorization key add it to .env file.  

## Usage

To run the script follow the below-mentioned steps:

- Run the below command to run the script locally.
- ``python main.py``


To Run the discord bot

- open the auth.json and add your bot_token, openai_api_key.
- Then run the ``python bot.py`` to run the bot.
- Then invite the bot to your server and use !help to check the usage help. 

## Support

- If you face any issue or bug, you can create an issue describing the error message and steps to reproduce the same error, with log file attached.

Please [open an issue](https://github.com/CraftyPythonDeveloper/discord-overview/issues/new) for support.

## Contributing

Please contribute by create a branch, add commits, and [open a pull request](https://github.com/CraftyPythonDeveloper/discord-overview/pulls).
