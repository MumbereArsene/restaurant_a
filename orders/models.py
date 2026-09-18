import uuid
from decimal import Decimal
from urllib.parse import quote

from django.core.mail import send_mail
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _gettext
from django.utils.translation import gettext_lazy as _


def _new_invoice_token() -> str:
    return uuid.uuid4().hex


def _new_invoice_code() -> str:
    from tables.codes import generate_code

    return generate_code()


class Order(models.Model):
    class Status(models.TextChoices):
        EN_ATTENTE = "en_attente", _("En attente")
        ACCEPTEE = "acceptee", _("Acceptée")
        EN_PREPARATION = "en_preparation", _("En préparation")
        PRETE = "prete", _("Prête")
        SERVIE = "servie", _("Servie")
        PAYEE = "payee", _("Payée")
        ANNULEE = "annulee", _("Annulée")

    class PaymentMethod(models.TextChoices):
        ESPECES = "especes", _("Espèces")
        MOBILE = "mobile", _("Mobile Money")
        ORANGE = "orange", _("Orange Money")
        AIRTEL = "airtel", _("Airtel Money")

    ACCEPTED_LIKE = (Status.ACCEPTEE, Status.EN_PREPARATION, Status.PRETE)
    OPEN_STATUSES = (
        Status.EN_ATTENTE,
        Status.ACCEPTEE,
        Status.EN_PREPARATION,
        Status.PRETE,
        Status.SERVIE,
    )

    table = models.ForeignKey(
        "tables.Table", on_delete=models.PROTECT, related_name="orders", verbose_name=_("table")
    )
    status = models.CharField(
        _("statut"), max_length=20, choices=Status.choices, default=Status.EN_ATTENTE
    )
    payment_method = models.CharField(
        _("méthode de paiement"),
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ESPECES,
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
    guest_email = models.EmailField(_("email client"), blank=True)
    guest_phone = models.CharField(_("WhatsApp client"), max_length=30, blank=True)
    customer = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_orders",
        verbose_name=_("compte client"),
    )
    invoice_token = models.CharField(
        _("token facture"),
        max_length=64,
        unique=True,
        default=_new_invoice_token,
        editable=False,
    )
    invoice_code = models.CharField(
        _("code facture"),
        max_length=8,
        unique=True,
        blank=True,
        help_text=_("Code court saisi par le serveur pour encaisser."),
    )
    created_at = models.DateTimeField(_("créée le"), auto_now_add=True)
    accepted_at = models.DateTimeField(_("acceptée le"), null=True, blank=True)
    served_at = models.DateTimeField(_("servie le"), null=True, blank=True)
    paid_at = models.DateTimeField(_("payée le"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("commande")
        indexes = [
            models.Index(fields=["created_at"], name="orders_orde_created_4a4a6e_idx"),
            models.Index(fields=["paid_at"], name="orders_orde_paid_at_8f0d1c_idx"),
            models.Index(fields=["status"], name="orders_orde_status_25e1e0_idx"),
            models.Index(fields=["invoice_token"], name="orders_orde_invoice_token_idx"),
        ]

    @property
    def subtotal(self) -> Decimal:
        return self.compute_total()

    @property
    def is_accepted_like(self) -> bool:
        return self.status in self.ACCEPTED_LIKE

    @property
    def is_payable(self) -> bool:
        return self.status == self.Status.SERVIE

    @property
    def has_invoice(self) -> bool:
        return self.status in (self.Status.SERVIE, self.Status.PAYEE)

    @property
    def next_status(self):
        if self.status == self.Status.EN_ATTENTE:
            return self.Status.ACCEPTEE
        if self.status in self.ACCEPTED_LIKE:
            return self.Status.SERVIE
        return None

    @property
    def staff_status_label(self) -> str:
        if self.status in self.ACCEPTED_LIKE:
            return str(_("Acceptée"))
        return self.get_status_display()

    @property
    def order_ref(self) -> str:
        year = self.created_at.year if self.created_at else timezone.now().year
        return f"CMD-{year}-{self.pk:06d}" if self.pk else ""

    @property
    def invoice_ref(self) -> str:
        year = self.created_at.year if self.created_at else timezone.now().year
        return f"FAC-{year}-{self.pk:06d}" if self.pk else ""

    def _invoice_code_taken(self, code: str) -> bool:
        qs = type(self).objects.filter(invoice_code=code)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            return True
        from tables.models import Table

        return Table.objects.filter(public_code=code).exists()

    def save(self, *args, **kwargs):
        if not self.invoice_code:
            from tables.codes import generate_unique_code

            self.invoice_code = generate_unique_code(is_taken=self._invoice_code_taken)
        super().save(*args, **kwargs)

    def invoice_scan_url(self, request) -> str:
        return request.build_absolute_uri(
            reverse("orders:invoice_scan", kwargs={"token": self.invoice_token})
        )

    def public_invoice_url(self, request) -> str:
        return request.build_absolute_uri(
            reverse("orders:public_invoice", kwargs={"token": self.invoice_token})
        )

    @property
    def contact_email(self) -> str:
        if self.guest_email:
            return self.guest_email
        if self.customer_id and self.customer.email:
            return self.customer.email
        return ""

    @property
    def contact_phone(self) -> str:
        if self.guest_phone:
            return self.guest_phone
        if self.customer_id and self.customer.phone:
            return self.customer.phone
        return ""

    @property
    def phone_digits(self) -> str:
        return "".join(c for c in self.contact_phone if c.isdigit())

    def whatsapp_url(self, request) -> str:
        digits = self.phone_digits
        if not digits:
            return ""
        text = _gettext("Votre facture #%(id)s — %(url)s") % {
            "id": self.pk,
            "url": self.public_invoice_url(request),
        }
        return f"https://wa.me/{digits}?text={quote(text)}"

    def notify_invoice(self, request) -> dict:
        """Email the public invoice when possible. WhatsApp is a share link."""
        import logging

        from django.conf import settings

        from core.models import Restaurant

        logger = logging.getLogger("orders.invoice")
        sent_email = False
        email = self.contact_email
        url = self.public_invoice_url(request)
        if email:
            try:
                resto_email = (Restaurant.get_solo().email or "").strip()
                from_email = resto_email or settings.DEFAULT_FROM_EMAIL
                sent = send_mail(
                    _gettext("Facture #%(id)s") % {"id": self.pk},
                    _gettext(
                        "Votre facture est prête : %(url)s\nTotal : %(total)s\n"
                        "Présentez-la au serveur pour le règlement."
                    )
                    % {"url": url, "total": self.total},
                    from_email,
                    [email],
                    fail_silently=False,
                )
                sent_email = bool(sent)
                if sent_email:
                    logger.info("invoice_email SUCCESS order=%s to=%s", self.pk, email)
                else:
                    logger.warning("invoice_email FAILED order=%s to=%s result=0", self.pk, email)
            except Exception:
                logger.exception("invoice_email FAILED order=%s to=%s", self.pk, email)
                sent_email = False
        return {"email": sent_email, "whatsapp": self.whatsapp_url(request)}

    def advance(self) -> bool:
        """Accepter or Servir. Returns True if the status changed."""
        nxt = self.next_status
        if not nxt:
            return False
        now = timezone.now()
        fields = ["status"]
        if nxt == self.Status.ACCEPTEE:
            self.accepted_at = now
            fields.append("accepted_at")
        elif nxt == self.Status.SERVIE:
            self.served_at = now
            fields.append("served_at")
            if not self.accepted_at:
                self.accepted_at = now
                fields.append("accepted_at")
        self.status = nxt
        self.save(update_fields=fields)
        return True

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
        self.discount_approved_by = user
        self.save(update_fields=["discount_status", "discount_approved_by"])
        self.refresh_total()
        return True

    @transaction.atomic
    def mark_paid(self, user, *, payment_method: str | None = None) -> bool:
        """Set status to paid and record the cash movement (cash only) exactly once.

        Mobile money payments are tracked on the order itself (payment_method);
        they never enter the cash drawer, so no CashEntry is created.

        Returns True if this call performed the payment, False if already paid.
        """
        from django.db import IntegrityError

        from cash.models import CashEntry

        method = payment_method or self.PaymentMethod.ESPECES
        if method not in self.PaymentMethod.values:
            method = self.PaymentMethod.ESPECES
        is_cash = method == self.PaymentMethod.ESPECES

        order = (
            type(self)
            .objects.select_for_update()
            .select_related("table")
            .get(pk=self.pk)
        )
        if order.status == self.Status.PAYEE:
            if is_cash and not CashEntry.objects.filter(order_id=order.pk).exists():
                try:
                    CashEntry.objects.create(
                        type=CashEntry.Type.IN,
                        amount=order.total,
                        reason=f"Commande #{order.pk} — Table {order.table.number}",
                        order=order,
                        created_by=user,
                    )
                except IntegrityError:
                    pass
            self.status = order.status
            self.paid_at = order.paid_at
            self.total = order.total
            self.payment_method = order.payment_method or method
            return False

        order.refresh_total()
        order.status = self.Status.PAYEE
        order.paid_at = timezone.now()
        order.payment_method = method
        order.save(update_fields=["status", "paid_at", "payment_method"])
        if is_cash:
            try:
                CashEntry.objects.create(
                    type=CashEntry.Type.IN,
                    amount=order.total,
                    reason=f"Commande #{order.pk} — Table {order.table.number}",
                    order=order,
                    created_by=user,
                )
            except IntegrityError:
                pass
        self.status = order.status
        self.paid_at = order.paid_at
        self.total = order.total
        self.payment_method = order.payment_method
        return True

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
