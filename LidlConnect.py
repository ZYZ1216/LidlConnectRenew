import os
import re
import sys
import time
from playwright.sync_api import Playwright, sync_playwright

# 💡 从 GitLab CI/CD Variables 读取密码，本地测试可保底
PHONE_NUMBER = os.getenv("LIDL_USER", "")
PASSWORD = os.getenv("LIDL_PASS", "")

if not PHONE_NUMBER or not PASSWORD:
    print("❌ 错误：未读取到环境变量 LIDL_USER 或 LIDL_PASS！")
    print("👉 请确保已在 GitLab Settings -> CI/CD -> Variables 中添加这两个变量。")
    sys.exit(1)

TARGET_URL = "https://kundenkonto.lidl-connect.de/mein-lidl-connect/uebersicht.html"


def do_login_with_verification(page) -> bool:
    """带状态校验的登录流程"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] 🔑 开始执行登录流程...")

    phone_input = page.get_by_role("textbox", name="Mobilfunknummer")
    pass_input = page.get_by_role("textbox", name="Passwort")

    try:
        phone_input.wait_for(state="visible", timeout=5000)
        pass_input.wait_for(state="visible", timeout=5000)
    except Exception:
        print("   ❌ 无法定位登录输入框，可能不在登录页。")
        return False

    phone_input.click()
    phone_input.fill(PHONE_NUMBER)
    phone_input.dispatch_event("input")

    pass_input.click()
    pass_input.fill(PASSWORD)
    pass_input.dispatch_event("input")

    if phone_input.input_value() != PHONE_NUMBER or len(pass_input.input_value()) == 0:
        print("   ❌ 账号或密码填充校验失败！")
        return False

    print("   👉 正在提交登录...")
    login_btn = page.get_by_role("button", name="Einloggen")
    if login_btn.is_visible():
        login_btn.click()
    else:
        pass_input.press("Enter")

    refill_btn = page.get_by_role("button", name="Datenvolumen per Refill")
    try:
        refill_btn.wait_for(state="visible", timeout=15000)
        print("   ✅ 登录成功！检测到 'Datenvolumen per Refill' 按钮。")
        return True
    except Exception:
        print("   ❌ 登录提交后 15 秒内未检测到 Refill 按钮（可能触发人机验证或密码错误）。")
        return False


def get_remaining_data_gb(page) -> float | None:
    """提取剩余流量数值"""
    try:
        elements = page.get_by_text(re.compile(r"\b\d+[,\.]\d+\s*GB\b")).all()
        target_text = None
        for el in elements:
            if el.is_visible():
                text = el.inner_text().strip()
                if len(text) < 15 and "Wochen" not in text and "€" not in text:
                    target_text = text
                    break

        if target_text:
            match = re.search(r"(\d+[,\.]?\d*)", target_text)
            if match:
                num_str = match.group(1).replace(",", ".")
                return float(num_str)
    except Exception as e:
        print(f"   ⚠️ 提取流量数值时异常: {e}")
    return None


def run_once(page):
    """单次检测流程（供 GitLab CI 定时任务调用）"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] 🔄 开始访问 Lidl Connect...")

    page.goto(TARGET_URL, wait_until="domcontentloaded")
    time.sleep(2)

    refill_btn = page.get_by_role("button", name="Datenvolumen per Refill")

    # 没按钮先走登录
    if not refill_btn.is_visible(timeout=3000):
        success = do_login_with_verification(page)
        if not success:
            print("❌ 登录流程失败，中止本轮运行。")
            sys.exit(1)
        refill_btn = page.get_by_role("button", name="Datenvolumen per Refill")

    # 检查数值
    if refill_btn.is_visible(timeout=2000):
        remaining_gb = get_remaining_data_gb(page)
        if remaining_gb is not None:
            print(f"   📊 当前剩余流量: {remaining_gb:.2f} GB")
            if remaining_gb < 0.50:
                print("   ⚡ 流量小于 0.50 GB，触发 Refill 点击！")
                refill_btn.click()
                print("   ✅ 已成功点击 'Datenvolumen per Refill'！")
                time.sleep(3)
            else:
                print("   👌 流量充足（≥ 0.50 GB），无需重置。")
        else:
            print("   ⚠️ 无法提取流量数值。")
    else:
        print("   ❌ 最终未找到 Refill 按钮。")


def main():
    with sync_playwright() as playwright:
        # CI 环境必须使用 headless=True
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="de-DE",
        )
        page = context.new_page()

        try:
            run_once(page)
        finally:
            browser.close()


if __name__ == "__main__":
    main()