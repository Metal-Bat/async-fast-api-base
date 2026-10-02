"""Tests for media image validation and conversion."""

import io

import pytest
from PIL import Image

from apps.media.application.service import _to_webp
from utils.exceptions import InvalidImageException


def test_image_is_converted_to_webp() -> None:
    source = io.BytesIO()
    Image.new("RGB", (8, 6), "red").save(source, format="PNG")
    converted, width, height = _to_webp(source.getvalue())
    assert (width, height) == (8, 6)
    assert converted.startswith(b"RIFF") and b"WEBP" in converted[:16]


def test_webp_conversion_strips_source_metadata() -> None:
    source = io.BytesIO()
    image = Image.new("RGB", (8, 6), "blue")
    exif = image.getexif()
    exif[0x010E] = "private metadata"
    image.save(source, format="JPEG", exif=exif)

    converted, _, _ = _to_webp(source.getvalue())

    with Image.open(io.BytesIO(converted)) as stored:
        assert not stored.getexif()
        assert not ({"exif", "icc_profile", "xmp"} & stored.info.keys())


def test_invalid_image_is_rejected() -> None:
    with pytest.raises(InvalidImageException):
        _to_webp(b"not an image")
