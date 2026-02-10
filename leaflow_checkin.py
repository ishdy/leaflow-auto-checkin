#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本
变量名：LEAFLOW_ACCOUNTS
变量值：邮箱1:密码1,邮箱2:密码2,邮箱3:密码3
"""

import os
import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
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
            # 增加User-Agent伪装，防止被Cloudflare拦截
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
            time.sleep(3)  # 等待弹窗加载
            
            # 尝试关闭弹窗
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
        """等待元素可点击"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def wait_for_element_present(self, by, value, timeout=10):
        """等待元素出现"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    
    def login(self):
        """执行登录流程"""
        logger.info(f"开始登录流程")
        
        # 访问登录页面
        self.driver.get("https://leaflow.net/login")
        time.sleep(5)
        
        # 关闭弹窗
        self.close_popup()
        
        # 输入邮箱
        try:
            logger.info("查找邮箱输入框...")
            time.sleep(2)
            
            email_selectors = [
                "input[type='text']",
                "input[type='email']", 
                "input[placeholder*='邮箱']",
                "input[name='email']"
            ]
            
            email_input = None
            for selector in email_selectors:
                try:
                    email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, selector, 5)
                    break
                except:
                    continue
            
            if not email_input:
                raise Exception("找不到邮箱输入框")
            
            email_input.clear()
            email_input.send_keys(self.email)
            logger.info("邮箱输入完成")
            time.sleep(1)
            
        except Exception as e:
            try:
                self.driver.execute_script(f"document.querySelector('input[type=\"text\"], input[type=\"email\"]').value = '{self.email}';")
                logger.info("通过JavaScript强制设置邮箱")
            except:
                raise Exception(f"无法输入邮箱: {e}")
        
        # 等待密码输入框
        try:
            password_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='password']", 10)
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("密码输入完成")
        except:
            raise Exception("找不到密码输入框")
        
        # 点击登录
        try:
            login_btn = self.wait_for_element_clickable(By.XPATH, "//button[@type='submit' or contains(text(), '登录')]", 10)
            login_btn.click()
            logger.info("已点击登录按钮")
        except Exception as e:
            raise Exception(f"点击登录按钮失败: {e}")
        
        # 等待跳转
        try:
            WebDriverWait(self.driver, 20).until(
                lambda driver: "login" not in driver.current_url
            )
            logger.info(f"登录成功，当前URL: {self.driver.current_url}")
            return True
        except:
            raise Exception("登录超时")

    def get_balance(self):
        """获取余额"""
        try:
            self.driver.get("https://leaflow.net/dashboard")
            time.sleep(3)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            # 正则匹配金额
            match = re.search(r'(?:¥|￥|余额)\s*(\d+\.?\d*)', page_text)
            if match:
                balance = match.group(1)
                logger.info(f"找到余额: {balance}元")
                return f"{balance}元"
            return "未知"
        except:
            return "未知"

    def checkin(self):
        """执行签到流程 - 针对新版HTML修复"""
        logger.info("正在跳转至签到页面...")
        self.driver.get("https://checkin.leaflow.net")
        
        # 增加等待，确保JS渲染完成
        time.sleep(10)
        
        try:
            # 1. 查找签到按钮 (针对你提供的 HTML: 类名为 checkin-btn)
            wait = WebDriverWait(self.driver, 20)
            btn = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "checkin-btn")))
            
            btn_text = btn.text.strip()
            is_disabled = btn.get_attribute("disabled") is not None
            
            logger.info(f"当前按钮状态: 文本='{btn_text}', 是否禁用={is_disabled}")

            # 2. 判断状态逻辑
            if "已完成" in btn_text or is_disabled:
                logger.info("伙计，今日你已经签到过了！")
                return "今日已签到"
            
            # 3. 尝试点击
            logger.info("找到可点击的签到按钮，正在执行...")
            self.driver.execute_script("arguments[0].click();", btn) # 使用JS点击更稳定
            time.sleep(5)
            
            # 4. 再次检查状态确认成功
            new_btn = self.driver.find_element(By.CLASS_NAME, "checkin-btn")
            if "已完成" in new_btn.text or new_btn.get_attribute("disabled"):
                # 尝试抓取奖励数值
                try:
                    reward = self.driver.find_element(By.CLASS_NAME, "reward-amount").text
                    return f"签到成功！获得 {reward}"
                except:
                    return "签到完成"
            else:
                return "点击了按钮但状态未更新"

        except TimeoutException:
            # 如果超时，可能是被Cloudflare拦截，打印标题排查
            title = self.driver.title
            logger.error(f"加载超时，当前页面标题: {title}")
            if "Cloudflare" in title or "Just a moment" in title:
                raise Exception("被Cloudflare防火墙拦截，GitHub Actions IP 无法访问")
            raise Exception("在签到页面未找到 checkin-btn 按钮")

    def run(self):
        """单账号执行"""
        try:
            if self.login():
                result = self.checkin()
                balance = self.get_balance()
                return True, result, balance
            return False, "登录失败", "未知"
        except Exception as e:
            return False, str(e), "未知"
        finally:
            if self.driver:
                self.driver.quit()

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
                    email, password = pair.split(':', 1)
                    accounts.append({'email': email.strip(), 'password': password.strip()})
        
        if not accounts:
            email = os.getenv('LEAFLOW_EMAIL')
            password = os.getenv('LEAFLOW_PASSWORD')
            if email and password:
                accounts.append({'email': email, 'password': password})
        
        if not accounts:
            raise ValueError("未找到有效账号配置")
        return accounts
    
    def send_notification(self, results):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
        try:
            success_count = sum(1 for _, s, _, _ in results if s)
            current_date = datetime.now().strftime("%Y/%m/%d")
            msg = f"🎁 <b>Leaflow自动签到汇总</b>\n📊 成功: {success_count}/{len(results)}\n📅 日期: {current_date}\n\n"
            for email, success, res, bal in results:
                masked = email[:3] + "***" + email[email.find("@"):]
                status = "✅" if success else "❌"
                msg += f"账号: {masked}\n{status} {res}\n💰 余额: {bal}\n\n"
            
            requests.post(f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage", 
                          data={"chat_id": self.telegram_chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            logger.error(f"通知发送失败: {e}")

    def run_all(self):
        results = []
        for account in self.accounts:
            success, res, bal = LeaflowAutoCheckin(account['email'], account['password']).run()
            results.append((account['email'], success, res, bal))
            time.sleep(5)
        self.send_notification(results)
        return results

def main():
    try:
        manager = MultiAccountManager()
        manager.run_all()
    except Exception as e:
        logger.error(f"运行出错: {e}")
        exit(1)

if __name__ == "__main__":
    main()
