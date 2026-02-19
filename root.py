import sys
import io
import os

# تنظیم encoding ویندوز به UTF-8 برای پشتیبانی از فارسی
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import socks
import socket
from telebot import apihelper

# تنظیم پروکسی Socks5
socks.set_default_proxy(
    socks.SOCKS5,
    "3.3pita.com",  # سرور
    25565,          # پورت
    True,           # RDNS
    None,           # username (اگه داره)
    None            # password (اگه داره)
)

# جایگزینی سوکت پیش‌فرض با سوکت پروکسی شده
socket.socket = socks.socksocket

# تنظیمات اضافی برای API helper
apihelper.proxy = {'http': 'socks5://3.3pita.com:25565', 
                   'https': 'socks5://3.3pita.com:25565'}






import telebot
import time
import json
import hashlib
import logging
import os
import sys
import sqlite3
import psutil
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from threading import Lock




# ================== تنظیمات ==================
TOKEN = "8303331831:AAFeVQiKyg7bY78C_4DQrGHmb0HwkumusLg"
bot = telebot.TeleBot(TOKEN)
BOT_START_TIME = time.time()
LOCK = Lock()

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================== پایگاه داده ==================
def init_db():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    c = conn.cursor()
    # جدول کاربران
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
                  language_code TEXT, is_bot INTEGER, is_premium INTEGER, first_seen TEXT,
                  last_seen TEXT, request_count INTEGER DEFAULT 0)''')
    # جدول تاریخچه درخواست‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, command TEXT,
                  timestamp TEXT, chat_id INTEGER, details TEXT)''')
    # جدول تنظیمات کاربر (مثلاً زبان انتخابی)
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings
                 (user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'fa')''')
    conn.commit()
    conn.close()

init_db()

def db_execute(query, params=(), fetchone=False, fetchall=False):
    with LOCK:
        conn = sqlite3.connect('bot_data.db', check_same_thread=False)
        c = conn.cursor()
        c.execute(query, params)
        if fetchone:
            result = c.fetchone()
        elif fetchall:
            result = c.fetchall()
        else:
            result = None
        conn.commit()
        conn.close()
    return result

def update_user_info(user):
    now = datetime.now().isoformat()
    user_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name
    language_code = user.language_code
    is_bot = 1 if user.is_bot else 0
    is_premium = 1 if getattr(user, 'is_premium', False) else 0

    # بررسی وجود کاربر
    existing = db_execute("SELECT last_seen FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if existing:
        db_execute("UPDATE users SET username=?, first_name=?, last_name=?, language_code=?, is_bot=?, is_premium=?, last_seen=? WHERE user_id=?",
                   (username, first_name, last_name, language_code, is_bot, is_premium, now, user_id))
    else:
        db_execute("INSERT INTO users (user_id, username, first_name, last_name, language_code, is_bot, is_premium, first_seen, last_seen, request_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (user_id, username, first_name, last_name, language_code, is_bot, is_premium, now, now, 0))
    # افزایش شمارنده درخواست
    db_execute("UPDATE users SET request_count = request_count + 1 WHERE user_id = ?", (user_id,))

def log_request(user_id, command, chat_id, details=None):
    now = datetime.now().isoformat()
    db_execute("INSERT INTO requests (user_id, command, timestamp, chat_id, details) VALUES (?,?,?,?,?)",
               (user_id, command, now, chat_id, json.dumps(details, ensure_ascii=False) if details else None))

def get_user_lang(user_id):
    result = db_execute("SELECT language FROM user_settings WHERE user_id = ?", (user_id,), fetchone=True)
    return result[0] if result else 'fa'

def set_user_lang(user_id, lang):
    db_execute("REPLACE INTO user_settings (user_id, language) VALUES (?,?)", (user_id, lang))

# ================== چندزبانه ==================
translations = {
    'fa': {
        'your_info': '🔹 اطلاعات شما (کاربر):',
        'bot_info': '🔸 اطلاعات ربات:',
        'chat_info': '💬 اطلاعات چت جاری:',
        'message_info': '📨 اطلاعات این پیام:',
        'system_info': '🖥 اطلاعات سیستم:',
        'id': '🆔 آیدی عددی',
        'username': '📛 نام کاربری',
        'name': '📇 نام',
        'fullname': '📇 نام کامل',
        'lang': '🌐 زبان',
        'is_bot': '🤖 آیا ربات هستید؟',
        'premium': '💎 پریمیوم',
        'photos_count': '📸 تعداد عکس‌های پروفایل',
        'profile_link': '🔗 لینک پروفایل',
        'online_status': '🟢 وضعیت آنلاین',
        'block_status': '🚫 بلاک بودن ربات',
        'chat_id': '🆔 آیدی چت',
        'chat_type': '📌 نوع چت',
        'chat_title': '📢 عنوان',
        'chat_username': '@ یوزرنیم چت',
        'chat_link': '📎 لینک چت',
        'chat_members': '👥 تعداد اعضا',
        'user_role': '👤 نقش شما',
        'message_id': '🆔 آیدی پیام',
        'message_date': '📅 زمان ارسال',
        'message_edit': '✏️ آخرین ویرایش',
        'message_type': '📦 نوع محتوا',
        'message_hash': '🔐 هش پیام',
        'bot_id': '🆔 آیدی ربات',
        'bot_username': '@ یوزرنیم ربات',
        'bot_name': '📛 نام ربات',
        'bot_can_join': '👥 قابلیت پیوستن به گروه‌ها',
        'bot_can_read': '📖 خواندن همه پیام‌های گروه',
        'bot_inline': '🔄 پشتیبانی از اینلاین',
        'bot_uptime': '⏱ آپتایم ربات',
        'python_version': '🐍 نسخه پایتون',
        'lib_version': '📚 نسخه کتابخانه',
        'memory_usage': '🧠 مصرف حافظه',
        'yes': '✅ بله',
        'no': '❌ خیر',
        'online': 'آنلاین',
        'offline': 'آفلاین',
        'last_online': 'آخرین آنلاین',
        'unknown': 'نامشخص',
        'admin': 'مدیر',
        'member': 'عضو',
        'creator': 'سازنده',
        'restricted': 'محدود شده',
        'left': 'ترک کرده',
        'not_available': 'در دسترس نیست',
        'refresh': '🔄 تازه‌سازی',
        'share': '📤 اشتراک‌گذاری',
        'qr': '📱 QR کد',
        'copy': '📋 کپی',
        'language': '🌐 تغییر زبان',
        'close': '❌ بستن',
        'choose_lang': 'لطفاً زبان خود را انتخاب کنید:',
        'lang_changed': 'زبان شما به فارسی تغییر یافت.',
        'lang_changed_en': 'Your language has been changed to English.',
    },
    'en': {
        'your_info': '🔹 Your Information (User):',
        'bot_info': '🔸 Bot Information:',
        'chat_info': '💬 Current Chat Information:',
        'message_info': '📨 Message Information:',
        'system_info': '🖥 System Information:',
        'id': '🆔 ID',
        'username': '📛 Username',
        'name': '📇 Name',
        'fullname': '📇 Full Name',
        'lang': '🌐 Language',
        'is_bot': '🤖 Are you a bot?',
        'premium': '💎 Premium',
        'photos_count': '📸 Profile photos count',
        'profile_link': '🔗 Profile link',
        'online_status': '🟢 Online status',
        'block_status': '🚫 Bot block status',
        'chat_id': '🆔 Chat ID',
        'chat_type': '📌 Chat type',
        'chat_title': '📢 Title',
        'chat_username': '@ Chat username',
        'chat_link': '📎 Chat link',
        'chat_members': '👥 Members count',
        'user_role': '👤 Your role',
        'message_id': '🆔 Message ID',
        'message_date': '📅 Date',
        'message_edit': '✏️ Last edit',
        'message_type': '📦 Content type',
        'message_hash': '🔐 Message hash',
        'bot_id': '🆔 Bot ID',
        'bot_username': '@ Bot username',
        'bot_name': '📛 Bot name',
        'bot_can_join': '👥 Can join groups',
        'bot_can_read': '📖 Can read all messages',
        'bot_inline': '🔄 Supports inline',
        'bot_uptime': '⏱ Uptime',
        'python_version': '🐍 Python version',
        'lib_version': '📚 Library version',
        'memory_usage': '🧠 Memory usage',
        'yes': '✅ Yes',
        'no': '❌ No',
        'online': 'Online',
        'offline': 'Offline',
        'last_online': 'Last seen',
        'unknown': 'Unknown',
        'admin': 'Admin',
        'member': 'Member',
        'creator': 'Creator',
        'restricted': 'Restricted',
        'left': 'Left',
        'not_available': 'Not available',
        'refresh': '🔄 Refresh',
        'share': '📤 Share',
        'qr': '📱 QR Code',
        'copy': '📋 Copy',
        'language': '🌐 Change language',
        'close': '❌ Close',
        'choose_lang': 'Please choose your language:',
        'lang_changed': 'Your language has been changed to English.',
        'lang_changed_en': 'Your language has been changed to English.',
    }
}

def _(user_id, key):
    lang = get_user_lang(user_id)
    return translations.get(lang, translations['fa']).get(key, key)

# ================== توابع کمکی پیشرفته ==================
def get_uptime():
    uptime_seconds = int(time.time() - BOT_START_TIME)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or len(parts) == 0:
        parts.append(f"{seconds}s")
    return " ".join(parts)

def get_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024  # MB
    return f"{mem:.2f} MB"

def get_profile_photos_count(user_id):
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        return photos.total_count
    except Exception as e:
        logger.error(f"Error getting profile photos: {e}")
        return "?"

def get_chat_members_count(chat_id):
    try:
        return bot.get_chat_members_count(chat_id)
    except:
        return "?"

def get_user_role_in_chat(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        status = member.status
        if status == 'creator':
            return 'creator'
        elif status == 'administrator':
            return 'admin'
        elif status == 'member':
            return 'member'
        elif status == 'restricted':
            return 'restricted'
        elif status == 'left':
            return 'left'
        elif status == 'kicked':
            return 'kicked'
        else:
            return 'unknown'
    except:
        return 'unknown'

def is_bot_blocked_by_user(user_id):
    """بررسی بلاک بودن ربات توسط کاربر با ارسال یک پیام آزمایشی"""
    try:
        bot.send_chat_action(user_id, 'typing')
        return False  # اگر خطایی رخ نداد، بلاک نیست
    except Exception as e:
        if "Forbidden: bot was blocked by the user" in str(e):
            return True
        else:
            # خطای دیگه‌ای (مثلاً کاربر ربات رو استارت نکرده)
            return None  # نامشخص

def get_user_online_status(user_id):
    """تلاش برای فهمیدن آنلاین بودن کاربر (غیرمستقیم)"""
    # این کار دقیق نیست، فقط با ارسال یک پیام و بررسی last seen می‌شه تخمین زد
    # اما تلگرام چنین اطلاعاتی رو در اختیار ربات نمی‌ذاره. فقط برای کاربران عادی در حالت خصوصی می‌شه از getChat استفاده کرد.
    # در گروه‌ها می‌شه آخرین فعالیت رو دید؟ خیر.
    # ما فقط یک پیام چت اکشن می‌فرستیم و در صورت موفقیت، احتمالاً آنلاین بوده (اما نه همیشه)
    try:
        bot.send_chat_action(user_id, 'typing')
        return "احتمالاً آنلاین"  # در بهترین حالت
    except:
        return "آفلاین یا بلاک کرده"

def compute_message_hash(message):
    """محاسبه هش محتوای پیام (برای تشخیص تغییرات احتمالی)"""
    # اطلاعاتی که می‌تونیم هش کنیم: متن، کپشن، فایل‌آیدی، و...
    # برای سادگی، از ترکیبی از متن و message_id و date استفاده می‌کنیم
    content = f"{message.message_id}{message.date}{message.text}{message.caption}"
    return hashlib.sha256(content.encode()).hexdigest()[:8]

def generate_qr(data):
    """تولید QR کد از داده و برگرداندن BytesIO"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    bio.name = 'qr.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# ================== هندلر اصلی دستور infomy ==================
@bot.message_handler(commands=['infomy'])
def mystart(message):
    chat = message.chat
    user = message.from_user
    msg = message
    user_id = user.id
    chat_id = chat.id

    # به‌روزرسانی اطلاعات کاربر در دیتابیس
    update_user_info(user)

    # لاگ درخواست
    log_request(user_id, '/infomy', chat_id, details={'chat_type': chat.type})

    # دریافت زبان کاربر
    lang = get_user_lang(user_id)

    # ------------------ اطلاعات کاربر ------------------
    username = f"@{user.username}" if user.username else _(user_id, 'no')
    first_name = user.first_name or _(user_id, 'unknown')
    last_name = user.last_name or ''
    full_name = f"{first_name} {last_name}".strip()
    language = user.language_code or _(user_id, 'unknown')
    is_bot_user = _(user_id, 'yes') if user.is_bot else _(user_id, 'no')
    is_premium = _(user_id, 'yes') if getattr(user, 'is_premium', False) else _(user_id, 'no')
    photos_count = get_profile_photos_count(user_id)
    profile_link = f"tg://user?id={user_id}"

    # وضعیت آنلاین و بلاک (با احتیاط)
    online_status = get_user_online_status(user_id)
    block_status = is_bot_blocked_by_user(user_id)
    if block_status is True:
        block_status = _(user_id, 'yes')
    elif block_status is False:
        block_status = _(user_id, 'no')
    else:
        block_status = _(user_id, 'unknown')

    # ------------------ اطلاعات چت ------------------
    chat_type_map = {
        'private': _(user_id, 'chat_type_private') if 'chat_type_private' in translations[lang] else 'خصوصی',
        'group': 'گروه',
        'supergroup': 'سوپرگروه',
        'channel': 'کانال'
    }
    chat_type = chat_type_map.get(chat.type, chat.type)
    chat_title = chat.title if chat.type != 'private' else _(user_id, 'not_available')
    chat_username = f"@{chat.username}" if chat.username else _(user_id, 'no')
    chat_link = f"https://t.me/{chat.username}" if chat.username else None
    chat_members = get_chat_members_count(chat_id) if chat.type != 'private' else _(user_id, 'not_available')
    user_role = get_user_role_in_chat(chat_id, user_id) if chat.type != 'private' else _(user_id, 'not_available')
    # ترجمه نقش
    role_trans = {
        'creator': _(user_id, 'creator'),
        'admin': _(user_id, 'admin'),
        'member': _(user_id, 'member'),
        'restricted': _(user_id, 'restricted'),
        'left': _(user_id, 'left'),
        'kicked': 'اخراج شده',
        'unknown': _(user_id, 'unknown')
    }
    user_role = role_trans.get(user_role, user_role)

    # ------------------ اطلاعات پیام ------------------
    message_id = msg.message_id
    message_date = datetime.fromtimestamp(msg.date).strftime("%Y-%m-%d %H:%M:%S")
    edit_date = datetime.fromtimestamp(msg.edit_date).strftime("%Y-%m-%d %H:%M:%S") if msg.edit_date else _(user_id, 'no')
    # نوع محتوا
    content_type = msg.content_type
    message_hash = compute_message_hash(msg)

    # ------------------ اطلاعات ربات ------------------
    try:
        bot_info = bot.get_me()
        bot_id = bot_info.id
        bot_username = f"@{bot_info.username}" if bot_info.username else _(user_id, 'no')
        bot_name = bot_info.first_name
        bot_can_join = _(user_id, 'yes') if getattr(bot_info, 'can_join_groups', False) else _(user_id, 'no')
        bot_can_read = _(user_id, 'yes') if getattr(bot_info, 'can_read_all_group_messages', False) else _(user_id, 'no')
        bot_inline = _(user_id, 'yes') if getattr(bot_info, 'supports_inline_queries', False) else _(user_id, 'no')
    except:
        bot_id = "?"
        bot_username = "?"
        bot_name = "?"
        bot_can_join = bot_can_read = bot_inline = _(user_id, 'unknown')

    # ------------------ اطلاعات سیستم ------------------
    uptime = get_uptime()
    python_version = sys.version.split()[0]
    lib_version = telebot.__version__
    memory = get_memory_usage()

    # ------------------ ساخت متن با توجه به زبان ------------------
    text = f"""
**{_(user_id, 'your_info')}**
├─ {_(user_id, 'id')}: `{user_id}`
├─ {_(user_id, 'username')}: {username}
├─ {_(user_id, 'fullname')}: {full_name}
├─ {_(user_id, 'lang')}: {language}
├─ {_(user_id, 'is_bot')}: {is_bot_user}
├─ {_(user_id, 'premium')}: {is_premium}
├─ {_(user_id, 'photos_count')}: {photos_count}
├─ {_(user_id, 'profile_link')}: [link]({profile_link})
├─ {_(user_id, 'online_status')}: {online_status}
└─ {_(user_id, 'block_status')}: {block_status}

**{_(user_id, 'chat_info')}**
├─ {_(user_id, 'chat_id')}: `{chat_id}`
├─ {_(user_id, 'chat_type')}: {chat_type}
├─ {_(user_id, 'chat_title')}: {chat_title}
├─ {_(user_id, 'chat_username')}: {chat_username}
├─ {_(user_id, 'chat_link')}: {f'[link]({chat_link})' if chat_link else _(user_id, 'no')}
├─ {_(user_id, 'chat_members')}: {chat_members}
└─ {_(user_id, 'user_role')}: {user_role}

**{_(user_id, 'message_info')}**
├─ {_(user_id, 'message_id')}: `{message_id}`
├─ {_(user_id, 'message_date')}: {message_date}
├─ {_(user_id, 'message_edit')}: {edit_date}
├─ {_(user_id, 'message_type')}: {content_type}
└─ {_(user_id, 'message_hash')}: `{message_hash}`

**{_(user_id, 'bot_info')}**
├─ {_(user_id, 'bot_id')}: `{bot_id}`
├─ {_(user_id, 'bot_username')}: {bot_username}
├─ {_(user_id, 'bot_name')}: {bot_name}
├─ {_(user_id, 'bot_can_join')}: {bot_can_join}
├─ {_(user_id, 'bot_can_read')}: {bot_can_read}
├─ {_(user_id, 'bot_inline')}: {bot_inline}
└─ {_(user_id, 'bot_uptime')}: {uptime}

**{_(user_id, 'system_info')}**
├─ {_(user_id, 'python_version')}: {python_version}
├─ {_(user_id, 'lib_version')}: {lib_version}
└─ {_(user_id, 'memory_usage')}: {memory}

🔍 *درخواست‌دهنده: playertop*
    """.strip()

    # ------------------ ساخت کیبورد اینلاین ------------------
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn_refresh = InlineKeyboardButton(_(user_id, 'refresh'), callback_data=f"refresh_{user_id}")
    btn_share = InlineKeyboardButton(_(user_id, 'share'), callback_data=f"share_{user_id}")
    btn_qr = InlineKeyboardButton(_(user_id, 'qr'), callback_data=f"qr_{user_id}")
    btn_copy = InlineKeyboardButton(_(user_id, 'copy'), callback_data=f"copy_{user_id}")
    btn_lang = InlineKeyboardButton(_(user_id, 'language'), callback_data="lang")
    btn_close = InlineKeyboardButton(_(user_id, 'close'), callback_data="close")
    keyboard.add(btn_refresh, btn_share, btn_qr, btn_copy, btn_lang, btn_close)

    # ------------------ ارسال پیام ------------------
    try:
        bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Markdown error: {e}")
        # ارسال بدون مارکداون
        bot.send_message(chat_id, text.replace('*', '').replace('`', ''), reply_markup=keyboard)

# ================== هندلر Callback ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data.startswith("refresh_"):
        # تازه‌سازی اطلاعات
        # برای تازه‌سازی، می‌توانیم دوباره دستور را برای همان کاربر شبیه‌سازی کنیم
        # اما برای سادگی، یک پیام جدید با همان متن می‌فرستیم
        bot.answer_callback_query(call.id, "در حال تازه‌سازی...")
        # ساختن یک پیام مجازی از روی call.message
        # بهترین کار این است که دوباره تابع mystart را با call.message فراخوانی کنیم
        mystart(call.message)

    elif data.startswith("share_"):
        # اشتراک‌گذاری اطلاعات
        text = f"اطلاعات من در ربات: {call.message.text[:100]}..."
        bot.answer_callback_query(call.id, "برای اشتراک‌گذاری، متن زیر را کپی کنید:")
        bot.send_message(user_id, text)

    elif data.startswith("qr_"):
        # تولید QR کد از اطلاعات کاربر
        info = f"User ID: {user_id}\nUsername: {call.from_user.username}\n"
        qr_img = generate_qr(info)
        bot.send_photo(user_id, qr_img, caption="QR کد اطلاعات شما")
        bot.answer_callback_query(call.id, "QR کد ساخته شد.")

    elif data.startswith("copy_"):
        # کپی اطلاعات (فقط یک پیام راهنما)
        bot.answer_callback_query(call.id, "می‌توانید متن پیام را manually کپی کنید.")

    elif data == "lang":
        # نمایش دکمه‌های انتخاب زبان
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("فارسی", callback_data="set_lang_fa"),
                   InlineKeyboardButton("English", callback_data="set_lang_en"))
        bot.edit_message_text(_(user_id, 'choose_lang'), user_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("set_lang_"):
        lang = data.split("_")[2]
        set_user_lang(user_id, lang)
        bot.answer_callback_query(call.id, _(user_id, 'lang_changed') if lang=='fa' else _(user_id, 'lang_changed_en'))
        # حذف پیام انتخاب زبان
        bot.delete_message(user_id, call.message.message_id)

    elif data == "close":
        bot.delete_message(user_id, call.message.message_id)
        bot.answer_callback_query(call.id, "بسته شد.")

    else:
        bot.answer_callback_query(call.id, "عملیات نامشخص.")

# ================== هندلر استارت (خوش‌آمدگویی) ==================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    update_user_info(message.from_user)
    welcome_text = f"سلام {message.from_user.first_name}!\nبه ربات اطلاعات پیشرفته خوش آمدید.\nاز دستور /infomy برای دریافت اطلاعات کامل استفاده کنید."
    bot.reply_to(message, welcome_text)

# ================== اجرای ربات ==================
if __name__ == "__main__":
    logger.info("Bot started successfully.")
    bot.infinity_polling()