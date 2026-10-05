import re
import time
from playwright.sync_api import Playwright, sync_playwright

PHONE_NUMBER = "+49 174 8424902"
PASSWORD = "Morning1216?"
TARGET_URL = "https://kundenkonto.lidl-connect.de/mein-lidl-connect/uebersicht.html"
CHECK_INTERVAL = 60  # 检查间隔时间（秒）


def do_login(page):
    """自动登录，直到检测到 'Datenvolumen per Refill' 按钮才返回"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] 🔑 未检测到 Refill 按钮，触发自动登录...")

    # 如果不在登录输入框页面，尝试进入
    if not page.get_by_role("textbox", name="Mobilfunknummer").is_visible():
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        time.sleep(1)

    # 1. 处理 Cookie 弹窗（如果存在）
    try:
        cookie_btn = page.get_by_role("button", name=re.compile("Accept|Zustimmen|Akzeptieren", re.I))
        if cookie_btn.is_visible(timeout=2000):
            cookie_btn.click()
            time.sleep(0.5)
    except Exception:
        pass

    # 2. 填写账号密码
    phone_input = page.get_by_role("textbox", name="Mobilfunknummer")
    phone_input.click()
    phone_input.fill(PHONE_NUMBER)
    phone_input.dispatch_event("input")
    phone_input.dispatch_event("change")
    time.sleep(0.3)

    pass_input = page.get_by_role("textbox", name="Passwort")
    pass_input.click()
    pass_input.fill(PASSWORD)
    pass_input.dispatch_event("input")
    pass_input.dispatch_event("change")
    time.sleep(0.5)

    # 3. 点击登录提交
    print("   👉 正在提交登录...")
    login_btn = page.get_by_role("button", name="Einloggen")
    
    if login_btn.is_visible():
        login_btn.click()
    else:
        pass_input.press("Enter")

    # 4. 关键点：不断等待并检测，直到 'Datenvolumen per Refill' 按钮出现才判定登录成功
    print("   ⏳ 正在等待登录完成并加载主页...")
    refill_btn = page.get_by_role("button", name="Datenvolumen per Refill")
    
    try:
        # 最多等待 15 秒，直到 Refill 按钮变为可见
        refill_btn.wait_for(state="visible", timeout=15000)
        print("   ✅ 成功检测到 'Datenvolumen per Refill' 按钮，登录成功！")
    except Exception:
        print("   ⚠️ 登录提交后 15 秒内未检测到 Refill 按钮，可能登录失败或页面卡顿。")


def get_remaining_data_gb(page) -> float | None:
    """提取剩余流量数值（例如将 '0,91 GB' 转化为 0.91）"""
    try:
        elements = page.get_by_text(re.compile(r"\b\d+[,\.]\d+\s*GB\b")).all()
        
        target_text = None
        for el in elements:
            if el.is_visible():
                text = el.inner_text().strip()
                # 过滤掉底部资费等干扰长文本，只保留像 "0,91 GB" 这样的短文本
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


def check_and_refill_once(page):
    """单次检查逻辑：刷新 -> 验证 Refill 按钮 -> 没按钮就登录 -> 检查数值并 Refill"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] 🔄 正在刷新页面...")

    # 1. 刷新/访问页面
    page.goto(TARGET_URL, wait_until="domcontentloaded")
    time.sleep(2)  # 给前端页面渲染留出缓冲

    refill_btn = page.get_by_role("button", name="Datenvolumen per Refill")

    # 2. 检测是否有 Datenvolumen per Refill 按钮，没有就去登录
    if not refill_btn.is_visible(timeout=3000):
        do_login(page)
        # 重新获取 Refill 按钮对象
        refill_btn = page.get_by_role("button", name="Datenvolumen per Refill")

    # 3. 再次确认按钮是否存在（如果登录成功，此时应该存在了）
    if refill_btn.is_visible(timeout=2000):
        # 4. 检测流量数值
        remaining_gb = get_remaining_data_gb(page)

        if remaining_gb is not None:
            print(f"   📊 当前剩余流量: {remaining_gb:.2f} GB")

            # 判断是否小于 0.50 GB
            if remaining_gb < 0.50:
                print("   ⚡ 流量小于 0.50 GB，触发 Refill！")
                refill_btn.click()
                print("   ✅ 已成功点击 'Datenvolumen per Refill'！")
                time.sleep(3)
            else:
                print("   👌 流量充足（≥ 0.50 GB），无需重置。")
        else:
            print("   ⚠️ 页面已加载，但未能成功提取流量数字。")
    else:
        print("   ❌ 无法找到 'Datenvolumen per Refill' 按钮，本轮跳过，等待下一次循环。")


def run(playwright: Playwright) -> None:
    # 测试阶段保持 headless=False，正常后台运行可改为 headless=True
    browser = playwright.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        locale="de-DE",
    )
    page = context.new_page()

    print("🚀 Lidl Connect 自动监测脚本已启动...")

    while True:
        try:
            check_and_refill_once(page)
        except Exception as e:
            print(f"⚠️ 本轮运行出现网络或页面异常（将在下一次循环重试）: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)