```markdown
# 🤖 Hamon E-Commerce Telegram Bot

A production-ready Telegram bot built with **Python 3.11** and **Aiogram 3.x** for **Hamon E-Commerce**, providing seamless customer authentication, order tracking, and support automation for POS device management.

---

## ✨ Features

- 🔐 **Smart Authentication**
  - National ID verification
  - Entity-based authentication
  - Secure session persistence

- 📦 **Advanced Order Tracking**
  - Search by reception number
  - Search by device serial number
  - Real-time order status

- 💬 **Customer Support Hub**
  - POS device repair requests
  - Complaint submission system
  - Automated ticket routing

- 🛠️ **Admin Control Panel**
  - Real-time notifications
  - Maintenance mode toggle
  - Dynamic configuration

- ⚡ **Performance & Scale**
  - Redis-powered FSM & sessions
  - Async API client (aiohttp)
  - Docker-ready deployment
  - Built-in metrics

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- API server credentials

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/Amirelvx11/Hamon-E-Commerce-telegram-bot.git
cd Hamon-E-Commerce-telegram-bot

**2. Configure environment**
bash
cp .env.example .env
# Edit .env with your API credentials

**3. Launch with Docker**
bash
docker-compose up -d --build

**4. Verify**
bash
docker-compose logs -f bot

---

## 📁 Project Structure


Hamon-E-Commerce-telegram-bot/
│
├── src/
│   ├── config/          # Settings, enums, callback schemas
│   ├── core/            # Bot manager, Redis client, API client
│   ├── services/        # Business logic, notifications, API services
│   ├── handlers/        # Message, command & callback routers
│   └── utils/           # Keyboard factory, message templates, formatters
│
├── main.py              # Bot entrypoint
├── requirements.txt     # Dependencies
├── Dockerfile           # Container image
├── docker-compose.yml   # Orchestration
└── .env.example         # Config template

---

## ⚙️ Configuration

### Environment Setup

Create `.env` from template:

env
# Bot Core
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_CHAT_ID=123456789

# API Endpoints
SERVER_URL=https://api.hamon.com
AUTH_TOKEN=your_api_auth_token
SERVER_URL_NUMBER=https://api.hamon.com/order/by-number
SERVER_URL_SERIAL=https://api.hamon.com/order/by-serial
SERVER_URL_NATIONAL_ID=https://api.hamon.com/auth/by-national-id
SERVER_URL_COMPLAINT=https://api.hamon.com/complaint/submit
SERVER_URL_REPAIR=https://api.hamon.com/repair/submit

# Redis
REDIS_URL=redis://redis:6379/1
REDIS_PASSWORD=

# Contact
SUPPORT_PHONE=03133127
WEBSITE_URL=https://hamon.com

# Features
ENABLE_METRICS=true
ENABLE_DYNAMIC_CONFIG=true
MAINTENANCE_MODE=false

---

## 🐳 Docker Deployment

bash
# Start services
docker-compose up -d --build

# Monitor logs
docker-compose logs -f bot

# Restart bot
docker-compose restart bot

# Stop everything
docker-compose down

# Clean restart
docker-compose down -v && docker-compose up -d --build

---

## 🧪 Development

### Local Setup

bash
# Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install deps
pip install -r requirements.txt

# Run bot
python main.py

### Project Guidelines

- **Handlers**: `/src/handlers/` - Message/command routing
- **Services**: `/src/services/` - Business logic & API calls
- **Utils**: `/src/utils/` - Shared utilities & helpers
- **Config**: `/src/config/` - Settings, enums, constants

---

## 📊 Monitoring

### Available Features

- **Metrics**: Enabled via `ENABLE_METRICS=true`
- **Health**: Bot health monitoring
- **Admin Alerts**: Automatic notifications to `ADMIN_CHAT_ID`
- **Logs**: Structured logging (INFO/WARNING/ERROR/DEBUG)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Bot Framework** | Aiogram 3.x |
| **Runtime** | Python 3.11 |
| **State/Cache** | Redis 7.x |
| **HTTP Client** | aiohttp |
| **Container** | Docker |
| **Orchestration** | Docker Compose |

---

## 🔒 Security

- Environment-based secrets (zero hardcoded credentials)
- Redis authentication
- API token-based auth
- Session encryption
- Input validation & sanitization

---

## 📝 License

MIT License - see [LICENSE](LICENSE)

---

## 🤝 Contributing

We welcome contributions!

1. **Fork** this repo
2. **Create branch**: `git checkout -b feature/awesome-feature`
3. **Commit**: `git commit -m 'Add awesome feature'`
4. **Push**: `git push origin feature/awesome-feature`
5. **PR**: Open a Pull Request

### Standards
- Follow PEP 8
- Write clear commit messages
- Document functions
- Test before PR

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Amirelvx11/Hamon-E-Commerce-telegram-bot/issues)
- **GitHub**: [@Amirelvx11](https://github.com/Amirelvx11)
- **Telegram**: [@amir11](https://t.me/amir11)

---

## 🙏 Acknowledgments

- [Aiogram](https://docs.aiogram.dev/) - Modern Telegram Bot framework
- [Redis](https://redis.io/) - High-performance cache
- [Docker](https://www.docker.com/) - Container platform

---