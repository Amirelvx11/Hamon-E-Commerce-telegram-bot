# 🤖 Telegram Bot Backend
A production-ready Telegram bot backend built with **Python 3.11** and **Aiogram 3.x**. This bot is designed for authentication, order tracking, and automating customer support tasks such as repair requests for POS machine devices and complaint submissions.

---



## ✨ Features

Here's what you can do with our app:

*   🔐 **Secure Login:** You can log in using your National ID. This works for both individuals and organizations.
*   📦 **Easy Order Tracking:** Keep an eye on your orders using either the reception number or the device serial number.
*   💬 **Submit Requests Easily:** You can easily submit complaints or repair requests directly through the app.
*   🛠️ **Admin Alerts:** Admins get notified about important stuff.
*   🔄 **Smooth Sessions:** We use Redis to manage your session and keep track of where you are in the process (like a simple state machine).
*   📊 **Metrics and Monitoring:** We track how things are going so we can make improvements.
*   🐳 **Ready to Go with Docker:** It's all set up to run in Docker, making deployment a breeze!

---




## 🚀 Quick Start

Want to get your Telegram Bot up and running fast? Just follow these easy steps, and you'll be chatting in no time!

*Let's get started!*



### What You'll Need Before We Get Started

Before diving in, let's make sure you have everything you need. Think of these as the essential tools and credentials to get our application up and running:

*   **Docker and Docker Compose:** These are like special boxes that allow the application to run smoothly, without messing with the rest of your computer. It's like giving the app its own little playground! If you don't have these yet, you'll need to download and install them. Docker creates this isolated space, or "container", for the application.
*   **Telegram Bot Token:** This is your application's secret key to control your Telegram bot. You can get it by talking to BotFather on Telegram (find them here: https://t.me/botfather). It's like a password that lets the application send messages and do other cool things with your bot.
*   **API Server Login Info (like an auth token):** If the application needs to get information from another computer (an API server), you'll probably need a username and password, or maybe a special token. This is just to make sure you're allowed to use the server and access the data.
*   **A Good Internet Connection:** Since the application might need to download files or talk to other computers online, a stable internet connection is important. If you're having internet troubles, a VPN or Cloudflare proxy *could* help, but you probably won't need them.



### Installation

Let's get this e-commerce Telegram bot up and running!

#### 1. Get the Code

First, you need to download the bot's code from GitHub to your computer. Open your terminal or command prompt and run these commands:

```bash
git clone https://github.com/Amirelvx11/Hamon-E-Commerce-telegram-bot.git
# Go to the bot's folder
cd Hamon-E-Commerce-telegram-bot
```

This will download the code and take you inside the project's folder.

#### 2. Set Up Your Settings

Next, we need to tell the bot about your Telegram account, server, and other important stuff. We do this by creating a `.env` file.

```bash
cp .env.example .env
```

This command copies the example settings file to a new file called `.env`. Now, open the `.env` file with a text editor and fill in the blanks with your own information.

#### Note:  Put in Your Own Info!

Make sure to edit the `.env` file with your actual Telegram token, authentication token, server URL, and Redis URL. This is how the bot knows who you are and where to connect.

#### 3. Start the Bot with Docker

We'll use Docker to easily run the bot. If you don't have Docker installed, please install it first. Then, run this command:

```bash
docker-compose up -d --build
```

This command builds the bot (if it's the first time) and starts it in the background. The `-d` flag means "detached," so it runs without tying up your terminal.

#### 4. See What's Happening

To check if the bot is running correctly, you can view the logs:

```bash
docker-compose logs -f bot
```

This command shows you the bot's log messages in real-time. If you see any errors, this is the place to start troubleshooting.




### 📁 Project Structure

Let's take a peek inside the `src/` folder to see how everything is organized. Think of it like the different rooms in a house, each with a special job!

- `config/`: This folder is like the bot's settings panel. It holds all the important settings and configs, special lists (we call them "enums"), and callback functions using aiogram callback, so the bot knows exactly how to behave. It's like the instruction manual for your bot.
- `core/`: This is where the real magic happens! Inside, you'll find the Bot Manager (the thing that keeps the bot running smoothly), the connection to Redis (a super-speedy database), Session and Cache Manager, API client (which lets the bot talk to other services) and also manages configurations, loading them dynamically from files or using default settings.
- `services/`: This folder is all about communication. It contains the code that lets the bot talk to other programs (like APIs) and send out notifications. It's how the bot gets information, shares it with users in Telegram, and even alerts the admins!
- `handlers/`: Think of this as the bot's brain. It figures out what to do with every message and button press (callback) it receives. Then, it sends the information to the right services, formats it nicely for the user, and more.
- `utils/`: This folder is like a toolbox filled with helpful gadgets. You'll find reusable tools and templates that are used throughout the project, like message builders, formatters, keyboard tools for creating interactive buttons (both inline and reply keyboards), and even a validator to make sure everything is correct.



### ⚙️ Configuration

Let's set up the important stuff! This section guides you through configuring the app using environment variables. Think of these like settings that tell the app how to behave.

#### Required Environment Variables

You'll need to create a `.env` file in the project's root directory and fill it with the following:

```
# Get your bot's token from BotFather on Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
```

#### API Endpoints

These settings define where the app connects to for various services. If you're using your own server or API, you'll need to configure these. Also, if you have any other server or program for API calls, define the tokens or passwords inside this section.

```
AUTH_TOKEN=your_chat_id

API_BASE_URL=https://api.example.com
SERVER_URL=https://api.example.com
SERVER_URL_NATIONAL_ID=https://api.example.com/nid
SERVER_URL_NUMBER=https://api.example.com/order/number
SERVER_URL_SERIAL=https://api.example.com/order/serial
SERVER_URL_COMPLAINT=https://api.example.com/order/complaint
SERVER_URL_REPAIR=https://api.example.com/order/repair
```

#### Redis Configuration

Redis is used for caching and session management. Here's how to configure its connection:

```
REDIS_URL = redis://127.0.0.1:6379/0
REDIS_PASSWORD=your_password
```

#### Feature Flags

These flags allow you to enable or disable certain features:

```
MAINTENANCE_MODE=false
ENABLE_METRICS=true
ENABLE_DYNAMIC_CONFIG=true
```

### Contact Information (Support)

Need help? Here's how to reach us:

```
SUPPORT_PHONE=your_support_phone
WEBSITE_URL=your_website_url
```

### Optional Settings (with Defaults)

These settings have default values, but you can customize them to fit your needs:

```
# Default values - feel free to adjust!

MAX_SESSIONS=3
SESSION_TIMEOUT=60 # in seconds
MAX_REQUESTS_DAY=1000
MAX_REQUESTS_HOUR=100
CACHE_SIZE=1000
CACHE_TTL=300 # in seconds
```



### 🐳 Docker Commands

These commands help you manage the bot using Docker. Make sure you have Docker and Docker Compose installed.

```bash
# Start the bot
docker-compose up -d --build
```
This command builds the bot's Docker image (if it's the first time) and starts it in the background.

```bash
# View logs
docker-compose logs -f bot
```
See what the bot is doing in real-time. This is helpful for debugging or just checking that everything is running smoothly.

```bash
# Restart the bot
docker-compose restart bot
```
If the bot isn't working correctly, this command restarts it.

```bash
# Clean restart (rebuilds the images)
docker-compose down -v && docker-compose up -d --build
```
This command stops and removes the existing containers and volumes (`docker-compose down -v`), then rebuilds the Docker image and starts the bot again (`docker-compose up -d --build`). Use this if you've made changes to the bot's code or configuration.



### 🧪 Development
#### Local Setup

Let's get this project up and running on your computer! Here's a simple guide to setting things up:

First, we'll create a special, isolated space for our project to live in. This is called a virtual environment. It helps keep our project's dependencies separate from other Python projects on your system. Open your terminal or command prompt and follow these steps:

```bash
# Create a virtual environment (named 'venv' here)
python -m venv venv

# Activate the virtual environment (this tells your terminal to use this environment)
source venv/bin/activate

# Install all the necessary packages (listed in the 'requirements.txt' file)
pip install -r requirements.txt

# Now, you're all set! Run the bot:
python main.py
```

**Explanation:**

*   `python -m venv venv`: This command creates a new virtual environment in a folder named `venv`. You can name it something else if you like!
*   `source venv/bin/activate`: This command activates the virtual environment.  You'll usually see the environment name (like `(venv)`) at the beginning of your terminal prompt to show you it's active.
*   `pip install -r requirements.txt`:  This command uses `pip` (the Python package installer) to install all the libraries and tools listed in the `requirements.txt` file. These are the things our project needs to run.
*   `python main.py`: This command finally starts the bot!

That's it! You should now have the project running locally.



### File Organization

Let's break down the project's file structure. This helps you quickly find what you're looking for!

*   **`src` Directory:** This is where all the main code lives.
    *   **`Config`:**  `/src/config/` - Contains configuration files. Think of these as settings for your app.
    *   **`Core`:** `/src/core/` - Holds the essential, fundamental code that makes the application run. 
    *   **`Handlers`:** `/src/handlers/` - Manages different parts of the app, like dealing with user requests or events.
    *   **`Services`:** `/src/services/` - Contains reusable components that do specific jobs, like connecting to a database or sending emails.
    *   **`Utils`:** `/src/utils/` -  Helpful utility functions or classes that are used throughout the project. They perform common tasks.

*   **`tests` Directory:**
    *   This directory contains all the test modules that verify if the code works as expected. You'll also find `pytest.ini` here, which configures how the tests run.

*   **`main.py`:** This is the main entry point of the application.  It's the first file that runs when you start the program.



### 📊 Monitoring
We're always watching to make sure everything is running smoothly. Here's how we do it:

*   **Basic Logging:** We keep a record of important things that happen, like when something works or when there's an error. We use simple labels like `INFO` for good things and `ERROR` for problems.
*   **Admin Alerts:** If something really bad happens, like a major error that could break things, the admins get a message right away so they can fix it.
*   **Health Checks:** You can check if the bot is working correctly by visiting a special link (also known as an API endpoint). It's like taking the bot's pulse to see if it's healthy.

### 🛠️ Tech Stack
Here's a simple explanation of the tools and technologies we use to build and run this bot:

| Component   | Tool          |
| :---------- | :------------ |
| Framework   | Aiogram 3.x   |
| Runtime     | Python 3.11   |
| Cache       | Redis 7.x     |
| HTTP Client | aiohttp       |
| Container   | Docker        |

*   **Framework:** Aiogram is what we use to create the Telegram bot's structure and features. Think of it as the bot's building blocks.
*   **Runtime:** Python is the programming language the bot uses to understand instructions and do its job. It's how we tell the bot what to do.
*   **Cache:** Redis is a super-fast way to store and grab data. It helps the bot remember things quickly so it doesn't have to look them up every time.
*   **HTTP Client:** aiohttp is like a web browser for the bot. It lets the bot talk to other websites and online services to get information or do things.
*   **Container:** Docker packages everything the bot needs into one neat little box, so it can run smoothly on any computer without problems.

### 🔒 Security
Keeping your data safe is super important to us. Here's how we protect it:

*   **Environment Variables:** We store sensitive info (like secret passwords or keys) in a safe place called environment variables, so they're not directly in the code.
*   **Input Validation:** We carefully check all the information you send to the bot to make sure it's safe and prevent bad guys from trying to trick the bot.
*   **Session Encryption:** We scramble all the messages and data sent between you and the bot so no one can eavesdrop or steal your information.

### 📝 License
This project is open-source, which means it's available for anyone to use, change, and share, under the MIT License. You can find the full details in the `LICENSE` file.

### 🤝 Contributing
Want to help us make the bot even better? Awesome! Here's how you can contribute:

*   **Fork:** Create your own copy of the project (called a "fork") on GitHub.
*   **Branch:** Make a new branch in your forked copy where you'll make your changes. This keeps your changes separate from the main project until they're ready.
*   **Pull Request:** When you're done with your changes, submit a "pull request" to the main project. This lets us review your changes and merge them into the main bot.

To make sure your code is a good fit, please follow these guidelines:

*   Follow PEP 8 style guidelines (this makes the code look neat and consistent).
*   Include tests (to make sure your changes work as expected and don't break anything).
*   Write clear documentation (so other developers can understand what your code does and how it works).

### 📞 Support
Need help or have questions? We're here for you!

*   **Issues:** [GitHub Issues](https://github.com/Amirelvx11/Hamon-E-Commerce-telegram-bot/issues) - Report bugs or ask questions here.
*   **GitHub:** [@Amirelvx11](https://github.com/Amirelvx11) - You can also reach out to me directly on GitHub.