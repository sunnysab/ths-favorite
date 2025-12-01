"""兼容层: 提供向后兼容的导入入口。"""

from client import THSHttpApiClient
from models import THSFavorite, THSFavoriteGroup
from service import THSUserFavorite

__all__ = [
    "THSFavorite",
    "THSFavoriteGroup",
    "THSHttpApiClient",
    "THSUserFavorite",
]
