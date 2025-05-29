"""The Almatel Balance integration."""

import logging
import re
import time
import datetime as dt
# import platform
from datetime import timedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# from homeassistant.helpers.entity_platform import AddEntitiesCallback
# from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN, NOTIFY_SERVICE, CONF_UPDATE_INTERVAL, ALMATEL_LOGIN_URL, ALMATEL_BALANCE_XPATH, ALMATEL_DUE_DATE_CLASS

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTION = SensorEntityDescription(
    key="almatel_balance",
    name=None,  # Используется перевод
    icon="mdi:cash",
    native_unit_of_measurement="RUB"
)

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = AlmatelDataUpdateCoordinator(hass, config_entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        raise ConfigEntryNotReady(f"Failed to fetch initial Almatel data: {e}")
    async_add_entities([AlmatelSensor(coordinator)])

class AlmatelDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry: ConfigEntry):
        self.hass = hass
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.update_interval_sec = entry.options.get(CONF_UPDATE_INTERVAL, entry.data.get(CONF_UPDATE_INTERVAL, 60))

        update_interval = timedelta(minutes=self.update_interval_sec)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval
        )


    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except Exception as e:
            msg = f"Almatel integration failed to update: {e}"
            _LOGGER.error(msg)
            self.hass.services.call(
                "persistent_notification",
                "create",
                {"title": "Almatel Error", "message": msg, "notification_id": "almatel_error"},
                blocking=False
            )
            return {
                "balance": None,
                "due_date": None,
                "message": "Ошибка соединения с Almatel",
                "days_left": None
            }


    def _fetch_data(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
# чтобы убрать WebGL ошибки
        # options.add_argument('--disable-software-rasterizer')
        # options.add_argument('--disable-dev-shm-usage')        # <= опционально
# можно явно указать
        # options.add_argument('--disable-webgl')

        driver = webdriver.Chrome(options=options)

        try:
            driver.set_page_load_timeout(20)
            driver.get(ALMATEL_LOGIN_URL)

            time.sleep(2)
            driver.find_element(By.NAME, "login").send_keys(self.username)
            driver.find_element(By.NAME, "password").send_keys(self.password)
            driver.find_element(By.CLASS_NAME, "login-form__input-submit").click()

            balance_text = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, ALMATEL_BALANCE_XPATH))
            ).text
            value = float(balance_text.replace(" ", "").replace("₽", "").replace(",", "."))

            due_date_raw = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, ALMATEL_DUE_DATE_CLASS))
            ).text
            due_date = extract_date(due_date_raw)
            if not due_date:
                due_date = dt.datetime.now().strftime("%d.%m.%Y")

            msg, num_days = time_to_pay(due_date)

            if num_days <= 3:
                self.hass.services.call(
                    NOTIFY_SERVICE.split(".")[0],
                    NOTIFY_SERVICE.split(".")[1],
                    {
                        "title": "Almatel Reminder",
                        "message": msg,
                        "notification_id": "almatel_due"
                    },
                    blocking=False
                )

            return {
                "balance": value,
                "due_date": due_date,
                "message": msg,
                "days_left": num_days
            }

        except Exception as e:
            _LOGGER.warning(f"Failed to fetch Almatel data: {e}")
            return {
                "balance": None,
                "due_date": None,
                "message": "Ошибка получения данных",
                "days_left": None
            }

        finally:
            driver.quit()

class AlmatelSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.entity_description = SENSOR_DESCRIPTION
        self._attr_unique_id = "almatel_balance"
        self._attr_translation_key = "almatel_balance"
        self._attr_name = "Almatel Balance"

    @property
    def native_value(self):
        _LOGGER.debug(f"Returning native value: {self.coordinator.data.get('balance')}")
        return self.coordinator.data.get("balance")

    @property
    def extra_state_attributes(self):
        return {
            "due_date": self.coordinator.data["due_date"],
            "message": self.coordinator.data["message"],
            "days_left": self.coordinator.data["days_left"]
        }


# helper functions

def extract_date(input_str):
    match = re.search(r'\d{2}\.\d{2}\.\d{4}', input_str)
    return match.group(0) if match else None

def day(num):
    reminder = num % 100 if num >= 100 else num % 10
    if num == 0 or reminder == 0 or reminder >= 5 or num in range(11, 19):
        return "дней"
    elif reminder == 1:
        return "день"
    else:
        return "дня"

def time_to_pay(due_date):
    due_date = dt.datetime.strptime(due_date, "%d.%m.%Y")
    target_timestamp = int(due_date.timestamp() + 10800)
    current_timestamp = int(time.time())
    num_days = (target_timestamp - current_timestamp) // 86400 + 1
    days = day(num_days)
    if num_days == 0:
        msg = "Сегодня срок оплаты Almatel!"
    elif 0 < num_days <= 5:
        msg = f"Через {num_days} {days} нужно оплатить Almatel!"
    elif num_days < 0:
        msg = "Просрочена оплата Almatel!!!"
    else:
        msg = f"Всё в порядке! Оплачивать Almatel нужно через {num_days} {days}."
    return msg, num_days
