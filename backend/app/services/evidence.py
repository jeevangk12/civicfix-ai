from io import BytesIO
from urllib.parse import urlsplit

from cloudinary import uploader
from cloudinary.exceptions import Error
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import Settings

FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class InvalidImage(Exception):
    pass


class UploadUnavailable(Exception):
    pass


def clean_image(contents: bytes, declared_type: str | None) -> bytes:
    try:
        with Image.open(BytesIO(contents), formats=list(FORMATS)) as source:
            if FORMATS.get(source.format) != declared_type or source.width * source.height > 16_000_000:
                raise InvalidImage("Choose a JPEG, PNG, or WebP photo up to 16 megapixels.")
            if getattr(source, "is_animated", False):
                raise InvalidImage("Choose a still photo.")
            source.verify()
        with Image.open(BytesIO(contents), formats=list(FORMATS)) as source:
            upright = ImageOps.exif_transpose(source).convert("RGB")
            upright.thumbnail((2048, 2048))
            clean = Image.new("RGB", upright.size)
            clean.paste(upright)
            with BytesIO() as result:
                clean.save(result, format="JPEG", quality=86)
                return result.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise InvalidImage("Choose a valid JPEG, PNG, or WebP photo.") from None


class CloudinaryEvidence:
    def __init__(self, settings: Settings):
        self.options = {
            "cloud_name": settings.cloudinary_cloud_name,
            "api_key": settings.cloudinary_api_key.get_secret_value(),
            "api_secret": settings.cloudinary_api_secret.get_secret_value(),
        }

    def upload(self, photo: bytes, key: str) -> str:
        if not all(self.options.values()):
            raise UploadUnavailable()
        try:
            result = uploader.upload(
                BytesIO(photo), **self.options, public_id=key, resource_type="image",
                type="authenticated", overwrite=False, timeout=10,
            )
            url = result.get("secure_url")
            if (
                result.get("public_id") != key or result.get("type") != "authenticated"
                or result.get("resource_type") != "image" or not isinstance(url, str) or urlsplit(url).scheme != "https"
            ):
                raise UploadUnavailable()
            return url
        except (Error, OSError, ValueError):
            raise UploadUnavailable() from None

    def remove(self, key: str) -> None:
        try:
            uploader.destroy(key, **self.options, resource_type="image", type="authenticated", timeout=10)
        except (Error, OSError, ValueError):
            raise UploadUnavailable() from None
