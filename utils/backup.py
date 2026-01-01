"""
Database Backup Utility
Automated backup system for database
"""
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
import logging
from flask import current_app

logger = logging.getLogger(__name__)


class BackupService:
    """Service for creating database backups"""
    
    @staticmethod
    def create_backup(backup_dir='backups'):
        """
        Create a backup of the database
        
        Args:
            backup_dir: Directory to store backups (default: 'backups')
        
        Returns:
            dict with 'success', 'backup_path', and optional 'error'
        """
        try:
            # Get database URI from config
            db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if not db_uri:
                return {'success': False, 'error': 'Database URI not configured'}
            
            # Create backup directory
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Generate backup filename
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            
            # Handle different database types
            if db_uri.startswith('sqlite'):
                # SQLite backup
                db_path = db_uri.replace('sqlite:///', '')
                if not os.path.isabs(db_path):
                    # Relative path - find it
                    app_root = Path(current_app.root_path).parent
                    db_path = app_root / db_path
                
                backup_file = backup_path / f'leads_{timestamp}.db'
                shutil.copy2(db_path, backup_file)
                
                logger.info(f"SQLite backup created: {backup_file}")
                return {
                    'success': True,
                    'backup_path': str(backup_file),
                    'size': os.path.getsize(backup_file)
                }
            
            elif db_uri.startswith('postgresql'):
                # PostgreSQL backup using pg_dump
                import subprocess
                backup_file = backup_path / f'leads_{timestamp}.sql'
                
                # Extract connection details from URI
                # Format: postgresql://user:pass@host:port/dbname
                from urllib.parse import urlparse
                parsed = urlparse(db_uri)
                
                pg_dump_cmd = [
                    'pg_dump',
                    '-h', parsed.hostname or 'localhost',
                    '-p', str(parsed.port or 5432),
                    '-U', parsed.username or 'postgres',
                    '-d', parsed.path.lstrip('/'),
                    '-f', str(backup_file),
                    '--no-password'  # Use .pgpass file or PGPASSWORD env var
                ]
                
                # Set PGPASSWORD if password is in URI
                env = os.environ.copy()
                if parsed.password:
                    env['PGPASSWORD'] = parsed.password
                
                result = subprocess.run(
                    pg_dump_cmd,
                    env=env,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    logger.info(f"PostgreSQL backup created: {backup_file}")
                    return {
                        'success': True,
                        'backup_path': str(backup_file),
                        'size': os.path.getsize(backup_file)
                    }
                else:
                    error_msg = result.stderr or 'Unknown error'
                    logger.error(f"PostgreSQL backup failed: {error_msg}")
                    return {
                        'success': False,
                        'error': f'pg_dump failed: {error_msg}'
                    }
            
            else:
                return {
                    'success': False,
                    'error': f'Unsupported database type: {db_uri.split("://")[0]}'
                }
        
        except Exception as e:
            logger.exception("Error creating database backup")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def cleanup_old_backups(backup_dir='backups', keep_days=30):
        """
        Remove backups older than specified days
        
        Args:
            backup_dir: Directory containing backups
            keep_days: Number of days to keep backups (default: 30)
        
        Returns:
            dict with 'deleted_count' and 'freed_space'
        """
        try:
            backup_path = Path(backup_dir)
            if not backup_path.exists():
                return {'deleted_count': 0, 'freed_space': 0}
            
            cutoff_time = datetime.now(timezone.utc).timestamp() - (keep_days * 24 * 3600)
            deleted_count = 0
            freed_space = 0
            
            for backup_file in backup_path.glob('*.db'):
                if backup_file.stat().st_mtime < cutoff_time:
                    size = backup_file.stat().st_size
                    backup_file.unlink()
                    deleted_count += 1
                    freed_space += size
            
            for backup_file in backup_path.glob('*.sql'):
                if backup_file.stat().st_mtime < cutoff_time:
                    size = backup_file.stat().st_size
                    backup_file.unlink()
                    deleted_count += 1
                    freed_space += size
            
            logger.info(f"Cleaned up {deleted_count} old backups, freed {freed_space / 1024 / 1024:.2f} MB")
            return {
                'deleted_count': deleted_count,
                'freed_space': freed_space
            }
        
        except Exception as e:
            logger.exception("Error cleaning up old backups")
            return {
                'deleted_count': 0,
                'freed_space': 0,
                'error': str(e)
            }
    
    @staticmethod
    def list_backups(backup_dir='backups'):
        """
        List all available backups
        
        Args:
            backup_dir: Directory containing backups
        
        Returns:
            list of backup file info dicts
        """
        try:
            backup_path = Path(backup_dir)
            if not backup_path.exists():
                return []
            
            backups = []
            for backup_file in sorted(backup_path.glob('*.db'), reverse=True):
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'size': backup_file.stat().st_size,
                    'created': datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc).isoformat()
                })
            
            for backup_file in sorted(backup_path.glob('*.sql'), reverse=True):
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'size': backup_file.stat().st_size,
                    'created': datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc).isoformat()
                })
            
            return sorted(backups, key=lambda x: x['created'], reverse=True)
        
        except Exception as e:
            logger.exception("Error listing backups")
            return []
