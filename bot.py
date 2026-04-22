import asyncio
import os
import re
import json
from typing import Dict, Optional

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioParameters
from pytgcalls.types.stream import Stream
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.exceptions import NoActiveGroupCall

# ============ CONFIGURATION - YAHAN APNI DETAILS DALO ============
API_ID = 33578855  # <-- Yahan apna API ID dalo
API_HASH = "f99e8fb11cf447b40af77f44f24cdca4"  # <-- Yahan apna API Hash dalo

# File to store settings
SETTINGS_FILE = "vc_settings.json"

# ============ INITIALIZATION ============
app = Client("my_account", api_id=API_ID, api_hash=API_HASH)
call = PyTgCalls(app)

# Store active voice chats
active_vc = {}  # {chat_id: {"status": "active", "volume": 100, "title": "name"}}
live_forwarding = {}  # {source_chat: {"dest": dest_chat, "active": True}}
volume_level = 100

# ============ LOAD/SAVE SETTINGS ============
def load_settings():
    global volume_level, active_vc, live_forwarding
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                volume_level = data.get("volume", 100)
        except:
            pass

def save_settings():
    with open(SETTINGS_FILE, 'w') as f:
        json.dump({"volume": volume_level}, f)

# ============ AUTO JOIN ON LINK ============
@app.on_message(filters.text & filters.private)
async def auto_join_on_link(client: Client, message: Message):
    """Automatically join voice chat when group link is sent"""
    
    text = message.text
    group_link_pattern = r'(?:https?://)?(?:t\.me/|telegram\.me/|telegram\.dog/)([a-zA-Z0-9_]+)'
    match = re.search(group_link_pattern, text)
    
    if match:
        username = match.group(1)
        processing_msg = await message.reply("🔍 **Processing group link...**")
        
        try:
            chat = await client.get_chat(username)
            chat_id = chat.id
            chat_title = chat.title
            
            await processing_msg.edit_text(f"✅ **Group:** {chat_title}\n🆔 `{chat_id}`\n🔊 Joining voice chat...")
            
            # Check if member
            try:
                member = await client.get_chat_member(chat_id, "me")
                if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    await client.join_chat(username)
                    await asyncio.sleep(1)
            except:
                pass
            
            # Join voice chat
            try:
                await call.join_group_call(
                    chat_id,
                    Stream(
                        AudioPiped(
                            "silence.ogg",
                            AudioParameters(volume=volume_level / 100)
                        )
                    )
                )
                
                active_vc[chat_id] = {
                    "status": "active",
                    "volume": volume_level,
                    "title": chat_title
                }
                
                await processing_msg.edit_text(
                    f"✅ **JOINED VOICE CHAT!** 🎉\n\n"
                    f"📌 **Group:** {chat_title}\n"
                    f"🆔 **ID:** `{chat_id}`\n"
                    f"🔊 **Volume:** {volume_level}%\n\n"
                    f"**Commands (send in this chat):**\n"
                    f"• `/volume 150` - Change volume\n"
                    f"• `/golive {chat_id} [dest_id]` - Start live forward\n"
                    f"• `/stoplive` - Stop forwarding\n"
                    f"• `/status` - Check status\n"
                    f"• `/leave` - Leave voice chat\n\n"
                    f"🎵 Send audio/voice notes to play!"
                )
                
                await client.send_message(
                    chat_id,
                    f"🎵 **Voice Bot Active!**\nVolume: {volume_level}%\nSend audio to play!"
                )
                
            except NoActiveGroupCall:
                await processing_msg.edit_text(
                    f"⚠️ **No Active Voice Chat!**\n\n"
                    f"Group: {chat_title}\n\n"
                    f"Please start voice chat manually first, then I'll join automatically!"
                )
            except Exception as e:
                if "chat admin" in str(e).lower():
                    await processing_msg.edit_text(
                        f"❌ **Admin Permission Required!**\n\n"
                        f"Make sure your account is admin with 'Manage Video Chats' permission!"
                    )
                else:
                    await processing_msg.edit_text(f"❌ Error: {str(e)[:200]}")
                    
        except Exception as e:
            await processing_msg.edit_text(f"❌ Failed: {str(e)[:200]}")

# ============ COMMAND HANDLERS ============

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await message.reply(
        "🎵 **Voice Chat Bot Active!**\n\n"
        "**How to use:**\n"
        "1️⃣ Send any group link (t.me/...)\n"
        "2️⃣ Bot auto-joins voice chat\n"
        "3️⃣ Send audio/voice notes to play\n\n"
        "**Commands:**\n"
        "🔊 `/volume 150` - Change volume\n"
        "🔴 `/golive source dest` - Live forward\n"
        "⏹️ `/stoplive` - Stop forward\n"
        "📊 `/status` - Check status\n"
        "👋 `/leave` - Leave all chats\n\n"
        "**Example:**\n"
        "`/golive -1001234567890 -1009876543210`"
    )

@app.on_message(filters.command("volume") & filters.private)
async def set_volume(client: Client, message: Message):
    global volume_level
    
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply("Usage: `/volume 100` (range: 1-200)")
            return
        
        volume = int(args[1])
        if volume < 1 or volume > 200:
            await message.reply("Volume must be between 1-200")
            return
        
        volume_level = volume
        save_settings()
        
        # Update all active voice chats
        updated = 0
        for chat_id in active_vc:
            try:
                await call.change_volume(chat_id, volume / 100)
                active_vc[chat_id]["volume"] = volume
                updated += 1
            except:
                pass
        
        await message.reply(
            f"🔊 **Volume Updated!**\n"
            f"New volume: **{volume}%**\n"
            f"Updated chats: {updated}"
        )
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command("golive") & filters.private)
async def start_live_forward(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.reply(
                "Usage: `/golive source_chat_id dest_chat_id`\n\n"
                "**Example:** `/golive -1001234567890 -1009876543210`\n\n"
                "**How to get chat ID:**\n"
                "1. Forward message from group to @chatIDRobot\n"
                "2. Copy the ID (starts with -100)"
            )
            return
        
        source_chat = int(args[1])
        dest_chat = int(args[2])
        
        # Check if both are active
        if source_chat not in active_vc:
            await message.reply(f"❌ Source chat `{source_chat}` not in voice chat!\nSend its group link first.")
            return
        
        if dest_chat not in active_vc:
            await message.reply(f"❌ Destination chat `{dest_chat}` not in voice chat!\nSend its group link first.")
            return
        
        # Start live forwarding
        live_forwarding[source_chat] = {
            "dest": dest_chat,
            "active": True,
            "source_title": active_vc[source_chat]["title"],
            "dest_title": active_vc[dest_chat]["title"]
        }
        
        await message.reply(
            f"🔴 **Live Forwarding Started!**\n\n"
            f"📡 **Source:** {active_vc[source_chat]['title']}\n"
            f"🆔 `{source_chat}`\n\n"
            f"🎯 **Destination:** {active_vc[dest_chat]['title']}\n"
            f"🆔 `{dest_chat}`\n\n"
            f"Use `/stoplive {source_chat}` to stop"
        )
        
        # Notify groups
        await client.send_message(source_chat, f"🔴 **Live Forwarding ACTIVE**\nAudio → {active_vc[dest_chat]['title']}")
        await client.send_message(dest_chat, f"🔴 **Receiving Live Audio**\nFrom: {active_vc[source_chat]['title']}")
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command("stoplive") & filters.private)
async def stop_live_forward(client: Client, message: Message):
    try:
        args = message.text.split()
        
        if len(args) == 2:
            source_chat = int(args[1])
            if source_chat in live_forwarding:
                data = live_forwarding[source_chat]
                del live_forwarding[source_chat]
                
                await message.reply(
                    f"⏹️ **Stopped live forwarding**\n"
                    f"Source: {data['source_title']}\n"
                    f"Destination: {data['dest_title']}"
                )
                
                # Notify groups
                await client.send_message(source_chat, "⏹️ Live forwarding stopped")
                await client.send_message(data["dest"], "⏹️ Live forwarding ended")
            else:
                await message.reply(f"❌ No active live session for `{source_chat}`")
        else:
            # Stop all
            count = len(live_forwarding)
            live_forwarding.clear()
            await message.reply(f"⏹️ **Stopped ALL live forwarding sessions**\nTotal: {count}")
            
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command("status") & filters.private)
async def check_status(client: Client, message: Message):
    status_text = "**📊 Voice Chat Status**\n\n"
    
    if active_vc:
        status_text += "**🎙 Active Voice Chats:**\n"
        for chat_id, data in active_vc.items():
            status_text += f"• **{data['title']}**\n"
            status_text += f"  🆔 `{chat_id}` | 🔊 {data['volume']}%\n"
    else:
        status_text += "**🎙 Active Voice Chats:** None\n"
    
    status_text += "\n"
    
    if live_forwarding:
        status_text += "**🔴 Live Forwarding:**\n"
        for source, data in live_forwarding.items():
            status_text += f"• {data['source_title']} → {data['dest_title']}\n"
            status_text += f"  🟢 Active\n"
    else:
        status_text += "**🔴 Live Forwarding:** None\n"
    
    status_text += f"\n**📊 Global Volume:** {volume_level}%\n"
    status_text += f"**📡 Total Chats:** {len(active_vc)}"
    
    await message.reply(status_text)

@app.on_message(filters.command("leave") & filters.private)
async def leave_vc(client: Client, message: Message):
    try:
        count = len(active_vc)
        
        for chat_id in list(active_vc.keys()):
            try:
                await call.leave_group_call(chat_id)
            except:
                pass
        
        active_vc.clear()
        live_forwarding.clear()
        
        await message.reply(f"👋 **Left all voice chats**\nTotal: {count} chat(s)\n\nSend new group link to join again!")
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    await start_cmd(client, message)

# ============ AUDIO HANDLER ============
@app.on_message(filters.voice | filters.audio)
async def handle_audio(client: Client, message: Message):
    if not active_vc:
        await message.reply("❌ No active voice chat! Send a group link first.")
        return
    
    status_msg = await message.reply("📥 Downloading audio...")
    
    try:
        audio_path = await message.download()
        await status_msg.delete()
        
        played = 0
        for chat_id in active_vc:
            try:
                await call.play(
                    chat_id,
                    AudioPiped(
                        audio_path,
                        AudioParameters(volume=volume_level / 100)
                    )
                )
                played += 1
            except Exception as e:
                print(f"Play error {chat_id}: {e}")
        
        await message.reply(
            f"🎵 **Playing Audio!**\n"
            f"📡 Sent to: {played} chat(s)\n"
            f"🔊 Volume: {volume_level}%\n\n"
            f"Use `/volume` to adjust volume"
        )
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)[:200]}")

# ============ CREATE SILENCE FILE ============
async def create_silence_file():
    if not os.path.exists("silence.ogg"):
        with open("silence.ogg", "wb") as f:
            f.write(b'\x00' * 1000)

# ============ MAIN ============
async def main():
    print("=" * 50)
    print("🚀 Starting Voice Chat Bot...")
    print("=" * 50)
    
    load_settings()
    await create_silence_file()
    
    await call.start()
    print("✅ Voice client started!")
    
    await app.start()
    print("✅ Telegram client started!")
    
    print("\n🎯 **BOT IS READY!**")
    print("=" * 50)
    print("\n📌 **How to use:**")
    print("1. DM this bot")
    print("2. Send any group link: https://t.me/yourgroup")
    print("3. Bot auto-joins voice chat")
    print("4. Send audio/voice notes to play")
    print("\n📌 **Commands (send in DM):**")
    print("   /volume 150 - Change volume")
    print("   /golive source dest - Live forward")
    print("   /stoplive - Stop forwarding")
    print("   /status - Check status")
    print("   /leave - Leave all chats")
    print("=" * 50)
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())