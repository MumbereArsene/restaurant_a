import uuid

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


def _new_token() -> str:
    return uuid.uuid4().hex


class Table(models.Model):
    """Physical table; its qr_token is embedded in the printed QR code."""

    class Status(models.TextChoices):
        LIBRE = "libre", _("Libre")
        OCCUPEE = "occupee", _("Occupée")

    number = models.PositiveIntegerField(_("numéro"), unique=True)
    capacity = models.PositiveIntegerField(_("capacité"), default=4)
    qr_token = models.CharField(
        _("token QR"), max_length=64, unique=True, default=_new_token, editable=False
    )
    status = models.CharField(
        _("statut"), max_length=10, choices=Status.choices, default=Status.LIBRE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        verbose_name = _("table")

    def regenerate_token(self):
        """Invalidate the old QR code (e.g. if reprinted or compromised)."""
        self.qr_token = _new_token()
        self.save(update_fields=["qr_token"])

    def order_url(self, request) -> str:
        return request.build_absolute_uri(
            reverse("orders:menu", kwargs={"token": self.qr_token})
        )

    def __str__(self) -> str:
        return f"Table {self.number}"
