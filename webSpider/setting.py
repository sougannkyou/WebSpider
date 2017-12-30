# coding=utf-8
import os

PAGE_SIZE = 20

TEST_SERVER = 'http://' + os.environ.get("config_test_uri")  # 'http://192.168.132.79'
_IS_LOCAL_DEBUG_ENV = True if os.environ.get('webspider_local_debug','no') == 'yes' else False
_IS_ALPHA_ENV = True if os.environ.get('visual_env') == 'alpha' else False

XGSJ_DOMAIN = 'https://xgsj3-alpha.istarshine.com' if _IS_ALPHA_ENV else "https://xgsj.istarshine.com"

if _IS_LOCAL_DEBUG_ENV:
    STATIC_TEMP_DIR = "http://172.16.254.15:8000"
elif _IS_ALPHA_ENV:
    STATIC_TEMP_DIR = "https://webspider-alpha.istarshine.com"
else:
    STATIC_TEMP_DIR = "https://webspider.istarshine.com"
