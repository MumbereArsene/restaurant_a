from datetime import datetime, time
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.validators import MinValueValidator
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from accounts.permissions import cash_access
from core.audit import log_action
from core.models import Restaurant
from core.widgets import FIELD

from .models import CashClosure, CashEntry


class CashEntryForm(forms.ModelForm):
    class Meta:
        model = CashEntry
        fields = ["type", "amount", "reason"]
        widgets = {
            "type": forms.Select(attrs={"class": FIELD}),
            "amount": forms.NumberInput(attrs={"class": FIELD, "min": 0, "step": "0.01"}),
            "reason": forms.TextInput(
                attrs={"class": FIELD, "placeholder": gettext_lazy("Ex : achat légumes")}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].validators.append(MinValueValidator(0))


class CashClosureForm(forms.Form):
    counted_amount = forms.DecimalField(
        label=gettext_lazy("Montant compté dans le tiroir"),
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": FIELD, "step": "0.01", "min": "0"}),
    )
    notes = forms.CharField(
        label=gettext_lazy("Notes"),
        required=False,
        widget=forms.Textarea(attrs={"class": FIELD, "rows": 3}),
    )


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _period_start():
    """Start of current open cash period = last closure or today midnight."""
    last = CashClosure.objects.order_by("-closed_at").first()
    if last:
        return last.closed_at
    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    return datetime.combine(today, time.min, tzinfo=tz)


def _period_totals(period_start):
    entries = CashEntry.objects.filter(created_at__gte=period_start)
    total_in = entries.filter(type=CashEntry.Type.IN).aggregate(s=Sum("amount"))["s"] or Decimal("0")
    total_out = entries.filter(type=CashEntry.Type.OUT).aggregate(s=Sum("amount"))["s"] or Decimal("0")
    return total_in, total_out, entries


@cash_access
def cash_ledger(request):
    """Cash history with period filter, totals and running balance."""
    date_from = _parse_date(request.GET.get("from"))
    date_to = _parse_date(request.GET.get("to"))

    entries = CashEntry.objects.select_related("created_by", "order")
    tz = timezone.get_current_timezone()
    if date_from:
        entries = entries.filter(
            created_at__gte=datetime.combine(date_from, time.min, tzinfo=tz)
        )
    if date_to:
        entries = entries.filter(
            created_at__lte=datetime.combine(date_to, time.max, tzinfo=tz)
        )

    total_in = entries.filter(type=CashEntry.Type.IN).aggregate(s=Sum("amount"))["s"] or 0
    total_out = entries.filter(type=CashEntry.Type.OUT).aggregate(s=Sum("amount"))["s"] or 0

    all_in = CashEntry.objects.filter(type=CashEntry.Type.IN).aggregate(s=Sum("amount"))["s"] or 0
    all_out = CashEntry.objects.filter(type=CashEntry.Type.OUT).aggregate(s=Sum("amount"))["s"] or 0

    return render(
        request,
        "cash/ledger.html",
        {
            "entries": entries[:300],
            "closures": CashClosure.objects.select_related("closed_by")[:10],
            "total_in": total_in,
            "total_out": total_out,
            "period_balance": total_in - total_out,
            "overall_balance": all_in - all_out,
            "date_from": request.GET.get("from", ""),
            "date_to": request.GET.get("to", ""),
        },
    )


@cash_access
def cash_entry_create(request):
    form = CashEntryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.created_by = request.user
        entry.save()
        log_action(
            request.user,
            "cash.entry",
            _("Mouvement %(type)s de %(amount)s — %(reason)s")
            % {
                "type": entry.get_type_display(),
                "amount": entry.amount,
                "reason": entry.reason,
            },
            object_type="CashEntry",
            object_id=entry.pk,
        )
        messages.success(request, _("Mouvement de caisse enregistré."))
        return redirect("cash:ledger")
    return render(request, "cash/entry_form.html", {"form": form})


@cash_access
def cash_close(request):
    """Close the cash drawer for the current open period."""
    start = _period_start()
    total_in, total_out, _entries = _period_totals(start)
    expected = total_in - total_out

    form = CashClosureForm(request.POST or None, initial={"counted_amount": expected})
    if request.method == "POST" and form.is_valid():
        counted = form.cleaned_data["counted_amount"]
        with transaction.atomic():
            Restaurant.objects.get_or_create(pk=1)
            Restaurant.objects.select_for_update().get(pk=1)
            start = _period_start()
            total_in, total_out, _entries = _period_totals(start)
            expected = total_in - total_out
            difference = counted - expected
            closure = CashClosure.objects.create(
                period_start=start,
                closed_by=request.user,
                total_in=total_in,
                total_out=total_out,
                expected_amount=expected,
                counted_amount=counted,
                difference=difference,
                notes=form.cleaned_data["notes"],
            )
        log_action(
            request.user,
            "cash.close",
            _("Clôture #%(id)s — attendu %(exp)s, compté %(cnt)s, écart %(diff)s")
            % {
                "id": closure.pk,
                "exp": expected,
                "cnt": counted,
                "diff": difference,
            },
            object_type="CashClosure",
            object_id=closure.pk,
        )
        messages.success(
            request,
            _("Caisse clôturée. Écart : %(diff)s") % {"diff": difference},
        )
        return redirect("cash:closure_detail", pk=closure.pk)

    return render(
        request,
        "cash/close.html",
        {
            "form": form,
            "period_start": start,
            "total_in": total_in,
            "total_out": total_out,
            "expected": expected,
        },
    )


@cash_access
def cash_closure_detail(request, pk):
    closure = get_object_or_404(CashClosure.objects.select_related("closed_by"), pk=pk)
    return render(request, "cash/closure_detail.html", {"closure": closure})
