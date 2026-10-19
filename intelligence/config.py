"""Business rules: adjust these thresholds and weights deliberately."""
from pathlib import Path
import os

DB_PATH = Path(os.environ.get('RD_DATABASE_PATH', str(Path(__file__).resolve().parents[1] / 'data' / 'intelligence.sqlite3')))
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_ROWS = 100_000
MARKETPLACES = ['Amazon US', 'Etsy', 'TikTok Shop US', 'eBay']
STATUSES = ['New', 'To Research', 'Researching', 'Ready for Sampling', 'Sampling', 'Testing', 'Approved for Launch', 'Launched', 'Rejected', 'Archived']
WEIGHTS = {'sales_signal': 20, 'consistency': 20, 'differentiation': 15, 'production_fit': 15, 'cost_coverage': 10, 'evidence': 10, 'risk_readiness': 10}
MIN_UNITS = 10
MIN_ACTIVE_DAYS = 5
TREND_WINDOW_DAYS = 30
GROWTH_THRESHOLD = 0.25
DECLINE_THRESHOLD = -0.25

SIGNAL_FULL_UNITS = 50
CONSISTENCY_FULL_DAYS = 20
CONFIDENCE_FULL_DAYS = 30
SEASONAL_PEAK_RATIO = 2.0
SEASONAL_MIN_DAYS_PER_MONTH = 5
