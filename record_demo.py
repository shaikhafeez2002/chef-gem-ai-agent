import asyncio
import os
import shutil
import time
from playwright.async_api import async_playwright

RECORDING_DIR = "/config/.gemini/antigravity/brain/0f5f8786-77dc-4cfd-8a18-0aa10a53f8b2/demo_recordings"
FINAL_VIDEO_PATH = "/config/.gemini/antigravity/brain/0f5f8786-77dc-4cfd-8a18-0aa10a53f8b2/demo_recording.webm"
APP_URL = "https://personal-chef-frontend-597656442262.us-east1.run.app"

os.makedirs(RECORDING_DIR, exist_ok=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        context = await browser.new_context(
            record_video_dir=RECORDING_DIR,
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        
        page = await context.new_page()
        print(f"Navigating to {APP_URL}...")
        await page.goto(APP_URL, wait_until="networkidle")
        
        # 1. Initial UI display
        print("Displaying app interface...")
        await asyncio.sleep(3)
        
        # 2. First prompt: Click example chip '30-Min Mediterranean Dinner'
        print("Clicking example chip '30-Min Mediterranean Dinner'...")
        chip = page.locator(".prompt-chip", has_text="30-Min Mediterranean Dinner")
        await chip.click()
        
        # Wait for agent response
        print("Waiting for Chef Gem response to 1st prompt...")
        await page.wait_for_selector(".msg.agent", timeout=30000)
        await asyncio.sleep(5)
        
        # 3. Second richer prompt: Allergy + Database Lookup + AI Tool Call (Generate Image)
        rich_prompt = "I am allergic to peanuts! Search my recipes for a nut-free dish and generate a photo of Lemon Herb Grilled Chicken."
        print(f"Submitting 2nd rich prompt: '{rich_prompt}'...")
        
        input_box = page.locator("#input")
        await input_box.fill(rich_prompt)
        await asyncio.sleep(1)
        
        send_button = page.locator("button[type='submit']")
        await send_button.click()
        
        # Wait for agent response to rich prompt (tool calls + image generation)
        print("Waiting for Chef Gem response with tool execution and generated image...")
        # We wait for the second agent message bubble
        await page.wait_for_function("document.querySelectorAll('.msg.agent').length >= 2", timeout=60000)
        await asyncio.sleep(8)
        
        print("Closing browser context to save recording...")
        video = page.video
        video_path = await video.path()
        await context.close()
        await browser.close()
        
        print(f"Video recorded to temporary path: {video_path}")
        shutil.copy(video_path, FINAL_VIDEO_PATH)
        print(f"Successfully saved demo video to: {FINAL_VIDEO_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
