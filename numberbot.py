# -*- coding: utf-8 -*-
"""
Enhanced WhatsApp Number Assignment Bot — SINGLE NUMBER ASSIGNMENT + FEEDBACK & BAD NUMBER MARKING + EXPORT FEATURE
- Assigns 1 number per request (no more 5-number batches)
- "Change Number" now asks for feedback: Worked / Login not available / Others
- "Login not available" marks the number as bad (bad_numbers table) and removes it from uploads/active pool
- "Others" prompts for free-text feedback (stored in feedbacks table)
- After feedback handling the bot automatically assigns a new single number
- "💾 Save Numbers" button now links to https://t.me/otp_cooldown_bot
- Uploads skip numbers in bad_numbers
- All other features preserved
- OTP Group button now uses DYNAMIC otp_link from pool (not hardcoded)
- NEW: Admin can EXPORT remaining numbers in a pool to CSV
- Zero syntax errors
"""
BOT_TOKEN = "8313328914:AAGL2hmm01EFIqERacAaFu45gon3lYts71I"
ADMIN_USER_ID = 7113000547
import os
import sqlite3
import logging
import re
import asyncio
import json
import requests
import aiohttp
import time
import threading
import csv
import io
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
Application, CommandHandler, MessageHandler, filters,
ContextTypes, CallbackQueryHandler, ConversationHandler
)
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning
from telegram.error import BadRequest
from html import escape

class AssignNumberRequest(BaseModel):
    number: str
    pool_id: int
    pool_name: str
    match_format: str

api_app = FastAPI()
DB_FILE = "numbers.db"
LIVE_MONITOR_FILE = "live_monitor.txt"
WATCHLIST_FILE = "otp_watchlist.json"
OTP_FORWARD_CHANNEL = "@frank_otp_forwardeer"
ACTIVE_MONITORING_FILE = "active_monitoring.json"
PENDING_OTPS_FILE = "pending_otps.json"
COOLDOWN_CHECK_URL = "http://127.0.0.1:8003/check_numbers_exist"
PLATFORM_URL = "http://198.135.52.238"
PLATFORM_USERNAME = "Frankhustle"
PLATFORM_PASSWORD = "f11111"
PLATFORM_OTP_GROUP_ID = -1003382674311
PHONE_RE = re.compile(r'(\+?\d{6,15})')
DEFAULT_LOCAL_PREFIX = "+234"

COUNTRY_MAP = {
    "1": "USA/Canada", "7": "Russia/Kazakhstan", "20": "Egypt", "27": "South Africa",
    "30": "Greece", "31": "Netherlands", "32": "Belgium", "33": "France",
    "34": "Spain", "39": "Italy", "40": "Romania", "41": "Switzerland",
    "43": "Austria", "44": "United Kingdom", "49": "Germany", "51": "Peru",
    "52": "Mexico", "54": "Argentina", "55": "Brazil", "61": "Australia",
    "62": "Indonesia", "63": "Philippines", "64": "New Zealand", "65": "Singapore",
    "66": "Thailand", "81": "Japan", "82": "South Korea", "84": "Vietnam",
    "86": "China", "90": "Turkey", "91": "India", "92": "Pakistan",
    "93": "Afghanistan", "94": "Sri Lanka", "95": "Myanmar", "98": "Iran",
    "211": "South Sudan", "212": "Morocco", "213": "Algeria", "216": "Tunisia",
    "218": "Libya", "220": "Gambia", "221": "Senegal", "222": "Mauritania",
    "223": "Mali", "224": "Guinea", "225": "Ivory Coast", "226": "Burkina Faso",
    "227": "Niger", "228": "Togo", "229": "Benin", "230": "Mauritius",
    "231": "Liberia", "232": "Sierra Leone", "233": "Ghana", "234": "Nigeria",
}
PREFIXES = sorted(COUNTRY_MAP.keys(), key=lambda x: -len(x))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

COUNTRY_CODE_TO_FLAG = {
    "1": "🇺🇸", "1242": "🇧🇸", "1246": "🇧🇧", "1264": "🇦🇮", "1268": "🇦🇬", "1284": "🇻🇬", "1340": "🇻🇮",
    "1345": "🇰🇾", "1441": "🇧🇲", "1473": "🇬🇩", "1649": "🇹🇨", "1664": "🇲🇸", "1670": "🇲🇵", "1671": "🇬🇺",
    "1684": "🇦🇸", "1721": "🇸🇽", "1758": "🇱🇨", "1767": "🇩🇲", "1784": "🇻🇨", "1809": "🇩🇴", "1829": "🇩🇴",
    "1849": "🇩🇴", "1868": "🇹🇹", "1869": "🇰🇳", "1876": "🇯🇲", "1939": "🇵🇷",
    "7": "🇷🇺", "76": "🇰🇿", "77": "🇰🇿",
    "20": "🇪🇬", "27": "🇿🇦", "30": "🇬🇷", "31": "🇳🇱", "32": "🇧🇪", "33": "🇫🇷", "34": "🇪🇸", "36": "🇭🇺",
    "39": "🇮🇹", "40": "🇷🇴", "41": "🇨🇭", "43": "🇦🇹", "44": "🇬🇧", "45": "🇩🇰", "46": "🇸🇪", "47": "🇳🇴",
    "48": "🇵🇱", "49": "🇩🇪", "51": "🇵🇪", "52": "🇲🇽", "53": "🇨🇺", "54": "🇦🇷", "55": "🇧🇷", "56": "🇨🇱",
    "57": "🇨🇴", "58": "🇻🇪", "591": "🇧🇴", "592": "🇬🇾", "593": "🇪🇨", "594": "🇬🇫", "595": "🇵🇾", "596": "🇲🇶",
    "597": "🇸🇷", "598": "🇺🇾", "599": "🇨🇼", "60": "🇲🇾", "61": "🇦🇺", "62": "🇮🇩", "63": "🇵🇭", "64": "🇳🇿",
    "65": "🇸🇬", "66": "🇹🇭", "670": "🇹🇱", "672": "🇦🇶", "673": "🇧🇳", "674": "🇳🇷", "675": "🇵🇬", "676": "🇹🇴",
    "677": "🇸🇧", "678": "🇻🇺", "679": "🇫🇯", "680": "🇵🇼", "681": "🇼🇫", "682": "🇨🇰", "683": "🇳🇺", "685": "🇼🇸",
    "686": "🇰🇮", "687": "🇰🇮", "688": "🇹🇻", "689": "🇵🇫", "690": "🇹🇰", "691": "🇫🇲", "692": "🇲🇭",
    "81": "🇯🇵", "82": "🇰🇷", "84": "🇻🇳", "86": "🇨🇳", "90": "🇹🇷", "91": "🇮🇳", "92": "🇵🇰", "93": "🇦🇫",
    "94": "🇱🇰", "95": "🇲🇲", "960": "🇲🇻", "961": "🇱🇧", "962": "🇯🇴", "963": "🇸🇾", "964": "🇮🇶", "965": "🇰🇼",
    "966": "🇸🇦", "967": "🇾🇪", "968": "🇴🇲", "970": "🇵🇸", "971": "🇦🇪", "972": "🇮🇱", "973": "🇧🇭", "974": "🇶🇦",
    "975": "🇧🇹", "976": "🇲🇳", "977": "🇳🇵", "98": "🇮🇷", "992": "🇹🇯", "993": "🇹🇲", "994": "🇦🇿", "995": "🇬🇪",
    "996": "🇰🇬", "998": "🇺🇿",
    "211": "🇸🇸", "212": "🇲🇦", "213": "🇩🇿", "216": "🇹🇳", "218": "🇱🇾", "220": "🇬🇲", "221": "🇸🇳", "222": "🇲🇷",
    "223": "🇲🇱", "224": "🇬🇳", "225": "🇨🇮", "226": "🇧🇫", "227": "🇳🇪", "228": "🇹🇬", "229": "🇧🇯", "230": "🇲🇺",
    "231": "🇱🇷", "232": "🇸🇱", "233": "🇬🇭", "234": "🇳🇬", "235": "🇹🇩", "236": "🇨🇫", "237": "🇨🇲", "238": "🇨🇻",
    "239": "🇸🇹", "240": "🇬🇶", "241": "🇬🇦", "242": "🇨🇬", "243": "🇨🇩", "244": "🇦🇴", "245": "🇬🇼", "246": "🇮🇴",
    "247": "🇸🇭", "248": "🇸🇨", "249": "🇸🇩", "250": "🇷🇼", "251": "🇪🇹", "252": "🇸🇴", "253": "🇩🇯", "254": "🇰🇪",
    "255": "🇹🇿", "256": "🇺🇬", "257": "🇧🇮", "258": "🇲🇿", "260": "🇿🇲", "261": "🇲🇬", "262": "🇷🇪", "263": "🇿🇼",
    "264": "🇳🇦", "265": "🇲🇼", "266": "🇱🇸", "267": "🇧🇼", "268": "🇸🇿", "269": "🇰🇲", "290": "🇸🇭", "291": "🇪🇷",
    "297": "🇦🇼", "298": "🇫🇴", "299": "🇬🇱", "350": "🇬🇮", "351": "🇵🇹", "352": "🇱🇺", "353": "🇮🇪", "354": "🇮🇸",
    "355": "🇦🇱", "356": "🇲🇹", "357": "🇨🇾", "358": "🇫🇮", "359": "🇧🇬", "370": "🇱🇹", "371": "🇱🇻", "372": "🇪🇪",
    "373": "🇲🇩", "374": "🇦🇲", "375": "🇧🇾", "376": "🇦🇩", "377": "🇲🇨", "378": "🇸🇲", "379": "🇻🇦", "380": "🇺🇦",
    "381": "🇷🇸", "382": "🇲🇪", "383": "🇽🇰", "385": "🇭🇷", "386": "🇸🇮", "387": "🇧🇦", "389": "🇲🇰", "501": "🇧🇿",
    "502": "🇬🇹", "503": "🇸🇻", "504": "🇭🇳", "505": "🇳🇮", "506": "🇨🇷", "507": "🇵🇦", "509": "🇭🇹", "672": "🇦🇶",
    "850": "🇰🇵", "852": "🇭🇰", "853": "🇲🇴", "855": "🇰🇭", "856": "🇱🇦", "880": "🇧🇩", "886": "🇹🇼", "969": "🇾🇪",
    "979": "🇮🇷"
}

def get_flag_from_country_code(code):
    clean = re.sub(r'\D', '', code)
    if not clean:
        return "🏳️"
    for length in range(min(4, len(clean)), 0, -1):
        prefix = clean[:length]
        if prefix in COUNTRY_CODE_TO_FLAG:
            return COUNTRY_CODE_TO_FLAG[prefix]
    return "🏳️"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_number(raw: str) -> str:
    s = re.sub(r'[^\d+]', '', raw)
    if s.startswith('+'): return s
    if s.startswith('0'): return DEFAULT_LOCAL_PREFIX + s[1:]
    return '+' + s

async def get_cooldown_duplicates(numbers: list[str]) -> list[str]:
    if not numbers:
        return []
    payload = {"numbers": numbers}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(COOLDOWN_CHECK_URL, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("existing", [])
                else:
                    logging.warning(f"Cooldown check failed: {resp.status}")
                    return []
        except Exception as e:
            logging.error(f"Failed to reach cooldown bot: {e}")
            return []

def detect_country(phone: str):
    digits = phone.lstrip('+')
    for pref in PREFIXES:
        if digits.startswith(pref): return pref, COUNTRY_MAP.get(pref, "Unknown")
    return "", "Unknown"

def parse_duration_to_seconds(text: str):
    text = text.lower().strip()
    total = 0
    patterns = [
        (r'(\d+)\s*d', 86400),
        (r'(\d+)\s*h', 3600),
        (r'(\d+)\s*m(?!\w)', 60),
        (r'(\d+)\s*s', 1)
    ]
    for regex, mult in patterns:
        for m in re.finditer(regex, text):
            total += int(m.group(1)) * mult
    if total == 0:
        onlynum = re.search(r'\b(\d{1,6})\b', text)
        if onlynum:
            n = int(onlynum.group(1))
            total = n if n <= 3600 else n * 3600
    return total if total > 0 else None

def add_group(chat_id: int, name: str):
    if not name.strip(): return
    with get_db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO groups (chat_id, name) VALUES (?, ?)", (chat_id, name.strip()))

def add_bad_number(number: str, marked_by: int | None = None, reason: str | None = None):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
            INSERT OR IGNORE INTO bad_numbers (number, marked_by, marked_at, reason)
            VALUES (?, ?, ?, ?)
            """, (number, marked_by, datetime.now(timezone.utc).isoformat(), reason or "marked as bad"))
            c.execute("DELETE FROM active_numbers WHERE number = ?", (number,))
            c.execute("DELETE FROM uploaded_numbers WHERE number = ?", (number,))
            c.execute("SELECT 1 FROM bad_numbers WHERE number = ?", (number,))
            if c.fetchone():
                logging.info(f"✅ BAD number saved: {number} (reason: {reason})")
            else:
                logging.warning(f"⚠️ Failed to save bad number: {number}")
            conn.commit()
    except Exception as e:
        logging.error(f"❌ Failed to mark bad number {number}: {e}")

def is_bad_number(number: str) -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM bad_numbers WHERE number = ?", (number,))
        return c.fetchone() is not None

def save_feedback(number: str, user_id: int, feedback: str):
    try:
        with get_db_connection() as conn:
            conn.execute("""
            INSERT INTO feedbacks (number, user_id, feedback, created_at)
            VALUES (?, ?, ?, ?)
            """, (number, user_id, feedback, datetime.now(timezone.utc).isoformat()))
            conn.commit()
    except Exception as e:
        logging.error(f"❌ Failed to save feedback: {e}")

def add_to_active_monitoring(number, pool_name):
    try:
        clean_num = re.sub(r'\D', '', number.lstrip('+'))
        if len(clean_num) < 7:
            return False
        match_format = "5+4"
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT match_format FROM country_pools WHERE name = ?", (pool_name,))
                row = c.fetchone()
                if row:
                    match_format = row[0]
        except Exception as e:
            logging.error(f"❌ Database error getting format: {e}")
        
        if os.path.exists(ACTIVE_MONITORING_FILE):
            with open(ACTIVE_MONITORING_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {}
        
        data[number] = {
            "number": number,
            "pool_name": pool_name,
            "match_format": match_format,
            "assigned_at": time.time()
        }
        now = time.time()
        data = {k: v for k, v in data.items() if now - v["assigned_at"] <= 600}
        
        with open(ACTIVE_MONITORING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logging.info(f"✅ Added {number} to active_monitoring.json with format {match_format}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to update active_monitoring.json: {e}")
        return False

platform_auth_token = None

def login_to_platform():
    global platform_auth_token
    try:
        logging.info("🔑 Attempting login to OTP platform...")
        resp = requests.post(
            f"{PLATFORM_URL}/api/auth/login",
            json={"username": PLATFORM_USERNAME, "password": PLATFORM_PASSWORD},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            platform_auth_token = data.get("token")
            if platform_auth_token:
                logging.info("✅ Platform login successful!")
                return True
            else:
                logging.error("❌ Token missing in login response")
        else:
            logging.error(f"❌ Platform login failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        logging.error(f"💥 Platform login exception: {e}")
    return False

def get_valid_platform_token():
    global platform_auth_token
    if not platform_auth_token:
        if not login_to_platform():
            return None
    try:
        resp = requests.get(
            f"{PLATFORM_URL}/api/sms?limit=1",
            headers={"Authorization": f"Bearer {platform_auth_token}"},
            timeout=15
        )
        if resp.status_code == 401:
            logging.warning("⚠️ Platform token expired. Re-logging in...")
            if login_to_platform():
                return platform_auth_token
            else:
                return None
        elif resp.status_code >= 400:
            logging.warning(f"⚠️ Platform API error: {resp.status_code} - {resp.text}")
            return None
        return platform_auth_token
    except requests.exceptions.Timeout:
        logging.error("❌ Platform API timeout after 15 seconds")
        return None
    except requests.exceptions.ConnectionError:
        logging.error("❌ Platform connection failed - server may be down")
        return None
    except Exception as e:
        logging.error(f"💥 Platform token validation error: {e}")
        return None
    return platform_auth_token

def load_watchlist():
    try:
        if not os.path.exists(WATCHLIST_FILE):
            return {}
        with open(WATCHLIST_FILE, 'r') as f:
            data = json.load(f)
        now = time.time()
        cleaned = {}
        for user_id, info in data.items():
            if now - info.get("added_at", 0) < 600:
                cleaned[user_id] = info
        if len(cleaned) != len(data):
            with open(WATCHLIST_FILE, 'w') as f:
                json.dump(cleaned, f, indent=2)
        return cleaned
    except Exception as e:
        logging.error(f"❌ Watchlist load error: {e}")
        return {}

def add_to_watchlist(user_id: int, phone_number: str, pool_name: str):
    try:
        watchlist = load_watchlist()
        watchlist[str(user_id)] = {
            "number": phone_number,
            "pool_name": pool_name,
            "added_at": time.time()
        }
        with open(WATCHLIST_FILE, 'w') as f:
            json.dump(watchlist, f, indent=2)
        logging.info(f"🔍 Added {phone_number} to watchlist for user {user_id}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to add to watchlist: {e}")
        return False

def remove_from_watchlist(user_id: int):
    try:
        watchlist = load_watchlist()
        user_str = str(user_id)
        if user_str in watchlist:
            del watchlist[user_str]
            with open(WATCHLIST_FILE, 'w') as f:
                json.dump(watchlist, f, indent=2)
            logging.info(f"✅ Removed user {user_id} from watchlist")
            return True
        return False
    except Exception as e:
        logging.error(f"❌ Failed to remove from watchlist: {e}")
        return False

def update_live_monitor_for_telegram(number: str, pool_id: int, match_format: str):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT name, otp_group FROM country_pools WHERE id = ?", (pool_id,))
            row = c.fetchone()
            if not row:
                logging.error(f"Pool {pool_id} not found")
                return
            pool_name, otp_group = row
            try:
                group_id = int(otp_group)
            except (ValueError, TypeError):
                group_id = -1003388744078
            
            resp = requests.post(
                "http://localhost:8002/add-monitor",
                json={
                    "number": number,
                    "group_id": group_id,
                    "match_format": match_format,
                    "pool_name": pool_name
                },
                timeout=5
            )
            if resp.status_code == 200:
                logging.info(f"✅ Userbot confirmed monitoring for {number}")
            else:
                logging.error(f"❌ Userbot rejected: {resp.status_code} - {resp.text}")
    except Exception as e:
        logging.error(f"❌ Failed to notify userbot: {e}")

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS country_pools (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL,
    otp_group TEXT NOT NULL,
    otp_link TEXT NOT NULL DEFAULT '',
    is_paused INTEGER DEFAULT 0,
    pause_reason TEXT DEFAULT '',
    trick_text TEXT DEFAULT '',
    is_admin_only INTEGER DEFAULT 0,
    uses_platform INTEGER DEFAULT 0,
    match_format TEXT DEFAULT '5+4'
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS active_numbers (
    id INTEGER PRIMARY KEY,
    pool_id INTEGER NOT NULL,
    number TEXT NOT NULL UNIQUE,
    FOREIGN KEY (pool_id) REFERENCES country_pools(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS archived_numbers (
    id INTEGER PRIMARY KEY,
    pool_id INTEGER NOT NULL,
    number TEXT NOT NULL,
    assigned_to INTEGER NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pool_id) REFERENCES country_pools(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
    user_id INTEGER PRIMARY KEY,
    current_pool_id INTEGER,
    current_prefix TEXT,
    current_monitored_number TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS uploaded_numbers (
    number TEXT NOT NULL UNIQUE
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS bad_numbers (
    number TEXT PRIMARY KEY,
    marked_by INTEGER,
    marked_at TEXT,
    reason TEXT DEFAULT ''
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS feedbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT,
    user_id INTEGER,
    feedback TEXT,
    created_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(chat_id, name)
    )
    """)
    
    def add_column_if_not_exists(table_name, column_name, column_def):
        try:
            c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
            conn.commit()
            logging.info(f"Added missing column: {column_name} to {table_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logging.debug(f"Column already exists: {column_name} in {table_name}")
            else:
                logging.error(f"Failed to add column {column_name} to {table_name}: {e}")
                raise

    add_column_if_not_exists("country_pools", "otp_link", "TEXT NOT NULL DEFAULT ''")
    add_column_if_not_exists("country_pools", "is_paused", "INTEGER DEFAULT 0")
    add_column_if_not_exists("country_pools", "pause_reason", "TEXT DEFAULT ''")
    add_column_if_not_exists("country_pools", "trick_text", "TEXT DEFAULT ''")
    add_column_if_not_exists("country_pools", "is_admin_only", "INTEGER DEFAULT 0")
    add_column_if_not_exists("country_pools", "uses_platform", "INTEGER DEFAULT 0")
    add_column_if_not_exists("country_pools", "match_format", "TEXT DEFAULT '5+4'")
    add_column_if_not_exists("user_sessions", "current_prefix", "TEXT")
    add_column_if_not_exists("user_sessions", "current_monitored_number", "TEXT")
    
    conn.commit()
    conn.close()
    logging.info("Database schema check and migrations completed successfully")

(
    AWAITING_COUNTRY_NAME,
    AWAITING_COUNTRY_CODE,
    AWAITING_OTP_ID,
    AWAITING_OTP_LINK,
    AWAITING_MATCH_FORMAT,
    AWAITING_USES_PLATFORM,
    AWAITING_BROADCAST,
    AWAITING_PREFIX,
    AWAITING_FILE_FOR_EXISTING,
    EDITING_POOL_NAME,
    EDITING_POOL_CODE,
    EDITING_POOL_OTP_ID,
    EDITING_POOL_OTP_LINK,
    EDITING_MATCH_FORMAT,
    EDITING_USES_PLATFORM,
    AWAITING_TRICK_TEXT,
    AWAITING_PAUSE_REASON,
    AWAITING_CUT_POOL_SELECTION,
    AWAITING_CUT_COUNT,
    AWAITING_CUSTOM_COUNT,
    AWAITING_DUPLICATE_CHOICE,
    AWAITING_COOLDOWN_INPUT,
    AWAITING_NEW_COOLDOWN_GROUP,
) = range(23)
AWAITING_FEEDBACK_TEXT = 23
AWAITING_EXPORT_POOL_SELECTION = 24

def is_admin(user_id):
    return user_id == ADMIN_USER_ID

async def clear_user_data(context: ContextTypes.DEFAULT_TYPE):
    keys_to_clear = [
        'awaiting_prefix', 'awaiting_broadcast', 'file_id_for_existing',
        'editing_pool_id', 'edit_name', 'edit_code', 'edit_otp_group', 'trick_pool_id',
        'pause_pool_id', 'broadcast_message', 'new_pool_uses_platform', 'edit_uses_platform',
        'match_format', 'edit_match_format', 'edit_otp_link', 'otp_link',
        'cut_pool_id', 'parsed_numbers', 'duplicate_choice',
        'awaiting_feedback', 'feedback_target_number', 'export_pool_id'
    ]
    for key in keys_to_clear:
        context.user_data.pop(key, None)

async def show_country_selection_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    is_adm = is_admin(user_id)
    with get_db_connection() as conn:
        c = conn.cursor()
        if is_adm:
            c.execute("""
            SELECT cp.id, cp.name, cp.code, COUNT(an.number) as count, cp.is_paused, cp.is_admin_only
            FROM country_pools cp
            LEFT JOIN active_numbers an ON cp.id = an.pool_id
            GROUP BY cp.id
            HAVING COUNT(an.number) > 0 OR cp.is_paused = 1
            ORDER BY cp.name
            """)
        else:
            c.execute("""
            SELECT cp.id, cp.name, cp.code, COUNT(an.number) as count, cp.is_paused, cp.is_admin_only
            FROM country_pools cp
            LEFT JOIN active_numbers an ON cp.id = an.pool_id
            WHERE cp.is_admin_only = 0
            GROUP BY cp.id
            HAVING COUNT(an.number) > 0 OR cp.is_paused = 1
            ORDER BY cp.name
            """)
        pools = c.fetchall()
        
        if not pools:
            text = "No countries available at the moment."
            if not is_adm:
                text += "\nNote: Some groups are reserved for admin only."
            await context.bot.send_message(chat_id=chat_id, text=text)
            return
        
        kb = []
        for row in pools:
            flag = get_flag_from_country_code(row[2])
            status_emoji = "⏸️" if row[4] else "▶️"
            admin_lock = "🔒" if row[5] else ""
            kb.append([
                InlineKeyboardButton(
                    f"{flag} {status_emoji} {admin_lock} {row[1]} ({row[2]}) - {row[3]} numbers",
                    callback_data=f"select_{row[0]}"
                )
            ])
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="🌍 Select your country:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

def db_assign_one_number(user_id: int, pool_id: int, prefix: str | None = None):
    with get_db_connection() as conn:
        c = conn.cursor()
        if prefix:
            likepat = f"+{prefix}%"
            c.execute("SELECT number FROM active_numbers WHERE pool_id = ? AND number LIKE ? LIMIT 1", (pool_id, likepat))
        else:
            c.execute("SELECT number FROM active_numbers WHERE pool_id = ? LIMIT 1", (pool_id,))
        row = c.fetchone()
        if not row:
            return None, None, None, None, None, None
        
        number = row[0]
        c.execute("DELETE FROM active_numbers WHERE pool_id = ? AND number = ?", (pool_id, number))
        c.execute("INSERT INTO archived_numbers (pool_id, number, assigned_to) VALUES (?, ?, ?)",
                  (pool_id, number, user_id))
        c.execute("INSERT OR REPLACE INTO user_sessions (user_id, current_pool_id, current_prefix, current_monitored_number) VALUES (?, ?, ?, ?)",
                  (user_id, pool_id, prefix, number))
        c.execute("SELECT name, code, otp_link, uses_platform, match_format FROM country_pools WHERE id = ?", (pool_id,))
        prow = c.fetchone()
        conn.commit()
        
        if prow:
            pool_name, pool_code, otp_link, uses_platform, match_format = prow
        else:
            pool_name = pool_code = otp_link = ""
            uses_platform = 0
            match_format = "5+4"
            
        return number, pool_name, pool_code, bool(uses_platform), match_format, otp_link

async def select_pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        pool_id = int(query.data.split("_")[1])
    except:
        await query.edit_message_text("Invalid selection.")
        return

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT is_paused, pause_reason, is_admin_only, uses_platform, name, match_format, code, otp_link FROM country_pools WHERE id = ?", (pool_id,))
        row = c.fetchone()
        if not row:
            await query.edit_message_text("Pool not found.")
            return
        
        is_paused, pause_reason, is_admin_only, uses_platform, pool_name, match_format, pool_code, otp_link = row
        
        if is_admin_only and not is_admin(user_id):
            await query.edit_message_text("🔒 This group is reserved for admin use only.")
            return
        
        if is_paused:
            reason = pause_reason.strip() if pause_reason else ""
            if reason:
                await query.edit_message_text(f"⏸️ This country is currently paused.\nReason: {reason}")
            else:
                await query.edit_message_text("⏸️ This country is currently paused. Please try again later.")
            return

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT current_prefix FROM user_sessions WHERE user_id = ?", (user_id,))
        pref_row = c.fetchone()
        current_prefix = pref_row[0] if pref_row else None
        
        result = db_assign_one_number(user_id, pool_id, current_prefix)
        if len(result) == 6:
            number, pool_name, pool_code, uses_platform_flag, match_format, otp_link = result
        else:
            number = None

        if not number:
            msg = "No numbers available in country right now."
            if current_prefix:
                msg += "\nTry a shorter prefix or clear it."
            await query.edit_message_text(msg)
            return

        if uses_platform_flag:
            add_to_watchlist(user_id, number, pool_name)
        else:
            update_live_monitor_for_telegram(number, pool_id, match_format)
            remove_from_watchlist(user_id)
            add_to_active_monitoring(number, pool_name)

        await asyncio.sleep(0.3)
        flag = get_flag_from_country_code(pool_code)
        msg_lines = [
            f"{flag} <b>{pool_name}</b>",
            "Assigned number:"
        ]
        msg_lines.append(f"1. <code>{number}</code>")
        msg_lines.append("")
        msg_lines.append("⏳ Monitoring for OTP for 10 minutes...")
        msg_lines.append("📬 Check your WhatsApp inbox now!")
        msg_lines.append("⏱️ We'll deliver it here AND to the OTP group if received.")
        msg_lines.append("❗ Don't close this chat.")
        msg = "\n".join(msg_lines)
        
        otp_button_url = otp_link.strip() if otp_link.strip() else "https://t.me/frank_otp_forwardeer"
        kb = [
            [InlineKeyboardButton("🔄 Change Number", callback_data="change_num")],
            [InlineKeyboardButton("ℹ️ Trick / Guide", callback_data=f"show_trick_{pool_id}")],
            [InlineKeyboardButton("🔍 Set Prefix", callback_data="set_prefix")],
            [InlineKeyboardButton("🌎 Change Country", callback_data="change_country")],
            [InlineKeyboardButton("🔔 OTP View / OTP Group", url=otp_button_url)],
            [InlineKeyboardButton("💾 Save Numbers", url="https://t.me/otp_cooldown_bot")]
        ]
        await query.edit_message_text(
            text=msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )

async def change_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT current_monitored_number, current_pool_id FROM user_sessions WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if not row or not row[0]:
            await query.edit_message_text("No active number to give feedback on. Use /start to get a number.")
            return
        current_number, current_pool_id = row[0], row[1]
    
    kb = [
        [InlineKeyboardButton("✅ Worked", callback_data=f"feedback_worked")],
        [InlineKeyboardButton("❌ Login not available", callback_data=f"feedback_bad")],
        [InlineKeyboardButton("✏️ Others", callback_data=f"feedback_others")]
    ]
    context.user_data['awaiting_feedback'] = True
    context.user_data['feedback_target_number'] = current_number
    context.user_data['feedback_pool_id'] = current_pool_id
    
    await query.message.reply_text(
        f"Please tell us how this number performed:\n<code>{escape(current_number)}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def handle_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    target_number = context.user_data.get('feedback_target_number')
    pool_id = context.user_data.get('feedback_pool_id')
    awaiting_feedback = context.user_data.get('awaiting_feedback', False)

    if not awaiting_feedback or not target_number:
        await query.edit_message_text(
            "No active feedback session.\nPress '🔄 Change Number' to get a new one.",
            parse_mode="HTML"
        )
        context.user_data.clear()
        return

    if data == "feedback_worked":
        await query.edit_message_text(
            f"✅ Thanks! Marked as working: <code>{escape(target_number)}</code>",
            parse_mode="HTML"
        )
        context.user_data.clear()
        await assign_replacement_after_feedback(user_id, pool_id, context)
        return

    if data == "feedback_bad":
        add_bad_number(target_number, marked_by=user_id, reason="login not available")
        await query.edit_message_text(
            f"❌ Number marked as BAD and removed:\n<code>{escape(target_number)}</code>\nAssigning new number...",
            parse_mode="HTML"
        )
        context.user_data.clear()
        await assign_replacement_after_feedback(user_id, pool_id, context)
        return

    if data == "feedback_others":
        await query.edit_message_text("✏️ Please send your feedback message (what happened):")
        context.user_data['awaiting_feedback_text'] = True
        return

async def receive_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_feedback_text'):
        return
    user_id = update.effective_user.id
    feedback = update.message.text.strip()
    target_number = context.user_data.get('feedback_target_number')
    pool_id = context.user_data.get('feedback_pool_id')
    
    if target_number and pool_id:
        save_feedback(target_number, user_id, feedback)
        await update.message.reply_text("✅ Feedback saved! Assigning new number...")
        context.user_data.clear()
        await assign_replacement_after_feedback(user_id, pool_id, context)
    else:
        await update.message.reply_text("❌ No active feedback session.")
        context.user_data.clear()

async def assign_replacement_after_feedback(user_id: int, pool_id: int, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('assigning_in_progress', False):
        logging.debug(f"Skipping duplicate assignment call for user {user_id}")
        return
    context.user_data['assigning_in_progress'] = True
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT current_prefix FROM user_sessions WHERE user_id = ?", (user_id,))
            pref_row = c.fetchone()
            current_prefix = pref_row[0] if pref_row else None
            
            c.execute("SELECT name, code, otp_link, uses_platform, match_format FROM country_pools WHERE id = ?", (pool_id,))
            prow = c.fetchone()
            if prow:
                pool_name, pool_code, otp_link, uses_platform, match_format = prow
            else:
                pool_name = pool_code = otp_link = ""
                uses_platform = 0
                match_format = "5+4"

            number, pool_name, pool_code, uses_platform_flag, match_format, otp_link = db_assign_one_number(user_id, pool_id, current_prefix)
            
            if not number:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="No replacement numbers available right now. Try again later."
                    )
                except Exception as e:
                    logging.error(f"Failed to notify user {user_id} about no numbers: {e}")
                return

            if uses_platform_flag:
                add_to_watchlist(user_id, number, pool_name)
            else:
                update_live_monitor_for_telegram(number, pool_id, match_format)
                remove_from_watchlist(user_id)
                add_to_active_monitoring(number, pool_name)

            flag = get_flag_from_country_code(pool_code)
            msg_lines = [
                f"{flag} <b>{pool_name}</b>",
                "Assigned number:",
                f"1. <code>{number}</code>",
                "",
                "⏳ Monitoring for OTP for 10 minutes...",
                "📬 Check your WhatsApp inbox now!",
                "⏱️ We'll deliver it here AND to the OTP group if received.",
                "❗ Don't close this chat."
            ]
            msg = "\n".join(msg_lines)
            otp_button_url = otp_link.strip() if otp_link.strip() else "https://t.me/frank_otp_forwardeer"
            kb = [
                [InlineKeyboardButton("🔄 Change Number", callback_data="change_num")],
                [InlineKeyboardButton("ℹ️ Trick / Guide", callback_data=f"show_trick_{pool_id}")],
                [InlineKeyboardButton("🔍 Set Prefix", callback_data="set_prefix")],
                [InlineKeyboardButton("🌎 Change Country", callback_data="change_country")],
                [InlineKeyboardButton("🔔 OTP View / OTP Group", url=otp_button_url)],
                [InlineKeyboardButton("💾 Save Numbers", url="https://t.me/otp_cooldown_bot")]
            ]
            await context.bot.send_message(
                chat_id=user_id,
                text=msg,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            logging.info(f"Assigned replacement number {number} to user {user_id} in pool {pool_id}")
    except Exception as e:
        logging.error(f"Error in assign_replacement_after_feedback for user {user_id}: {e}")
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Something went wrong while assigning a new number. Try 'Change Number' again."
            )
        except:
            pass
    finally:
        context.user_data.pop('assigning_in_progress', None)

async def set_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_prefix'] = True
    await query.message.reply_text("📱 Send the prefix you want to search for (e.g., 50492):")

async def receive_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_prefix', False):
        return
    user_id = update.effective_user.id
    raw_text = update.message.text.strip()
    prefix = re.sub(r'\D', '', raw_text)
    
    if not prefix or len(prefix) < 3:
        await update.message.reply_text("❌ Invalid prefix. Please send at least 3 digits.")
        return
    
    context.user_data.pop('awaiting_prefix', None)
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT current_pool_id FROM user_sessions WHERE user_id = ?", (user_id,))
        session_row = c.fetchone()
        if not session_row or not session_row[0]:
            await update.message.reply_text("No active session. Use /start.")
            return
        pool_id = session_row[0]
        
        c.execute("""
        SELECT is_paused, pause_reason, name, code, otp_link,
        is_admin_only, uses_platform
        FROM country_pools WHERE id = ?
        """, (pool_id,))
        country_row = c.fetchone()
        if not country_row:
            await update.message.reply_text("Country not found.")
            return
        
        is_paused, pause_reason, country_name, country_code, otp_link, is_admin_only, uses_platform = country_row
        
        if is_admin_only and not is_admin(user_id):
            await update.message.reply_text("🔒 This group is reserved for admin use only.")
            return
        
        if is_paused:
            reason = pause_reason.strip() if pause_reason else ""
            msg = f"⏸️ This country is paused.\nReason: {reason}" if reason else "⏸️ This country is currently paused."
            await update.message.reply_text(msg)
            return

        c.execute("SELECT number FROM active_numbers WHERE pool_id = ? AND number LIKE ? LIMIT 1", (pool_id, f"+{prefix}%"))
        number_row = c.fetchone()
        if not number_row:
            await update.message.reply_text(
                f"❌ No numbers found starting with <code>+{prefix}</code> in this country.\n"
                "Try a shorter prefix (e.g., 2011 instead of 20111421).",
                parse_mode="HTML"
            )
            return
        
        number = number_row[0]
        c.execute("DELETE FROM active_numbers WHERE pool_id = ? AND number = ?", (pool_id, number))
        c.execute("INSERT INTO archived_numbers (pool_id, number, assigned_to) VALUES (?, ?, ?)",
                  (pool_id, number, user_id))
        c.execute("UPDATE user_sessions SET current_prefix = ?, current_monitored_number = ? WHERE user_id = ?",
                  (prefix, number, user_id))
        conn.commit()
        
        flag = get_flag_from_country_code(country_code)
        msg = (
            f"{flag} <b>Prefix Activated</b>\n"
            f"Country: {country_name}\n"
            f"Number: <code>{number}</code>\n"
            f"Prefix set to: <code>+{prefix}</code>\n"
            "From now on, 'Change Number' will give a number starting with this prefix.\n"
            "Use the '❌ Clear Prefix' button when you want random numbers again."
        )
        
        if uses_platform:
            remove_from_watchlist(user_id)
            add_to_watchlist(user_id, number, country_name)
        else:
            c.execute("SELECT match_format FROM country_pools WHERE id = ?", (pool_id,))
            match_row = c.fetchone()
            match_format = match_row[0] if match_row else "5+4"
            update_live_monitor_for_telegram(number, pool_id, match_format)
            remove_from_watchlist(user_id)
            add_to_active_monitoring(number, country_name)
            
        otp_button_url = otp_link.strip() if otp_link.strip() else "https://t.me/frank_otp_forwardeer"
        kb = [
            [InlineKeyboardButton("🔄 Change Number", callback_data="change_num")],
            [InlineKeyboardButton("❌ Clear Prefix", callback_data="clear_prefix")],
            [InlineKeyboardButton("ℹ️ Trick / Guide", callback_data=f"show_trick_{pool_id}")],
            [InlineKeyboardButton("🔍 Change Prefix", callback_data="set_prefix")],
            [InlineKeyboardButton("🌎 Change Country", callback_data="change_country")],
            [InlineKeyboardButton("🔔 OTP View / OTP Group", url=otp_button_url)],
            [InlineKeyboardButton("💾 Save Numbers", url="https://t.me/otp_cooldown_bot")]
        ]
        await update.message.reply_text(
            text=msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )

async def change_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE user_sessions SET current_pool_id = NULL, current_prefix = NULL, current_monitored_number = NULL WHERE user_id = ?", (user_id,))
        conn.commit()
    await show_country_selection_for_chat(query.message.chat_id, context, user_id)

# === ADMIN PANEL HANDLERS ===

async def pause_resume_menu_from_callback(query: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return [], "❌ Admin only."
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code, is_paused FROM country_pools ORDER BY name")
        pools = c.fetchall()
        if not pools:
            return [], "No pools available."
        kb = []
        for pid, name, code, paused in pools:
            status = "⏸️ Pause" if not paused else "▶️ Resume"
            kb.append([InlineKeyboardButton(f"{status} - {name} ({code})", callback_data=f"toggle_pause_{pid}")])
        kb.append([InlineKeyboardButton("Cancel", callback_data="cancel_pause")])
        text = "⏸️ Select a country to pause/resume:"
        return kb, text

async def toggle_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.edit_message_text("❌ Invalid selection.")
        return
    context.user_data["pause_pool_id"] = pool_id
    await query.message.reply_text("📝 Optional: Provide a reason for pausing (or just send 'skip'):")
    return AWAITING_PAUSE_REASON

async def receive_pause_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    pool_id = context.user_data.get("pause_pool_id")
    if not pool_id:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    
    reason = update.message.text.strip()
    if reason.lower() == "skip":
        reason = ""
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT is_paused FROM country_pools WHERE id = ?", (pool_id,))
        current = c.fetchone()
        if not current:
            await update.message.reply_text("❌ Pool not found.")
            return ConversationHandler.END
        
        new_state = 1 - current[0]
        c.execute("UPDATE country_pools SET is_paused = ?, pause_reason = ? WHERE id = ?", (new_state, reason, pool_id))
        conn.commit()
        
        status = "⏸️ paused" if new_state else "▶️ resumed"
        await update.message.reply_text(f"✅ Pool updated: now {status}.")
        context.user_data.pop("pause_pool_id", None)
        return ConversationHandler.END

async def cancel_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Operation cancelled.")
    return ConversationHandler.END

async def delete_pool_menu_from_callback(query: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return [], "❌ Admin only."
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM country_pools ORDER BY name")
        pools = c.fetchall()
        if not pools:
            return [], "No pools to delete."
        kb = []
        for pid, name, code in pools:
            kb.append([InlineKeyboardButton(f"{name} ({code})", callback_data=f"confirm_del_{pid}")])
        kb.append([InlineKeyboardButton("Cancel", callback_data="cancel_del")])
        text = "🗑️ Confirm deletion:"
        return kb, text

async def confirm_delete_pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.edit_message_text("❌ Invalid selection.")
        return
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM country_pools WHERE id = ?", (pool_id,))
        name = c.fetchone()
        if not name:
            await query.edit_message_text("❌ Pool not found.")
            return
        c.execute("DELETE FROM country_pools WHERE id = ?", (pool_id,))
        c.execute("DELETE FROM active_numbers WHERE pool_id = ?", (pool_id,))
        conn.commit()
        await query.edit_message_text(f"✅ Deleted pool: {name[0]}")
        return

async def cancel_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Deletion cancelled.")
    return

async def broadcast_message_from_callback(query: Update, context: ContextTypes.DEFAULT_TYPE):
    await query.message.reply_text("📣 Send your broadcast message:")
    return AWAITING_BROADCAST

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    message = update.message.text
    context.user_data['broadcast_message'] = message
    success = failed = 0
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT assigned_to FROM archived_numbers")
        users = set(row[0] for row in c.fetchall())
    
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            success += 1
        except:
            failed += 1
    
    await update.message.reply_text(f"✅ Broadcast completed!\n✓ Sent to {success} users\n✗ Failed for {failed} users")
    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📁 Upload Numbers", callback_data="upload")],
        [InlineKeyboardButton("⏸️ Pause/Resume", callback_data="pause")],
        [InlineKeyboardButton("🔒 Admin Only Toggle", callback_data="admin_only_toggle")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("✏️ Edit Group", callback_data="edit_pool")],
        [InlineKeyboardButton("📝 Add Trick/Write-up", callback_data="add_trick")],
        [InlineKeyboardButton("🗑️ Delete Pool", callback_data="delete")],
        [InlineKeyboardButton("✂️ Cut Numbers", callback_data="cut_numbers")],
        [InlineKeyboardButton("📤 Export Numbers", callback_data="export_numbers")], # New Button
        [InlineKeyboardButton("⚙️ Platform Settings", callback_data="platform_settings")]
    ]
    text = "✅ Admin Panel"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    elif update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        except BadRequest as e:
            if "message to edit not found" in str(e).lower():
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
            else:
                raise e

async def edit_pool_menu(query: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM country_pools ORDER BY name")
        pools = c.fetchall()
        if not pools:
            await context.bot.send_message(user_id, "No pools to edit.")
            return
        kb = []
        for pid, name, code in pools:
            kb.append([InlineKeyboardButton(f"{name} ({code})", callback_data=f"edit_start_{pid}")])
        kb.append([InlineKeyboardButton("Cancel", callback_data="admin_panel")])
        await context.bot.send_message(user_id, "Select group to edit:", reply_markup=InlineKeyboardMarkup(kb))

async def start_edit_pool_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.edit_message_text("❌ Invalid selection.")
        return ConversationHandler.END
    context.user_data['editing_pool_id'] = pool_id
    await query.message.reply_text("✏️ Send new group name:")
    return EDITING_POOL_NAME

async def receive_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('editing_pool_id'):
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    context.user_data['edit_name'] = update.message.text.strip()
    await update.message.reply_text("🔢 Send new country code (e.g., +992):")
    return EDITING_POOL_CODE

async def receive_edit_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('editing_pool_id'):
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    code = update.message.text.strip()
    if not code.startswith("+"):
        code = "+" + code
    context.user_data['edit_code'] = code
    await update.message.reply_text("🌐 Send new user-facing OTP link (@username or URL):")
    return EDITING_POOL_OTP_LINK

async def receive_edit_otp_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('editing_pool_id'):
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    otp_link = update.message.text.strip()
    if not otp_link.startswith("http") and not otp_link.startswith("@"):
        otp_link = "@" + otp_link.lstrip("@")
    context.user_data['edit_otp_link'] = otp_link
    await update.message.reply_text(f"⏳ Resolving: {otp_link}")
    resolved_id = await resolve_group_link(otp_link, context)
    if resolved_id:
        context.user_data['edit_otp_group'] = str(resolved_id)
        await update.message.reply_text("✏️ Enter match format (e.g., '5+5', '3+4', '4+4'):")
        return EDITING_MATCH_FORMAT
    else:
        await update.message.reply_text("❌ Resolution failed. Enter numeric ID manually:")
        return EDITING_POOL_OTP_ID

async def receive_edit_otp_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('editing_pool_id'):
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    try:
        otp_input = update.message.text.strip()
        if otp_input.startswith("-100"):
            otp_group_id = int(otp_input)
        elif otp_input.startswith("-"):
            otp_group_id = -1000000000000 + abs(int(otp_input))
        else:
            otp_group_id = -1000000000000 + int(otp_input)
        context.user_data['edit_otp_group'] = str(otp_group_id)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID format.")
        context.user_data.clear()
        return ConversationHandler.END
    await update.message.reply_text("✏️ Enter match format (e.g., '5+5', '3+4', '4+4'):")
    return EDITING_MATCH_FORMAT

async def receive_edit_match_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('editing_pool_id'):
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    fmt = update.message.text.strip()
    if not re.match(r'^\d+\+\d+$', fmt):
        await update.message.reply_text("❌ Invalid format. Use 'X+Y' where X and Y are numbers (e.g., '5+5').")
        return EDITING_MATCH_FORMAT
    context.user_data['edit_match_format'] = fmt
    await update.message.reply_text("🔌 Update Platform Monitoring?\n1 for YES, 0 for NO")
    return EDITING_USES_PLATFORM

async def receive_edit_uses_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('editing_pool_id'):
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    try:
        uses_platform = int(update.message.text.strip())
        if uses_platform not in (0, 1):
            raise ValueError
        context.user_data['edit_uses_platform'] = uses_platform
    except:
        await update.message.reply_text("❌ Invalid input. Must be 0 or 1.")
        context.user_data.clear()
        return ConversationHandler.END
    
    pool_id = context.user_data.get('editing_pool_id')
    name = context.user_data['edit_name']
    code = context.user_data['edit_code']
    otp_group = context.user_data['edit_otp_group']
    otp_link = context.user_data['edit_otp_link']
    uses_platform = context.user_data['edit_uses_platform']
    match_format = context.user_data['edit_match_format']
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE country_pools SET name = ?, code = ?, otp_group = ?, otp_link = ?, uses_platform = ?, match_format = ? WHERE id = ?",
                  (name, code, otp_group, otp_link, uses_platform, match_format, pool_id))
        conn.commit()
    
    platform_status = "✅ Platform monitoring ENABLED" if uses_platform else "✅ Telegram group monitoring ENABLED"
    await update.message.reply_text(f"✅ Group updated!\nMatch format: {match_format}\n{platform_status}")
    context.user_data.clear()
    return ConversationHandler.END

async def add_trick_menu(query: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM country_pools ORDER BY name")
        pools = c.fetchall()
        if not pools:
            await context.bot.send_message(user_id, "No groups found.")
            return
        kb = []
        for pid, name, code in pools:
            kb.append([InlineKeyboardButton(f"{name} ({code})", callback_data=f"set_trick_{pid}")])
        kb.append([InlineKeyboardButton("Cancel", callback_data="admin_panel")])
        await context.bot.send_message(user_id, "Select group to add/edit trick:", reply_markup=InlineKeyboardMarkup(kb))

async def start_set_trick_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.edit_message_text("❌ Invalid selection.")
        return ConversationHandler.END
    context.user_data['trick_pool_id'] = pool_id
    await query.message.reply_text("✏️ Send the trick/write-up for this group (supports HTML):")
    return AWAITING_TRICK_TEXT

async def receive_trick_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('trick_pool_id'):
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    pool_id = context.user_data.get('trick_pool_id')
    trick = update.message.text
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE country_pools SET trick_text = ? WHERE id = ?", (trick, pool_id))
        conn.commit()
    await update.message.reply_text("✅ Trick saved!")
    context.user_data.pop('trick_pool_id', None)
    return ConversationHandler.END

async def admin_only_toggle_menu(query: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code, is_admin_only FROM country_pools ORDER BY name")
        pools = c.fetchall()
        if not pools:
            await context.bot.send_message(user_id, "No country pools available.")
            return
        kb = []
        for pid, name, code, admin_only in pools:
            status = "🔒 Admin Only" if admin_only else "🌐 Public"
            kb.append([InlineKeyboardButton(f"{status} - {name} ({code})", callback_data=f"toggle_adminonly_{pid}")])
        kb.append([InlineKeyboardButton("◀️ Back", callback_data="admin_panel")])
        await context.bot.send_message(user_id, "Toggle Admin-Only status:", reply_markup=InlineKeyboardMarkup(kb))

async def toggle_admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.edit_message_text("❌ Invalid selection.")
        return
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name, is_admin_only FROM country_pools WHERE id = ?", (pool_id,))
        result = c.fetchone()
        if not result:
            await query.edit_message_text("❌ Pool not found.")
            return
        name, current = result
        new_val = 0 if current else 1
        c.execute("UPDATE country_pools SET is_admin_only = ? WHERE id = ?", (new_val, pool_id))
        conn.commit()
        status = "🔒 Admin Only" if new_val else "🌐 Public"
        await query.edit_message_text(f"✅ '{name}' is now {status}.")

async def resolve_group_link(link: str, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    try:
        link = link.strip()
        if link.startswith("https://t.me/"):
            username = link.replace("https://t.me/", "")
        elif link.startswith("http://t.me/"):
            username = link.replace("http://t.me/", "")
        elif link.startswith("t.me/"):
            username = link.replace("t.me/", "")
        elif link.startswith("@"):
            username = link[1:]
        else:
            username = link
        
        username = username.strip().split('?')[0]
        if not username:
            return None
        try:
            chat = await context.bot.get_chat(username)
            return chat.id
        except Exception as e:
            if not username.startswith("@"):
                try:
                    chat = await context.bot.get_chat(f"@{username}")
                    return chat.id
                except:
                    pass
    except Exception as e:
        logging.error(f"💥 Critical error in group resolution: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await clear_user_data(context)
    if is_admin(user_id):
        kb = [
            [InlineKeyboardButton("🧑‍💼 Use as Regular User", callback_data="user_mode")],
            [InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel")]
        ]
        await update.message.reply_text(
            "👋 Welcome, Admin! Choose your mode:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        await show_country_selection_for_chat(update.effective_chat.id, context, user_id)

# === CUT NUMBERS ===
async def start_cut_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    user_id = update.effective_user.id
    if not is_admin(user_id):
        if update.message:
            await update.message.reply_text("❌ Admin only.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("❌ Admin only.")
        return ConversationHandler.END
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM country_pools ORDER BY name")
        pools = c.fetchall()
        if not pools:
            if update.message:
                await update.message.reply_text("❌ No groups found.")
            elif update.callback_query:
                await update.callback_query.edit_message_text("❌ No groups found.")
            return ConversationHandler.END
        
        kb = []
        for pid, name, code in pools:
            kb.append([InlineKeyboardButton(f"{name} ({code})", callback_data=f"cut_pool_{pid}")])
        kb.append([InlineKeyboardButton("◀️ Cancel", callback_data="admin_panel")])
        
        text = "✂️ Select group to cut numbers from:"
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return AWAITING_CUT_POOL_SELECTION

async def select_cut_pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Admin only.")
        return ConversationHandler.END
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.edit_message_text("❌ Invalid selection.")
        return ConversationHandler.END
    
    context.user_data['cut_pool_id'] = pool_id
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM country_pools WHERE id = ?", (pool_id,))
        pool_name = c.fetchone()[0]
    
    kb = [
        [InlineKeyboardButton("50", callback_data="cut_count_50"),
         InlineKeyboardButton("100", callback_data="cut_count_100")],
        [InlineKeyboardButton("150", callback_data="cut_count_150"),
         InlineKeyboardButton("200", callback_data="cut_count_200")],
        [InlineKeyboardButton("🖊️ Custom Amount", callback_data="cut_custom")],
        [InlineKeyboardButton("◀️ Cancel", callback_data="admin_panel")]
    ]
    await query.edit_message_text(
        f"✂️ <b>{pool_name}</b>\nHow many numbers to delete?\n(Oldest first)",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return AWAITING_CUT_COUNT

async def handle_cut_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "cut_custom":
        await query.edit_message_text("🔢 Enter custom amount (e.g., 300):")
        return AWAITING_CUSTOM_COUNT
    if data.startswith("cut_count_"):
        try:
            count = int(data.split("_")[-1])
            return await perform_cut(update, context, count)
        except:
            await query.edit_message_text("❌ Invalid amount.")
            return AWAITING_CUT_COUNT
    return AWAITING_CUT_COUNT

async def receive_custom_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if count <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Invalid number. Please enter a positive integer.")
        return AWAITING_CUSTOM_COUNT
    return await perform_cut(update, context, count)

async def perform_cut(update: Update, context: ContextTypes.DEFAULT_TYPE, count: int):
    pool_id = context.user_data.get('cut_pool_id')
    if not pool_id:
        await update.effective_message.reply_text("❌ Session expired. Start again with /cut.")
        context.user_data.clear()
        return ConversationHandler.END
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM country_pools WHERE id = ?", (pool_id,))
            pool_row = c.fetchone()
            if not pool_row:
                await update.effective_message.reply_text("❌ Group not found.")
                context.user_data.clear()
                return ConversationHandler.END
            
            c.execute("SELECT number FROM active_numbers WHERE pool_id = ? ORDER BY rowid LIMIT ?", (pool_id, count))
            numbers = [row[0] for row in c.fetchall()]
            
            if not numbers:
                await update.effective_message.reply_text("❌ No numbers left to delete in this group.")
                context.user_data.clear()
                return ConversationHandler.END
            
            c.executemany("DELETE FROM active_numbers WHERE pool_id = ? AND number = ?",
                          [(pool_id, num) for num in numbers])
            conn.commit()
            
            pool_name = pool_row[0]
            actual = len(numbers)
            await update.effective_message.reply_text(
                f"✅ Successfully deleted <b>{actual}</b> numbers from '<b>{pool_name}</b>'.\n"
                f"(Requested: {count} | Oldest first)",
                parse_mode="HTML"
            )
    except Exception as e:
        logging.error(f"Cut error: {e}")
        await update.effective_message.reply_text("⚠️ Error occurred. Try again.")
    context.user_data.clear()
    return ConversationHandler.END

# === FILE UPLOAD ===
async def show_pools_for_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    doc = update.message.document
    if not doc or not doc.file_name.endswith((".txt", ".csv")):
        await update.message.reply_text("❌ Only .txt or .csv files are supported.")
        return
    
    file_id = doc.file_id
    file = await context.bot.get_file(file_id)
    content = (await file.download_as_bytearray()).decode("utf-8", errors="ignore")
    
    numbers = []
    for line in content.splitlines():
        clean = re.sub(r'\D', '', line)
        if 8 <= len(clean) <= 15:
            num = "+" + clean if not clean.startswith("+") else clean
            numbers.append(num)
    
    if not numbers:
        await update.message.reply_text("❌ No valid numbers found in file.")
        return
    
    filtered_numbers = []
    skipped_bad = 0
    with get_db_connection() as conn:
        c = conn.cursor()
        for num in numbers:
            c.execute("SELECT reason FROM bad_numbers WHERE number = ?", (num,))
            row = c.fetchone()
            if row:
                skipped_bad += 1
                logging.info(f"Skipped bad number during upload: {num} (reason: {row[0]})")
                continue
            filtered_numbers.append(num)
    
    if not filtered_numbers:
        await update.message.reply_text(
            f"❌ All {len(numbers)} numbers in file were marked as bad (skipped {skipped_bad}).\n"
            "No new numbers were added."
        )
        return
    
    cooldown_duplicates = await get_cooldown_duplicates(filtered_numbers)
    skipped_cooldown = len(cooldown_duplicates)
    filtered_numbers = [n for n in filtered_numbers if n not in cooldown_duplicates]
    logging.info(f"Skipped {skipped_cooldown} numbers already in cooldown bot during upload")
    
    new_numbers = []
    duplicates = []
    with get_db_connection() as conn:
        c = conn.cursor()
        for num in filtered_numbers:
            c.execute("SELECT 1 FROM uploaded_numbers WHERE number = ?", (num,))
            if c.fetchone():
                duplicates.append(num)
            else:
                new_numbers.append(num)
    
    context.user_data["parsed_numbers"] = filtered_numbers
    context.user_data["file_id_for_existing"] = file_id
    
    if duplicates:
        kb = [
            [InlineKeyboardButton("✅ Upload All", callback_data="dup_upload_all")],
            [InlineKeyboardButton("🆕 Upload New Only", callback_data="dup_upload_new")],
            [InlineKeyboardButton("🔁 Upload Duplicates Only", callback_data="dup_upload_dup_only")]
        ]
        await update.message.reply_text(
            f"⚠️ Found <b>{len(duplicates)}</b> duplicate(s) out of <b>{len(filtered_numbers)}</b> total\n"
            f"(skipped {skipped_bad} bad numbers, {skipped_cooldown} already in cooldown).\n"
            f"Choose how to proceed:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return AWAITING_DUPLICATE_CHOICE
    else:
        context.user_data['duplicate_choice'] = "dup_upload_new"
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, name, code FROM country_pools ORDER BY name")
            pools = c.fetchall()
            kb = []
            for pid, name, code in pools:
                kb.append([InlineKeyboardButton(f"{name} ({code})", callback_data=f"use_pool_{pid}")])
            kb.append([InlineKeyboardButton("➕ Add New Group", callback_data="start_new_pool")])
            await update.message.reply_text(
                f"📁 No duplicates found! Parsed {len(filtered_numbers)} numbers\n"
                f"(skipped {skipped_bad} bad numbers, {skipped_cooldown} in cooldown).\n"
                "Choose a group to add these numbers to:",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return ConversationHandler.END

# === USE EXISTING POOL ===
async def use_existing_pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        return
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.edit_message_text("❌ Invalid selection.")
        return
    
    file_id = context.user_data.get("file_id_for_existing")
    parsed_numbers = context.user_data.get("parsed_numbers")
    duplicate_choice = context.user_data.get("duplicate_choice")
    
    if not parsed_numbers:
        await query.edit_message_text("❌ No numbers to process.")
        return
    if not file_id:
        await query.edit_message_text("❌ No file found.")
        return
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name, code FROM country_pools WHERE id = ?", (pool_id,))
        pool_info = c.fetchone()
        if not pool_info:
            await query.edit_message_text("❌ Pool not found.")
            return
        pool_name, pool_code = pool_info
        
        if duplicate_choice == "dup_upload_all":
            numbers_to_add = parsed_numbers
        elif duplicate_choice == "dup_upload_new":
            numbers_to_add = []
            for num in parsed_numbers:
                c.execute("SELECT 1 FROM uploaded_numbers WHERE number = ?", (num,))
                if not c.fetchone():
                    numbers_to_add.append(num)
        elif duplicate_choice == "dup_upload_dup_only":
            numbers_to_add = []
            for num in parsed_numbers:
                c.execute("SELECT 1 FROM uploaded_numbers WHERE number = ?", (num,))
                if c.fetchone():
                    numbers_to_add.append(num)
        else:
            numbers_to_add = parsed_numbers
        
        final_numbers = []
        for num in numbers_to_add:
            c.execute("SELECT 1 FROM bad_numbers WHERE number = ?", (num,))
            if c.fetchone():
                continue
            final_numbers.append(num)
        
        if final_numbers:
            c.executemany(
                "INSERT OR IGNORE INTO active_numbers (pool_id, number) VALUES (?, ?)",
                [(pool_id, n) for n in final_numbers]
            )
            c.executemany(
                "INSERT OR IGNORE INTO uploaded_numbers (number) VALUES (?)",
                [(n,) for n in parsed_numbers]
            )
            conn.commit()
            await query.edit_message_text(
                f"✅ Successfully added {len(final_numbers)} numbers to '{pool_name}' (skipped bad numbers)."
            )
            context.user_data.pop("file_id_for_existing", None)
            context.user_data.pop("parsed_numbers", None)
            context.user_data.pop("duplicate_choice", None)

# === ADMIN: CREATE POOL ===
async def start_new_pool_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        return
    file_id = context.user_data.get("file_id_for_existing")
    parsed_numbers = context.user_data.get("parsed_numbers")
    if not file_id or not parsed_numbers:
        await query.message.reply_text("❌ No file found. Please upload again.")
        return
    context.user_data["file_id"] = file_id
    await query.message.reply_text("🌍 Country name (e.g., Honduras WS):")
    return AWAITING_COUNTRY_NAME

async def receive_country_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("🔢 Country code (e.g., +504):")
    return AWAITING_COUNTRY_CODE

async def receive_country_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    if not code.startswith("+"):
        code = "+" + code
    context.user_data["code"] = code
    await update.message.reply_text("🌐 User-facing OTP link (@username or https://t.me/...):")
    return AWAITING_OTP_LINK

async def receive_otp_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    otp_link = update.message.text.strip()
    if not otp_link.startswith("http") and not otp_link.startswith("@"):
        otp_link = "@" + otp_link.lstrip("@")
    context.user_data["otp_link"] = otp_link
    await update.message.reply_text(f"⏳ Resolving group link: {otp_link}")
    resolved_id = await resolve_group_link(otp_link, context)
    if resolved_id:
        context.user_data["otp_group"] = str(resolved_id)
        await update.message.reply_text(
            f"✅ Successfully resolved!\nGroup ID: {resolved_id}\n"
            "✏️ Enter match format (e.g., '5+5', '3+4', '4+4'):"
        )
        return AWAITING_MATCH_FORMAT
    else:
        await update.message.reply_text(
            "❌ Failed to resolve group link. Please enter numeric ID manually:"
        )
        return AWAITING_OTP_ID

async def receive_otp_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        otp_input = update.message.text.strip()
        if otp_input.startswith("-100"):
            otp_group_id = int(otp_input)
        elif otp_input.startswith("-"):
            otp_group_id = -1000000000000 + abs(int(otp_input))
        else:
            otp_group_id = -1000000000000 + int(otp_input)
        context.user_data["otp_group"] = str(otp_group_id)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID format.")
        context.user_data.clear()
        return ConversationHandler.END
    await update.message.reply_text("✏️ Enter match format (e.g., '5+5', '3+4', '4+4'):")
    return AWAITING_MATCH_FORMAT

async def receive_match_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fmt = update.message.text.strip()
    if not re.match(r'^\d+\+\d+$', fmt):
        await update.message.reply_text("❌ Invalid format. Use 'X+Y' where X and Y are numbers (e.g., '5+5').")
        return AWAITING_MATCH_FORMAT
    context.user_data["match_format"] = fmt
    await update.message.reply_text(
        "🔌 Enable OTP Platform Monitoring?\n1 for YES (platform), 0 for NO (Telegram group)"
    )
    return AWAITING_USES_PLATFORM

async def receive_uses_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uses_platform = int(update.message.text.strip())
        if uses_platform not in (0, 1):
            raise ValueError
        context.user_data["uses_platform"] = uses_platform
    except:
        await update.message.reply_text("❌ Invalid input. Must be 0 or 1.")
        context.user_data.clear()
        return ConversationHandler.END
    
    name = context.user_data["name"]
    code = context.user_data["code"]
    otp_group = context.user_data["otp_group"]
    otp_link = context.user_data["otp_link"]
    uses_platform = context.user_data["uses_platform"]
    match_format = context.user_data["match_format"]
    parsed_numbers = context.user_data.get("parsed_numbers")
    
    if not parsed_numbers:
        await update.message.reply_text("❌ No numbers to assign.")
        return ConversationHandler.END
    
    final_numbers = []
    skipped_bad = 0
    with get_db_connection() as conn:
        c = conn.cursor()
        for n in parsed_numbers:
            c.execute("SELECT 1 FROM bad_numbers WHERE number = ?", (n,))
            if c.fetchone():
                skipped_bad += 1
                continue
            final_numbers.append(n)
        
        c.execute("INSERT OR IGNORE INTO country_pools (name, code, otp_group, otp_link, uses_platform, match_format) VALUES (?, ?, ?, ?, ?, ?)",
                  (name, code, otp_group, otp_link, uses_platform, match_format))
        c.execute("SELECT id FROM country_pools WHERE name = ?", (name,))
        pool_id = c.fetchone()[0]
        
        if final_numbers:
            c.executemany("INSERT OR IGNORE INTO active_numbers (pool_id, number) VALUES (?, ?)",
                          [(pool_id, n) for n in final_numbers])
            c.executemany("INSERT OR IGNORE INTO uploaded_numbers (number) VALUES (?)",
                          [(n,) for n in parsed_numbers])
            conn.commit()
        
        await update.message.reply_text(f"✅ Created group '{name}' and added {len(final_numbers)} numbers! (skipped {skipped_bad} bad numbers)")
        context.user_data.clear()
        return ConversationHandler.END

# === SHOW TRICK ===
async def show_trick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.message.reply_text("❌ Invalid group.")
        return
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT trick_text FROM country_pools WHERE id = ?", (pool_id,))
        row = c.fetchone()
        if row and row[0].strip():
            await query.message.reply_text(
                f"<b>ℹ️ Trick for this group:</b>\n{row[0]}",
                parse_mode="HTML"
            )
        else:
            await query.message.reply_text("No trick available for this group.")

# === DUPLICATE CHOICE HANDLER ===
async def handle_duplicate_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Admin only.")
        return ConversationHandler.END
    choice = query.data
    valid_choices = ("dup_upload_all", "dup_upload_new", "dup_upload_dup_only")
    if choice not in valid_choices:
        await query.edit_message_text("❌ Invalid choice.")
        return ConversationHandler.END
    context.user_data['duplicate_choice'] = choice
    parsed_numbers = context.user_data.get('parsed_numbers')
    if not parsed_numbers:
        await query.edit_message_text("❌ No numbers found.")
        return ConversationHandler.END
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM country_pools ORDER BY name")
        pools = c.fetchall()
        kb = []
        for pid, name, code in pools:
            kb.append([InlineKeyboardButton(f"{name} ({code})", callback_data=f"use_pool_{pid}")])
        kb.append([InlineKeyboardButton("➕ Add New Group", callback_data="start_new_pool")])
        await query.edit_message_text(
            "📁 Numbers processed! Now choose a group to add these numbers to:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return ConversationHandler.END

# === EXPORT NUMBERS FEATURE ===
async def start_export_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Admin only.")
        return ConversationHandler.END
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM country_pools ORDER BY name")
        pools = c.fetchall()
        if not pools:
            await query.edit_message_text("❌ No pools available to export.")
            return ConversationHandler.END
        
        kb = []
        for pid, name, code in pools:
            kb.append([InlineKeyboardButton(f"{name} ({code})", callback_data=f"export_select_{pid}")])
        kb.append([InlineKeyboardButton("◀️ Cancel", callback_data="admin_panel")])
        
        await query.edit_message_text(
            "📤 <b>Export Numbers</b>\nSelect a pool to download all remaining numbers as CSV:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return AWAITING_EXPORT_POOL_SELECTION

async def process_export_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Admin only.")
        return ConversationHandler.END
    
    try:
        pool_id = int(query.data.split("_")[-1])
    except:
        await query.edit_message_text("❌ Invalid selection.")
        return ConversationHandler.END
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name, code FROM country_pools WHERE id = ?", (pool_id,))
        pool_info = c.fetchone()
        if not pool_info:
            await query.edit_message_text("❌ Pool not found.")
            return ConversationHandler.END
        
        pool_name, pool_code = pool_info
        
        # Fetch all active numbers for this pool
        c.execute("SELECT number FROM active_numbers WHERE pool_id = ? ORDER BY id", (pool_id,))
        numbers = [row[0] for row in c.fetchall()]
        
        if not numbers:
            await query.edit_message_text(f"❌ No numbers found in pool '{pool_name}'.")
            return ConversationHandler.END
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Number"]) # Header
        for num in numbers:
            writer.writerow([num])
        
        csv_content = output.getvalue()
        output.close()
        
        filename = f"export_{pool_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        await context.bot.send_document(
            chat_id=user_id,
            document=io.BytesIO(csv_content.encode('utf-8')),
            filename=filename,
            caption=f"✅ Exported <b>{len(numbers)}</b> numbers from <b>{pool_name}</b>.",
            parse_mode="HTML"
        )
        
        await query.edit_message_text(f"✅ File sent! Downloaded {len(numbers)} numbers from '{pool_name}'.")
        context.user_data.clear()
        return ConversationHandler.END

# === HANDLE CALLBACK ===
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "user_mode":
        await query.message.delete()
        await show_country_selection_for_chat(query.message.chat_id, context, user_id)
        return
    elif data == "admin_panel":
        await admin_panel(update, context)
        return
    elif data == "upload":
        await context.bot.send_message(user_id, "Send your .txt or .csv file with numbers:")
        return
    elif data == "pause":
        kb, text = await pause_resume_menu_from_callback(query, context)
        await context.bot.send_message(user_id, text, reply_markup=InlineKeyboardMarkup(kb))
        return
    elif data == "admin_only_toggle":
        await admin_only_toggle_menu(query, context)
        return
    elif data.startswith("toggle_adminonly_"):
        await toggle_admin_only(update, context)
        return
    elif data == "broadcast":
        return await broadcast_message_from_callback(query, context)
    elif data == "delete":
        kb, text = await delete_pool_menu_from_callback(query, context)
        await context.bot.send_message(user_id, text, reply_markup=InlineKeyboardMarkup(kb))
        return
    elif data == "edit_pool":
        await edit_pool_menu(query, context)
        return
    elif data == "add_trick":
        await add_trick_menu(query, context)
        return
    elif data == "cut_numbers":
        await start_cut_numbers(update, context)
        return
    elif data == "export_numbers": # New Handler
        return await start_export_numbers(update, context)
    elif data.startswith("show_trick_"):
        await show_trick(update, context)
        return
    elif data.startswith("select_"):
        await select_pool(update, context)
        return
    elif data == "change_num":
        await change_number(update, context)
        return
    elif data == "set_prefix":
        await set_prefix(update, context)
        return
    elif data == "change_country":
        await change_country(update, context)
        return
    elif data.startswith("confirm_del_"):
        await confirm_delete_pool(update, context)
        return
    elif data == "cancel_del":
        await cancel_delete(update, context)
        return
    elif data.startswith("toggle_pause_"):
        return await toggle_pause(update, context)
    elif data == "cancel_pause":
        await cancel_pause(update, context)
        return
    elif data.startswith("use_pool_"):
        await use_existing_pool(update, context)
        return
    elif data == "start_new_pool":
        return await start_new_pool_entry(update, context)
    elif data.startswith("edit_start_"):
        return await start_edit_pool_entry(update, context)
    elif data.startswith("set_trick_"):
        return await start_set_trick_entry(update, context)
    elif data.startswith("cut_pool_"):
        return await select_cut_pool(update, context)
    elif data.startswith("cut_count_"):
        try:
            count = int(data.split("_")[-1])
            context.user_data['cut_pool_id'] = context.user_data.get('cut_pool_id')
            await perform_cut(update, context, count)
        except:
            await query.edit_message_text("❌ Invalid amount.")
        return
    elif data == "cut_custom":
        await query.edit_message_text("🔢 Enter custom amount (e.g., 300):")
        return AWAITING_CUSTOM_COUNT
    elif data.startswith("export_select_"):
        return await process_export_selection(update, context)
    elif data == "platform_settings":
        await query.message.reply_text(
            "🔧 Platform Settings\n"
            "This bot monitors OTPs based on 'uses_platform' flag:\n"
            "- uses_platform=1 → polls platform API (5+4 only)\n"
            "- uses_platform=0 → triggers userbot for Telegram groups\n"
            "Current credentials:\n"
            f"Username: {PLATFORM_USERNAME}\n"
            f"URL: {PLATFORM_URL}\n"
            "To change credentials, edit the script directly."
        )
        return
    elif data in ("dup_upload_all", "dup_upload_new", "dup_upload_dup_only"):
        await handle_duplicate_choice(update, context)
        return
    elif data == "clear_prefix":
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE user_sessions SET current_prefix = NULL WHERE user_id = ?", (user_id,))
            conn.commit()
        await query.edit_message_text("✅ Prefix filter removed.\nNow getting random numbers from the pool.")
        await assign_replacement_after_feedback(user_id, context.user_data.get('current_pool_id'), context)
        return
    elif data.startswith("feedback_"):
        await handle_feedback_callback(update, context)
        return
    
    logging.warning(f"Unknown callback {data}")
    await query.edit_message_text("❌ Unknown command. Please start over with /start")

# === ERROR HANDLER ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Exception while handling an update:", exc_info=context.error)
    if update and hasattr(update, 'effective_message'):
        try:
            await update.effective_message.reply_text("⚠️ An error occurred. Please try again.")
        except:
            pass

# === CONVERSATION HANDLERS ===
upload_new_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_new_pool_entry, pattern="^start_new_pool$")],
    states={
        AWAITING_COUNTRY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_country_name)],
        AWAITING_COUNTRY_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_country_code)],
        AWAITING_OTP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_otp_link)],
        AWAITING_OTP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_otp_id)],
        AWAITING_MATCH_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_match_format)],
        AWAITING_USES_PLATFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_uses_platform)]
    },
    fallbacks=[CommandHandler('start', start)],
    allow_reentry=True
)

edit_pool_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_pool_entry, pattern="^edit_start_\\d+$")],
    states={
        EDITING_POOL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_name)],
        EDITING_POOL_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_code)],
        EDITING_POOL_OTP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_otp_link)],
        EDITING_POOL_OTP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_otp_id)],
        EDITING_MATCH_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_match_format)],
        EDITING_USES_PLATFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_uses_platform)]
    },
    fallbacks=[CommandHandler('start', start)],
    allow_reentry=True
)

set_trick_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_set_trick_entry, pattern="^set_trick_\\d+$")],
    states={
        AWAITING_TRICK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_trick_text)]
    },
    fallbacks=[CommandHandler('start', start)],
    allow_reentry=True
)

pause_reason_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(toggle_pause, pattern="^toggle_pause_\\d+$")],
    states={
        AWAITING_PAUSE_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pause_reason)]
    },
    fallbacks=[CommandHandler('start', start)],
    allow_reentry=True
)

broadcast_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(broadcast_message_from_callback, pattern="^broadcast$")],
    states={
        AWAITING_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast)]
    },
    fallbacks=[CommandHandler('start', start)],
    allow_reentry=True
)

cut_numbers_conv = ConversationHandler(
    entry_points=[CommandHandler("cut", start_cut_numbers)],
    states={
        AWAITING_CUT_POOL_SELECTION: [CallbackQueryHandler(select_cut_pool, pattern="^cut_pool_\\d+$")],
        AWAITING_CUT_COUNT: [CallbackQueryHandler(handle_cut_count, pattern="^cut_")],
        AWAITING_CUSTOM_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_count)]
    },
    fallbacks=[CommandHandler('start', start)],
    allow_reentry=True
)

duplicate_choice_conv = ConversationHandler(
    entry_points=[],
    states={
        AWAITING_DUPLICATE_CHOICE: [CallbackQueryHandler(handle_duplicate_choice, pattern="^dup_")]
    },
    fallbacks=[CommandHandler('start', start)],
    allow_reentry=True
)

export_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_export_numbers, pattern="^export_numbers$")],
    states={
        AWAITING_EXPORT_POOL_SELECTION: [CallbackQueryHandler(process_export_selection, pattern="^export_select_\\d+$")]
    },
    fallbacks=[CommandHandler('start', start)],
    allow_reentry=True
)

# === FASTAPI ENDPOINT ===
@api_app.post("/assign-number")
async def assign_number(req: AssignNumberRequest):
    number = req.number
    pool_id = req.pool_id
    pool_name = req.pool_name
    match_format = req.match_format
    use_platform = False
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT uses_platform FROM country_pools WHERE id = ?", (pool_id,))
            row = c.fetchone()
            if row:
                use_platform = bool(row[0])
    except Exception as e:
        logging.error(f"❌ Database error checking monitoring type: {e}")
    
    if use_platform:
        result = add_to_active_monitoring(number, pool_name)
        action = "Platform monitoring" if result else "Failed to add to platform monitoring"
    else:
        update_live_monitor_for_telegram(number, pool_id, match_format)
        action = "Telegram monitoring"
    
    logging.info(f"✅ {action} for {number} ({match_format}) - Group ID: {pool_id} - Type: {'platform' if use_platform else 'telegram'}")
    return {
        "status": "ok",
        "number": number,
        "pool_id": pool_id,
        "pool_name": pool_name,
        "match_format": match_format,
        "monitoring_type": "platform" if use_platform else "telegram"
    }

# === MAIN ===
def main():
    setup_database()
    
    def run_api():
        uvicorn.run(api_app, host="0.0.0.0", port=8001, log_level="info")
    
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    async def start_background_tasks(app: Application):
        pass
    
    application.post_init = start_background_tasks
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cut", start_cut_numbers))
    
    application.add_handler(upload_new_conv)
    application.add_handler(edit_pool_conv)
    application.add_handler(set_trick_conv)
    application.add_handler(pause_reason_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(cut_numbers_conv)
    application.add_handler(duplicate_choice_conv)
    application.add_handler(export_conv) # Added Export Handler
    
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(CallbackQueryHandler(handle_feedback_callback, pattern="^feedback_"), group=1)
    application.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, show_pools_for_file))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, receive_prefix),
        group=1
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, receive_feedback_text),
        group=0
    )
    
    application.add_error_handler(error_handler)
    
    logging.info(f"✅ Main bot started. Monitoring channel: {OTP_FORWARD_CHANNEL}")
    logging.info("🚀 Number Bot API running on http://localhost:8001")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()