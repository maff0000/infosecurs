from django import forms

from key_assets.models import KeyAsset


def _apply_field_css_classes(form):
    """
    Gives every widget the same CSS hooks as organisations.forms's helper of
    the same name, so KeyAsset forms render with the product's existing
    input/select/textarea styling. Duplicated rather than imported: the
    organisations app is read-only to this dispatch and key_assets should
    not depend on its (private, underscore-prefixed) internals.
    """
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "checkbox")
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "select")
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault("class", "textarea")
        else:
            widget.attrs.setdefault("class", "input")


class KeyAssetForm(forms.ModelForm):
    """
    M008-FREE-TEXT-REPLACEMENT-REGISTER.md Row 3: `description` is
    retired from this form entirely - it is NOT repurposed into a shorter
    text field, it is simply dropped. The `KeyAsset.description` column
    itself stays on the model (existing legacy values, if any, remain
    visible read-only on the asset detail/list pages - M008-FREE-TEXT-
    REPLACEMENT-REGISTER.md Row 3's own "Legacy values visible/read-only:
    Yes"), so no migration is needed; only this form's own `Meta.fields`/
    `Meta.widgets` change.

    Found and corrected by the M008C-WI2a dispatch while folding this
    existing create/edit flow into Stage 3 (M008B-STAGES-1-3-CATALOGUE.md
    §3.7): Row 3 was already approved design (Revision 1, unaffected by
    the Revision 2 correction pass) but had not actually been implemented
    - this form still carried a live, writable `description` Textarea
    before this change. Left in place, Stage 3's folded-in "Key assets"
    step would still have contained a free-text field, contradicting this
    WI's own "zero Textarea anywhere in Stages 1-3" requirement by
    indirection through a reused flow. See this dispatch's report for the
    full reasoning.
    """

    class Meta:
        model = KeyAsset
        fields = ["name", "category", "criticality"]
        labels = {
            "name": "Name",
            "category": "Category",
            "criticality": "Business criticality",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Asset name cannot be empty.")
        return name
