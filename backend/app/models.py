from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Sum,F


# Create your models here.
class Session(models.Model):
    title = models.CharField(max_length=100)
    tax = models.FloatField(default=0, validators=[MinValueValidator(0)])
    service = models.FloatField(default=0, validators=[MinValueValidator(0)])
    discount = models.FloatField(default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    def subtotal(self):
        return sum(person.calculate_amount() for person in self.persons.all())

    def total(self):
        total = self.subtotal() * (1+(self.tax/100)) * (1+(self.service/100)) - self.subtotal()*((self.discount)/100)
        return round(total, 2)
    def taxed(self,amount):
        taxed = amount * (1+(self.tax/100)) * (1+(self.service/100)) - amount*((self.discount)/100)
        return round(taxed,2)


    def __str__(self):
        return self.title
    
class Person(models.Model):
    name=models.CharField(max_length=80)
    session = models.ForeignKey(Session,on_delete=models.CASCADE,related_name='persons')

    def calculate_amount(self):
        return  (
            self.items
            .aggregate(
                total=Sum(F('price') * F('quantity'))
            )['total']
            or 0
        )
    def calculate_taxed_amount(self):
        amount = self.calculate_amount()
        return self.session.taxed(amount)
    def __str__(self):
        return f"{self.name}"

    
    
class Item(models.Model):
    name=models.CharField(max_length=50)
    price=models.FloatField(validators=[MinValueValidator(1)])
    quantity=models.PositiveIntegerField(default=1)
    person = models.ForeignKey( Person, on_delete=models.CASCADE,related_name='items')

    def __str__(self):
        return f"{self.name} :: {self.price} :: {self.quantity}"
    def total(self):
        return self.price * self.quantity


