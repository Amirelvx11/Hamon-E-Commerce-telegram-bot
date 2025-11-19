# 🤖 Telegram Bot Backend
A production-ready Telegram bot backend built with **Python 3.11** and **Aiogram 3.x**. This bot is designed for authentication, order tracking, and automating customer support tasks such as repair requests for POS machine devices and complaint submissions.

---



## Table of Contents

Here's how I've organized my README:
- [Features I Built](#features)
- [Perequisites](#Perequisites)
- [How to Install](#installation)
- [Configuration](#Configuration)
- [Run Locally](#Development)
- [File Structure](#File_Structure)
- [Monitoring](#Monitoring)
- [Tech Stack](#Tech_Stack)
- [Security](#Security)
- [My Toolkit](#My_Toolkit)
- [How to Contribute](#contributing)
- [Contact Us](#Connect_With_Me)
- [License Information](#license)

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



## 🛠️ Prerequisites
Want to get your Telegram Bot up and running fast? Just follow these easy steps, and you'll be chatting in no time!

### What You'll Need Before We Get Started

Before diving in, let's make sure you have everything you need. Think of these as the essential tools and credentials to get our application up and running:

*   **Docker and Docker Compose:** These are like special boxes that allow the application to run smoothly, without messing with the rest of your computer. It's like giving the app its own little playground! If you don't have these yet, you'll need to download and install them. Docker creates this isolated space, or "container", for the application.
*   **Telegram Bot Token:** This is your application's secret key to control your Telegram bot. You can get it by talking to BotFather on Telegram (find them here: https://t.me/botfather). It's like a password that lets the application send messages and do other cool things with your bot.
*   **API Server Login Info (like an auth token):** If the application needs to get information from another computer (an API server), you'll probably need a username and password, or maybe a special token. This is just to make sure you're allowed to use the server and access the data.
*   **A Good Internet Connection:** Since the application might need to download files or talk to other computers online, a stable internet connection is important. If you're having internet troubles, a VPN or Cloudflare proxy *could* help, but you probably won't need them.
---



## Installation

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

---



## ⚙️ Configuration

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

---



## 🧪 Development (Local Setup)

Let's get this project running on your own computer! This guide will walk you through setting everything up step-by-step.

First, we're going to create a special, isolated area for our project. It's called a "virtual environment" and it helps prevent conflicts with other Python projects you might have on your computer.

Open your computer's terminal or command prompt. Then, carefully follow these instructions:

```bash
# Create a virtual environment - Make sure you have Python 3.10 or higher installed.
python -m venv venv

# Activate the virtual environment.
source venv/bin/activate

# Install all the required packages.
pip install -r requirements.txt

# Now you're ready to go! Start the bot:
python main.py
```

That's all there is to it! Give it a try to make sure it works correctly. You should now have the project up and running locally. Have fun!

---



## My Project Structure

Here's a simple overview of how the code is structured. It's designed to be easy to navigate:

```
telegram-bot/
├── src/
│   ├── config/         # Configuration, enums, and callback definitions
│   ├── core/           # Core systems (session manager, cache, dispatcher build and etc)
│   ├── handlers/       # Aiogram routers for commands, callbacks, workflows
│   ├── models/         # Pydantic models for API responses, orders, sessions
│   ├── services/       # External API integration + Telegram notification service
│   ├── utils/          # Unified formatters, keyboard factory, helper functions
├── main.py             # Entrypoint — builds Dispatcher, starts polling/webhook
├── tests/              # Unit/integration tests (pytest configured)
├── bot.log             # Runtime logs
├── .env                # Enviroment Variables
├── docker-compose.yml  # Compose for Containerization
└── Dockerfile          # Dockerization
```

### File Organization

Let's take a closer look at how the project is organized! This will help you quickly find the files you need and understand where things are located.

*   **`src` Directory:** This is where all the important code lives. Think of it as the heart of the project; all the important logic lives here.
    *   **`Config`:** `/src/config/`
        *   `settings.py`: Loads environment variables and manages dynamic configuration reloading.
        *   `callbacks.py`: Contains structured `CallbackData` factories (like `MenuCallback`, `AuthCallback`, etc.). These help manage button presses(inline-buttons) in the Telegram bot.
        *   `enums.py`: Defines business-related enums (like `UserState`, `WorkflowSteps`, `ComplaintType`).  Enums help make the code more readable and prevent errors.
        *   **Purpose:** Defines environment configuration, constants, and all callback route signatures. It's where you set up how your bot behaves.
    *   **`Core`:** `/src/core/` - This directory contains the bot's engine, state management, dynamic configuration, HTTP client, and caching.
        *   `bot.py`: Builds the `Dispatcher`, loads routers, connects services, and manages the bot's lifecycle. This file is essential for starting and running the bot.
        *   `cache.py`: Manages the asynchronous Redis cache (for JSON serialization, stats, and invalidation). Caching makes the bot faster by storing frequently accessed data.
        *   `session.py`: Implements a Redis-backed `SessionManager` for handling FSM (Finite State Machine), authentication state, message tracking, rate limiting, and cleanup.  Sessions are crucial for managing conversations with users.
        *   `client.py`: Defines the HTTP client module for base client and server configurations and interactions.
        *   `dynamic.py`: Handles configuration reloading and runtime parameter updates from environment variables or an API. This allows you to change the bot's behavior without restarting it.
        *   **Purpose:** This is the central hub for bot initialization, state persistence, caching, and dynamic runtime control.
    *   **`Handlers`:** `/src/handlers/` - This directory contains the logic for handling different user interactions.
        *   `common_router.py`: Handles common commands like start, cancel, logout, and displaying the main menu.
        *   `auth_router.py`: Manages authentication using a national ID, displaying user info, and managing orders.
        *   `order_router.py`: Implements the order search and order detail flow.
        *   `support_router.py`: Handles complaint submissions and repair requests.
        *   **Purpose:** This is the routing layer, containing message/command/callback logic and business workflows. It determines how the bot responds to different user actions.
    *   **`Models`:** `/src/models/`
        *   `domain.py`: Defines the `Order` model, which is validated based on data from the API. Also includes `AuthResponse` and `SubmissionResponse` models.
        *   `user.py`: Defines the `UserSession` model for in-memory and Redis serialization. This stores user-specific data during a session.
        *   **Purpose:** Enforces strict Pydantic validation for API and state data. This helps ensure data consistency and prevents errors.
    *   **`Services`:** `/src/services/`
        *   `api.py`: Contains the `APIService` for calling configured endpoints(based on our methods) and parse the response and pass it to handlers, with proper error handling and exceptions.
        *   `notifications.py`: Handles Telegram notifications (order status, session expired, rate limit, broadcast messages and maintenance mode).
        *   **Purpose:** Manages all external interactions, including HTTP API calls(make request and parse response) and sending messages to Telegram.
    *   **`Utils`:** `/src/utils/`
        *   `formatters.py`: Provides functions for formatting user profiles, order lists/details into displayable text and also include repar and complaint request's submission response's.
        *   `keyboards.py`: Builds inline and reply keyboards with optional extra buttons, making it easier to create interactive bot interfaces.
        *   `validators.py`: Input validator module for order, nid and other text input's user send to bot.
        *   `messages.py`: Retrieves message templates based on keys - includes main and more often used messages.
        *   **Purpose:** This is a pure helper layer, containing formatting and UI elements that can be reused by handlers and services.

*   **`tests` Directory:**
    *   This directory holds all the tests that check if the code is working correctly. Testing is super important!
    *   You'll also find `pytest.ini` here. This file configures how the tests are run, so you can customize the testing process to fit your needs. 

*   **`main.py`:** This is the main entry point of the application. It's the first file that runs when you start the program. It's like the front door of the app – everything starts here!


---



## 📊 Monitoring

We're always keeping an eye on things to make sure everything is running smoothly! Here's how we monitor the bot:

*   **Basic Logging:** We keep a record of important events, like when the bot interacts with something or if an error pops up. We use labels like `INFO` (for general info), `WARNING` (for potential problems), and `ERROR` (for when something goes wrong).
*   **Health Checks:** We also have health checks to monitor active sessions and cache performance (how often the bot finds what it needs in its quick-access memory), use stats or admin commands within the bot to check its overall status. Just remember to set your admin chat ID in the `.env` file so you can use these features!
*   **Admin Alerts:** If something serious happens that could cause problems, the admins get notified immediately. This helps them jump in and fix things quickly.

---



## 🛠️ Tech Stack

Let's break down the tools and technologies that power this bot. Think of it as a peek under the hood!

| **Component**   | **Tool**          |
| :---------- | :------------ |
| Framework   | Aiogram 3.x   |
| Runtime     | Python 3.11   |
| Cache       | Redis 7.x     |
| HTTP Client | aiohttp       |
| Container   | Docker        |

*   **Framework:** We use Aiogram 3.x as the framework. It provides the structure and tools we need to build the Telegram bot. You can think of it as the foundation upon which the bot's features are built.
*   **Runtime:** The bot is powered by Python 3.11. Python is the language that lets us write instructions the bot can understand and follow. It's how we tell the bot what actions to perform.
*   **Cache:**  To help the bot remember things quickly, we use Redis 7.x. Redis is a super-fast data storage system. It allows the bot to quickly access frequently used information, making it more responsive.
*   **HTTP Client:** The bot uses `aiohttp` to communicate with other websites and services on the internet. It's like giving the bot its own web browser, allowing it to retrieve data or interact with online APIs.
*   **Container:**  We use Docker to package the bot and all its dependencies into a container.  This ensures the bot runs consistently, no matter where it's deployed.  It's like putting everything the bot needs into a neat package, so it works the same on any computer.



## 🔒 Security
Keeping your data safe is super important to us. Here's how we protect it:

*   **Environment Variables:** We store sensitive info (like secret passwords or keys) in a safe place called environment variables, so they're not directly in the code.
*   **Input Validation:** We carefully check all the information you send to the bot to make sure it's safe and prevent bad guys from trying to trick the bot.
*   **Session Encryption:** We scramble all the messages and data sent between you and the bot so no one can eavesdrop or steal your information.




## 🛠️ My Toolkit

**Languages:**
<p align="left">
 <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />

**DevOps:**
<p align="left">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions" />
</p>




## 🤝 Contributing

I welcome contributions! Here's how you can help improve my bot:

1. **Fork** my repository
2. Create your **Feature Branch** `git checkout -b feature/your-idea`
3. Commit your changes `git commit -m 'Add your feature'`
4. Push to branch `git push origin feature/your-idea`
5. Open a **Pull Request**

I review all PRs and appreciate your help!



## 🔗 Connect With Me
Got questions or need some help? No problem! Here's how you can reach out:

*   **Report Issues:** Use [![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Amirelvx11/Hamon-E-Commerce-telegram-bot/issues) - to report any bugs you find or ask questions.
*   **GitHub Profile:** [![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Amirelvx11) - Feel free to reach out directly!
*   **LinkedIn:** [![linkedin](https://img.shields.io/badge/linkedin-0A66C2?style=for-the-badge)](https://www.linkedin.com/in/amir-jamshidi-79b3a0337) - Connect with me on LinkedIn!



## 📝 License

I've released this project under the [MIT License](LICENSE.md).  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)