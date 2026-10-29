
import os
import random
import re
import string

from django.utils.text import slugify


def random_string_generator(size=10, chars=string.ascii_lowercase + string.digits):
    """Generate a random string of the requested length."""
    return "".join(random.choice(chars) for _ in range(size))


def unique_key_generator(instance, size=32):
    """Generate a key that is not already used by another instance."""
    model_class = instance.__class__

    while True:
        new_key = random_string_generator(size=size)
        if not model_class.objects.filter(key=new_key).exists():
            return new_key


def unique_order_id_generator(instance):
    """Generate a unique order ID."""
    model_class = instance.__class__

    while True:
        new_order_id = random_string_generator(size=12).upper()
        if not model_class.objects.filter(order_id=new_order_id).exists():
            return new_order_id


def unique_slug_generator(instance, new_slug=None):
    """Generate a unique slug for a model with a slug field."""
    slug_field = instance._meta.get_field("slug")
    max_length = slug_field.max_length

    source = (
        getattr(instance, "title", None)
        or getattr(instance, "name", None)
        or str(instance)
    )

    base_slug = slugify(source) or "item"
    candidate = new_slug or base_slug
    candidate = candidate[:max_length].strip("-") or "item"

    model_class = instance.__class__
    queryset = model_class.objects.filter(slug=candidate)

    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    if not queryset.exists():
        return candidate

    suffix = random_string_generator(size=6)
    suffix_length = len(suffix) + 1
    shortened_base = base_slug[:max_length - suffix_length].strip("-")
    candidate = f"{shortened_base}-{suffix}"

    return unique_slug_generator(instance, new_slug=candidate)


def get_filename(path):
    """Return the filename portion of a path."""
    return os.path.basename(path)


class AWSDownload:
    """Generate temporary download URLs for objects stored in AWS S3."""

    def __init__(self, access_key, secret_key, bucket, region, *args, **kwargs):
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        super().__init__(*args, **kwargs)

    @property
    def expires(self):
        from django.conf import settings
        return getattr(settings, "AWS_DOWNLOAD_EXPIRE", 5000)

    def s3connect(self):
        # Import the legacy AWS dependency only when S3 is actually used.
        import boto
        from boto.s3.connection import OrdinaryCallingFormat

        return boto.s3.connect_to_region(
            self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            is_secure=True,
            calling_format=OrdinaryCallingFormat(),
        )

    def get_bucket(self):
        return self.s3connect().get_bucket(self.bucket)

    def get_key(self, path):
        return self.get_bucket().get_key(path)

    def get_filename(self, path, new_filename=None):
        current_filename = os.path.basename(path)

        if new_filename is None:
            return current_filename

        _, extension = os.path.splitext(current_filename)
        safe_name = re.sub(r"[^A-Za-z0-9#]+", "-", new_filename)
        return safe_name + extension

    def generate_url(self, path, download=True, new_filename=None):
        aws_object = self.get_key(path)

        if not aws_object:
            return None

        headers = None
        if download:
            filename = self.get_filename(path, new_filename=new_filename)
            headers = {
                "response-content-type": "application/force-download",
                "response-content-disposition": f'attachment;filename="{filename}"',
            }

        return aws_object.generate_url(
            response_headers=headers,
            expires_in=self.expires,
            method="GET",
        )