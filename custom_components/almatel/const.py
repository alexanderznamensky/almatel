"""The Almatel Balance integration."""

DOMAIN = "almatel"
NOTIFY_SERVICE = "persistent_notification.create"
CONF_UPDATE_INTERVAL = "update_interval"

ALMATEL_LOGIN_URL = "https://almatel.ru/lk/login.php"
ALMATEL_BALANCE_XPATH = "//*[@id='profile-info']/div[3]/div/div[1]/div[1]/div/div[2]/div[2]/div[2]"
ALMATEL_DUE_DATE_CLASS = "lk-aside__block-descr"