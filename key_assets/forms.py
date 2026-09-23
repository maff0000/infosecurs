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
    class Meta:
        model = KeyAsset
        fields = ["name", "category", "description", "criticality"]
        labels = {
            "name": "Name",
            "category": "Category",
            "description": "Short description",
            "criticality": "Business criticality",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Asset name cannot be empty.")
        return name
