#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本 - 完整修复版
"""

import os
import time
import logging
import re
import requests
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LeaflowAutoCheckin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        
        if not self.email or not self.password:
            raise ValueError("邮箱和密码不能为空")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动选项"""
        chrome_options = Options()
        
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            # 关键：模拟真实浏览器 UA
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def close_popup(self):
        """关闭初始弹窗"""
        try:
            time.sleep(3)
            actions = ActionChains(self.driver)
            actions.move_by_offset(10, 10).click().perform()
            logger.info("尝试关闭弹窗完成")
            time.sleep(2)
        except:
            pass

    def login(self):
        """执行登录流程"""
        logger.info(f"正在登录账号: {self.email[:3]}***")
        self.driver.get("https://leaflow.net/login")
        time.sleep(5)
        
        self.close_popup()
        
        try:
            # 邮箱定位
            wait = WebDriverWait(self.driver, 15)
            email_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[name='email']")))
            email_input.clear()
            email_input.send_keys(self.email)
            
            # 密码定位
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_input.clear()
            password_input.send_keys(self.password)
            
            # 登录按钮
            login_btn = self.driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), '登录')]")
            login_btn.click()
            
            # 等待页面跳转
            wait.until(lambda d: "login" not in d.current_url)
            logger.info("登录成功")
            return True
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False

    def get_balance(self):
        """获取余额"""
        try:
            self.driver.get("https://leaflow.net/dashboard")
            time.sleep(3)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            match = re.search(r'(?:¥|￥|余额)\s*(\d+\.?\d*)', page_text)
            return f"{match.group(1)}元" if match else "未知"
        except:
            return "未知"

    def checkin(self):
        """核心签到逻辑 - 针对你提供的 HTML 结构"""
        logger.info("正在跳转至签到子站...")
        self.driver.get("https://checkin.leaflow.net")
        
        # 页面加载缓冲
        time.sleep(8)
        
        try:
            wait = WebDriverWait(self.driver, 20)
            # 根据提供的源码：按钮类名是 checkin-btn
            btn = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "checkin-btn")))
            
            btn_text = btn.text.strip()
            is_disabled = btn.get_attribute("disabled") is not None
            
            logger.info(f"按钮检测: [{btn_text}] | 禁用状态: {is_disabled}")

            if "已完成" in btn_text or is_disabled:
                return "今日已签到过"
            
            # 模拟点击
            logger.info("执行签到点击...")
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(5)
            
            # 验证结果
            try:
                reward = self.driver.find_element(By.CLASS_NAME, "reward-amount").text
                return f"签到成功 ({reward})"
            except:
                return "签到已发送"

        except TimeoutException:
            # 针对 502 等异常情况的诊断
            title = self.driver.title
            if "502" in title or "Gateway" in title:
                return "服务器502报错"
            return "未找到签到按钮"

    def run(self):
        """单账号任务入口"""
        result_msg = "未知错误"
        balance = "未知"
        success = False
        try:
            if self.login():
                result_msg = self.checkin()
                balance = self.get_balance()
                success = True if "成功" in result_msg or "签到过" in result_msg else False
        except Exception as e:
            result_msg = str(e)
        finally:
            if self.driver:
                self.driver.quit()
        return success, result_msg, balance

class MultiAccountManager:
    def __init__(self):
        self.accounts = self.load_config()
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')

    def load_config(self):
        accounts = []
        raw = os.getenv('LEAFLOW_ACCOUNTS', '')
        if raw:
            for item in raw.split(','):
                if ':' in item:
                    u, p = item.split(':', 1)
                    accounts.append({'email': u.strip(), 'password': p.strip()})
        if not accounts:
            u, p = os.getenv('LEAFLOW_EMAIL'), os.getenv('LEAFLOW_PASSWORD')
            if u and p: accounts.append({'email': u, 'password': p})
        return accounts

    def send_tg(self, results):
        if not self.bot_token or not self.chat_id: return
        
        success_num = sum(1 for _, s, _, _ in results if s)
        text = f"<b>🎁 Leaflow 签到报告</b>\n成功: {success_num}/{len(results)}\n"
        for email, success, msg, bal in results:
            icon = "✅" if success else "❌"
            masked = email[:2] + "**" + email[email.find("@"):]
            text += f"\n{icon} {masked}\n结果: {msg}\n余额: {bal}\n"
        
        try:
            requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                          data={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        except: pass

    def start(self):
        final_results = []
        for acc in self.accounts:
            success, msg, bal = LeaflowAutoCheckin(acc['email'], acc['password']).run()
            final_results.append((acc['email'], success, msg, bal))
            time.sleep(2)
        self.send_tg(final_results)

if __name__ == "__main__":
    MultiAccountManager().start()
