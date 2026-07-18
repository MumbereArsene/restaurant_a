"""Populate the database with demo data (restaurant, tables, menu, users)."""

from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import User
from core.models import Restaurant
from menu.models import Category, Dish
from tables.models import Table

DEMO_USERS = [
    ("admin", "admin1234", User.Role.ADMIN, "Alice", "Admin"),
    ("manager", "manager1234", User.Role.MANAGER, "Marc", "Manager"),
    ("caissier", "caissier1234", User.Role.CAISSIER, "Claire", "Caissier"),
    ("serveur", "serveur1234", User.Role.SERVEUR, "Serge", "Serveur"),
    ("cuisine", "cuisine1234", User.Role.CUISINE, "Carla", "Cuisine"),
]

# name_fr, name_en, desc_fr, desc_en, price, image_url
MENU = {
    ("Entrées", "Starters"): [
        (
            "Salade fraîcheur",
            "Garden salad",
            "Laitue, tomates, concombre, vinaigrette maison.",
            "Lettuce, tomatoes, cucumber, house dressing.",
            "4.50",
            "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Soupe du jour",
            "Soup of the day",
            "Préparée chaque matin avec des produits frais.",
            "Made fresh every morning.",
            "3.00",
            "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=800&q=80",
        ),
    ],
    ("Plats", "Main courses"): [
        (
            "Poulet braisé",
            "Braised chicken",
            "Poulet mariné, braisé au feu de bois, accompagné de bananes plantains.",
            "Marinated chicken, wood-fire braised, served with plantains.",
            "12.00",
            "https://images.unsplash.com/photo-1598103442097-8b74394b95c6?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Poisson grillé",
            "Grilled fish",
            "Tilapia entier grillé, sauce tomate épicée.",
            "Whole grilled tilapia with spicy tomato sauce.",
            "14.50",
            "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Riz sauté aux légumes",
            "Vegetable fried rice",
            "Riz parfumé sauté au wok avec légumes de saison.",
            "Fragrant rice wok-fried with seasonal vegetables.",
            "8.00",
            "https://images.unsplash.com/photo-1603133872878-684f208fb84b?auto=format&fit=crop&w=800&q=80",
        ),
    ],
    ("Desserts", "Desserts"): [
        (
            "Salade de fruits",
            "Fruit salad",
            "Fruits frais de saison.",
            "Fresh seasonal fruits.",
            "3.50",
            "https://images.unsplash.com/photo-1564093497595-593b96d77633?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Beignets maison",
            "Homemade beignets",
            "Servis tièdes, saupoudrés de sucre.",
            "Served warm with a dusting of sugar.",
            "2.50",
            "https://images.unsplash.com/photo-1551024601-bec78aea704b?auto=format&fit=crop&w=800&q=80",
        ),
    ],
    ("Boissons", "Drinks"): [
        (
            "Jus de gingembre",
            "Ginger juice",
            "Fait maison, servi bien frais.",
            "Homemade, served chilled.",
            "2.00",
            "https://images.unsplash.com/photo-1622597467836-f3285f2131b8?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Eau minérale",
            "Mineral water",
            "Bouteille fraîche.",
            "Chilled bottle.",
            "1.00",
            "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?auto=format&fit=crop&w=800&q=80",
        ),
    ],
}


class Command(BaseCommand):
    help = "Crée des données de démonstration (restaurant, tables, menu, comptes)."

    def handle(self, *args, **options):
        resto = Restaurant.get_solo()
        if not resto.description_fr:
            resto.name = "Chez AMC"
            resto.description_fr = (
                "Une cuisine généreuse et conviviale au cœur de la ville. "
                "Produits frais, recettes maison et service chaleureux."
            )
            resto.description_en = (
                "Generous, friendly cooking in the heart of the city. "
                "Fresh produce, homemade recipes and warm service."
            )
            resto.address = "12 Avenue du Marché"
            resto.phone = "+243 900 000 000"
            resto.opening_hours_fr = "Lun–Sam : 11h00 – 22h30\nDim : 12h00 – 21h00"
            resto.opening_hours_en = "Mon–Sat: 11:00 am – 10:30 pm\nSun: 12:00 pm – 9:00 pm"
            resto.save()
            self.stdout.write(self.style.SUCCESS("Restaurant configuré."))

        for username, password, role, first, last in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"role": role, "first_name": first, "last_name": last},
            )
            if created:
                user.set_password(password)
                if role == User.Role.ADMIN:
                    user.is_superuser = True
                    user.is_staff = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Compte {username} créé ({role})."))

        for number in range(1, 5):
            _, created = Table.objects.get_or_create(number=number, defaults={"capacity": 4})
            if created:
                self.stdout.write(self.style.SUCCESS(f"Table {number} créée avec QR token."))

        for pos, ((name_fr, name_en), dishes) in enumerate(MENU.items()):
            category, _ = Category.objects.get_or_create(
                name_fr=name_fr, defaults={"name_en": name_en, "position": pos}
            )
            for d_fr, d_en, desc_fr, desc_en, price, image_url in dishes:
                dish, created = Dish.objects.get_or_create(
                    category=category,
                    name_fr=d_fr,
                    defaults={
                        "name_en": d_en,
                        "description_fr": desc_fr,
                        "description_en": desc_en,
                        "price": Decimal(price),
                        "image_url": image_url,
                    },
                )
                if created:
                    self.stdout.write(f"  Plat « {d_fr} » ajouté.")
                elif not dish.image_url:
                    dish.image_url = image_url
                    dish.save(update_fields=["image_url"])
                    self.stdout.write(f"  Image ajoutée pour « {d_fr} ».")

        self.stdout.write(self.style.SUCCESS("Données de démo prêtes."))
        self.stdout.write(
            "Comptes : admin/admin1234, manager/manager1234, caissier/caissier1234, "
            "serveur/serveur1234, cuisine/cuisine1234"
        )
        for table in Table.objects.all():
            self.stdout.write(f"  Table {table.number} -> /order/{table.qr_token}/")
