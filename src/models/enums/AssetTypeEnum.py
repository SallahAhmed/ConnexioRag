from enum import Enum

class AssetTypeEnum(str, Enum):
    FILE = "file"
    URL = "url"
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"