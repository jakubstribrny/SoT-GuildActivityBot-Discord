# SoT-GuildActivityBot

A Discord bot designed for Sea of Thieves guild management, featuring automated activity tracking, temporary voice channel creation, and a progression system based on playtime. Built as a hobby project to track and reward guild member engagement.

## 🎮 About

This bot was created to manage a Sea of Thieves gaming guild, automating member activity tracking and incentivizing participation through a level-based reward system. It runs 24/7 on a Linux server, continuously monitoring player activity and managing guild operations.

## ✨ Features

### 📊 Activity Tracking
- **Reaction-based time tracking** - Members start/stop activity sessions using emoji reactions (▶️/⏹️)
- **Persistent session storage** - All play sessions stored in MySQL database
- **Bi-weekly leaderboards** - Automated ranking tables posted every 2 weeks
- **Anti-cheat monitoring** - Alerts for suspicious sessions (10+ hours)

### 🎙️ Voice Channel Management
- **Dynamic channel creation** - Members can create their own temporary voice channels
- **Auto-cleanup** - Channels automatically deleted when empty
- **Custom permissions** - Channel creators get management rights

### 🏆 Progression System
- **10-tier level system** (Úroveň 0-9) based on total playtime
- **Automatic role assignment** - Roles updated as members reach milestones
- **Progress tracking** - `/stats` command shows current level and time until next rank
- **Public announcements** - Level-up celebrations in dedicated channel

### 👥 Member Management
- **Auto-role assignment** - New members automatically receive "Sailor" role
- **Welcome messages** - Customized greetings for new pirates
- **Database cleanup** - Removes data when members leave the server

## 📋 Requirements

- Python 3.8+
- MySQL Server
- Discord Bot Token

### Python Dependencies
```
discord.py
mysql-connector-python
```

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/SoT-GuildActivityBot.git
cd SoT-GuildActivityBot
```

### 2. Install Dependencies
```bash
pip install discord.py mysql-connector-python
```

### 3. Configure API Keys
Create an `apikeys.py` file in the project root:
```python
BOTTOKEN = "your_discord_bot_token_here"
```

### 4. Database Setup
Create a MySQL database and tables:
```sql
CREATE DATABASE your_database_name;

USE your_database_name;

CREATE TABLE sail_times (
    user BIGINT PRIMARY KEY,
    recent INT DEFAULT 0,
    2weeks INT DEFAULT 0,
    total INT DEFAULT 0
);

CREATE TABLE temp_channels (
    channel_id BIGINT,
    channel_name VARCHAR(255),
    creator_id BIGINT PRIMARY KEY
);
```

### 5. Update Database Credentials
Edit the `connect_to_mysql()` function in `main.py`:
```python
db_connection = mysql.connector.connect(
    host="your_host",
    user="your_username",
    password="your_password",
    database="your_database",
    connect_timeout=connection_timeout,
    auth_plugin='mysql_native_password'
)
```

### 6. Configure Channel & Role IDs
Update the hardcoded Discord IDs throughout the code to match your server:
- Channel IDs (welcome, activity, stats, etc.)
- Role IDs (Sailor, admin roles, level roles)
- Guild ID

## 🐧 Running on Linux Server (24/7)

### Using screen (Recommended for hobby projects)
```bash
screen -S discord-bot
python3 main.py
# Detach with: Ctrl+A then D
# Reattach with: screen -r discord-bot
```

### Using systemd (Production)
Create `/etc/systemd/system/sot-bot.service`:
```ini
[Unit]
Description=Sea of Thieves Guild Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/SoT-GuildActivityBot
ExecStart=/usr/bin/python3 /path/to/SoT-GuildActivityBot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable sot-bot
sudo systemctl start sot-bot
sudo systemctl status sot-bot
```

View logs:
```bash
journalctl -u sot-bot -f
```

## 📝 Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `/sail` | Create activity tracking embed | Admin only |
| `/stats` | View personal statistics and level progress | Guildmate role |
| `/vypsat_tabulku` | Display bi-weekly activity leaderboard | Admin only |
| `/navod_na_aktivitu` | Show activity tracking tutorial | Admin only |
| `/end_all_sails` | Force-end all active sessions | Admin only |
| `/remove_left_users` | Clean up database (removes left members) | Admin only |
| `/export_user_ids` | Export user data to text file | Admin only |

## 🎯 How It Works

1. **Member joins server** → Automatically assigned "Sailor" role + welcome message
2. **Member clicks ▶️** → Bot starts tracking their play session
3. **Member clicks ⏹️** → Bot calculates duration, stores in database
4. **Background task** → Monitors for suspicious sessions (10+ hours)
5. **Bi-weekly** → Admin runs `/vypsat_tabulku` to display rankings
6. **Automatic** → Bot checks for level-ups and assigns new roles

## 🏅 Level System

| Level | Required Time | Seconds |
|-------|---------------|---------|
| Úroveň 0 | 0h | 0 |
| Úroveň 1 | 69h 27m | 250,000 |
| Úroveň 2 | 138h 53m | 500,000 |
| Úroveň 3 | 208h 20m | 750,000 |
| Úroveň 4 | 277h 47m | 1,000,000 |
| Úroveň 5 | 347h 13m | 1,250,000 |
| Úroveň 6 | 416h 40m | 1,500,000 |
| Úroveň 7 | 486h 6m | 1,750,000 |
| Úroveň 8 | 555h 33m | 2,000,000 |
| Úroveň 9 | 625h 0m | 2,250,000 |

## 🔒 Security Notes

⚠️ **Important**: Before deploying, remove hardcoded credentials from `main.py`:
- Database credentials
- Channel IDs specific to your test server
- Role IDs

Consider using environment variables:
```python
import os
host = os.getenv('DB_HOST')
password = os.getenv('DB_PASSWORD')
```

## 🐛 Logging

The bot maintains two logs:
- **Console output** - Real-time activity monitoring
- **bot_log.log** - Persistent file logging

## 🎨 Why This Bot?

**Built for gamers, by gamers.** This hobby project solves real problems:
- ✅ Eliminates manual time tracking spreadsheets
- ✅ Gamifies guild participation with levels and leaderboards
- ✅ Automates repetitive server management tasks
- ✅ Provides fair, transparent activity metrics
- ✅ Encourages healthy competition among members

Perfect for small to medium gaming guilds looking to boost engagement without complex infrastructure.

## 🤝 Contributing

This is a hobby project, but improvements are welcome! Feel free to fork and adapt for your own guild.

## 📜 License

This project is provided as-is for educational and hobby purposes.

## 🏴‍☠️ Credits

Created for the **Unbroken Warriors** Sea of Thieves guild.

*Fair winds and following seas!* ⛵

---

**Note**: This bot was designed for a specific Discord server setup. You'll need to customize channel IDs, role IDs, and potentially adjust the Czech language strings to match your community's needs.
