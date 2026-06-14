"""Tạo audio intro cho đầu tập, transition cho giữa các chương, và outro cho cuối tập bằng edge-tts"""
import asyncio
import edge_tts
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "audio_assets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VOICE = "vi-VN-NamMinhNeural"
STORY_NAME = "Võ Luyện Đỉnh Phong"

async def create_intro(episode_num: int):
    """Tạo audio intro cho đầu tập: bộ chuyện, tên truyện, chúc các bạn nghe truyện vui vẻ, số tập"""
    text = f"Bộ chuyện, {STORY_NAME}, chúc các bạn nghe truyện vui vẻ, tập {episode_num}"
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%")
    output_path = OUTPUT_DIR / f"intro_ep{episode_num}.mp3"
    await communicate.save(str(output_path))
    print(f"[OK] Đã tạo intro tập {episode_num}: {output_path}")

async def create_transition():
    """Tạo audio transition cho giữa các chương: các bạn hãy follow để được nhận thông báo mới nhất từ truyện nhé, cảm ơn các bạn"""
    text = "Các bạn hãy follow để được nhận thông báo mới nhất từ truyện nhé, cảm ơn các bạn"
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%")
    output_path = OUTPUT_DIR / "transition.mp3"
    await communicate.save(str(output_path))
    print(f"[OK] Đã tạo transition: {output_path}")

async def create_outro():
    """Tạo audio outro cho cuối tập: cảm ơn các bạn đã nghe, chúc các bạn ngày mới vui vẻ bên gia đình"""
    text = "Cảm ơn các bạn đã nghe, chúc các bạn ngày mới vui vẻ bên gia đình"
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%")
    output_path = OUTPUT_DIR / "outro.mp3"
    await communicate.save(str(output_path))
    print(f"[OK] Đã tạo outro: {output_path}")

async def main():
    print("[INFO] Đang tạo audio intro, transition và outro...")
    await create_transition()
    await create_outro()
    print("\n[INFO] Hoàn tất!")

if __name__ == "__main__":
    asyncio.run(main())
