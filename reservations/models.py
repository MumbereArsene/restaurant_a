from django.db import models
from django.utils.translation import gettext_lazy as _


class Reservation(models.Model):
    class Status(models.TextChoices):
        EN_ATTENTE = "en_attente", _("En attente")
        CONFIRMEE = "confirmee", _("Confirmée")
        REFUSEE = "refusee", _("Refusée")
        ANNULEE = "annulee", _("Annulée")

    name = models.CharField(_("nom"), max_length=120)
    phone = models.CharField(_("téléphone"), max_length=30)
    date = models.DateField(_("date"))
    time = models.TimeField(_("heure"))
    guests = models.PositiveIntegerField(_("nombre de personnes"), default=2)
    notes = models.TextField(_("notes"), blank=True)
    status = models.CharField(
        _("statut"), max_length=20, choices=Status.choices, default=Status.EN_ATTENTE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-time"]
        verbose_name = _("réservation")

    def __str__(self) -> str:
        return f"{self.name} — {self.date} {self.time} ({self.guests}p)"
