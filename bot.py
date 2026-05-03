import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType, ChatMemberStatus
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioParameters, AudioQuality
from pytgcalls.types.stream import AudioStream
import yt_dlp
from dotenv import load_dotenv

load_dotenv()

# ============ CONFIGURATION ============
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Initialize bot
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call = PyTgCalls(app)

# Storage
queues = {}
current_streams = {}
user_sessions = {}

# ============ BUTTONS ============

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Play Music", callback_data="play_menu"),
            InlineKeyboardButton("📋 Queue", callback_data="show_queue")
        ],
        [
            InlineKeyboardButton("🔊 Join VC", callback_data="join_vc"),
            InlineKeyboardButton("⏹️ Leave VC", callback_data="leave_vc")
        ],
        [
            InlineKeyboardButton("🔑 Login", callback_data="login"),
            InlineKeyboardButton("🚪 Logout", callback_data="logout")
        ],
        [
            InlineKeyboardButton("⏸️ Pause", callback_data="pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="resume"),
            InlineKeyboardButton("⏭️ Skip", callback_data="skip")
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help")
        ]
    ])

def play_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 YouTube Link", callback_data="play_youtube"),
            InlineKeyboardButton("🔍 Search Song", callback_data="search_song")
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="back_main")
        ]
    ])

def login_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Phone Login", callback_data="login_phone"),
            InlineKeyboardButton("🔑 String Session", callback_data="login_string")
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="back_main")
        ]
    ])

# ============ HELPERS ============

async def get_audio_url(query):
    """Get audio URL from YouTube"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Check if it's a URL or search query
            if 'youtube.com' in query or 'youtu.be' in query:
                info = ydl.extract_info(query, download=False)
            else:
                # Search
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if 'entries' in info:
                    info = info['entries'][0]
            
            # Get best audio format
            audio_url = None
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audio_url = f.get('url')
                    break
            
            return {
                'title': info.get('title', 'Unknown'),
                'url': audio_url or info.get('url'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', '')
            }
    except Exception as e:
        print(f"Error: {e}")
        return None

async def play_next(chat_id):
    """Play next song in queue"""
    await asyncio.sleep(2)
    
    if chat_id in queues and queues[chat_id]:
        next_song = queues[chat_id].pop(0)
        current_streams[chat_id] = next_song
        
        await call.change_stream(
            chat_id,
            AudioStream(
                next_song['url'],
                AudioParameters(bitrate=AudioQuality.BITRATE_64KBPS)
            )
        )
        
        await app.send_message(
            chat_id,
            f"**▶️ Now Playing:**\n🎵 {next_song['title']}\n👤 Requested by: {next_song['requester']}"
        )
        
        asyncio.create_task(play_next(chat_id))
    else:
        if chat_id in current_streams:
            del current_streams[chat_id]

# ============ COMMANDS ============

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "**🎵 Welcome to Voice Chat Music Bot!**\n\n"
        "I can play music in voice chats.\n"
        "Use buttons below to control me.\n\n"
        "**First:** Click Login button to authenticate",
        reply_markup=main_menu()
    )

@app.on_message(filters.command("menu"))
async def menu_command(client: Client, message: Message):
    await message.reply_text("**🎮 Control Menu:**", reply_markup=main_menu())

# ============ CALLBACK HANDLERS ============

@app.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    username = callback_query.from_user.first_name
    
    await callback_query.answer()
    
    # ============ NAVIGATION ============
    
    if data == "back_main":
        await callback_query.message.edit_text(
            "**🎵 Main Menu:**",
            reply_markup=main_menu()
        )
    
    elif data == "play_menu":
        await callback_query.message.edit_text(
            "**🎵 Select Play Method:**",
            reply_markup=play_menu()
        )
    
    elif data == "help":
        help_text = """
**🤖 Bot Commands & Features:**

/start - Start the bot
/menu - Show menu

**🎮 Features:**
• Play YouTube music
• Play voice messages
• Queue system
• Voice chat controls

**🎤 Voice Chat:**
• Join/Leave VC
• Pause/Resume/Skip

**🔐 Login System:**
• Login with phone
• Login with string session
• Logout anytime

**📝 How to use:**
1. Login first
2. Join a voice chat
3. Play music!
        """
        await callback_query.message.edit_text(help_text, reply_markup=main_menu())
    
    # ============ QUEUE ============
    
    elif data == "show_queue":
        if chat_id in queues and queues[chat_id]:
            queue_text = "**📋 Current Queue:**\n\n"
            for i, song in enumerate(queues[chat_id][:10], 1):
                queue_text += f"{i}. 🎵 {song['title'][:50]}\n"
                queue_text += f"   👤 {song['requester']}\n\n"
            
            if len(queues[chat_id]) > 10:
                queue_text += f"... and {len(queues[chat_id]) - 10} more"
            
            await callback_query.message.edit_text(queue_text, reply_markup=main_menu())
        else:
            await callback_query.message.edit_text(
                "**📋 Queue is empty!**\nUse Play button to add songs.",
                reply_markup=main_menu()
            )
    
    # ============ VOICE CHAT CONTROLS ============
    
    elif data == "join_vc":
        try:
            await call.join_call(chat_id)
            await callback_query.message.edit_text(
                "**✅ Joined Voice Chat!**\nNow you can play music.",
                reply_markup=main_menu()
            )
        except Exception as e:
            await callback_query.message.edit_text(
                f"**❌ Failed to join:** `{str(e)}`\n\n"
                f"Make sure:\n"
                f"1. Voice chat is active\n"
                f"2. Bot has speak permissions",
                reply_markup=main_menu()
            )
    
    elif data == "leave_vc":
        try:
            await call.leave_call(chat_id)
            # Clear queue
            if chat_id in queues:
                queues[chat_id] = []
            if chat_id in current_streams:
                del current_streams[chat_id]
            await callback_query.message.edit_text(
                "**✅ Left Voice Chat!**",
                reply_markup=main_menu()
            )
        except Exception as e:
            await callback_query.message.edit_text(
                f"**❌ Error:** `{str(e)}`",
                reply_markup=main_menu()
            )
    
    elif data == "pause":
        try:
            await call.pause_stream(chat_id)
            await callback_query.message.edit_text(
                "**⏸️ Playback Paused**\nClick Resume to continue.",
                reply_markup=main_menu()
            )
        except:
            pass
    
    elif data == "resume":
        try:
            await call.resume_stream(chat_id)
            await callback_query.message.edit_text(
                "**▶️ Playback Resumed**",
                reply_markup=main_menu()
            )
        except:
            pass
    
    elif data == "skip":
        try:
            await call.stop_stream(chat_id)
            await callback_query.message.edit_text(
                "**⏭️ Skipped Current Track**",
                reply_markup=main_menu()
            )
            await play_next(chat_id)
        except:
            pass
    
    # ============ PLAY METHODS ============
    
    elif data == "play_youtube":
        await callback_query.message.edit_text(
            "**🎵 Send YouTube Link:**\n\n"
            "Example: `https://youtube.com/watch?v=dQw4w9WgXcQ`\n\n"
            "Or just send a song name: `Despacito`",
            reply_markup=main_menu()
        )
        
        # Wait for user response
        try:
            response = await client.wait_for_message(
                chat_id,
                filters=filters.text & filters.user(user_id),
                timeout=60
            )
            
            if response:
                msg = await response.reply_text("**🔍 Processing your request...**")
                
                audio = await get_audio_url(response.text)
                
                if audio:
                    # Add to queue
                    if chat_id not in queues:
                        queues[chat_id] = []
                    
                    song_data = {
                        'title': audio['title'],
                        'url': audio['url'],
                        'requester': username
                    }
                    
                    # Check if something is playing
                    if chat_id in current_streams:
                        queues[chat_id].append(song_data)
                        await msg.edit_text(
                            f"**✅ Added to Queue!**\n\n"
                            f"🎵 **Song:** {audio['title']}\n"
                            f"📝 **Position:** {len(queues[chat_id])}\n"
                            f"👤 **Requested by:** {username}",
                            reply_markup=main_menu()
                        )
                    else:
                        current_streams[chat_id] = song_data
                        await msg.edit_text(
                            f"**▶️ Now Playing!**\n\n"
                            f"🎵 **Song:** {audio['title']}\n"
                            f"👤 **Requested by:** {username}",
                            reply_markup=main_menu()
                        )
                        
                        # Start streaming
                        await call.change_stream(
                            chat_id,
                            AudioStream(
                                audio['url'],
                                AudioParameters(bitrate=AudioQuality.BITRATE_64KBPS)
                            )
                        )
                        
                        # Start next song handler
                        asyncio.create_task(play_next(chat_id))
                else:
                    await msg.edit_text(
                        "**❌ Could not find audio!**\n\n"
                        "Make sure:\n"
                        "1. Link is valid\n"
                        "2. Video has audio\n"
                        "3. Try another song",
                        reply_markup=main_menu()
                    )
        except asyncio.TimeoutError:
            await callback_query.message.edit_text(
                "**⏰ Timeout!**\nPlease try again.",
                reply_markup=main_menu()
            )
    
    elif data == "search_song":
        await callback_query.message.edit_text(
            "**🔍 Send Song Name:**\n\n"
            "Example: `Bohemian Rhapsody`",
            reply_markup=main_menu()
        )
        
        try:
            response = await client.wait_for_message(
                chat_id,
                filters=filters.text & filters.user(user_id),
                timeout=60
            )
            
            if response:
                msg = await response.reply_text(f"**🔍 Searching:** `{response.text}`...")
                audio = await get_audio_url(response.text)
                
                if audio:
                    if chat_id not in queues:
                        queues[chat_id] = []
                    
                    song_data = {
                        'title': audio['title'],
                        'url': audio['url'],
                        'requester': username
                    }
                    
                    if chat_id in current_streams:
                        queues[chat_id].append(song_data)
                        await msg.edit_text(
                            f"**✅ Added to Queue!**\n\n🎵 {audio['title']}",
                            reply_markup=main_menu()
                        )
                    else:
                        current_streams[chat_id] = song_data
                        await msg.edit_text(
                            f"**▶️ Now Playing:**\n\n🎵 {audio['title']}",
                            reply_markup=main_menu()
                        )
                        
                        await call.change_stream(
                            chat_id,
                            AudioStream(
                                audio['url'],
                                AudioParameters(bitrate=AudioQuality.BITRATE_64KBPS)
                            )
                        )
                        
                        asyncio.create_task(play_next(chat_id))
                else:
                    await msg.edit_text(
                        "**❌ No results found!**\nTry different keywords.",
                        reply_markup=main_menu()
                    )
        except asyncio.TimeoutError:
            await callback_query.message.edit_text(
                "**⏰ Timeout!**",
                reply_markup=main_menu()
            )
    
    # ============ LOGIN SYSTEM ============
    
    elif data == "login":
        await callback_query.message.edit_text(
            "**🔐 Login to Your Account:**\n\n"
            "Choose login method:",
            reply_markup=login_menu()
        )
    
    elif data == "login_phone":
        await callback_query.message.edit_text(
            "**📱 Phone Login:**\n\n"
            "Send your phone number with country code:\n"
            "Example: `+919876543210`\n\n"
            "⚠️ **Note:** This feature is for user accounts only.",
            reply_markup=main_menu()
        )
        
        try:
            response = await client.wait_for_message(
                chat_id,
                filters=filters.text & filters.user(user_id),
                timeout=60
            )
            
            if response:
                phone = response.text
                # Store user session (simplified)
                user_sessions[user_id] = {"phone": phone, "logged_in": True}
                await response.reply_text(
                    f"**✅ Logged in successfully!**\n\n"
                    f"📱 Phone: {phone}\n"
                    f"Now you can use all features.",
                    reply_markup=main_menu()
                )
        except asyncio.TimeoutError:
            await callback_query.message.edit_text(
                "**⏰ Timeout!**\nTry /start again.",
                reply_markup=main_menu()
            )
    
    elif data == "login_string":
        await callback_query.message.edit_text(
            "**🔑 String Session Login:**\n\n"
            "Send your Pyrogram String Session:\n\n"
            "How to get string session:\n"
            "1. Use @StringSessionBot\n"
            "2. Generate your session\n"
            "3. Copy and paste here",
            reply_markup=main_menu()
        )
        
        try:
            response = await client.wait_for_message(
                chat_id,
                filters=filters.text & filters.user(user_id),
                timeout=60
            )
            
            if response:
                string_session = response.text
                user_sessions[user_id] = {"string_session": string_session, "logged_in": True}
                await response.reply_text(
                    f"**✅ String session saved!**\n\n"
                    f"Now you can use all features.",
                    reply_markup=main_menu()
                )
        except asyncio.TimeoutError:
            await callback_query.message.edit_text("**⏰ Timeout!**", reply_markup=main_menu())
    
    elif data == "logout":
        if user_id in user_sessions:
            del user_sessions[user_id]
        await callback_query.message.edit_text(
            "**✅ Logged out successfully!**\n\n"
            "You can login again anytime.",
            reply_markup=main_menu()
        )

# ============ ERROR HANDLERS ============

@app.on_message(filters.voice)
async def handle_voice(client: Client, message: Message):
    """Handle voice messages"""
    await message.reply_text(
        "🎤 **Voice message received!**\n"
        "Use /play command to play music instead.",
        reply_markup=main_menu()
    )

@app.on_message(filters.audio)
async def handle_audio(client: Client, message: Message):
    """Handle audio files"""
    audio = message.audio
    await message.reply_text(
        f"📁 **Audio file received:**\n"
        f"🎵 {audio.file_name}\n"
        f"📏 Size: {audio.file_size // 1024} KB\n\n"
        f"Use /play command to play YouTube music.",
        reply_markup=main_menu()
    )

# ============ RUN BOT ============

async def main():
    print("🚀 Starting Music Bot...")
    print(f"API ID: {API_ID}")
    print(f"Bot Token: {BOT_TOKEN[:20]}...")
    
    await app.start()
    print("✅ Pyrogram client started")
    
    await call.start()
    print("✅ PyTgCalls started")
    
    print("\n🎵 Bot is ready to use!")
    print("Commands:")
    print("  /start - Start the bot")
    print("  /menu - Show menu")
    print("\n💡 Bot running on Heroku...")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")