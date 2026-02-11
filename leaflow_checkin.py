#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本
变量名：LEAFLOW_ACCOUNTS
变量值：邮箱1:密码1,邮箱2:密码2,邮箱3:密码3
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
            # 增加 UA 模拟，防止被识别为机器人
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
            
            # 尝试多种选择器找到邮箱输入框
            email_selectors = [
                "input[type='text']",
                "input[type='email']", 
                "input[placeholder*='邮箱']",
                "input[placeholder*='邮件']",
                "input[placeholder*='email']",
                "input[name='email']",
                "input[name='username']"
            ]
            
            email_input = None
            for selector in email_selectors:
                try:
                    email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, selector, 5)
                    logger.info(f"找到邮箱输入框")
                    break
                except:
                    continue
            
            if not email_input:
                raise Exception("找不到邮箱输入框")
            
            # 清除并输入邮箱
            email_input.clear()
            email_input.send_keys(self.email)
            logger.info("邮箱输入完成")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"输入邮箱时出错: {e}")
            # 尝试使用JavaScript直接设置值
            try:
                self.driver.execute_script(f"document.querySelector('input[type=\"text\"], input[type=\"email\"]').value = '{self.email}';")
                logger.info("通过JavaScript设置邮箱")
                time.sleep(2)
            except:
                raise Exception(f"无法输入邮箱: {e}")
        
        # 等待密码输入框出现并输入密码
        try:
            logger.info("查找密码输入框...")
            password_input = self.wait_for_element_clickable(
                By.CSS_SELECTOR, "input[type='password']", 10
            )
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("密码输入完成")
            time.sleep(1)
        except TimeoutException:
            raise Exception("找不到密码输入框")
        
        # 点击登录按钮
        try:
            logger.info("查找登录按钮...")
            login_btn_selectors = [
                "//button[contains(text(), '登录')]",
                "//button[contains(text(), 'Login')]",
                "//button[@type='submit']",
                "//input[@type='submit']",
                "button[type='submit']"
            ]
            
            login_btn = None
            for selector in login_btn_selectors:
                try:
                    if selector.startswith("//"):
                        login_btn = self.wait_for_element_clickable(By.XPATH, selector, 5)
                    else:
                        login_btn = self.wait_for_element_clickable(By.CSS_SELECTOR, selector, 5)
                    logger.info(f"找到登录按钮")
                    break
                except:
                    continue
            
            if not login_btn:
                raise Exception("找不到登录按钮")
            
            login_btn.click()
            logger.info("已点击登录按钮")
        except Exception as e:
            raise Exception(f"点击登录按钮失败: {e}")
        
        # 等待登录完成
        try:
            WebDriverWait(self.driver, 20).until(
                lambda driver: "dashboard" in driver.current_url or "workspaces" in driver.current_url or "login" not in driver.current_url
            )
            current_url = self.driver.current_url
            if "dashboard" in current_url or "workspaces" in current_url or "login" not in current_url:
                logger.info(f"登录成功，当前URL: {current_url}")
                return True
            else:
                raise Exception("登录后未跳转到正确页面")
        except TimeoutException:
            raise Exception("登录超时，无法确认登录状态")
    
    def get_balance(self):
        """获取当前账号的总余额"""
        try:
            logger.info("获取账号余额...")
            self.driver.get("https://leaflow.net/dashboard")
            time.sleep(3)
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            balance_selectors = [
                "//*[contains(text(), '¥') or contains(text(), '￥') or contains(text(), '元')]",
                "//*[contains(@class, 'balance')]",
                "//*[contains(@class, 'money')]"
            ]
            
            for selector in balance_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        text = element.text.strip()
                        if any(char.isdigit() for char in text) and ('¥' in text or '￥' in text or '元' in text):
                            import re
                            numbers = re.findall(r'\d+\.?\d*', text)
                            if numbers:
                                balance = numbers[0]
                                logger.info(f"找到余额: {balance}元")
                                return f"{balance}元"
                except:
                    continue
            return "未知"
        except Exception as e:
            logger.warning(f"获取余额时出错: {e}")
            return "未知"
    
    def wait_for_checkin_page_loaded(self, max_retries=3, wait_time=20):
        """等待签到页面完全加载，支持重试"""
        for attempt in range(max_retries):
            logger.info(f"等待签到页面加载，尝试 {attempt + 1}/{max_retries}，等待 {wait_time} 秒...")
            time.sleep(wait_time)
            try:
                # 针对新HTML增加 .checkin-btn 识别
                checkin_indicators = [
                    "button.checkin-btn",
                    "//button[contains(text(), '立即签到')]",
                    "//button[contains(text(), '已完成')]",
                    "//*[contains(text(), '每日签到')]"
                ]
                for indicator in checkin_indicators:
                    try:
                        if indicator.startswith("//"):
                            element = self.driver.find_element(By.XPATH, indicator)
                        else:
                            element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                        if element.is_displayed():
                            logger.info(f"找到签到页面元素")
                            return True
                    except:
                        continue
            except Exception as e:
                logger.warning(f"第 {attempt + 1} 次检查页面出错: {e}")
        return False
    
    def find_and_click_checkin_button(self):
        """查找并点击签到按钮 - 适配你的 HTML 源码"""
        logger.info("查找签到按钮...")
        try:
            time.sleep(5)
            # 优先使用 .checkin-btn 类名定位
            try:
                checkin_btn = self.driver.find_element(By.CLASS_NAME, "checkin-btn")
            except:
                checkin_btn = self.driver.find_element(By.CSS_SELECTOR, "button[class*='checkin']")

            if checkin_btn.is_displayed():
                btn_text = checkin_btn.text.strip()
                # 检查文字：已完成 或 按钮被禁用
                if "已完成" in btn_text or "已签到" in btn_text or checkin_btn.get_attribute("disabled"):
                    logger.info("伙计，今日你已经签到过了！")
                    return "already_checked_in"
                
                if checkin_btn.is_enabled():
                    logger.info(f"找到并点击按钮：{btn_text}")
                    # 使用 JS 点击，解决无头模式下的点击拦截问题
                    self.driver.execute_script("arguments[0].click();", checkin_btn)
                    return True
                else:
                    return "already_checked_in"
            return False
        except Exception as e:
            logger.error(f"查找签到按钮时出错: {e}")
            return False
    
    def checkin(self):
        """执行签到流程"""
        logger.info("跳转到签到页面...")
        self.driver.get("https://checkin.leaflow.net")
        
        if not self.wait_for_checkin_page_loaded(max_retries=3, wait_time=20):
            raise Exception("签到页面加载失败，无法找到签到相关元素")
        
        checkin_result = self.find_and_click_checkin_button()
        
        if checkin_result == "already_checked_in":
            return "今日已签到"
        elif checkin_result is True:
            time.sleep(5)
            return self.get_checkin_result()
        else:
            raise Exception("找不到立即签到按钮或按钮不可点击")
    
    def get_checkin_result(self):
        """获取签到结果消息"""
        try:
            time.sleep(3)
            success_selectors = [".alert-success", ".success", ".message", ".modal-content", ".reward-amount"]
            for selector in success_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        text = element.text.strip()
                        if text: return text
                except:
                    continue
            
            # 检查奖励数值
            try:
                reward = self.driver.find_element(By.CLASS_NAME, "reward-amount").text
                if reward: return f"签到成功！获得 {reward}"
            except:
                pass
                
            return "签到完成"
        except Exception as e:
            return f"获取结果异常: {str(e)}"
    
    def run(self):
        """单个账号执行流程"""
        try:
            logger.info(f"开始处理账号")
            if self.login():
                result = self.checkin()
                balance = self.get_balance()
                logger.info(f"签到结果: {result}, 余额: {balance}")
                return True, result, balance
            else:
                raise Exception("登录失败")
        except Exception as e:
            error_msg = f"失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, "未知"
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
            try:
                account_pairs = [pair.strip() for pair in accounts_str.split(',')]
                for pair in account_pairs:
                    if ':' in pair:
                        email, password = pair.split(':', 1)
                        accounts.append({'email': email.strip(), 'password': password.strip()})
            except Exception as e:
                logger.error(f"解析配置失败: {e}")
        
        if not accounts:
            email = os.getenv('LEAFLOW_EMAIL', '').strip()
            password = os.getenv('LEAFLOW_PASSWORD', '').strip()
            if email and password:
                accounts.append({'email': email, 'password': password})
        
        if not accounts:
            raise ValueError("未找到有效的账号配置")
        return accounts
    
    def send_notification(self, results):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info("跳过通知")
            return
        try:
            success_count = sum(1 for _, success, _, _ in results if success)
            current_date = datetime.now().strftime("%Y/%m/%d")
            message = f"🎁 Leaflow自动签到通知\n📊 成功: {success_count}/{len(results)}\n📅 签到时间：{current_date}\n\n"
            for email, success, result, balance in results:
                status = "✅" if success else "❌"
                masked_email = email[:3] + "***" + email[email.find("@"):]
                message += f"账号：{masked_email}\n{status} {result}！\n💰 当前总余额：{balance}。\n\n"
            
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            requests.post(url, data={"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            logger.error(f"通知出错: {e}")
    
    def run_all(self):
        results = []
        for i, account in enumerate(self.accounts, 1):
            logger.info(f"处理第 {i}/{len(self.accounts)} 个账号")
            auto_checkin = LeaflowAutoCheckin(account['email'], account['password'])
            success, result, balance = auto_checkin.run()
            results.append((account['email'], success, result, balance))
            if i < len(self.accounts): time.sleep(5)
        
        self.send_notification(results)
        return results

def main():
    try:
        manager = MultiAccountManager()
        manager.run_all()
    except Exception as e:
        logger.error(f"出错: {e}")
        exit(1)

if __name__ == "__main__":
    main()
