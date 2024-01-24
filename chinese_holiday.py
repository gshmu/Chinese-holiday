# !/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   parse_holiday.py
@Time    :   2019/12/26 09:21:37
@Author  :   Chariothy
@Contact :   chariothy@gmail.com
@Desc    :   从国务院官网解析节假日信息
@Updater :   gshmu
@Upate_at:   2024/01/23
"""

import datetime as dt
import json
import os
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

HOLIDAY_DATA_PATH = os.path.join(os.getcwd(), "holiday.json")
P_LINE_FIX = re.compile(r"[(（][^)）]+.")


def get_holiday_data(year, force_refresh=False):
    """加载节假日数据，没有则去国务院网站解析

    Keyword Arguments:
        year {str} -- 四位数字年份
        force_refresh {bool} -- 是否强制加载 (default: {False})

    Returns:
        array -- 节假日数组，每行格式为：(from_date, to_date, need_work)
                 如： ('2020-1-1', '2020-1-1', False) 表示2020-1-1放假
                     ('2020-10-1', '2020-10-8', False) 表示2020-10-1到2020-10-8放假
                     ('2020-1-19', '2020-1-19', True) 表示2020-1-19补班
    """
    year = str(year)
    holiday_data = None
    if os.path.exists(HOLIDAY_DATA_PATH):
        all_holiday = read_all_holiday()
        holiday_data = all_holiday.get(str(year), None)
    if holiday_data is None or force_refresh:
        url = search_notice_url(year)
        parsed_year, holiday_data = parse_holiday_info(url)
        if parsed_year != year or len(holiday_data) == 0:
            raise Exception("Can not parse holiday info from {}.".format(url))
        all_holiday[year] = holiday_data
        save_all_holiday(all_holiday)
    return holiday_data


def save_all_holiday(all_holiday):
    with open(HOLIDAY_DATA_PATH, "w", encoding="utf8") as fp:
        json.dump(all_holiday, fp, indent=2, ensure_ascii=False)


def read_all_holiday():
    with open(HOLIDAY_DATA_PATH, "r", encoding="utf8") as fp:
        try:
            all_holiday = json.load(fp)
        except Exception:
            all_holiday = {}
    if not isinstance(all_holiday, dict):
        return {}
    return all_holiday


def get_delta():
    result = {True: [], False: []}
    for year, data in read_all_holiday().items():
        for start, end, work in data:
            start = datetime.strptime(start, "%Y-%m-%d")
            days = (datetime.strptime(end, "%Y-%m-%d") - start).days + 1
            for delta in range(days):
                day = (start + timedelta(days=delta)).date()
                if (not work and day.weekday() < 5) or (work and day.weekday() >= 5):
                    result[work].append(day)
    return result


def is_holiday(date_time):
    """判断日期是否是节假日（包含正常周末和法定节假日）

    Arguments:
        date_time {str} -- 日期，格式: yyyy-mm-dd

    Returns:
        bool -- 是否为假日
    """
    if type(date_time) == str:
        date_time = datetime.strptime(date_time, "%Y-%m-%d")
    assert type(date_time) == datetime

    year = date_time.strftime("%Y")
    holiday_lines = get_holiday_data(year)
    assert type(holiday_lines) == list and len(holiday_lines) > 0
    for holiday_line in holiday_lines:
        from_date, to_date, work = holiday_line
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
        to_date = datetime.strptime(to_date, "%Y-%m-%d")
        if date_time >= from_date and date_time <= to_date:
            return not work
    if date_time.weekday() in (5, 6):
        return True
    else:
        return False
    return True


def get_latest_workday(begin=datetime.today()):
    """获取最近的一个工作日

    Keyword Arguments:
        begin {datetime} -- 开始日 (default: {datetime.today()})

    Returns:
        datetime -- 最近的一个工作日
    """
    start = begin
    while True:
        if not is_holiday(start.strftime("%Y-%m-%d")):
            break
        start = start - timedelta(days=1)
    return start


def search_notice_url(year):
    """从国务院网站查询节假日公告链接
    Arguments:
        year {str} -- 四位数字的年份
    Returns:
        str -- 公告链接
    Raises:
        Exception: 解析搜索结果出错
    """
    title = "国务院办公厅关于{}年部分节假日安排的通知".format(year)

    parma = {
        "code": "17da70961a7",
        "historySearchWords": [],
        "dataTypeId": "15",
        "orderBy": "time",
        "searchBy": "title",
        "appendixType": "",
        "granularity": "CUSTOM",
        "trackTotalHits": True,
        "beginDateTime": "",  # 1664553600000,
        "endDateTime": "",  # 1706716799999,
        "isSearchForced": 0,
        "filters": [],
        "pageNo": 1,
        "pageSize": 10,
        "customFilter": {"operator": "and", "properties": []},
        "searchWord": title,
    }

    headers = {
        "Athenaappkey": "dHb0Wd5a0SFiUGDAfJ74cjx9bhGY2bNS3thUj8%2FXn4LLllTj3EviO5eoqvqj2XOOsir9AI61gTIYF63ljt%2FeVnJrAhr9bi0iPfXvVAQfndmTTb8fTrw%2F243wTSz9XIXO3WJmNbdTuU%2Bd%2Bk7b4wOV5F7CRJgqRfI3u4AKhukLPMM%3D",
        "Athenaappname": "%E5%9B%BD%E7%BD%91%E6%90%9C%E7%B4%A2"
    }

    url = "https://sousuoht.www.gov.cn/athena/forward/2B22E8E39E850E17F95A016A74FCB6B673336FA8B6FEC0E2955907EF9AEE06BE"
    response = requests.post(url, json=parma, headers=headers)

    try:
        page_content = response.json()
        for item in page_content['result']['data']['middle']['list']:
            if item['title_no_tag'] == title:
                return item["url"]
    except Exception as ex:
        pass
    return None


def decode_response_content(response):
    """当无法从网页预测出编码格式时，为网页内容解码

    Arguments:
        response {} -- 网页响应

    Returns:
        str -- 解码后的内容
    """
    page_content = response.content
    if response.encoding == "ISO-8859-1":
        encodings = requests.utils.get_encodings_from_content(response.text)
        if encodings:
            encoding = encodings[0]
        else:
            encoding = response.apparent_encoding
        page_content = response.content.decode(encoding, "replace")  # 如果设置为replace，则会用?取代非法字符；
    return page_content


def fix_line(line):
    return P_LINE_FIX.sub("", line)


def parse_holiday_info(url):
    """从国务院公告链接中解析节假日信息

    Arguments:
        url {str} -- 国务院节假日公告链接

    Raises:
        Exception: 公告内容非预期
    """
    response = requests.get(url, stream=True)
    page_content = decode_response_content(response)
    soup = BeautifulSoup(page_content, features="html.parser")
    text = soup.find(id="UCAP-CONTENT").get_text()

    holiday_lines = text.split()
    holiday_data = []

    match = re.match(r"国务院办公厅关于(\d{4})年", "".join(holiday_lines))
    if match:
        year = match.group(1)
    else:
        raise Exception("Wrong message: " + text)

    reg_holiday_occur = re.compile(
        r"""
((?:\d{4}年)?\d{1,2}月\d{1,2}日)                #开始日
(?:至((?:\d{4}年)?(?:\d{1,2}月)?\d{1,2}日))?    #结束日，可能没有
放假""",
        re.VERBOSE,
    )
    for holiday_line in holiday_lines:
        holiday_line = fix_line(holiday_line)
        for holiday_occur in reg_holiday_occur.finditer(holiday_line):
            first_holiday, last_holiday, count_day = holiday_occur.groups()
            if count_day is None:
                count_day = "1"
            if "年" not in first_holiday:
                first_holiday = year + "年" + first_holiday

            first_holiday = datetime.strptime(first_holiday, "%Y年%m月%d日")
            last_holiday = first_holiday + dt.timedelta(days=int(count_day) - 1)
            holiday_data.append((first_holiday.strftime("%Y-%m-%d"), last_holiday.strftime("%Y-%m-%d"), False))

        for workday_occur in re.finditer(r'((?:(?:(?:\d{4}年)?\d{1,2}月)?\d{1,2}日、?)+)上班。', holiday_line):
            work_str = workday_occur.group(1)
            workdays = re.findall(r"(?:(?:\d{4}年)?\d{1,2}月|(?<=、))\d{1,2}日", work_str)
            before_workday = ""
            for workday in workdays:
                if "月" not in workday:
                    workday = before_workday[:before_workday.index("月")+1] + workday
                if "年" not in workday:
                    workday = year + "年" + workday
                before_workday = workday
                workday = datetime.strptime(workday, "%Y年%m月%d日").strftime("%Y-%m-%d")
                holiday_data.append((workday, workday, True))
    return (year, holiday_data)


if __name__ == "__main__":
    all_holiday = []
    for year in range(2010, 2024 + 1):
        notice_url = search_notice_url(year)
        if not notice_url:
            print(f"search url fail: {year=}")
            continue
        year_holiday = parse_holiday_info(notice_url)
        all_holiday.append(year_holiday)
    save_all_holiday(dict(all_holiday))

    print(get_delta())
