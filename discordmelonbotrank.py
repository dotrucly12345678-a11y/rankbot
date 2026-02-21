import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import time
import os  # 환경 변수 사용을 위해 추가
from dotenv import load_dotenv  # python-dotenv 라이브러리
from PIL import Image, ImageDraw, ImageFont # type: ignore
import aiohttp
from io import BytesIO

# .env 파일의 내용을 로드합니다.
load_dotenv()

# 환경 변수에서 값을 가져옵니다.
TOKEN = os.getenv("DISCORD_TOKEN")
# GUILD_ID는 숫자(int)여야 하므로 변환이 필요합니다.
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

user_data = {}
chat_cooldown = {}

# ---------------- 데이터 ---------------- #

def load_data():
    global user_data
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            user_data = json.load(f)
    except:
        user_data = {}

def save_data():
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=4, ensure_ascii=False)

def create_user(user_id):
    user_data[user_id] = {
        "chat_xp": 0,
        "chat_level": 1,
        "voice_xp": 0,
        "voice_level": 1
    }

# ---------------- 카드 생성 ---------------- #

async def create_rank_card(member, chat_level, chat_xp, chat_required,
                           voice_level, voice_xp, voice_required):

    width = 950
    height = 320

    image = Image.new("RGB", (width, height), (28, 28, 40))
    draw = ImageDraw.Draw(image)

    # 한글 폰트 경로 (시스템 환경에 맞춰 수정 필요할 수 있음)
    font_path = "C:/Windows/Fonts/malgun.ttf"
    font_title = ImageFont.truetype(font_path, 34)
    font_small = ImageFont.truetype(font_path, 24)
    font_bar = ImageFont.truetype(font_path, 22)

    # ---------------- 프로필 ----------------
    async with aiohttp.ClientSession() as session:
        async with session.get(member.display_avatar.url) as resp:
            avatar_bytes = await resp.read()

    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((170, 170))

    mask = Image.new("L", (170, 170), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, 170, 170), fill=255)

    image.paste(avatar, (40, 75), mask)

    bar_x = 270
    bar_width = 600
    bar_height = 32
    radius = 16 

    # 💬 채팅 섹션
    chat_total_xp = (chat_level - 1) * 100 + chat_xp
    chat_ratio = min(chat_xp / chat_required, 1) if chat_required > 0 else 0

    draw.text((bar_x, 40), f"채팅 LV.{chat_level}", fill=(180,180,255), font=font_title)
    right_text = f"누적 경험치 : {chat_total_xp}"
    text_width = draw.textlength(right_text, font=font_small)
    draw.text((width - text_width - 40, 45), right_text, fill=(200,200,200), font=font_small)

    bar_y = 90
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], radius=radius, fill=(70,70,90))
    draw.rounded_rectangle([bar_x, bar_y, bar_x + int(bar_width * chat_ratio), bar_y + bar_height], radius=radius, fill=(120,100,255))

    center_text = f"{chat_xp} / {chat_required}"
    text_w = draw.textlength(center_text, font=font_bar)
    draw.text((bar_x + (bar_width - text_w) / 2, bar_y + 5), center_text, fill=(255,255,255), font=font_bar)

    # 🎤 음성 섹션
    voice_total_xp = (voice_level - 1) * 100 + voice_xp
    voice_ratio = min(voice_xp / voice_required, 1) if voice_required > 0 else 0

    draw.text((bar_x, 170), f"음성 LV.{voice_level}", fill=(255,180,180), font=font_title)
    right_text2 = f"누적 경험치 : {voice_total_xp}"
    text_width2 = draw.textlength(right_text2, font=font_small)
    draw.text((width - text_width2 - 40, 175), right_text2, fill=(200,200,200), font=font_small)

    bar_y2 = 220
    draw.rounded_rectangle([bar_x, bar_y2, bar_x + bar_width, bar_y2 + bar_height], radius=radius, fill=(70,70,90))
    draw.rounded_rectangle([bar_x, bar_y2, bar_x + int(bar_width * voice_ratio), bar_y2 + bar_height], radius=radius, fill=(255,120,120))

    center_text2 = f"{voice_xp} / {voice_required}"
    text_w2 = draw.textlength(center_text2, font=font_bar)
    draw.text((bar_x + (bar_width - text_w2) / 2, bar_y2 + 5), center_text2, fill=(255,255,255), font=font_bar)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer

# ---------------- 이벤트 및 커맨드 ---------------- #

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    if not voice_xp_loop.is_running():
        voice_xp_loop.start()
    print(f"{bot.user} 온라인!")

@bot.tree.command(name="rank", description="유저의 레벨을 확인합니다.")
@app_commands.describe(member="확인할 유저 (선택 안 하면 본인)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        member = interaction.user
    user_id = str(member.id)
    if user_id not in user_data:
        create_user(user_id)

    data = user_data[user_id]
    card_buffer = await create_rank_card(
        member, data["chat_level"], data["chat_xp"], data["chat_level"] * 100,
        data["voice_level"], data["voice_xp"], data["voice_level"] * 100
    )
    file = discord.File(card_buffer, filename="rank.png")
    await interaction.response.send_message(file=file)

@bot.tree.command(name="랭킹", description="서버 레벨 랭킹을 확인합니다.")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ranking(interaction: discord.Interaction):
    if not user_data:
        await interaction.response.send_message("데이터가 없습니다.")
        return

    guild = interaction.guild
    chat_sorted = sorted(user_data.items(), key=lambda x: (x[1].get("chat_level", 1), x[1].get("chat_xp", 0)), reverse=True)
    voice_sorted = sorted(user_data.items(), key=lambda x: (x[1].get("voice_level", 1), x[1].get("voice_xp", 0)), reverse=True)

    embed = discord.Embed(title="🏆 서버 레벨 랭킹", color=discord.Color.gold())
    
    chat_lines = [f"**{i+1}위** <@{uid}> - LV.{d['chat_level']}" for i, (uid, d) in enumerate(chat_sorted[:10]) if guild.get_member(int(uid))]
    embed.add_field(name="💬 채팅 TOP 10", value="\n".join(chat_lines) if chat_lines else "데이터 없음", inline=False)

    voice_lines = [f"**{i+1}위** <@{uid}> - LV.{d['voice_level']}" for i, (uid, d) in enumerate(voice_sorted[:10]) if guild.get_member(int(uid))]
    embed.add_field(name="🎤 음성 TOP 10", value="\n".join(voice_lines) if voice_lines else "데이터 없음", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot: return
    user_id = str(message.author.id)
    now = time.time()
    if user_id in chat_cooldown and now - chat_cooldown[user_id] < 5: return
    chat_cooldown[user_id] = now

    if user_id not in user_data: create_user(user_id)
    user_data[user_id]["chat_xp"] += 10
    if user_data[user_id]["chat_xp"] >= user_data[user_id]["chat_level"] * 100:
        user_data[user_id]["chat_level"] += 1
        user_data[user_id]["chat_xp"] = 0
    save_data()
    await bot.process_commands(message)

@tasks.loop(minutes=10)
async def voice_xp_loop():
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            for member in channel.members:
                if member.bot or member.voice.self_mute or member.voice.self_deaf: continue
                user_id = str(member.id)
                if user_id not in user_data: create_user(user_id)
                user_data[user_id]["voice_xp"] += 50
                if user_data[user_id]["voice_xp"] >= user_data[user_id]["voice_level"] * 100:
                    user_data[user_id]["voice_level"] += 1
                    user_data[user_id]["voice_xp"] = 0
    save_data()

# ---------------- 실행 ---------------- #

if __name__ == "__main__":
    load_data()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("에러: .env 파일에서 DISCORD_TOKEN을 찾을 수 없습니다.")