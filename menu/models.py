from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _


class TranslatedNameMixin(models.Model):
    """FR is the source of truth; EN falls back to FR when empty."""

    name_fr = models.CharField(_("nom (FR)"), max_length=120)
    name_en = models.CharField(_("nom (EN)"), max_length=120, blank=True)

    class Meta:
        abstract = True

    @property
    def name(self) -> str:
        if get_language() == "en" and self.name_en:
            return self.name_en
        return self.name_fr

    def __str__(self) -> str:
        return self.name_fr


class Category(TranslatedNameMixin):
    position = models.PositiveIntegerField(_("ordre d'affichage"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ["position", "name_fr"]
        verbose_name = _("catégorie")
        verbose_name_plural = _("catégories")


class Dish(TranslatedNameMixin):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="dishes", verbose_name=_("catégorie")
    )
    description_fr = models.TextField(_("description (FR)"), blank=True)
    description_en = models.TextField(_("description (EN)"), blank=True)
    price = models.DecimalField(_("prix"), max_digits=10, decimal_places=2)
    image = models.ImageField(_("image"), upload_to="dishes/", blank=True, null=True)
    image_url = models.URLField(
        _("URL image"),
        blank=True,
        help_text=_("Utilisée si aucun fichier image n'est uploadé."),
    )
    is_active = models.BooleanField(_("disponible"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__position", "name_fr"]
        verbose_name = _("plat")
        verbose_name_plural = _("plats")

    @property
    def description(self) -> str:
        if get_language() == "en" and self.description_en:
            return self.description_en
        return self.description_fr

    @property
    def photo_url(self) -> str:
        if self.image:
            return self.image.url
        return self.image_url or ""
