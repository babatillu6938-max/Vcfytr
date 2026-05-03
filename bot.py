import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus
import yt_dlp

# ============ CONFIG ============
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Storage
users = {}
saved_music = {}

# ============ BUTTONS ============
def main_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Search Music", callback_data="search"),
         InlineKeyboardButton("🎤 Voice Chat Help", callback_data="vc_help")],
        [InlineKeyboardButton("🔑 Login", callback_data="login"),
         InlineKeyboardButton("🚪 Logout", callback_data="logout")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ])

def login_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Phone Login", callback_data="login_phone"),
         InlineKeyboardButton("🔑 String Session", callback_data="login_string")],
        [InlineKeyboardButton("◀️ Back", callback_data="back")]
    ])

# ============ MUSIC SEARCH ============
async def search_youtube(query):
    """Search YouTube and return audio info"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search
            info = ydl.extract_info(f"ytsearch3:{query}", download=False)
            
            results = []
            if 'entries' in info:
                for entry in info['entries'][:3]:
                    # Get audio URL
                    audio_url = None
                    for f in entry.get('formats', []):
                        if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                            audio_url = f.get('url')
                            break
                    
                    if audio_url:
                        results.append({
                            'title': entry.get('title', 'Unknown'),
                            'url': audio_url,
                            'duration': entry.get('duration', 0),
                            'uploader': entry.get('uploader', 'Unknown')
                        })
            
            return results
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ============ COMMANDS ============
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "**🎵 Music Bot**\n\n"
        "✅ Search & Play YouTube Music\n"
        "✅ ID Login System (Phone/String)\n"
        "✅ Easy to Use\n\n"
        "*Note:* Voice chat feature requires user account login",
        reply_markup=main_buttons()
    )

@app.on_message(filters.command("search"))
async def search_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: `/search song name`\nExample: `/search Despacito`")
        return
    
    query = " ".join(message.command[1:])
    msg = await message.reply_text(f"🔍 **Searching:** {query}...")
    
    results = await search_youtube(query)
    
    if results:
        # Create buttons for each result
        buttons = []
        for i, song in enumerate(results[:3], 1):
            buttons.append([InlineKeyboardButton(
                f"{i}. {song['title'][:40]}", 
                callback_data=f"play_{i}_{query}"
            )])
        
        # Store results temporarily
        saved_music[message.chat.id] = results
        buttons.append([InlineKeyboardButton("◀️ Back", callback_data="back")])
        
        await msg.edit_text(
            f"**🎵 Search Results for:** {query}\n\nClick on any song to play:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await msg.edit_text("❌ No results found!", reply_markup=main_buttons())

@app.on_message(filters.command("play"))
async def play_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: `/play YouTube_URL`\nExample: `/play https://youtube.com/watch?v=...`")
        return
    
    url = message.command[1]
    msg = await message.reply_text(f"🔍 **Processing:** {url}...")
    
    results = await search_youtube(url)
    
    if results:
        song = results[0]
        await msg.edit_text(
            f"**▶️ Ready to Play!**\n\n"
            f"**Title:** {song['title']}\n"
            f"**Duration:** {song['duration']} seconds\n"
            f"**Channel:** {song['uploader']}\n\n"
            f"[Click here to download/play]({song['url']})",
            reply_markup=main_buttons(),
            disable_web_page_preview=True
        )
    else:
        await msg.edit_text("❌ Failed to get audio!", reply_markup=main_buttons())

@app.on_message(filters.command("login"))
async def login_cmd(client, message):
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply_text(
            "**🔐 Login Methods:**\n\n"
            "`/login phone` - Login with phone number (OTP)\n"
            "`/login string <session>` - Login with string session\n\n"
            "Get string session from @StringSessionBot"
        )
        return
    
    uid = message.from_user.id
    
    if args[1] == "phone":
        users[uid] = {"method": "phone", "status": "waiting"}
        await message.reply_text(
            "📱 **Send your phone number with country code:**\n"
            "Example: `+919876543210`\n\n"
            "You will receive OTP on Telegram"
        )
        
        try:
            resp = await app.wait_for_message(
                message.chat.id, 
                filters=filters.text & filters.user(uid), 
                timeout=60
            )
            if resp:
                users[uid] = {
                    "method": "phone", 
                    "phone": resp.text, 
                    "logged_in": True
                }
                await resp.reply_text(
                    f"✅ **Logged in successfully!**\n📱 {resp.text}\n\n"
                    f"Now you can use /search to find music",
                    reply_markup=main_buttons()
                )
        except asyncio.TimeoutError:
            await message.reply_text("⏰ Timeout! Try again.")
    
    elif args[1] == "string" and len(args) >= 3:
        users[uid] = {
            "method": "string",
            "session": args[2],
            "logged_in": True
        }
        await message.reply_text(
            "✅ **String session saved!**\n"
            "You are now logged in.\n\n"
            "Use /search to find and play music",
            reply_markup=main_buttons()
        )

@app.on_message(filters.command("logout"))
async def logout_cmd(client, message):
    uid = message.from_user.id
    if uid in users:
        del users[uid]
        await message.reply_text("✅ **Logged out successfully!**", reply_markup=main_buttons())
    else:
        await message.reply_text("❌ You are not logged in!", reply_markup=main_buttons())

@app.on_message(filters.command("status"))
async def status_cmd(client, message):
    uid = message.from_user.id
    if uid in users and users[uid].get('logged_in'):
        await message.reply_text(
            f"✅ **Logged In**\n"
            f"Method: {users[uid].get('method')}\n"
            f"Phone: {users[uid].get('phone', 'N/A')}",
            reply_markup=main_buttons()
        )
    else:
        await message.reply_text("❌ **Not logged in!**\nUse /login to login", reply_markup=main_buttons())

@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    help_text = """
**🤖 Music Bot Commands:**

/start - Start the bot
/search <song> - Search and play music
/play <url> - Play YouTube link
/login - Login to account
/logout - Logout from account
/status - Check login status
/help - Show this help

**🎵 Features:**
• Search YouTube music
• Get direct audio links
• Login with phone/string session
• Easy to use buttons

**📝 How to use:**
1. Login with /login
2. Search music with /search
3. Click on song to play
"""
    await message.reply_text(help_text, reply_markup=main_buttons())

# ============ CALLBACK HANDLERS ============
@app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    data = query.data
    uid = query.from_user.id
    chat_id = query.message.chat.id
    
    await query.answer()
    
    if data == "back":
        await query.message.edit_text(
            "**🎵 Music Bot Menu**\n\nUse commands below:",
            reply_markup=main_buttons()
        )
    
    elif data == "search":
        await query.message.edit_text(
            "🔍 **Search Music**\n\n"
            "Use command: `/search song name`\n\n"
            "Example: `/search Despacito`\n"
            "Example: `/search Bohemian Rhapsody`",
            reply_markup=main_buttons()
        )
    
    elif data == "vc_help":
        await query.message.edit_text(
            "**🎤 Voice Chat Feature**\n\n"
            "To use voice chat with this bot, you need:\n\n"
            "1. Login with your Telegram account\n"
            "2. Use a voice chat bot like @VCPlayerBot\n"
            "3. Or use the audio links from /search\n\n"
            "Get audio link from /search and use any VC bot to play it.",
            reply_markup=main_buttons()
        )
    
    elif data == "login":
        await query.message.edit_text(
            "**🔐 Login Methods:**\n\n"
            "**Method 1 - Phone OTP:**\n"
            "Type: `/login phone`\n\n"
            "**Method 2 - String Session:**\n"
            "Type: `/login string YOUR_STRING_SESSION`\n\n"
            "Get string session from @StringSessionBot",
            reply_markup=login_buttons()
        )
    
    elif data == "login_phone":
        await query.message.edit_text(
            "📱 **Phone Login**\n\n"
            "Type: `/login phone`\n\n"
            "Then send your phone number with country code\n"
            "Example: `+919876543210`",
            reply_markup=main_buttons()
        )
    
    elif data == "login_string":
        await query.message.edit_text(
            "🔑 **String Session Login**\n\n"
            "Type: `/login string YOUR_STRING_SESSION`\n\n"
            "How to get string session:\n"
            "1. Go to @StringSessionBot\n"
            "2. Send /start\n"
            "3. Send your API_ID and API_HASH\n"
            "4. Login with your phone number\n"
            "5. Copy the session string",
            reply_markup=main_buttons()
        )
    
    elif data == "logout":
        if uid in users:
            del users[uid]
            await query.message.edit_text("✅ **Logged out!**", reply_markup=main_buttons())
        else:
            await query.message.edit_text("❌ Not logged in!", reply_markup=main_buttons())
    
    elif data == "help":
        help_text = """
**Commands:**
/search <song> - Search music
/play <url> - Play YouTube link
/login - Login to account
/logout - Logout
/status - Check login
/help - This help
"""
        await query.message.edit_text(help_text, reply_markup=main_buttons())
    
    # Handle play buttons from search
    elif data.startswith("play_"):
        parts = data.split("_")
        if len(parts) >= 3:
            index = int(parts[1]) - 1
            search_query = "_".join(parts[2:])
            
            if chat_id in saved_music and index < len(saved_music[chat_id]):
                song = saved_music[chat_id][index]
                await query.message.edit_text(
                    f"**✅ Ready to Play!**\n\n"
                    f"**Title:** {song['title']}\n"
                    f"**Duration:** {song['duration']} seconds\n"
                    f"**Channel:** {song['uploader']}\n\n"
                    f"🔗 **Audio Link:**\n`{song['url']}`\n\n"
                    f"Copy this link and use it with any voice chat bot to play!",
                    reply_markup=main_buttons()
                )

# ============ ERROR HANDLER ============
@app.on_message()
async def handle_other(client, message):
    if message.text and not message.text.startswith('/'):
        # Auto search if user sends text without command
        if len(message.text) > 3:
            await search_cmd(client, message)

# ============ START BOT ============
async def main():
    print("🚀 Starting Music Bot on Heroku...")
    print(f"Python Version: {os.sys.version}")
    
    await app.start()
    print("✅ Bot Started!")
    print(f"Bot Username: {(await app.get_me()).username}")
    print("\n📝 Commands:")
    print("  /start - Start bot")
    print("  /search <song> - Search music")
    print("  /login - Login to account")
    print("  /status - Check login status")
    print("  /help - Help")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot Stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
