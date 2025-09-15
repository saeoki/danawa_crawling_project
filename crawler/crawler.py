#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass, asdict
from typing import List

import re
import sys
import os
import time
import psycopg2
from psycopg2.extras import execute_values
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException

import logging
# danawa_crawler라는 태그가 달린 로거
logger = logging.getLogger("danawa_crawler")
# 핸들러 없는 경우(ex Airflow 아닌 로컬 실행) 간단한 콘솔 출력
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


# 핵심 모델 데이터클래스
@dataclass
class Product:
    prod_name: str
    spec_list: str
    review_score: float
    review_count: int
    lowest_price: int
    prod_img: str


# 유틸
def txt(el):
    return el.get_text(" ", strip=True) if el else ""

def to_int(s):
    s = txt(s) if hasattr(s, "get_text") else (s or "")
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else 0

def abs_img(src):
    if not src:
        return ""
    return "https:" + src if src.startswith("//") else src


# DB 저장
def save_to_postgres(category: str, items: List[Product]):
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST", "postgres"),
            # host='localhost', # for test
            port=int(os.getenv("PGPORT", 5432)),
            dbname=os.getenv("PGDATABASE", "danawa"),
            user=os.getenv("PGUSER", "airflow"),
            password=os.getenv("PGPASSWORD", "airflow"),
        )
        cur = conn.cursor()

        records = [
            (
                category,
                it.prod_name,
                it.spec_list,
                it.review_score,
                it.review_count,
                it.lowest_price,
                it.prod_img,
            )
            for it in items
        ]

        sql = """
        INSERT INTO product
            (category, prod_name, spec_list, review_score, review_count, lowest_price, prod_img)
        VALUES %s
        ON CONFLICT (category, prod_name) DO UPDATE SET
            spec_list = EXCLUDED.spec_list,
            review_score = EXCLUDED.review_score,
            review_count = EXCLUDED.review_count,
            lowest_price = EXCLUDED.lowest_price,
            prod_img = EXCLUDED.prod_img;
        """

        execute_values(cur, sql, records)
        conn.commit()
        logger.info("[DB] Inserted %d records into product table.", len(records))

    except Exception as e:
        logger.exception("[DB ERROR] %s", e)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


# 드라이버
def build_driver():
    opt = Options()
    opt.add_argument("--headless=new")
    opt.add_argument("--disable-gpu")
    opt.add_argument("--disable-3d-apis")
    opt.add_argument("--disable-webgl")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--window-size=1400,2000")
    opt.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    d = webdriver.Chrome(options=opt)
    d.implicitly_wait(5)
    return d


# HTML DOM구조 파싱
def parse_list_html(html: str) -> List[Product]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Product] = []

    for li in soup.select("ul.product_list > li.prod_item"):
        # 이름
        name_a = li.select_one(".prod_info .prod_name a[name='productName']")
        prod_name = txt(name_a)

        # 스펙: 펼침(.spec-box--full .spec_list) 우선, 없으면 접힘(.spec-box .spec_list)
        spec_full = li.select_one(".spec-box--full .spec_list")
        spec_fold = li.select_one(".spec-box .spec_list")
        spec_list = txt(spec_full or spec_fold)

        # 리뷰 별점/수
        score_el = li.select_one(".prod_sub_info .text__score")
        review_score = float(score_el.text.strip()) if score_el else 0.0

        review_count = to_int(li.select_one(".prod_sub_info .text__number"))

        # 최저가
        lowest_price = to_int(li.select_one(".prod_pricelist .price_sect strong"))

        # 이미지
        img = li.select_one(".thumb_image img")
        prod_img = abs_img(img.get("src") if img else "")

        if prod_name:
            out.append(Product(prod_name, spec_list, review_score, review_count, lowest_price, prod_img))
    return out


# 페이지 전환(번호 클릭) + 리스트 교체 감지
def wait_list_present(driver):
    WebDriverWait(driver, 12).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.product_list > li.prod_item"))
    )

def first_item_id(driver):
    try:
        el = driver.find_elements(By.CSS_SELECTOR, "ul.product_list > li.prod_item")[0]
        return el.get_attribute("id") or el.text  # id가 확실하면 그걸로
    except Exception:
        return None

def click_page(driver, page_num):
    before = first_item_id(driver)

    # 페이지네이션은 하단에 있으므로 하단으로 스크롤
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.4)

    try:
        # number_wrap 안의 page_num 텍스트를 가진 a.num 버튼만 정확히 지정
        target = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//div[@class='number_wrap']//a[normalize-space(text())='{page_num}']")
            )
        )
        try:
            target.click()
        except (ElementClickInterceptedException, StaleElementReferenceException):
            driver.execute_script("arguments[0].click();", target)
    except TimeoutException:
        return False

    # 리스트 교체 대기: 첫 li의 식별자(id/text)가 바뀌었는지 확인
    try:
        WebDriverWait(driver, 12).until(
            lambda d: first_item_id(d) not in (None, before)
        )
    except TimeoutException:
        # 최소한 리스트 존재는 보장
        try:
            wait_list_present(driver)
        except TimeoutException:
            return False

    return True


# 카테고리 별 크롤링 실행
def crawl_category(url: str, max_pages: int = 2) -> List[Product]:
    d = build_driver()
    try:
        d.get(url)
        wait_list_present(d)

        all_items: List[Product] = []
        # p1
        all_items.extend(parse_list_html(d.page_source))

        # p2부터..
        for p in range(2, max_pages + 1):
            if not click_page(d, p):
                break
            wait_list_present(d)
            all_items.extend(parse_list_html(d.page_source))

        # 상한 자르기
        return all_items[: max_pages * 30]
    finally: 
        d.quit()


# 메인 실행부
if __name__ == "__main__":
    category = os.getenv("CATEGORY", "notebook")
    url = os.getenv("URL")

    # # for test
    # category = "notebook"
    # url = "http://prod.danawa.com/list/?cate=112758"
    if not url:
        logger.error("!!URL is required")
        sys.exit(1)

    logger.info("Crawling category=%s, url=%s", category, url)
    data = crawl_category(url, max_pages=10)
    logger.info("Crawled %d items", len(data))

    save_to_postgres(category, data)
    logger.info("[DONE]")
