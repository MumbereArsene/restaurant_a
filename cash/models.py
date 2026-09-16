from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class CashEntry(models.Model):
    """Cash movement: IN (order payments, manual income) or OUT (expenses)."""

    class Type(models.TextChoices):
        IN = "in", _("Entrée")
        OUT = "out", _("Sortie")

    type = models.CharField(_("type"), max_length=3, choices=Type.choices)
    amount = models.DecimalField(
        _("montant"),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    reason = models.CharField(_("motif"), max_length=255)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_entry",
        verbose_name=_("commande"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("créé par"),
    )
    created_at = models.DateTimeField(_("date"), auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("mouvement de caisse")
        verbose_name_plural = _("mouvements de caisse")
        indexes = [
            models.Index(fields=["created_at"], name="cash_cashen_created_b2a91e_idx"),
            models.Index(fields=["type"], name="cash_cashen_type_6d4c0a_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="cash_entry_amount_gte_0",
            ),
        ]

    def __str__(self) -> str:
        sign = "+" if self.type == self.Type.IN else "-"
        return f"{sign}{self.amount} — {self.reason}"


class CashClosure(models.Model):
    """End-of-shift / end-of-day cash drawer closure snapshot."""

    period_start = models.DateTimeField(_("début de période"))
    closed_at = models.DateTimeField(_("clôturée le"), auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cash_closures",
        verbose_name=_("clôturée par"),
    )
    total_in = models.DecimalField(_("total entrées"), max_digits=12, decimal_places=2)
    total_out = models.DecimalField(_("total sorties"), max_digits=12, decimal_places=2)
    expected_amount = models.DecimalField(_("montant attendu"), max_digits=12, decimal_places=2)
    counted_amount = models.DecimalField(_("montant compté"), max_digits=12, decimal_places=2)
    difference = models.DecimalField(_("écart"), max_digits=12, decimal_places=2)
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        ordering = ["-closed_at"]
        verbose_name = _("clôture de caisse")
        verbose_name_plural = _("clôtures de caisse")

    def __str__(self) -> str:
        return f"Clôture {self.closed_at:%d/%m/%Y %H:%M}"
