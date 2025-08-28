import os
import asyncio
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.client.default import DefaultBotProperties
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SPOTIFY_CLIENT_ID = "8cf672fedd5b4fcd90430f12cd80f2d1"
SPOTIFY_CLIENT_SECRET = "28ac385824814fcf942961dfc75f727e"
OUTPUT_FOLDER = r"C:\downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB - лимит Telegram

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

def sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    return filename[:200]

async def convert_to_mp3(input_path: str) -> str:
    if input_path.lower().endswith('.mp3'):
        return input_path
    output_path = os.path.splitext(input_path)[0] + '.mp3'
    try:
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format="mp3", bitrate="192k")
        os.remove(input_path)
        return output_path
    except Exception as e:
        logger.error(f"Ошибка конвертации: {str(e)}")
        if os.path.exists(input_path):
            return input_path
        raise

async def compress_audio(input_path: str) -> str:
    audio = AudioSegment.from_file(input_path)
    for quality in [192, 160, 128, 96]:
        output_path = f"{os.path.splitext(input_path)[0]}_{quality}k.mp3"
        audio.export(output_path, format="mp3", bitrate=f"{quality}k")
        if os.path.getsize(output_path) < MAX_FILE_SIZE:
            os.replace(output_path, input_path)
            return input_path
        os.remove(output_path)
    raise ValueError("Не удалось сжать файл до 50MB")

async def safe_send_audio(chat_id: int, file_path: str):
    for attempt in range(3):
        try:
            await bot.send_audio(chat_id=chat_id, audio=FSInputFile(file_path),
                                 title=os.path.basename(file_path)[:-4])
            return
        except Exception as e:
            logger.error(f"Ошибка отправки (попытка {attempt+1}): {str(e)}")
            if attempt == 2:
                raise
            await asyncio.sleep(2)

async def download_audio(url: str) -> str:
    temp_dir = os.path.join(OUTPUT_FOLDER, f"temp_{int(time.time())}")
    os.makedirs(temp_dir, exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'quiet': True,
        'socket_timeout': 120,
        'logger': logger,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            ydl.download([url])
            for file in os.listdir(temp_dir):
                if not file.endswith('.part'):
                    file_path = os.path.join(temp_dir, file)
                    if not file.lower().endswith('.mp3'):
                        file_path = await convert_to_mp3(file_path)
                    final_path = os.path.join(OUTPUT_FOLDER, os.path.basename(file_path))
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    os.rename(file_path, final_path)
                    try: os.rmdir(temp_dir)
                    except: pass
                    return final_path
            raise FileNotFoundError("Файл не найден после загрузки")
    except Exception as e:
        try:
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except: pass
        raise

async def safe_download(query, retries=3):
    for attempt in range(retries):
        try:
            return await download_audio(query)
        except Exception as e:
            logger.warning(f"Ошибка скачивания ({attempt+1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                raise e

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎵 <b>Spotify | YouTube | SoundCloud</b>\n\n"
        "Отправьте ссылку на трек или плейлист, и я пришлю MP3 (макс. 50MB).\n\n"
    )
