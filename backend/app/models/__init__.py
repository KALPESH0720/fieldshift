"""ORM model exports; importing these registers every table on ``Base.metadata``."""

from app.db.base import Base
from app.models.alert import Alert
from app.models.crop_record import CropRecord
from app.models.crop_rule import CropRule, CropRuleAudit, CropRuleReview
from app.models.farmer import Farmer
from app.models.farmer_preferences import FarmerPreferences
from app.models.group import Group
from app.models.input_dealer import InputDealer
from app.models.market_price import MarketPrice, MinimumSupportPrice
from app.models.pest_host_rule import PestHostRule
from app.models.plot import Plot
from app.models.recommendation import RecommendationOutcome, RecommendationRun
from app.models.season import Season
from app.models.satellite_job import SatelliteJob
from app.models.soil_test import SoilTest
from app.models.soil_card_upload import SoilCardUpload
from app.models.weather_snapshot import WeatherSnapshot
from app.models.warehouse import Warehouse
from app.models.sync import SyncChange, SyncOperationLog

__all__ = ["Base", "Farmer", "FarmerPreferences", "Plot", "Season", "CropRecord", "CropRule", "CropRuleReview", "CropRuleAudit", "SoilTest", "SoilCardUpload", "WeatherSnapshot", "SatelliteJob", "MarketPrice", "MinimumSupportPrice", "PestHostRule", "Alert", "SyncChange", "SyncOperationLog", "Group", "InputDealer", "Warehouse", "RecommendationRun", "RecommendationOutcome"]
