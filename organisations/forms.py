from django import forms

from organisations.models import Organisation, OrganisationProfile


def _apply_field_css_classes(form):
    """Give every widget a consistent CSS hook without a template-tag library."""
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


class OrganisationCreateForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = ["name"]
        labels = {"name": "Organisation name"}
        help_texts = {"name": "The name you'll use to identify this organisation."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Organisation name cannot be empty.")
        return name


class OrganisationProfileForm(forms.ModelForm):
    class Meta:
        model = OrganisationProfile
        fields = [
            "legal_trading_name",
            "description",
            "staff_count",
            "working_model",
            "endpoint_management",
            "productivity_platform",
            "primary_cloud_provider",
            "develops_hosts_own_software",
            "handles_personal_data",
            "handles_confidential_business_data",
            "handles_payment_card_data",
            "handles_special_category_data",
            "receives_security_questionnaires",
            "cyber_essentials_status",
            "iso27001_status",
            "commercial_security_driver",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "commercial_security_driver": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_legal_trading_name(self):
        name = self.cleaned_data["legal_trading_name"].strip()
        if not name:
            raise forms.ValidationError(
                "Legal/trading name is required and cannot be empty."
            )
        return name
