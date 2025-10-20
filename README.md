# 🚀 Hamoon Telegram Bot

A production-ready Telegram bot for order tracking, authentication, and customer support.

## 📋 Quick Start (Local)

### Prerequisites
- Python 3.11+
- Redis (local or cloud)
- Telegram Bot Token from @BotFather

### Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/hamon-bot.git
cd hamon-bot

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN and other settings

# Start Redis (if not running)
# Option 1: Local Redis - start redis-server
# Option 2: Docker - docker run -d -p 6379:6379 redis:7-alpine

# Run the bot
python main.py

### 🐳 Docker Deployment (Recommended)

#### Single Container (Simple)
bash
# Build the image
docker build -t hamon-bot .

# Run with your .env
docker run -d --name hamon-bot --env-file .env --restart unless-stopped hamon-bot

#### With Docker Compose (Redis Included)
bash
# Start both bot and Redis
docker-compose up -d --build

# View logs
docker-compose logs -f bot

# Stop
docker-compose down

### 🌐 Production Deployment Options

#### Railway.app (Free Tier - Easiest)
1. Push to GitHub
2. Connect [railway.app](https://railway.app) to your repo
3. Add environment variables in Railway dashboard
4. Deploy! Railway auto-builds Docker

#### VPS (DigitalOcean/Linode)
bash
# On Ubuntu server
apt update && apt install docker.io docker-compose
git clone https://github.com/amirjamshidi-developer/Hamon-E-Commerce-telegram-bot
cd hamon-bot
docker-compose up -d --build

# Check status
docker-compose ps
docker-compose logs -f bot

#### Render.com
- Connect GitHub repo
- Set environment variables
- Deploy as Docker service

### 🔧 Environment Variables

Required:
- `TELEGRAM_BOT_TOKEN`: Your bot token
- `REDIS_URL`: Redis connection (default: `redis://localhost:6379/0`)

Optional:
- `MAINTENANCE_MODE`: Set to `true` for maintenance
- `MAX_REQUESTS_HOUR`: Rate limiting (default: 100)
- `SERVER_URL_*`: Your API endpoints

See `.env.example` for complete list.

### 🧪 Testing

#### Local Testing
bash
# Test environment
python test_env.py

# Test Redis  
python test_redis.py

# Run bot
python main.py

#### CI/CD
GitHub Actions automatically tests on every push:
- Python linting & formatting
- Unit tests execution
- Dependency verification

### 📊 Features

✅ **User Authentication** - National ID verification  
✅ **Order Tracking** - By number or serial  
✅ **Session Management** - Redis-powered sessions  
✅ **Rate Limiting** - Prevent abuse  
✅ **Error Handling** - Graceful failures  
✅ **Multi-language** - Persian/English support  
✅ **Admin Features** - Maintenance mode  

### 🛠️ Project Structure


hamon-bot/
├── main.py              # Bot entry point
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Redis + Bot setup
├── README.md          ← You're here!
├── modules/            # Core bot logic
│   ├── CoreConfig.py
│   ├── MessageHandler.py
│   ├── CallBackHandler.py
│   ├── DataProvider.py
│   └── SessionManager.py
├── tests/             # Unit tests
└── .github/workflows/ # CI/CD pipeline
└── test.yml

### 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### 📞 Support

- **Telegram**: @hamon_telegram_bot
- **Website**: https://hamoonpay.com

### 📄 License

MIT License - see `LICENSE` file for details.

---
