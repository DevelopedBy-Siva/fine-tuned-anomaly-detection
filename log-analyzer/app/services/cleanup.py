# app/services/cleanup.py
from app.services.storage import SessionLocal, Incident, Analysis
import logging

logger = logging.getLogger(__name__)


def cleanup_all_data():
    """Empty the incidents and analyses tables"""
    db = SessionLocal()

    try:
        db.query(Analysis).delete()
        db.query(Incident).delete()

        db.commit()
        logger.info("All incidents and analyses deleted")

    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup failed: {str(e)}")

    finally:
        db.close()
