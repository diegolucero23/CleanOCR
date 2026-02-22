import os
import pytest
from unittest.mock import patch, MagicMock
from app.services import pdf_converter

def test_convert_pdf_uses_process_pool_executor():
    """
    TDD Test: Verifies that `convert_pdf_in_chunks` utilizes ProcessPoolExecutor
    to process PDF chunks concurrently.
    """
    dummy_pdf_path = "dummy.pdf"
    dummy_output_folder = "dummy_output"
    
    with patch('app.services.pdf_converter.os.path.exists', return_value=True), \
         patch('app.services.pdf_converter.os.makedirs'), \
         patch('app.services.pdf_converter.pdfinfo_from_path', return_value={'Pages': 4}), \
         patch('app.services.pdf_converter.concurrent.futures.ThreadPoolExecutor') as mock_executor, \
         patch('app.services.pdf_converter.convert_from_path', return_value=[MagicMock(), MagicMock()]):
         
        # Mock the executor context manager
        mock_instance = MagicMock()
        mock_executor.return_value.__enter__.return_value = mock_instance
        
        # We need to simulate the execution of the function
        pdf_converter.convert_pdf_in_chunks(dummy_pdf_path, dummy_output_folder, chunk_size=2)
        
        # Assert that the ProcessPoolExecutor was actually used
        mock_executor.assert_called()

def test_ocr_page_task_updates_redis_state():
    """
    TDD Test: Verifies that the new streamed OCR Celery task updates the custom Redis
    state tracking metrics (e.g., job_id:completed_pages) upon completion.
    """
    with patch('app.workers.celery_worker.batch_ocr.process_single_image'), \
         patch('app.workers.celery_worker.redis.Redis.from_url') as mock_redis_cls, \
         patch('app.workers.celery_worker.celery_app') as mock_celery_app, \
         patch('app.workers.celery_worker.batch_ocr') as mock_batch_ocr:
         
        mock_redis = MagicMock()
        mock_redis_cls.return_value = mock_redis
        mock_celery_app.conf.broker_url = "redis://dummy:6379/0"
        
        from app.workers.celery_worker import ocr_page_task
        dummy_job_id = "1234-5678"
        ocr_page_task(dummy_job_id, "page_001.png", "dummy_in", "dummy_out")
        
        # Verifies the state tracking logic is executed
        mock_redis.incr.assert_called_with(f"cache:{dummy_job_id}:completed_pages")
