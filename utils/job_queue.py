"""
Job Queue Utilities
Background job processing with RQ (Redis Queue)
"""
import os
from redis import Redis
from rq import Queue, Connection, Worker
from rq.job import Job
from flask import current_app
import logging

logger = logging.getLogger(__name__)

# Global Redis connection (will be initialized in app context)
_redis_conn = None
_job_queue = None


def init_redis():
    """Initialize Redis connection"""
    global _redis_conn, _job_queue
    
    try:
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        _redis_conn = Redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        _redis_conn.ping()
        
        # Create default queue
        _job_queue = Queue('default', connection=_redis_conn)
        
        logger.info("Redis connection initialized successfully")
        return True
    except Exception as e:
        logger.warning(f"Redis not available: {e}. Background jobs will be disabled.")
        _redis_conn = None
        _job_queue = None
        return False


def get_queue(queue_name='default'):
    """
    Get a job queue
    
    Args:
        queue_name: Name of the queue (default: 'default')
    
    Returns:
        Queue object or None if Redis not available
    """
    global _redis_conn, _job_queue
    
    if not _redis_conn:
        if not init_redis():
            return None
    
    if queue_name == 'default':
        return _job_queue
    else:
        return Queue(queue_name, connection=_redis_conn)


def enqueue_job(func, *args, **kwargs):
    """
    Enqueue a job for background processing with priority support
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments (job_timeout, queue_name, priority, etc.)
    
    Returns:
        Job object or None if queue not available
    """
    queue_name = kwargs.pop('queue_name', 'default')
    job_timeout = kwargs.pop('job_timeout', '10m')
    priority = kwargs.pop('priority', 0)  # Default priority
    
    queue = get_queue(queue_name)
    if not queue:
        logger.warning("Job queue not available, executing synchronously")
        # Fallback to synchronous execution
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Error executing job synchronously: {e}")
            raise
    
    try:
        # Use priority queue if priority is set
        if priority != 0:
            from rq.queue import Queue
            # Create a priority queue by using queue name with priority
            priority_queue_name = f"{queue_name}_priority_{priority}"
            queue = Queue(priority_queue_name, connection=_redis_conn)
        
        job = queue.enqueue(
            func,
            *args,
            job_timeout=job_timeout,
            **kwargs
        )
        
        # Log job with priority information
        priority_info = f" (priority: {priority})" if priority != 0 else ""
        logger.info(f"Job {job.id} enqueued in queue '{queue_name}'{priority_info}")
        return job
    except Exception as e:
        logger.exception(f"Error enqueuing job: {e}")
        return None


def get_job(job_id):
    """
    Get a job by ID
    
    Args:
        job_id: Job ID
    
    Returns:
        Job object or None
    """
    try:
        return Job.fetch(job_id, connection=_redis_conn)
    except Exception:
        return None


def get_job_status(job_id):
    """
    Get job status
    
    Args:
        job_id: Job ID
    
    Returns:
        dict with status information
    """
    job = get_job(job_id)
    if not job:
        return {'status': 'not_found', 'error': 'Job not found'}
    
    status = {
        'id': job.id,
        'status': job.get_status(),
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'ended_at': job.ended_at.isoformat() if job.ended_at else None,
    }
    
    if job.is_finished:
        status['result'] = job.result
    elif job.is_failed:
        status['error'] = str(job.exc_info) if job.exc_info else 'Unknown error'
    
    return status


def cancel_job(job_id):
    """
    Cancel a job
    
    Args:
        job_id: Job ID
    
    Returns:
        True if cancelled, False otherwise
    """
    job = get_job(job_id)
    if not job:
        return False
    
    try:
        job.cancel()
        logger.info(f"Job {job_id} cancelled successfully")
        return True
    except Exception as e:
        logger.exception(f"Error cancelling job {job_id}: {e}")
        return False


def get_queue_stats(queue_name='default'):
    """
    Get statistics for a specific queue
    
    Args:
        queue_name: Name of the queue
    
    Returns:
        dict with queue statistics
    """
    queue = get_queue(queue_name)
    if not queue:
        return {'error': 'Queue not available'}
    
    try:
        from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
        
        return {
            'queue_name': queue_name,
            'pending': len(queue),
            'started': len(StartedJobRegistry(queue.name, connection=_redis_conn)),
            'finished': len(FinishedJobRegistry(queue.name, connection=_redis_conn)),
            'failed': len(FailedJobRegistry(queue.name, connection=_redis_conn)),
            'workers': len(Worker.all(connection=_redis_conn))
        }
    except Exception as e:
        logger.exception(f"Error getting queue stats: {e}")
        return {'error': str(e)}


def clear_queue(queue_name='default'):
    """
    Clear all jobs from a queue
    
    Args:
        queue_name: Name of the queue to clear
    
    Returns:
        True if cleared, False otherwise
    """
    queue = get_queue(queue_name)
    if not queue:
        return False
    
    try:
        queue.empty()
        logger.info(f"Queue '{queue_name}' cleared successfully")
        return True
    except Exception as e:
        logger.exception(f"Error clearing queue {queue_name}: {e}")
        return False


def get_failed_jobs(queue_name='default', limit=50):
    """
    Get failed jobs from a queue
    
    Args:
        queue_name: Name of the queue
        limit: Maximum number of jobs to return
    
    Returns:
        list of failed job info
    """
    try:
        from rq.registry import FailedJobRegistry
        registry = FailedJobRegistry(queue_name, connection=_redis_conn)
        
        failed_jobs = []
        for job_id in registry.get_job_ids(limit):
            job = Job.fetch(job_id, connection=_redis_conn)
            failed_jobs.append({
                'id': job.id,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'ended_at': job.ended_at.isoformat() if job.ended_at else None,
                'error': str(job.exc_info) if job.exc_info else 'Unknown error',
                'func_name': job.func_name
            })
        
        return failed_jobs
    except Exception as e:
        logger.exception(f"Error getting failed jobs: {e}")
        return []
