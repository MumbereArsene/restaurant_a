from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Category, Dish


class PublicMenuFilterTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(name_fr="Plats", name_en="Meals", position=1)
        self.pizza = Dish.objects.create(
            category=cat, name_fr="Pizza Margherita", name_en="Pizza Margherita",
            description_fr="Tomate, mozzarella", price=Decimal("12.00"),
        )
        self.pasta = Dish.objects.create(
            category=cat, name_fr="Pâtes", name_en="Pasta",
            description_fr="Crème, parmesan", price=Decimal("9.00"),
        )
        self.drink = Dish.objects.create(
            category=cat, name_fr="Jus d'ananas", name_en="Pineapple juice",
            description_fr="Frais", price=Decimal("3.00"),
        )

    def _results(self, **params):
        r = self.client.get(reverse("menu:public"), params)
        self.assertEqual(r.status_code, 200)
        return r

    def test_search_by_name(self):
        r = self._results(q="Pizza")
        self.assertContains(r, "Pizza Margherita")
        self.assertNotContains(r, "Pâtes")
        self.assertNotContains(r, "Jus")

    def test_search_is_bilingual(self):
        r = self._results(q="pasta")
        self.assertContains(r, "Pâtes")

    def test_max_price_filter(self):
        r = self._results(max="10")
        self.assertContains(r, "Pâtes")
        self.assertContains(r, "Jus")
        self.assertNotContains(r, "Pizza Margherita")

    def test_category_filter(self):
        other = Category.objects.create(name_fr="Boissons", position=2)
        Dish.objects.create(category=other, name_fr="Coca", price=Decimal("2.00"))
        r = self._results(cat=str(other.pk))
        self.assertContains(r, "Coca")
        self.assertNotContains(r, "Pizza Margherita")

    def test_sort_by_price_asc(self):
        r = self._results(sort="price_asc")
        content = r.content.decode()
        self.assertLess(content.index("Jus"), content.index("Pizza Margherita"))

    def test_no_result_message(self):
        r = self._results(q="xyzzy")
        self.assertContains(r, "Aucun plat ne correspond")

    def test_no_filters_shows_all(self):
        r = self._results()
        self.assertContains(r, "Pizza Margherita")
        self.assertContains(r, "Pâtes")
        self.assertContains(r, "Jus")