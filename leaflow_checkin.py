#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本 - 完整无损修复版
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import requests
from datetime import datetime

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
        
        # GitHub Actions环境配置
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            # --- 关键补丁：伪装 UA ---
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 通用配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def close_popup(self):
        """关闭初始弹窗"""
        try:
            logger.info("尝试关闭初始弹窗...")
            time.sleep(3)
            try:
                actions = ActionChains(self.driver)
                actions.move_by_offset(10, 10).click().perform()
                logger.info("已成功关闭弹窗")
                time.sleep(2)
                return True
            except:
                pass
            return False
        except Exception as e:
            logger.warning(f"关闭弹窗时出错: {e}")
            return False
    
    def wait_for_element_clickable(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by, value)))
    
    def login(self):
        """执行登录流程"""
        logger.info(f"开始登录流程")
        self.driver.get("https://leaflow.net/login")
        time.sleep(5)
        self.close_popup()
        
        try:
            logger.info("查找邮箱输入框...")
            time.sleep(2)
            email_selectors = ["input[type='text']", "input[type='email']", "input[placeholder*='邮箱']", "input[name='email']"]
            email_input = None
            for selector in email_selectors:
                try:
                    email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, selector, 5)
                    break
                except: continue
            
            if not email_input: raise Exception("找不到邮箱输入框")
            email_input.clear()
            email_input.send_keys(self.email)
            logger.info("邮箱输入完成")
            time.sleep(2)
            
            logger.info("查找密码输入框...")
            password_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='password']", 10)
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("密码输入完成")
            
            login_btn = self.wait_for_element_clickable(By.XPATH, "//button[@type='submit' or contains(text(), '登录')]", 10)
            login_btn.click()
            logger.info("已点击登录按钮")
            
            WebDriverWait(self.driver, 20).until(lambda driver: "dashboard" in driver.current_url or "login" not in driver.current_url)
            return True
        except Exception as e:
            raise Exception(f"登录失败: {e}")
    
    def get_balance(self):
        """获取总余额"""
        try:
            logger.info("获取账号余额...")
            self.driver.get("https://leaflow.net/dashboard")
            time.sleep(3)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            import re
            numbers = re.findall(r'\d+\.?\d*', page_text)
            for n in numbers:
                if "." in n and len(n) >= 3: return f"{n}元"
            return "未知"
        except: return "未知"

    def wait_for_checkin_page_loaded(self, max_retries=3, wait_time=20):
        """等待签到页面完全加载"""
        for attempt in range(max_retries):
            logger.info(f"等待签到页面加载，尝试 {attempt + 1}/{max_retries}...")
            time.sleep(wait_time)
            # --- 关键修改：增加 .checkin-btn 识别 ---
            checkin_indicators = ["button.checkin-btn", "//button[contains(text(), '已完成')]", "//*[contains(text(), '签到')]"]
            for indicator in checkin_indicators:
                try:
                    if indicator.startswith("//"):
                        el = self.driver.find_element(By.XPATH, indicator)
                    else:
                        el = self.driver.find_element(By.CSS_SELECTOR, indicator)
                    if el.is_displayed(): return True
                except: continue
        return False
    
    def find_and_click_checkin_button(self):
        """查找并点击签到按钮"""
        try:
            time.sleep(5)
            # --- 关键修改：精准匹配你的 HTML ---
            try:
                checkin_btn = self.driver.find_element(By.CLASS_NAME, "checkin-btn")
            except:
                checkin_btn = self.driver.find_element(By.XPATH, "//button[contains(@class, 'checkin')]")

            btn_text = checkin_btn.text.strip()
            if "已完成" in btn_text or "已签到" in btn_text or checkin_btn.get_attribute("disabled"):
                logger.info("伙计，今日你已经签到过了！")
                return "already_checked_in"
            
            logger.info(f"执行点击：{btn_text}")
            self.driver.execute_script("arguments[0].click();", checkin_btn)
            return True
        except Exception as e:
            logger.error(f"查找签到按钮出错: {e}")
            return False
    
    def checkin(self):
        self.driver.get("https://checkin.leaflow.net")
        if not self.wait_for_checkin_page_loaded():
            raise Exception("签到页面加载失败，无法找到签到相关元素")
        
        res = self.find_and_click_checkin_button()
        if res == "already_checked_in": return "今日已签到"
        elif res is True:
            time.sleep(5)
            return "签到成功"
        else: raise Exception("点击按钮失败")

    def run(self):
        try:
            logger.info(f"开始处理账号")
            if self.login():
                result = self.checkin()
                balance = self.get_balance()
                return True, result, balance
            return False, "登录失败", "未知"
        except Exception as e:
            return False, str(e), "未知"
        finally:
            if self.driver: self.driver.quit()

class MultiAccountManager:
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts()
    
    def load_accounts(self):
        accounts = []
        accounts_str = os.getenv('LEAFLOW_ACCOUNTS', '').strip()
        if accounts_str:
            for pair in accounts_str.split(','):
                if ':' in pair:
                    u, p = pair.split(':', 1)
                    accounts.append({'email': u.strip(), 'password': p.strip()})
        if not accounts:
            u, p = os.getenv('LEAFLOW_EMAIL'), os.getenv('LEAFLOW_PASSWORD')
            if u and p: accounts.append({'email': u, 'password': p})
        return accounts
    
    def send_notification(self, results):
        if not self.telegram_bot_token or not self.telegram_chat_id: return
        msg = f"🎁 Leaflow自动签到通知\n"
        for email, success, result, balance in results:
            status = "✅" if success else "❌"
            msg += f"账号：{email[:3]}***\n{status} {result}\n💰 余额：{balance}\n\n"
        requests.post(f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage", data={"chat_id": self.telegram_chat_id, "text": msg})

    def run_all(self):
        results = []
        for account in self.accounts:
            success, res, bal = LeaflowAutoCheckin(account['email'], account['password']).run()
            results.append((account['email'], success, res, bal))
            time.sleep(5)
        self.send_notification(results)

if __name__ == "__main__":
    MultiAccountManager().run_all()
