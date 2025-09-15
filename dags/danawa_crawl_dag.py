from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from datetime import datetime

default_args = {"owner": "sewook", "retries": 1}

with DAG(
    dag_id="danawa_crawl_dag",
    default_args=default_args,
    description="다나와 사이트에서 노트북, 데스크탑, 모니터 카테고리를 크롤링하여 최저가 및 스펙 정보 수집",
    schedule_interval="@daily",
    start_date=datetime(2025, 9, 15),
    catchup=False,
) as dag:

    crawl_notebook = DockerOperator(
        task_id="crawl_notebook",
        image="danawa_crawler:latest",
        api_version="auto",
        auto_remove=True,
        command=None,
        docker_url="unix://var/run/docker.sock",
        network_mode="danawa_crawling_default",
        environment={
            "CATEGORY": "notebook",
            "URL": "https://prod.danawa.com/list/?cate=112758",
            "PGHOST": "postgres",
            "PGPORT": "5432",
            "PGDATABASE": "danawa",
            "PGUSER": "airflow",
            "PGPASSWORD": "airflow",
        },
    )

    crawl_desktop = DockerOperator(
        task_id="crawl_desktop",
        image="danawa_crawler:latest",
        api_version="auto",
        auto_remove=True,
        command=None,
        docker_url="unix://var/run/docker.sock",
        network_mode="danawa_crawling_default",
        environment={
            "CATEGORY": "desktop",
            "URL": "https://prod.danawa.com/list/?cate=112756",
            "PGHOST": "postgres",
            "PGPORT": "5432",
            "PGDATABASE": "danawa",
            "PGUSER": "airflow",
            "PGPASSWORD": "airflow",
        },
    )

    crawl_monitor = DockerOperator(
        task_id="crawl_monitor",
        image="danawa_crawler:latest",
        api_version="auto",
        auto_remove=True,
        command=None,
        docker_url="unix://var/run/docker.sock",
        network_mode="danawa_crawling_default",
        environment={
            "CATEGORY": "monitor",
            "URL": "https://prod.danawa.com/list/?cate=112757",
            "PGHOST": "postgres",
            "PGPORT": "5432",
            "PGDATABASE": "danawa",
            "PGUSER": "airflow",
            "PGPASSWORD": "airflow",
        },
    )

    # 병렬 실행
    [crawl_notebook, crawl_desktop, crawl_monitor]
