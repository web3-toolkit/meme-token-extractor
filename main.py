import csv
import json
import random
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

ADSPOWER_API_BASE_URL = "http://local.adspower.net:50325"
PROFILES_TO_OPEN = "profiles_to_open.txt"

def map_profile_name_to_id():
    result = {}

    pages_left = True
    page = 1
    profiles = []
    while pages_left:
        result = {}
        query = {'page_size': '100', 'page': page}
        response = requests.get(ADSPOWER_API_BASE_URL + "/api/v1/user/list", query)
        profiles.extend(response.json()['data']['list'])
        if len(response.json()['data']['list']) < 100:
            pages_left = False
        else:
            page += 1
        time.sleep(1)

    for profileInfo in profiles:
        name = profileInfo['name']
        id = profileInfo['user_id']
        result[name] = id
    return result


def connect_to_profile(profile_id):
    attempts = 3
    sleep_time = 20
    while attempts > 0:
        try:
            query = {'user_id': profile_id}
            response = requests.get(ADSPOWER_API_BASE_URL + "/api/v1/browser/start", query).json()
            selenium_url = response["data"]["ws"]["selenium"]
            driver_path = response["data"]["webdriver"]
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", selenium_url)
            chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
            service = Service(executable_path=driver_path)
            return webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print("An exception occurred {}".format(e))
        time.sleep(sleep_time)
        sleep_time *= 2
        attempts -= 1

def close_profile(profile_id):
    query = {'user_id': profile_id}
    requests.get(ADSPOWER_API_BASE_URL + "/api/v1/browser/stop", query).json()


def new_tab(driver, url):
    driver.switch_to.new_window()
    driver.get(url)


def get_profile_names_to_open():
    profile_names_to_open = []
    with open(PROFILES_TO_OPEN, 'r') as file:
        for line in file:
            profile_names_to_open.append(line.replace("\n", ""))
    return profile_names_to_open


def save_csv(profile_name_to_token):
    result = []
    for profile_and_token in profile_name_to_token.items():
        result.append({"Profile name": profile_and_token[0], "Token": profile_and_token[1]})
    with open("results.csv", "w", newline="") as csv_file:
        field_names = list(result[0].keys())
        writer = csv.DictWriter(csv_file, fieldnames=field_names)
        writer.writeheader()
        for row in result:
            writer.writerow(row)


def try_authenticate(driver, profile_id):
    try:
        connect_with_button = driver.find_elements(By.XPATH, "//*[contains(text(), 'CONNECT WITH')]")
        if len(connect_with_button) > 0:
            time.sleep(random.randint(1, 5))
            connect_with_button[0].click()
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'MEMEPOINTS')]"))
            )
            time.sleep(2)
    except Exception:
        print(f"Authentication failed for {profile_id} profile")


if __name__ == '__main__':
    profile_name_to_id = map_profile_name_to_id()
    profile_names_to_open = get_profile_names_to_open()

    profile_name_to_token = {}
    for profile_name in profile_names_to_open:
        profile_id = profile_name_to_id.get(profile_name)
        driver = connect_to_profile(profile_id=profile_id)
        new_tab(driver, "https://www.memecoin.org/farming")

        try_authenticate(driver, profile_id)

        profile_name_to_token[profile_name] = "Could not authenticate"
        if driver.find_elements(By.XPATH, "//*[contains(text(), 'MEMEPOINTS')]") == 0:
            print(f"Could not authenticate {profile_name} profile")
            continue
        logs = driver.get_log("performance")
        try:
            for log in logs:
                log_str = str(log)
                if 'https://memefarm-api.memecoin.org/user/info' in log_str and "Bearer" in log_str:
                    token = (json
                             .loads(log["message"])["message"]["params"]["request"]["headers"]["authorization"]
                             .replace("Bearer ", ""))
                    profile_name_to_token[profile_name] = token
                    print(f"Successfully extracted token from {profile_name} profile")
            driver.close()
            close_profile(profile_id)
            time.sleep(1)
        except Exception:
            print(f"Could not authenticate {profile_name} profile")

    save_csv(profile_name_to_token)
