from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Order(models.Model):
    class Status(models.TextChoices):
        EN_ATTENTE = "en_attente", _("En attente")
        EN_PREPARATION = "en_preparation", _("En préparation")
        PRETE = "prete", _("Prête")
        SERVIE = "servie", _("Servie")
        PAYEE = "payee", _("Payée")
        ANNULEE = "annulee", _("Annulée")

    table = models.ForeignKey(
        "tables.Table", on_delete=models.PROTECT, related_name="orders", verbose_name=_("table")
    )
    status = models.CharField(
        _("statut"), max_length=20, choices=Status.choices, default=Status.EN_ATTENTE
    )
    total = models.DecimalField(_("total"), max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(
        _("remise"), max_digits=12, decimal_places=2, default=0
    )
    discount_reason = models.CharField(_("motif de remise"), max_length=255, blank=True)
    discount_status = models.CharField(
        _("statut remise"),
        max_length=20,
        choices=[
            ("none", _("Aucune")),
            ("pending", _("En attente")),
            ("approved", _("Approuvée")),
            ("rejected", _("Refusée")),
        ],
        default="none",
    )
    discount_requested_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discount_requests",
        verbose_name=_("remise demandée par"),
    )
    discount_approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discount_approvals",
        verbose_name=_("remise validée par"),
    )
    note = models.TextField(_("note"), blank=True)
    created_at = models.DateTimeField(_("créée le"), auto_now_add=True)
    paid_at = models.DateTimeField(_("payée le"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("commande")

    @property
    def subtotal(self) -> Decimal:
        return self.compute_total()

    def compute_total(self) -> Decimal:
        return sum((item.subtotal for item in self.items.all()), Decimal("0"))

    def refresh_total(self):
        sub = self.compute_total()
        discount = self.discount_amount if self.discount_status == "approved" else Decimal("0")
        if discount < 0:
            discount = Decimal("0")
        if discount > sub:
            discount = sub
        self.total = sub - discount
        self.save(update_fields=["total"])

    def apply_discount(self, amount: Decimal, reason: str, user, *, auto_approve: bool = False):
        """Request or apply a discount. Manager/admin can auto-approve."""
        sub = self.compute_total()
        amount = Decimal(amount)
        if amount < 0:
            amount = Decimal("0")
        if amount > sub:
            amount = sub
        self.discount_amount = amount
        self.discount_reason = (reason or "").strip()
        self.discount_requested_by = user
        if auto_approve or amount == 0:
            self.discount_status = "approved" if amount > 0 else "none"
            self.discount_approved_by = user if amount > 0 else None
            if amount == 0:
                self.discount_amount = Decimal("0")
                self.discount_reason = ""
        else:
            self.discount_status = "pending"
            self.discount_approved_by = None
        self.save(
            update_fields=[
                "discount_amount",
                "discount_reason",
                "discount_status",
                "discount_requested_by",
                "discount_approved_by",
            ]
        )
        self.refresh_total()

    def approve_discount(self, user):
        if self.discount_status != "pending":
            return False
        self.discount_status = "approved"
        self.discount_approved_by = user
        self.save(update_fields=["discount_status", "discount_approved_by"])
        self.refresh_total()
        return True

    def reject_discount(self, user):
        if self.discount_status != "pending":
            return False
        self.discount_status = "rejected"
        self.discount_amount = Decimal("0")
        self.discount_approved_by = user
        self.save(
            update_fields=["discount_status", "discount_amount", "discount_approved_by"]
        )
        self.refresh_total()
        return True

    @transaction.atomic
    def mark_paid(self, user):
        """Set status to paid and create the cash IN entry exactly once."""
        from cash.models import CashEntry

        if self.status == self.Status.PAYEE:
            return
        self.status = self.Status.PAYEE
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at"])
        if not hasattr(self, "cash_entry"):
            CashEntry.objects.create(
                type=CashEntry.Type.IN,
                amount=self.total,
                reason=f"Commande #{self.pk} — Table {self.table.number}",
                order=self,
                created_by=user,
            )

    def __str__(self) -> str:
        return f"Commande #{self.pk} — Table {self.table.number}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    dish = models.ForeignKey(
        "menu.Dish", on_delete=models.PROTECT, related_name="order_items", verbose_name=_("plat")
    )
    quantity = models.PositiveIntegerField(_("quantité"), default=1)
    unit_price = models.DecimalField(_("prix unitaire"), max_digits=10, decimal_places=2)
    note = models.CharField(_("note"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("ligne de commande")

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    def __str__(self) -> str:
        return f"{self.quantity} x {self.dish.name_fr}"
