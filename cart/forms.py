"""A tiny form so quantity input is validated, not trusted."""

from django import forms

from .cart import MAX_QUANTITY_PER_ITEM


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        max_value=MAX_QUANTITY_PER_ITEM,
        initial=1,
    )
    # Set from the detail page so "add" replaces rather than increments.
    override = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput)
