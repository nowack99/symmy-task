from django.db import models


class Product(models.Model):
    sku = models.CharField(max_length=64, primary_key=True)
    payload_hash = models.CharField(max_length=64, blank=True)
    remote_exists = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.sku
