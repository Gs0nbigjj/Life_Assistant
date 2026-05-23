# cogs\LifeTracker\src\invoice_crawler.py
import os
import time
import base64
import io
import ddddocr
import PIL.Image
from PIL import Image

if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select 
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

class InvoiceCrawler:
    def __init__(self):
        self.ocr = ddddocr.DdddOcr()
        self.download_dir = os.path.abspath(os.path.join(os.getcwd(), "cogs", "LifeTracker", "src", "downloads"))
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            
        self.driver = self._setup_stealth_driver()

    def _setup_stealth_driver(self):
        options = Options()
        options.add_argument("--headless=new") 
        
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1080,720")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        options.add_argument("--disable-dev-shm-usage") 
        options.add_argument("--disable-software-rasterizer")
        
        options.add_argument("--disable-crash-reporter")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-in-process-stack-traces")
        options.add_argument("--disable-logging")
        options.add_argument("--log-level=3")
        options.add_argument("--output=/dev/null")
        options.page_load_strategy = 'normal' 
        
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        options.add_argument(f"user-agent={user_agent}")
        
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True 
        }
        options.add_experimental_option("prefs", prefs)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': self.download_dir
        })
        
        return driver

    def login(self, phone, password):
        target_url = "https://www.einvoice.nat.gov.tw/accounts/login/mw"
        max_retries = 5
        wait = WebDriverWait(self.driver, 10)

        for attempt in range(max_retries):
            try:
                print(f"🔄 開始登入嘗試 ({attempt+1}/{max_retries})...")
                self.driver.get(target_url)
                
                phone_input = wait.until(EC.presence_of_element_located((By.ID, "mobile_phone")))
                phone_input.clear()
                phone_input.send_keys(phone)
                
                pwd_input = self.driver.find_element(By.ID, "password")
                pwd_input.clear()
                pwd_input.send_keys(password)
                
                captcha_img = self.driver.find_element(By.XPATH, "//img[@alt='圖形驗證碼']")
                img_src = captcha_img.get_attribute("src")
                
                base64_data = img_src.split(',')[1]
                raw_img_bytes = base64.b64decode(base64_data)
                
                image = Image.open(io.BytesIO(raw_img_bytes))
                if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                    alpha = image.convert('RGBA').split()[-1]
                    bg = Image.new("RGB", image.size, (255, 255, 255))
                    bg.paste(image, mask=alpha)
                    image = bg
                else:
                    image = image.convert('RGB')
                
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                clean_img_bytes = img_byte_arr.getvalue()
                
                captcha_text = self.ocr.classification(clean_img_bytes)
                print(f"👁️ OCR 辨識出驗證碼: {captcha_text}")
                
                captcha_input = self.driver.find_element(By.ID, "captcha")
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)
                captcha_input.send_keys(Keys.RETURN)
                
                time.sleep(3) 
                
                if len(self.driver.find_elements(By.ID, "mobile_phone")) == 0:
                    print("✅ 登入成功！")
                    return True
                else:
                    print("⚠️ 登入失敗，準備重試...")
                    
            except Exception as e:
                print(f"❌ 錯誤: {e}")
                time.sleep(2)
                
        self.driver.quit()
        return False
        
    # 動態監控資料夾
    def _wait_for_download(self, timeout=30):
        """監控下載資料夾，直到 CSV 檔案完全下載完畢，最多等待 timeout 秒"""
        print("⏳ 正在監控下載進度...")
        for _ in range(timeout):
            files = os.listdir(self.download_dir)
            
            is_downloading = any(f.endswith('.crdownload') for f in files)
            has_csv = any(f.endswith('.csv') for f in files)
            
            if has_csv and not is_downloading:
                print("✅ 檔案下載完成！")
                return True
                
            time.sleep(1)
            
        return False
    
    def download_csv(self, start_id: str, end_id: str):
        """執行查詢、過濾與下載 CSV 的自動化流程"""
        wait = WebDriverWait(self.driver, 10)
        JS_CLICK = "arguments[0].click();"
        
        try:
            print(f"📅 準備點擊日曆，區間: {start_id} ~ {end_id}")

            time.sleep(2) 
            date_input = wait.until(EC.presence_of_element_located((By.ID, "dp-input-searchInvoiceDate")))
            wait.until(EC.element_to_be_clickable((By.ID, "dp-input-searchInvoiceDate")))
            
            self.driver.execute_script(JS_CLICK, date_input)
            time.sleep(1)

            print(f"🖱️ 點擊設定起始日 ({start_id})...")
            start_element = wait.until(EC.presence_of_element_located((By.ID, start_id)))
            self.driver.execute_script(JS_CLICK, start_element)
            time.sleep(0.5)
            
            print(f"🖱️ 點擊設定結束日 ({end_id})...")
            end_element = wait.until(EC.presence_of_element_located((By.ID, end_id)))
            self.driver.execute_script(JS_CLICK, end_element)
            time.sleep(1)

            print("🔍 點擊查詢按鈕...")
            search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@title='查詢']")))
            self.driver.execute_script(JS_CLICK, search_btn)
            time.sleep(3) 
            
            try:
                print("📄 確認是否有資料並設定顯示筆數為 100 筆...")
                short_wait = WebDriverWait(self.driver, 5)
                select_element = short_wait.until(EC.presence_of_element_located((By.ID, "SelectSizes")))
                select = Select(select_element)
                select.select_by_value("100")
                time.sleep(2) 
                
                print("🔄 點擊第一頁刷新...")
                page_one_btn = short_wait.until(EC.presence_of_element_located((By.XPATH, "//a[@title='1']")))
                self.driver.execute_script(JS_CLICK, page_one_btn)
                time.sleep(3) 
                
                print("☑️ 勾選全選...")
                select_all_cb = short_wait.until(EC.presence_of_element_located((By.ID, "invoiceDetailAll")))
                self.driver.execute_script(JS_CLICK, select_all_cb)
                time.sleep(1)
                
                print("⬇️ 點擊下載 CSV 檔...")
                download_btn = short_wait.until(
                    lambda d: d.find_element(By.XPATH, "//button[@title='下載CSV檔']") 
                    if not d.find_element(By.XPATH, "//button[@title='下載CSV檔']").get_attribute("disabled") 
                    else False
                )
                self.driver.execute_script(JS_CLICK, download_btn)
                print("🎉 CSV 下載指令已送出！等待檔案下載...")
                
                # 動態監控
                if not self._wait_for_download(timeout=30):
                    print("❌ 警告：下載超時或失敗，找不到完成的 CSV 檔案。")
                    return False
                
            except Exception:
                print("⚠️ 查無資料：該區間沒有發票紀錄，略過下載步驟。")

        except Exception as e:
            print(f"❌ 查詢流程發生錯誤: {e}")
            return False
            
        finally:
            try:
                print("🚪 任務完成，準備登出系統...")
                
                try:
                    alert = self.driver.switch_to.alert
                    alert.accept()
                except:
                    pass

                logout_xpath = "//a[@title='登出' or contains(text(), '登出') or contains(., '登出')]"
                
                logout_btn = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, logout_xpath))
                )
                
                self.driver.execute_script("arguments[0].click();", logout_btn)
                
                time.sleep(3) 
                print("✅ 成功登出，安全下線！")
                
            except Exception as e:
                print(f"⚠️ 登出時發生異常，網頁可能已跳轉或按鈕被隱藏。錯誤詳情: {type(e).__name__}")
                
        return True