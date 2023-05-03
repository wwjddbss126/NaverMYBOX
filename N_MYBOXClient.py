import requests
import time
import re
import json
import cowsay
import datetime
import pyfiglet
from playwright.sync_api import (Locator, Page, sync_playwright, Playwright, BrowserType)
from urllib.parse import urlencode
from colorama import Fore, Style
from tabulate import tabulate

urls = {
    "url_login": 'https://nid.naver.com/nidlogin.login?url=https%3A%2F%2Fmybox.naver.com',
    "url_userinfo": "https://static.nid.naver.com/getLoginStatus?callback=showGNB&charset=utf-8&svc=ndrive&template"
                    "=gnb_utf8&one_naver=1",
    "url_quota": "https://api.mybox.naver.com/service/quota/get",
    "url_service": "https://api.mybox.naver.com/service/user/get",
    "url_rk": "https://api.mybox.naver.com/service/file/get?resourceKey=root",
    "url_rkv": "https://api.mybox.naver.com/service/file/count?resourceKey=",
    "url_list": "https://api.mybox.naver.com/service/file/list",
    "url_thumb": "https://thumb2.photo.mybox.naver.com/",
    "url_data": "https://files.mybox.naver.com/file/download.api?resourceKey="
}

ck, headers, rk = '', '', ''

req_data = {
    "NDriveSvcType": "NHN/ND-WEB Ver",
    "resourceKey": "root",
    "resourceOption": "photo",
    "fileOption": "all",
    "startNum": "0",
    "pagingRow": "200",
    "optFields": "parentKey,nickname",
    "sort": "create",
    "order": "desc"
}

def log_info(message):
    print(Fore.LIGHTBLUE_EX + f"[INFO] {message}" + Style.RESET_ALL)

def log_debug(message):
    print(Fore.GREEN + f"[DEBUG] {message}" + Style.RESET_ALL)

def log_warning(message):
    print(Fore.RED + f"[DEBUG] {message}" + Style.RESET_ALL)

def login(playwright, input_id, input_pw):

    chromium = playwright.chromium
    browser = chromium.launch(headless=False)
    context = browser.new_context()

    page = context.new_page()
    page.goto(urls['url_login'])

    log_debug("[*] Singing in...")

    page.fill('#id', input_id)
    page.fill('#pw', input_pw)

    page.click('#log\.login')
    time.sleep(1)

    if page.query_selector('#content > div.title.title_v2'):
        page.click('#new\.dontsave')

    log_debug("[*] Getting User Cookies...")

    global ck
    ck = page.context.cookies()

    global headers
    headers = {
        'Host': 'static.nid.naver.com',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
        'sec-ch-ua-platform': "Windows",
        'Accept': "*/*",
        'Referer': 'https://mybox.naver.com/',
        'Accept-Language': 'ko-KR,ko;q=0.9,es-ES;q=0.8,es;q=0.7,en-US;q=0.6,en;q=0.5'
    }

    cookies = {}
    for item in ck:
        if item['name'] == 'NNB':
            cookies['nid_buk'] = item['value']
        cookies[item['name']] = item['value']
    cookie_header = '; '.join([f'{name}={value}' for name, value in cookies.items()])

    headers['Cookie'] = cookie_header

    ck = context.cookies()

def user():
    log_debug("[*] Collecting User Account Information...")
    response = requests.get(urls['url_userinfo'], headers=headers)

    log_info("[*] User Information")

    match = re.search(r'showGNB\(({.*})\);', response.text)
    if match:
        data_str = match.group(1)
        data = eval(data_str)

        for key, value in data.items():
            print(f"{key}: {value}")

    log_info("[*] Account Information")

    data = json.loads(requests.get(urls['url_quota'], headers=headers).text)
    for key, value in data['result'].items():
        print(f"{key}: {value}")

    log_info("[*] Resource Information")

    data = json.loads(requests.get(urls['url_service'], headers=headers).text)
    for key, value in data['result'].items():
        print(f"{key}: {value}")

    user_rk()

def user_rk():
    global rk
    log_info("[*] User Resource Information")

    data = json.loads(requests.get(urls['url_rk'], headers=headers).text)
    for key, value in data['result'].items():
        if key == "resourceKey":
            rk = value
        print(f"{key}: {value}")

    log_debug("[*] Verifying Resource Key")
    data = json.loads(requests.get(urls['url_rkv'] + rk + "&resourceOption=folder", headers=headers).text)
    if data["message"] != "success":
        raise Exception("Resource key verification Failed")
    else:
        log_info("[*] Resource key verification Succeed")

def file_list():
    log_info("[*] File Metadata Information")
    response = json.loads(requests.post(urls['url_list'], headers=headers, data=req_data).text)
    for key, value in response['result'].items():
        if key != "list":
            print(f"{key}: {value}")
        else:
            print(tabulate([item.values() for item in value], headers=value[0].keys()))

def file_thumb():
    table_data = []
    response = json.loads(requests.post(urls['url_list'], headers=headers, data=req_data).text)['result']['list']
    for i, item in enumerate(response):
        row = [i + 1]
        row.extend([item['resourceType'], item['resourcePath'], item['resourceSize'],
                    datetime.datetime.fromtimestamp(item['createDate'] / 1000),
                    datetime.datetime.fromtimestamp(item['updateDate'] / 1000)])
        table_data.append(row)

    log_info("[*] File List")
    print(tabulate(table_data, headers=["File #.", "Type", "Path", "Size", "Create Date", "Update Date"]))

    down_thumb(table_data, response)


def down_thumb(table_data, response):
    log_info("[*] Select File #. to collect thumbnail (Exit: 0)")
    headers["Host"] = "thumb2.photo.mybox.naver.com"
    headers["Referer"] = "https://mybox.naver.com/"
    row = int(input())

    if 0 < row <= len(table_data):
        fn = "thumbnail_" + response[row - 1]['resourcePath'][1:]

        with open(fn, "wb") as f:
            url = urls['url_thumb'] + str(response[row - 1]['resourceNo']) + "?type=m740_390_2"
            print(url)
            f.write(requests.get(url, headers=headers).content)

        log_info("[*] Thumbnail Download Succeed: " + fn)
        print(tabulate([table_data[row - 1]],
                       headers=["File #.", "Type", "Path", "Size", "Create Date", "Update Date"]))
    else:
        log_info("[*] Invalid row number")

def file_data():
    table_data = []
    response = json.loads(requests.post(urls['url_list'], headers=headers, data=req_data).text)['result']['list']
    for i, item in enumerate(response):
        row = [i + 1]
        row.extend([item['resourceType'], item['resourcePath'], item['resourceSize'],
                    datetime.datetime.fromtimestamp(item['createDate'] / 1000),
                    datetime.datetime.fromtimestamp(item['updateDate'] / 1000)])

        table_data.append(row)

    log_info("[*] File List")
    print(tabulate(table_data, headers=["File #.", "Type", "Path", "Size", "Create Date", "Update Date"]))

    down_file(table_data, response)

def down_file(table_data, response):
    log_info("[*] Select File #. to collect data (Exit: 0)")
    headers["Host"] = headers["Referer"] = "api.mybox.naver.com"

    row = int(input())

    if 0 < row <= len(table_data):
        fn = response[row - 1]['resourcePath'][1:]

        with open(fn, "wb") as f:
            url = urls['url_data'] + str(response[row - 1]['resourceKey']) + "&NDriveSvcType=NHN%2FND-WEB%20Ver"
            f.write(requests.get(url, headers=headers).content)
            log_info("[*] File Data Download Succeed: " + fn)

        print(tabulate([table_data[row - 1]],
                       headers=["File #.", "Type", "Path", "Size", "Create Date", "Update Date"]))
    else:
        log_info("[*] Invalid row number")


if __name__ == "__main__":
    print(pyfiglet.figlet_format("NAVER MYBOX", font="isometric1"))

    log_info("[*] Naver Credentials")
    log_debug("[*] Enter NAVER ID")
    input_id = input()
    log_debug("[*] Enter NAVER PW")
    input_pw = input()

    creds = {
        "id": input_id,
        "pw": input_pw
    }

    try:
        with sync_playwright() as playwright:
            login(playwright, creds["id"], creds["pw"])
    except:
        log_warning("[*] User Authentication Failed")

    while 1:
        cowsay.cow(
            """
            0. Exit Script
            1. Show User Account & Service Information
            2. Show File List
            3. Download Thumbnail
            4. Download File data
            """)
        num = int(input())
        if num == 0:
            log_debug("[*] End Script...")
            exit(-1)
        if num == 1:
            log_debug("[*] Collecting User Resource Information...")
            user()
        if num == 2:
            log_debug("[*] Collecting File Resource Information...")
            file_list()
        if num == 3:
            log_debug("[*] Collecting File Thumbnail...")
            file_thumb()
        if num == 4:
            log_debug("[*] Collecting File Data...")
            file_data()
