#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本 - 完整修复整合版
功能：多账号支持、Telegram 通知、余额抓取、GitHub Actions 适配
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
        
        # GitHub Actions环境配置
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            # 关键：模拟真实浏览器 UA，防止被拦截
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
            actions = ActionChains(self.driver)
            actions.move_by_offset(10, 10).click().perform()
            logger.info("已成功关闭弹窗")
            time.sleep(2)
            return True
        except:
            return False
            
    def wait_for_element_clickable(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by, value)))

    def login(self):
        """执行登录流程"""
        logger.info(f"开始登录流程: {self.email[:3]}***")
        self.driver.get("https://leaflow.net/login")
        time.sleep(5)
        self.close_popup()
        
        try:
            # 兼容多种输入框
            email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[name='email']", 15)
            email_input.clear()
            email_input.send_keys(self.email)
            
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_input.clear()
            password_input.send_keys(self.password)
            
            login_btn = self.driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), '登录')]")
            login_btn.click()
            
            # 等待登录成功跳转
            WebDriverWait(self.driver, 20).until(lambda d: "login" not in d.current_url)
            logger.info(f"登录成功，当前URL: {self.driver.current_url}")
            return True
        except Exception as e:
            logger.error(f"登录流程出错: {e}")
            return False
    
    def get_balance(self):
        """获取总余额"""
        try:
            logger.info("获取账号余额...")
            self.driver.get("https://leaflow.net/dashboard")
            time.sleep(3)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            match = re.search(r'(?:¥|￥|余额)\s*(\d+\.?\d*)', page_text)
            if match:
                return f"{match.group(1)}元"
            return "未知"
        except Exception as e:
            logger.warning(f"获取余额失败: {e}")
            return "未知"

    def checkin(self):
        """核心签到流程 - 针对最新HTML修复"""
        logger.info("跳转至签到子站...")
        self.driver.get("https://checkin.leaflow.net")
        
        # 针对异步加载给予充足时间
        time.sleep(10)
        
        try:
            wait = WebDriverWait(self.driver, 20)
            # 精准定位 HTML 源码中的 checkin-btn 类名
            btn = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "checkin-btn")))
            
            btn_text = btn.text.strip()
            is_disabled = btn.get_attribute("disabled") is not None
            
            logger.info(f"状态检测: [{btn_text}] | 禁用状态: {is_disabled}")

            if "已完成" in btn_text or "已签到" in btn_text or is_disabled:
                return "今日已签到"
            
            # 执行点击（JS点击防止遮挡）
            logger.info("执行签到点击操作...")
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(5)
            
            # 抓取奖励结果
            try:
                reward = self.driver.find_element(By.CLASS_NAME, "reward-amount").text
                return f"签到成功！获得 {reward}"
            except:
                return "签到完成，未抓取到奖励数值"

        except TimeoutException:
            title = self.driver.title
            if "502" in title: return "服务器502报错"
            return "找不到签到按钮(超时)"
        except Exception as e:
            return f"签到异常: {str(e)}"

    def run(self):
        """单账号运行逻辑"""
        try:
            if self.login():
                result = self.checkin()
                balance = self.get_balance()
                logger.info(f"结果: {result} | 余额: {balance}")
                return True, result, balance
            return False, "登录失败", "未知"
        except Exception as e:
            return False, str(e), "未知"
        finally:
            if self.driver:
                self.driver.quit()

class MultiAccountManager:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts()
    
    def load_accounts(self):
        accounts = []
        # 处理多账号环境变量
        accounts_str = os.getenv('LEAFLOW_ACCOUNTS', '').strip()
        if accounts_str:
            for pair in accounts_str.split(','):
                if ':' in pair:
                    email, pwd = pair.split(':', 1)
                    accounts.append({'email': email.strip(), 'password': pwd.strip()})
        # 兼容单账号环境变量
        if not accounts:
            email, pwd = os.getenv('LEAFLOW_EMAIL'), os.getenv('LEAFLOW_PASSWORD')
            if email and pwd:
                accounts.append({'email': email.strip(), 'password': pwd.strip()})
        
        if not accounts:
            raise ValueError("未配置有效账号")
        return accounts
    
    def send_notification(self, results):
        """发送汇总通知"""
        if not self.bot_token or not self.chat_id:
            logger.info("未配置Telegram通知，跳过")
            return
        
        try:
            success_count = sum(1 for _, success, _, _ in results if success)
            date_str = datetime.now().strftime("%Y/%m/%d")
            
            message = f"🎁 <b>Leaflow 签到任务报告</b>\n"
            message += f"📊 状态: {success_count}/{len(results)} 成功\n"
            message += f"📅 日期: {date_str}\n"
            
            for email, success, result, balance in results:
                status_icon = "✅" if success else "❌"
                masked_email = email[:3] + "***" + email[email.find("@"):]
                message += f"\n账号: {masked_email}\n"
                message += f"{status_icon} 结果: {result}\n"
                message += f"💰 余额: {balance}\n"
            
            requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                          data={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}, timeout=15)
            logger.info("Telegram通知已发送")
        except Exception as e:
            logger.error(f"通知发送失败: {e}")

    def run_all(self):
        logger.info(f"开始批量执行 {len(self.accounts)} 个账号")
        all_results = []
        for account in self.accounts:
            success, res, bal = LeaflowAutoCheckin(account['email'], account['password']).run()
            all_results.append((account['email'], success, res, bal))
            time.sleep(3)
        self.send_notification(all_results)

if __name__ == "__main__":
    try:
        manager = MultiAccountManager()
        manager.run_all()
    except Exception as e:
        logger.error(f"脚本执行失败: {e}")
