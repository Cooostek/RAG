"""
Тут запускается планировщик задач. те ->
Контейнер scheduler стартует.
Выполняется job():
   проверяется доступность Milvus (до 240 секунд);
   запускается пайплайн индексации (run_full_pipeline);
   если FORCE_REINDEX=true, происходит полная переиндексация.
Планировщик переходит в режим ожидания.
Через 24 часа снова запускается job() (с теми же проверками и логикой).
Цикл повторяется бесконечно, пока контейнер не будет остановлен.
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from pymilvus import connections, utility
import time
import os

from app.ingestion.pipeline import run_full_pipeline
from app.core.logger import setup_logger
from app.core.config import settings

#Создаёт логгер с именем scheduler
#все сообщения с таким тегом
logger = setup_logger("scheduler")

def wait_for_milvus(timeout_sec: int = 180):
    """
    Ждем, пока Milvus поднимется и начнет отвечать.
    """
    started = time.time()
    while True:
        try:
            #проверяет доступность, запрашивая список коллекций
            connections.connect("default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
            _ = utility.list_collections()
            logger.info("Milvus доступен")
            return
        except Exception as e:
            if time.time() - started > timeout_sec:
                logger.exception("Milvus не поднялся за таймаут")
                raise
            logger.info(f"Жду Milvus... ({e})")
            time.sleep(2)

def job():
    #Проверяет переменную окружения
    force_env = os.getenv("FORCE_REINDEX", "false").lower() in ("1", "true", "yes")
    logger.info(f"Плановый запуск ingestion pipeline... FORCE_REINDEX={force_env}")

    try:
        wait_for_milvus(timeout_sec=240)
        # основной пайплайн индексации (те последовательную обработку документов от загрузки до выгрузку в ВБД)
        result = run_full_pipeline(force=force_env)
        logger.info(f"Pipeline result: {result}")
    except Exception:
        logger.exception("Pipeline error (stacktrace)")

if __name__ == "__main__":
    scheduler = BlockingScheduler()

    # Первый запуск сразу при старте контейнера
    job()

    # Потом раз в 24 часа
    scheduler.add_job(
        job,
        trigger="interval",
        hours=24,
        id="ingestion_job",
        max_instances=1,
        coalesce=True
    )
    scheduler.start()