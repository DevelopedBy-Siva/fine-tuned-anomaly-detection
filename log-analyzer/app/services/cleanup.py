# app/services/cleanup.py
from app.services.storage import (
    SessionLocal,
    Incident,
    Analysis,
    ActionLog,
    InvestigationRun,
)
import logging

logger = logging.getLogger(__name__)


def cleanup_all_data():
    """Empty incident-processing tables used for demos and local reset flows."""
    db = SessionLocal()

    try:
        db.query(ActionLog).delete()
        db.query(InvestigationRun).delete()
        db.query(Analysis).delete()
        db.query(Incident).delete()

        db.commit()
        logger.info("All incident-processing data deleted")

    except Exception as e:
        db.rollback()
        logger.error("Cleanup failed: %s", e)

    finally:
        db.close()
