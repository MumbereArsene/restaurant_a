from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

HEX_COLOR = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message=_("Couleur invalide. Format attendu : #RRGGBB"),
)


class Restaurant(models.Model):
    """Singleton holding the restaurant profile, branding and public content."""

    name = models.CharField(_("nom"), max_length=120, default="Mon Restaurant")
    description_fr = models.TextField(_("description (FR)"), blank=True)
    description_en = models.TextField(_("description (EN)"), blank=True)
    address = models.CharField(_("adresse"), max_length=255, blank=True)
    phone = models.CharField(_("téléphone"), max_length=50, blank=True)
    email = models.EmailField(_("email"), blank=True)
    opening_hours_fr = models.TextField(
        _("horaires (FR)"), blank=True, help_text=_("Une ligne par plage, ex : Lun–Ven : 11h–22h")
    )
    opening_hours_en = models.TextField(_("horaires (EN)"), blank=True)
    logo = models.ImageField(_("logo"), upload_to="restaurant/", blank=True, null=True)
    logo_url = models.URLField(
        _("URL du logo"),
        blank=True,
        help_text=_("Utilisée si aucun fichier logo n'est uploadé."),
    )
    cover_image = models.ImageField(
        _("image de couverture"), upload_to="restaurant/", blank=True, null=True
    )
    cover_image_url = models.URLField(
        _("URL de couverture"),
        blank=True,
        help_text=_("Utilisée si aucune image de couverture n'est uploadée."),
    )

    # Brand palette — injected as CSS variables site-wide
    color_ink = models.CharField(
        _("couleur texte / encre"), max_length=7, default="#0A0A0A", validators=[HEX_COLOR]
    )
    color_paper = models.CharField(
        _("couleur fond"), max_length=7, default="#F4F4F5", validators=[HEX_COLOR]
    )
    color_surface = models.CharField(
        _("couleur surface"), max_length=7, default="#FFFFFF", validators=[HEX_COLOR]
    )
    color_accent = models.CharField(
        _("couleur accent"), max_length=7, default="#FF5A00", validators=[HEX_COLOR]
    )
    color_accent_dark = models.CharField(
        _("couleur accent foncée"), max_length=7, default="#E04E00", validators=[HEX_COLOR]
    )

    class Meta:
        verbose_name = _("restaurant")

    def save(self, *args, **kwargs):
        from core.media_cleanup import delete_replaced_file

        delete_replaced_file(self, "logo")
        delete_replaced_file(self, "cover_image")
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> "Restaurant":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def description(self) -> str:
        if get_language() == "en" and self.description_en:
            return self.description_en
        return self.description_fr

    @property
    def opening_hours(self) -> str:
        if get_language() == "en" and self.opening_hours_en:
            return self.opening_hours_en
        return self.opening_hours_fr

    @property
    def logo_src(self) -> str:
        if self.logo:
            return self.logo.url
        return self.logo_url or ""

    @property
    def cover_src(self) -> str:
        if self.cover_image:
            return self.cover_image.url
        return self.cover_image_url or ""

    def theme_css(self) -> str:
        """Inline CSS overriding Tailwind theme tokens from admin palette."""
        return (
            f"--color-ink:{self.color_ink};"
            f"--color-paper:{self.color_paper};"
            f"--color-surface:{self.color_surface};"
            f"--color-vermilion:{self.color_accent};"
            f"--color-vermilion-dark:{self.color_accent_dark};"
            f"--color-staff-rail:{self.color_ink};"
        )

    def __str__(self) -> str:
        return self.name


class ContactMessage(models.Model):
    """Public contact form submissions."""

    name = models.CharField(_("nom"), max_length=120)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("téléphone"), max_length=40, blank=True)
    subject = models.CharField(_("sujet"), max_length=160, blank=True)
    message = models.TextField(_("message"))
    is_read = models.BooleanField(_("lu"), default=False)
    created_at = models.DateTimeField(_("envoyé le"), auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("message de contact")
        verbose_name_plural = _("messages de contact")

    def __str__(self) -> str:
        return f"{self.name} — {self.subject or self.message[:40]}"


class AuditLog(models.Model):
    """Immutable log of important staff actions."""

    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("acteur"),
    )
    action = models.CharField(_("action"), max_length=64, db_index=True)
    object_type = models.CharField(_("type d'objet"), max_length=64, blank=True)
    object_id = models.CharField(_("id objet"), max_length=64, blank=True)
    message = models.TextField(_("message"))
    created_at = models.DateTimeField(_("date"), auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("entrée d'audit")
        verbose_name_plural = _("journal d'audit")

    def __str__(self) -> str:
        return f"{self.created_at:%d/%m %H:%M} — {self.action}"
