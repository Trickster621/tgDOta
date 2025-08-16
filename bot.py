# Замените всю функцию на эту.
def get_page_content_with_selenium(url):
    """
    Получает полный HTML-контент страницы после выполнения JavaScript.
    """
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Теперь драйвер не устанавливается, а просто находится в системе
        service = Service("/usr/bin/google-chrome") # Путь к исполняемому файлу Chrome на сервере
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        logger.info(f"Начинаю загрузку страницы с помощью Selenium: {url}")
        driver.get(url)
        
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "updates-content"))
        )
        
        content = driver.page_source
        logger.info("Страница успешно загружена, возвращаю контент.")
        return content
    
    except TimeoutException:
        logger.error("Таймаут ожидания загрузки контента.")
        return None
    except WebDriverException as e:
        logger.error(f"Ошибка WebDriver: {e}")
        return None
    except Exception as e:
        logger.error(f"Неизвестная ошибка Selenium: {e}")
        return None
    
    finally:
        if driver:
            logger.info("Закрываю драйвер.")
            driver.quit()
