import os
import random
import string
import time
import threading
import sqlite3
import requests
import names
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ------------------- Configuration -------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")  # Set in Render environment
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))        # Admin chat ID for logs

# Admin user IDs (add more as needed)
ADMIN_IDS = [ADMIN_CHAT_ID] if ADMIN_CHAT_ID else []

# Global proxy setting (None = no proxy)
proxies = None

# Color codes for console output (kept from original, but not used in bot)
rd, gn, lgn, yw, lrd, be, pe = '\033[00;31m', '\033[00;32m', '\033[01;32m', '\033[01;33m', '\033[01;31m', '\033[94m', '\033[01;35m'
cn, k, g = '\033[00;36m', '\033[90m', '\033[38;5;130m'

# ------------------- Database Setup -------------------
def get_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            password TEXT,
            email TEXT,
            sessionid TEXT,
            csrftoken TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    conn.close()

# ------------------- Helper Functions -------------------
def is_admin(user_id):
    return user_id in ADMIN_IDS

def save_account_to_db(user_id, username, password, email, sessionid, csrftoken):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO accounts (user_id, username, password, email, sessionid, csrftoken) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, password, email, sessionid, csrftoken)
    )
    conn.commit()
    conn.close()

def log_admin_action(action, details):
    """Send a log message to the admin chat."""
    if ADMIN_CHAT_ID:
        bot.send_message(ADMIN_CHAT_ID, f"[ADMIN LOG] {action}: {details}")

# ------------------- Instagram Functions (adapted) -------------------
def get_headers(Country, Language):
    """Same as original, but with error handling"""
    try:
        an_agent = (
            f'Mozilla/5.0 (Linux; Android {random.randint(9, 13)}; '
            f'{"".join(random.choices(string.ascii_uppercase, k=3))}{random.randint(111, 999)}) '
            f'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Mobile Safari/537.36'
        )
        r = requests.get(
            'https://www.instagram.com/api/v1/web/accounts/login/ajax/',
            headers={'user-agent': an_agent},
            proxies=proxies,
            timeout=30
        ).cookies

        response1 = requests.get(
            'https://www.instagram.com/',
            headers={'user-agent': an_agent},
            proxies=proxies,
            timeout=30
        )
        appid = response1.text.split('APP_ID":"')[1].split('"')[0]
        rollout = response1.text.split('rollout_hash":"')[1].split('"')[0]

        headers = {
            'authority': 'www.instagram.com',
            'accept': '*/*',
            'accept-language': f'{Language}-{Country},en-US;q=0.8,en;q=0.7',
            'content-type': 'application/x-www-form-urlencoded',
            'cookie': f'dpr=3; csrftoken={r["csrftoken"]}; mid={r["mid"]}; ig_did={r["ig_did"]}',
            'origin': 'https://www.instagram.com',
            'referer': 'https://www.instagram.com/accounts/signup/email/',
            'user-agent': an_agent,
            'x-csrftoken': r["csrftoken"],
            'x-ig-app-id': str(appid),
            'x-instagram-ajax': str(rollout),
            'x-web-device-id': r["ig_did"],
        }
        return headers
    except Exception as e:
        raise Exception(f"Failed to get headers: {e}")

def get_username_suggestion(Headers, Name, Email):
    try:
        data = {'email': Email, 'name': Name + str(random.randint(1, 99))}
        response = requests.post(
            'https://www.instagram.com/api/v1/web/accounts/username_suggestions/',
            headers=Headers, data=data, proxies=proxies, timeout=30
        )
        if 'status":"ok' in response.text:
            return random.choice(response.json()['suggestions'])
        else:
            raise Exception("Username suggestion failed")
    except Exception as e:
        raise Exception(f"Get username error: {e}")

def send_verify_email(Headers, Email):
    try:
        data = {
            'device_id': Headers['cookie'].split('mid=')[1].split(';')[0],
            'email': Email
        }
        response = requests.post(
            'https://www.instagram.com/api/v1/accounts/send_verify_email/',
            headers=Headers, data=data, proxies=proxies, timeout=30
        )
        return response.text
    except Exception as e:
        raise Exception(f"Send verify email error: {e}")

def check_confirmation_code(Headers, Email, Code):
    try:
        data = {
            'code': Code,
            'device_id': Headers['cookie'].split('mid=')[1].split(';')[0],
            'email': Email
        }
        response = requests.post(
            'https://www.instagram.com/api/v1/accounts/check_confirmation_code/',
            headers=Headers, data=data, proxies=proxies, timeout=30
        )
        return response
    except Exception as e:
        raise Exception(f"Check code error: {e}")

def upload_profile_pic(sessionid, csrftoken, retries=3):
    try:
        folder = 'Profile_pic'
        if not os.path.exists(folder):
            os.makedirs(folder)
            return "No profile pictures found in folder."
        valid_exts = ['.jpg', '.jpeg', '.png']
        files = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in valid_exts]
        if not files:
            return "No profile pictures found in folder."
        photo_path = os.path.join(folder, random.choice(files))

        url = 'https://www.instagram.com/accounts/web_change_profile_picture/'
        headers = {
            'cookie': f'sessionid={sessionid}; csrftoken={csrftoken};',
            'x-csrftoken': csrftoken,
            'referer': 'https://www.instagram.com/accounts/edit/',
            'x-requested-with': 'XMLHttpRequest',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }
        for attempt in range(1, retries + 1):
            with open(photo_path, 'rb') as f:
                files = {'profile_pic': f}
                resp = requests.post(url, headers=headers, files=files, proxies=proxies)
            if resp.status_code == 200 and '"changed_profile":true' in resp.text:
                return f"Profile picture uploaded! [Attempt {attempt}]"
        return f"Failed to upload profile picture after {retries} attempts."
    except Exception as e:
        return f"Exception during profile pic upload: {e}"

def convert_to_professional(sessionid, csrftoken, retries=3):
    try:
        url = "https://www.instagram.com/api/v1/business/account/convert_account/"
        headers = {
            'cookie': f'sessionid={sessionid}; csrftoken={csrftoken};',
            'x-csrftoken': csrftoken,
            'referer': 'https://www.instagram.com/accounts/convert_to_professional_account/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'content-type': 'application/x-www-form-urlencoded',
            'x-ig-app-id': '1217981644879628',
            'x-requested-with': 'XMLHttpRequest'
        }
        category_ids = [
            "180164648685982",
            "180410820992720",
            "180504230065143",
            "180213508993482",
            "180144472006690",
            "180559408665151"
        ]
        category_id = random.choice(category_ids)
        data = {
            "category_id": category_id,
            "create_business_id": "true",
            "entry_point": "ig_web_settings",
            "set_public": "true",
            "should_bypass_contact_check": "true",
            "should_show_category": "0",
            "to_account_type": "3",
            "jazoest": "22663"
        }
        for attempt in range(1, retries + 1):
            resp = requests.post(url, headers=headers, data=data, proxies=proxies)
            if resp.status_code == 200 and '\"status\":\"ok\"' in resp.text:
                return f"Converted to Professional Account! Category ID: {category_id}"
        return f"Failed to convert account after {retries} attempts."
    except Exception as e:
        return f"Exception during conversion: {e}"

def create_account(headers, email, signup_code):
    """Return (username, password, sessionid, csrftoken) or raise exception."""
    try:
        firstname = names.get_first_name()
        username = get_username_suggestion(headers, firstname, email)
        password = firstname.strip() + '@' + str(random.randint(111, 999))

        data = {
            'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{round(time.time())}:{password}',
            'email': email,
            'username': username,
            'first_name': firstname,
            'month': random.randint(1, 12),
            'day': random.randint(1, 28),
            'year': random.randint(1990, 2001),
            'client_id': headers['cookie'].split('mid=')[1].split(';')[0],
            'seamless_login_enabled': '1',
            'tos_version': 'row',
            'force_sign_up_code': signup_code,
        }

        response = requests.post(
            'https://www.instagram.com/api/v1/web/accounts/web_create_ajax/',
            headers=headers, data=data, proxies=proxies, timeout=30
        )
        if '"account_created":true' in response.text:
            sessionid = response.cookies.get('sessionid')
            csrftoken = headers['x-csrftoken']
            return username, password, sessionid, csrftoken
        else:
            raise Exception("Account creation failed: " + response.text)
    except Exception as e:
        raise Exception(f"Create account error: {e}")

# ------------------- Bot Instance -------------------
bot = telebot.TeleBot(BOT_TOKEN)

# ------------------- User State Management -------------------
user_temp = {}  # {user_id: {'email': str, 'headers': dict, 'signup_code': str?}}

# ------------------- Handlers -------------------
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name

    # Register user in database
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                   (user_id, username, first_name))
    conn.commit()
    conn.close()

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Create Account", callback_data="create"),
        InlineKeyboardButton("📋 My Accounts", callback_data="myaccounts"),
        InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        InlineKeyboardButton("💬 Support", callback_data="support")
    )
    bot.send_message(user_id, "Welcome! Choose an option:", reply_markup=markup)

@bot.message_handler(commands=['myaccounts'])
def myaccounts(message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM accounts WHERE user_id=?", (user_id,))
    accounts = cursor.fetchall()
    conn.close()

    if not accounts:
        bot.send_message(user_id, "❌ No accounts created yet.")
        return

    for acc_id, username, email in accounts:
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("🔑 Show Password", callback_data=f"showpwd_{acc_id}"),
            InlineKeyboardButton("🖼 Change Pic", callback_data=f"changepic_{acc_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"delacc_{acc_id}")
        )
        markup.add(InlineKeyboardButton("📊 Stats", callback_data=f"stats_{acc_id}"))
        bot.send_message(user_id, f"📧 {email}\n👤 {username}", reply_markup=markup)

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(user_id, "⛔ Unauthorized.")
        return

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("👥 All Users", callback_data="admin_users"),
        InlineKeyboardButton("📊 All Accounts", callback_data="admin_accounts"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("📈 Statistics", callback_data="admin_stats"),
        InlineKeyboardButton("🗑 Delete User", callback_data="admin_deluser")
    )
    bot.send_message(user_id, "🔧 Admin Panel", reply_markup=markup)

# ------------------- Callback Handlers -------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "create":
        bot.send_message(user_id, "Please enter your email address:")
        bot.register_next_step_handler(call.message, process_email)
        bot.answer_callback_query(call.id)

    elif data == "myaccounts":
        myaccounts(call.message)
        bot.answer_callback_query(call.id)

    elif data.startswith("showpwd_"):
        acc_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT password, user_id FROM accounts WHERE id=?", (acc_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[1] == user_id:
            bot.send_message(user_id, f"🔑 Password: `{row[0]}`", parse_mode="Markdown")
        else:
            bot.send_message(user_id, "❌ Account not found or you don't have permission.")
        bot.answer_callback_query(call.id)

    elif data.startswith("changepic_"):
        acc_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sessionid, csrftoken, user_id FROM accounts WHERE id=?", (acc_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[2] == user_id:
            sessionid, csrftoken = row[0], row[1]
            # Run in thread to avoid blocking
            def change_pic_task(chat_id, sessionid, csrftoken):
                result = upload_profile_pic(sessionid, csrftoken)
                bot.send_message(chat_id, result)
            threading.Thread(target=change_pic_task, args=(user_id, sessionid, csrftoken)).start()
            bot.send_message(user_id, "⏳ Changing profile picture, please wait...")
        else:
            bot.send_message(user_id, "❌ Account not found or you don't have permission.")
        bot.answer_callback_query(call.id)

    elif data.startswith("delacc_"):
        acc_id = int(data.split("_")[1])
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Yes", callback_data=f"confirm_del_{acc_id}"),
            InlineKeyboardButton("❌ No", callback_data="cancel_del")
        )
        bot.send_message(user_id, "Are you sure you want to delete this account?", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("confirm_del_"):
        acc_id = int(data.split("_")[2])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id=? AND user_id=?", (acc_id, user_id))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "✅ Account deleted from database.")
        bot.answer_callback_query(call.id)

    elif data == "cancel_del":
        bot.send_message(user_id, "Deletion cancelled.")
        bot.answer_callback_query(call.id)

    # Admin callbacks
    elif data == "admin_users":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, first_name, join_date FROM users")
        users = cursor.fetchall()
        conn.close()
        if not users:
            bot.send_message(user_id, "No users found.")
        else:
            text = "👥 *Users List*\n\n"
            for u in users:
                text += f"`{u[0]}` - @{u[1] or 'None'} ({u[2]})\nJoined: {u[3]}\n\n"
            bot.send_message(user_id, text[:4000], parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "admin_accounts":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, email, created_at FROM accounts ORDER BY created_at DESC")
        accounts = cursor.fetchall()
        conn.close()
        if not accounts:
            bot.send_message(user_id, "No accounts found.")
        else:
            text = "📊 *All Accounts*\n\n"
            for a in accounts:
                text += f"👤 UserID: `{a[0]}`\n👤 Username: {a[1]}\n📧 Email: {a[2]}\n📅 Created: {a[3]}\n\n"
            bot.send_message(user_id, text[:4000], parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "admin_broadcast":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        bot.send_message(user_id, "Send me the message you want to broadcast to all users.")
        bot.register_next_step_handler(call.message, broadcast_message)
        bot.answer_callback_query(call.id)

    elif data == "admin_stats":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM accounts")
        total_accounts = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE date(created_at) = date('now')")
        today_accounts = cursor.fetchone()[0]
        conn.close()
        stats = f"📈 *Statistics*\n\n👥 Total Users: {total_users}\n📋 Total Accounts: {total_accounts}\n📅 Today's Accounts: {today_accounts}"
        bot.send_message(user_id, stats, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "admin_deluser":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        bot.send_message(user_id, "Enter the User ID to delete:")
        bot.register_next_step_handler(call.message, delete_user_by_id)
        bot.answer_callback_query(call.id)

    # Placeholder for settings/support
    elif data == "settings":
        bot.send_message(user_id, "Settings are under construction.")
        bot.answer_callback_query(call.id)
    elif data == "support":
        bot.send_message(user_id, "For support, contact @DarkFrozenOwner")
        bot.answer_callback_query(call.id)

# ------------------- Step Handlers for Account Creation -------------------
def process_email(message):
    user_id = message.from_user.id
    email = message.text.strip()
    user_temp[user_id] = {'email': email}
    bot.send_message(user_id, "⏳ Preparing...")
    # Get headers in background
    def get_headers_task(chat_id, email):
        try:
            headers = get_headers('US', 'en')
            user_temp[chat_id]['headers'] = headers
            # Send verification email
            ss = send_verify_email(headers, email)
            if 'email_sent":true' in ss:
                bot.send_message(chat_id, f"📧 Verification code sent to {email}. Please enter the code:")
                bot.register_next_step_handler_by_chat_id(chat_id, process_otp)
            else:
                bot.send_message(chat_id, "❌ Failed to send verification code. Try again later.")
                user_temp.pop(chat_id, None)
        except Exception as e:
            bot.send_message(chat_id, f"❌ Error: {e}")
            user_temp.pop(chat_id, None)
    threading.Thread(target=get_headers_task, args=(user_id, email)).start()

def process_otp(message):
    user_id = message.from_user.id
    code = message.text.strip()
    temp = user_temp.get(user_id)
    if not temp or 'headers' not in temp:
        bot.send_message(user_id, "Session expired. Please start over with /start")
        return
    headers = temp['headers']
    email = temp['email']
    bot.send_message(user_id, "⏳ Verifying code...")
    try:
        resp = check_confirmation_code(headers, email, code)
        if 'status":"ok' in resp.text:
            signup_code = resp.json().get('signup_code')
            bot.send_message(user_id, "✅ Code verified. Creating account (may take 10-20 seconds)...")
            # Create account in background
            def create_task(chat_id, headers, email, signup_code):
                try:
                    username, password, sessionid, csrftoken = create_account(headers, email, signup_code)
                    # Save to DB
                    save_account_to_db(chat_id, username, password, email, sessionid, csrftoken)
                    # Send success message
                    msg = f"✅ Account created successfully!\n\n👤 Username: {username}\n🔑 Password: `{password}`\n📧 Email: {email}\n\nSessionID: `{sessionid}`"
                    bot.send_message(chat_id, msg, parse_mode="Markdown")
                    # Upload profile pic and convert in background
                    pic_result = upload_profile_pic(sessionid, csrftoken)
                    conv_result = convert_to_professional(sessionid, csrftoken)
                    bot.send_message(chat_id, f"📸 {pic_result}\n💼 {conv_result}")
                    # Admin log
                    log_admin_action("Account created", f"User {chat_id} created {username}")
                except Exception as e:
                    bot.send_message(chat_id, f"❌ Account creation failed: {e}")
                    log_admin_action("Account creation failed", f"User {chat_id}: {e}")
                finally:
                    user_temp.pop(chat_id, None)
            threading.Thread(target=create_task, args=(user_id, headers, email, signup_code)).start()
        else:
            bot.send_message(user_id, "❌ Invalid OTP. Please try again.")
            # Optionally allow retry
            user_temp.pop(user_id, None)
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {e}")
        user_temp.pop(user_id, None)

# ------------------- Admin Helper Functions -------------------
def broadcast_message(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        return
    broadcast_text = message.text
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    all_users = cursor.fetchall()
    conn.close()
    success = 0
    for (uid,) in all_users:
        try:
            bot.send_message(uid, broadcast_text)
            success += 1
        except:
            pass
    bot.send_message(user_id, f"✅ Broadcast sent to {success} users.")
    log_admin_action("Broadcast", f"Sent to {success} users")

def delete_user_by_id(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        return
    try:
        target_id = int(message.text.strip())
    except:
        bot.send_message(user_id, "Invalid User ID. Please enter a numeric ID.")
        return
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE user_id=?", (target_id,))
    cursor.execute("DELETE FROM users WHERE user_id=?", (target_id,))
    conn.commit()
    conn.close()
    bot.send_message(user_id, f"✅ User {target_id} and all their accounts deleted.")
    log_admin_action("Delete user", f"Admin {user_id} deleted user {target_id}")

# ------------------- Start Bot -------------------
if __name__ == "__main__":
    init_db()
    print("Bot started...")
    bot.infinity_polling()
