import os
import shutil
import tempfile

from django.test import TestCase, override_settings

from config.tests.test_security import ProductionSettingsTests  # noqa: F401

_MEDIA_ROOT = tempfile.mkdtemp(prefix="resto-media-")


class CoreSmokeTests(TestCase):
    def test_home_ok(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
class MediaCleanupTests(TestCase):
    """Cloudinary / disk uploads are removed when replaced or deleted."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from menu.models import Category, Dish

        self._png = SimpleUploadedFile(
            "plat.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16, content_type="image/png"
        )
        cat = Category.objects.create(name_fr="Plats")
        self.dish = Dish(category=cat, name_fr="Test", price=10)
        self.dish.image = self._png
        self.dish.save()

    def _path(self, field):
        return os.path.join(_MEDIA_ROOT, field.name)

    def test_replaced_image_deletes_previous_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        old_path = self._path(self.dish.image)
        self.assertTrue(os.path.exists(old_path))

        new_png = SimpleUploadedFile(
            "plat2.png", b"\x89PNG\r\n\x1a\n" + b"\x01" * 16, content_type="image/png"
        )
        self.dish.image = new_png
        self.dish.save()
        self.dish.refresh_from_db()

        self.assertFalse(os.path.exists(old_path))
        self.assertNotEqual(getattr(self.dish.image, "name", ""), "plat.png")
        self.assertTrue(os.path.exists(self._path(self.dish.image)))

    def test_deleted_dish_removes_image(self):
        path = self._path(self.dish.image)
        self.assertTrue(os.path.exists(path))
        self.dish.delete()
        self.assertFalse(os.path.exists(path))

    def test_category_cascade_removes_dish_images(self):
        path = self._path(self.dish.image)
        self.dish.category.delete()
        self.assertFalse(os.path.exists(path))
