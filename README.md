# 📌 Project Purpose

가격비교 사이트 ‘다나와’에서 전자제품 데이터와 최저가를 자동 수집하는 파이프라인을 구현

‘노트북’, ‘데스크탑’, ‘모니터’ 제품 군의 데이터를 각각 300개씩 수집하고 DB에 담는다.

# 📌 Plan

`Docker-compose` 를 사용하여 컨테이너화 된 파이프라인 환경을 구축

- 자동화 툴 : Airflow, 메타데이터 DB 및 제품 데이터베이스 : Postgres
- 크롤링 코드를 Docker Image로 빌드하고 DockerOperator를 사용하여 Docker Image를 task로 병렬 실행, Dag 실행 시간을 단축

## Table Schema

- danawa.product
    
    
    | 컬럼 | Field | Type |  |
    | --- | --- | --- | --- |
    | 제품 id | id | Serial | PK |
    | 카테고리 | category | VARCAHR(50) | NOT NULL |
    | 상품 명 | prod_name | VARCHAR | NOT NULL |
    | 스펙 리스트 | spec_list | TEXT |  |
    | 리뷰 별점 | review_score | DOUBLE PRECISION |  |
    | 리뷰 수 | review_count | INT |  |
    | 상품 최저가 | lowest_price | INT |  |
    | 상품 이미지 링크 | prod_img | VARCHAR(500) |  |
    | 생성 타임스탬프 | created_at | TIMESTAMP |  |

## 크롤링 설계 전략

1. 크롤링 효율성을 위해 동적 Action이 필요한 경우에만 Selenium을 사용하고 HTML 파싱은 BS4를 사용
2. 코드 재사용성 및 공유의 용이성을 위해 Docker Image 빌드 및 Docker Compose만으로 개발 환경이 전부 펼쳐지도록 구성
3. 카테고리 별 크롤링 Task를 각각의 DockerOperator Task로 만들어 3개의 크롤링 Task를 동시 실행
    
    (직렬 수집 대비 3배 빠른 성능)
    
4. danawa_crawl_dag DAG를 실행하기만 하면 수집부터 DB 저장까지 자동으로 진행

![image.png](attachment:53472b94-c769-49a9-a396-39a636b24ab6:image.png)

# 📌 How to use

```bash
# danawa_crawling_project
docker build -t danawa_crawler:latest ./crawler

docker compose up -d

Airflow Web UI 접속 -> danawa_crawl_dan ON
#   (기본: http://localhost:8080 , 아이디/비번: airflow/airflow)
```

dag 실행 시에 3개의 컨테이너가 동시 생성, 병렬 실행 (종료 후 자동으로 사라짐)

![image.png](attachment:0d81bf09-7ed3-49cd-b35f-7a5a2eecdd9a:image.png)
