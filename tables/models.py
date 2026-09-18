import uuid

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


def _new_token() -> str:
    return uuid.uuid4().hex


class Table(models.Model):
    """Physical table. public_code is typed by guests and waiters (not a QR scan)."""

    class Status(models.TextChoices):
        LIBRE = "libre", _("Libre")
        OCCUPEE = "occupee", _("Occupée")

    number = models.PositiveIntegerField(_("numéro"), unique=True)
    capacity = models.PositiveIntegerField(_("capacité"), default=4)
    qr_token = models.CharField(
        _("identifiant interne"),
        max_length=64,
        unique=True,
        default=_new_token,
        editable=False,
    )
    public_code = models.CharField(
        _("code table"),
        max_length=8,
        unique=True,
        blank=True,
        help_text=_("Code court permanent saisi par le client et le serveur."),
    )
    status = models.CharField(
        _("statut"), max_length=10, choices=Status.choices, default=Status.LIBRE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        verbose_name = _("table")

    def _code_is_taken(self, code: str) -> bool:
        qs = Table.objects.filter(public_code=code)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            return True
        from orders.models import Order

        return Order.objects.filter(invoice_code=code).exists()

    def save(self, *args, **kwargs):
        if not self.public_code:
            from .codes import generate_unique_code

            self.public_code = generate_unique_code(is_taken=self._code_is_taken)
        super().save(*args, **kwargs)

    def occupy(self):
        if self.status != self.Status.OCCUPEE:
            self.status = self.Status.OCCUPEE
            self.save(update_fields=["status"])

    def release_if_idle(self) -> bool:
        """Set LIBRE when no open (unpaid, non-cancelled) orders remain."""
        from orders.models import Order

        if self.orders.filter(status__in=Order.OPEN_STATUSES).exists():
            return False
        if self.status != self.Status.LIBRE:
            self.status = self.Status.LIBRE
            self.save(update_fields=["status"])
        return True

    def has_open_orders(self) -> bool:
        from orders.models import Order

        return self.orders.filter(status__in=Order.OPEN_STATUSES).exists()

    def regenerate_token(self):
        """Issue a new public table code (printed cards must be updated)."""
        from .codes import generate_unique_code

        self.public_code = generate_unique_code(is_taken=self._code_is_taken)
        self.save(update_fields=["public_code"])

    def order_url(self, request) -> str:
        return request.build_absolute_uri(
            reverse("orders:menu", kwargs={"token": self.public_code})
        )

    def __str__(self) -> str:
        return f"Table {self.number} ({self.public_code})"
