# Deployment Guide

This guide covers deploying the Voice AI Agent to production environments.

## Prerequisites

- Docker & Docker Compose (recommended)
- PostgreSQL 14+
- Redis 7+
- OpenAI API Key
- Vercel account (for frontend)

## Option 1: Docker Deployment (Recommended)

### Create Docker Compose File

Create `docker-compose.yml` in project root:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secure_password_here
      POSTGRES_DB: voice_agent_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:secure_password_here@postgres:5432/voice_agent_db
      REDIS_URL: redis://redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      HOST: 0.0.0.0
      PORT: 8000
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app

  frontend:
    build: ./
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
    depends_on:
      - backend

volumes:
  postgres_data:
```

### Create Backend Dockerfile

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (you'll need to generate this)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Initialize database and start server
CMD ["sh", "-c", "python setup_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### Create Frontend Dockerfile

Create `Dockerfile` in root:

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install

COPY . .
RUN pnpm build

FROM node:18-alpine

WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY package.json next.config.mjs ./

EXPOSE 3000

CMD ["npm", "start"]
```

### Deploy with Docker Compose

```bash
# Set environment variables
export OPENAI_API_KEY=your_key_here

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Option 2: Vercel Deployment (Frontend)

### Deploy Frontend to Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy
vercel
```

### Environment Variables in Vercel

Set in Vercel Project Settings:

```
NEXT_PUBLIC_API_URL=https://your-backend-domain.com
```

## Option 3: Railway/Render Deployment

### Using Railway

1. **Push to GitHub**:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin your-repo-url
git push -u origin main
```

2. **Create on Railway**:
   - Go to railway.app
   - Connect GitHub repository
   - Add PostgreSQL plugin
   - Add Redis plugin
   - Set environment variables
   - Deploy

### Environment Variables on Railway

```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
OPENAI_API_KEY=your_key
HOST=0.0.0.0
PORT=8000
```

## Option 4: AWS EC2 Deployment

### Setup EC2 Instance

```bash
# Connect to EC2
ssh -i your-key.pem ec2-user@your-instance-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3-pip nodejs npm postgresql redis-server

# Clone repository
git clone your-repo-url
cd your-repo

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup_db.py

# Start backend with systemd
sudo cp backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start voice-ai-backend
sudo systemctl enable voice-ai-backend

# Frontend setup
cd ..
npm install
npm run build

# Start frontend with systemd
sudo cp frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start voice-ai-frontend
sudo systemctl enable voice-ai-frontend
```

### Systemd Service Files

Create `backend.service`:

```ini
[Unit]
Description=Voice AI Agent Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/voice-ai/backend
Environment="PATH=/home/ubuntu/voice-ai/backend/venv/bin"
ExecStart=/home/ubuntu/voice-ai/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create `frontend.service`:

```ini
[Unit]
Description=Voice AI Agent Frontend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/voice-ai
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## SSL/TLS Setup with Let's Encrypt

### Using Nginx as Reverse Proxy

```bash
# Install Nginx
sudo apt install -y nginx

# Create config
sudo nano /etc/nginx/sites-available/voice-ai

# Content:
upstream backend {
    server localhost:8000;
}

upstream frontend {
    server localhost:3000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/voice-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## Monitoring & Logging

### Setup Logging

```bash
# Backend logs
journalctl -u voice-ai-backend -f

# Frontend logs
journalctl -u voice-ai-frontend -f

# Combined logs
journalctl -u voice-ai-backend -u voice-ai-frontend -f
```

### Health Checks

Create monitoring script:

```bash
#!/bin/bash
# check_health.sh

BACKEND_URL="https://your-domain.com/api/health"

response=$(curl -s -o /dev/null -w "%{http_code}" $BACKEND_URL)

if [ $response -ne 200 ]; then
  echo "Backend unhealthy (HTTP $response)"
  systemctl restart voice-ai-backend
else
  echo "Backend healthy"
fi
```

Add to crontab:
```
*/5 * * * * /home/ubuntu/check_health.sh
```

## Database Backup

### Automated PostgreSQL Backups

```bash
#!/bin/bash
# backup_db.sh

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

pg_dump -U postgres -h localhost voice_agent_db > "$BACKUP_DIR/backup_$DATE.sql"

# Keep only last 7 days
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
```

Add to crontab:
```
0 2 * * * /home/ubuntu/backup_db.sh
```

## Performance Optimization

### Database Optimization

```sql
-- Create indexes for faster queries
CREATE INDEX idx_appointments_user_id ON appointments(user_id);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_sessions_user_id ON conversation_sessions(user_id);
CREATE INDEX idx_history_session_id ON conversation_history(session_id);

-- Run VACUUM to maintain database
VACUUM ANALYZE;
```

### Redis Optimization

```
# In redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

## Troubleshooting

### Backend Won't Start

```bash
# Check logs
journalctl -u voice-ai-backend -n 50

# Test database connection
python -c "from app.database.connection import SessionLocal; db = SessionLocal(); print('Database connected')"

# Test OpenAI API
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

### Frontend Can't Connect to Backend

```bash
# Check CORS headers
curl -H "Origin: https://your-domain.com" http://localhost:8000/health

# Check firewall
sudo ufw allow 8000
sudo ufw allow 3000
```

### High Memory Usage

```bash
# Check Redis memory
redis-cli info memory

# Check PostgreSQL connections
psql -U postgres -c "SELECT * FROM pg_stat_activity;"

# Restart Redis to clear cache
sudo systemctl restart redis-server
```

## Scaling Considerations

For production with high traffic:

1. **Load Balancing**: Use Nginx or AWS ELB
2. **Database**: Upgrade to managed PostgreSQL (AWS RDS)
3. **Cache**: Use managed Redis (AWS ElastiCache)
4. **API Caching**: Implement response caching
5. **CDN**: Use CloudFront or Cloudflare
6. **Monitoring**: Set up CloudWatch or Datadog

## Security Checklist

- [ ] Use strong PostgreSQL passwords
- [ ] Enable SSL/TLS certificates
- [ ] Set CORS allowed origins appropriately
- [ ] Enable firewall (ufw/iptables)
- [ ] Keep dependencies updated
- [ ] Set up rate limiting
- [ ] Use environment variables for secrets
- [ ] Enable database backups
- [ ] Monitor error logs
- [ ] Set up alerting

## Rollback Procedure

```bash
# Get previous version
git log --oneline
git checkout <commit-hash>

# Rebuild and restart
docker-compose down
docker-compose up -d

# Or for systemd
systemctl restart voice-ai-backend voice-ai-frontend
```
