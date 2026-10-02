from django import forms

from organisations.models import (
    DRIVER_CERTIFICATION_CONTRACT,
    DRIVER_CUSTOMER_SUPPLIER,
    DRIVER_GENERAL_RISK,
    DRIVER_NOT_SURE,
    DRIVER_SENSITIVE_DATA,
    NO,
    Organisation,
    OrganisationProfile,
    SECTOR_CONSTRUCTION_TRADES,
    SECTOR_EDUCATION_TRAINING,
    SECTOR_FINANCIAL_ACCOUNTING,
    SECTOR_HEALTHCARE_CARE,
    SECTOR_HOSPITALITY,
    SECTOR_LEGAL_SERVICES,
    SECTOR_MANUFACTURING_LOGISTICS,
    SECTOR_NOT_SURE,
    SECTOR_OTHER,
    SECTOR_PROFESSIONAL_CONSULTING,
    SECTOR_RETAIL_ECOMMERCE,
    SECTOR_TECHNOLOGY_SOFTWARE,
    UNKNOWN,
    YES,
)


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
    """
    `working_model` (docs/adr/ADR-0002-IDENTITY-GOVERNANCE-WORKPLACE-AND-
    DISTRIBUTION-BOUNDARIES.md §5.2, docs/pids/M004-POLICY-FOUNDATION.md
    §9.2): once the `workplace` app exists, `OrganisationProfile.
    working_model` is a derived summary computed from the organisation's
    active `workplace.Workplace` rows (see `workplace.services.
    sync_working_model`) - it is no longer an independently
    product-editable fact, so this form must not let a submission change
    it.

    `working_model` deliberately stays in `Meta.fields` below rather than
    being removed outright: removing it would also silently drop this
    codebase's ordinary per-field validation (an out-of-choices value
    would no longer be rejected at all, it would just be ignored) and
    would stop the field rendering on the profile page, which still wants
    to *show* the organisation's current working model. What actually
    enforces "no longer editable" is `save()` below: whatever value is
    submitted is discarded and the value present before this submission
    is restored immediately before the row is written, so the only way to
    change `working_model` is through `workplace.services.
    sync_working_model`.
    """

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
            # M008B-WI1: commercial_security_driver changed from a free
            # TextField to a choices-constrained CharField (the
            # DRIVER_* options) - this stale Textarea override is
            # removed so the field renders as the Select its new
            # choices actually require. Leaving the override in place
            # would have rendered a textarea for what is now a
            # five-option enum and rejected any typed value that isn't
            # one of the five option codes, with no indication to the
            # customer of what to type - a live regression on the
            # existing /organisations/<id>/profile/ page, not merely
            # cosmetic, since that page is already reachable today.
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)
        # Captured now, before any submitted POST data can reach
        # self.instance (that only happens later, inside
        # full_clean()/is_valid() -> _post_clean() -> construct_instance()).
        # For a brand-new (unbound-to-DB) instance this is the model
        # field's own default ("unknown"); for an existing profile it is
        # the value currently stored in the database.
        self._working_model_before_submission = self.instance.working_model
        self.fields["working_model"].help_text = (
            "Derived automatically from your workplaces - it can no "
            "longer be set directly here."
        )

    def save(self, commit=True):
        self.instance.working_model = self._working_model_before_submission
        return super().save(commit=commit)

    def clean_legal_trading_name(self):
        name = self.cleaned_data["legal_trading_name"].strip()
        if not name:
            raise forms.ValidationError(
                "Legal/trading name is required and cannot be empty."
            )
        return name


# ---------------------------------------------------------------------------
# M008C/M008B-WI2a - Stage 1-3 of the guided Foundations journey
# (docs/design/M008B-STAGES-1-3-CATALOGUE.md, docs/design/
# M008C-UX-FLOW-DESIGN.md). Each form below exposes EXACTLY the
# `OrganisationProfile` fields that one stage's own catalogue entry names -
# never the full field list `OrganisationProfileForm` above exposes - so a
# future addition to that legacy form can never silently leak an extra
# field onto one of these stage screens. No field below is a Textarea or
# any other free-text widget (M008-FREE-TEXT-REPLACEMENT-REGISTER.md) -
# every one is a bounded choice, a bounded integer, or (legal_trading_name
# only) the one short, bounded text identifier the catalogue itself
# exempts.
# ---------------------------------------------------------------------------


def _choices_in_order(model_choices, ordered_values):
    """
    Reorders a model field's own `choices` to match a literal option order
    `docs/design/M008B-STAGES-1-3-CATALOGUE.md` specifies, where that order
    differs from the model field's own internal `choices=` list (found for
    `sector`/`commercial_security_driver`: the model lists "Not sure yet"
    FIRST, matching this codebase's general UNKNOWN-first convention, but
    the catalogue's own §1.2/§1.4 tables list it LAST). This is a
    presentation-only override of the FORM field's `choices` - it changes
    nothing about the model, needs no migration (Django migrations track a
    field's `choices=` kwarg; reordering a form field's `choices` after
    `__init__` touches no model state at all), and every stored value
    remains exactly the one the model already defines.

    `ordered_values` must name exactly the same set of values
    `model_choices` already has - a mismatch is a programming error (e.g.
    a typo'd option code, or the model gaining/losing a choice this form
    was not updated for), so it is asserted rather than silently dropping
    or duplicating an option.
    """
    by_value = dict(model_choices)
    assert set(by_value) == set(ordered_values), (
        "Stage form choice order must cover exactly the model field's "
        "existing choice values - got model values "
        f"{sorted(str(v) for v in by_value)} vs ordered values "
        f"{sorted(str(v) for v in ordered_values)}."
    )
    return [(value, by_value[value]) for value in ordered_values]


class OrganisationProfileStage1Form(forms.ModelForm):
    """
    Stage 1 - Your Business (M008B-STAGES-1-3-CATALOGUE.md Stage 1,
    questions 1.1-1.5). Exactly these five fields - every one of them
    already exists on `OrganisationProfile` (WI1 landed `sector`,
    `commercial_security_driver`'s choice conversion, and confirmed
    `receives_security_questionnaires` already existed) - no new field, no
    migration.
    """

    class Meta:
        model = OrganisationProfile
        fields = [
            "legal_trading_name",
            "sector",
            "staff_count",
            "commercial_security_driver",
            "receives_security_questionnaires",
        ]
        labels = {
            "legal_trading_name": "What is your business's legal or trading name?",
            "sector": "Which best describes what your business does?",
            "staff_count": "Approximately how many people work at the business?",
            "commercial_security_driver": "Why are you working on security now?",
            "receives_security_questionnaires": (
                "Do customers or suppliers ever ask you to complete "
                "security questionnaires?"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

        # M008B §1.2/§1.4: catalogue option order, "Not sure yet" last -
        # see `_choices_in_order`'s own docstring for why this is a form-
        # layer-only reorder, not a model change.
        self.fields["sector"].choices = _choices_in_order(
            self.fields["sector"].choices,
            [
                SECTOR_PROFESSIONAL_CONSULTING,
                SECTOR_RETAIL_ECOMMERCE,
                SECTOR_FINANCIAL_ACCOUNTING,
                SECTOR_HEALTHCARE_CARE,
                SECTOR_TECHNOLOGY_SOFTWARE,
                SECTOR_MANUFACTURING_LOGISTICS,
                SECTOR_CONSTRUCTION_TRADES,
                SECTOR_EDUCATION_TRAINING,
                SECTOR_LEGAL_SERVICES,
                SECTOR_HOSPITALITY,
                SECTOR_OTHER,
                SECTOR_NOT_SURE,
            ],
        )
        self.fields["commercial_security_driver"].choices = _choices_in_order(
            self.fields["commercial_security_driver"].choices,
            [
                DRIVER_CUSTOMER_SUPPLIER,
                DRIVER_SENSITIVE_DATA,
                DRIVER_CERTIFICATION_CONTRACT,
                DRIVER_GENERAL_RISK,
                DRIVER_NOT_SURE,
            ],
        )
        # M008B §1.5: "presented to the customer as Yes / No / Not sure" -
        # the field's existing TRI_STATE_CHOICES label for UNKNOWN ("Not
        # confirmed") is overridden to "Not sure" for this question only,
        # matching M008C-UX-FLOW-DESIGN.md §4's "Not sure" as the one
        # customer-facing phrase for every not-yet-confirmed answer in this
        # guided journey. The stored value is unchanged ("unknown").
        self.fields["receives_security_questionnaires"].choices = [
            (YES, "Yes"),
            (NO, "No"),
            (UNKNOWN, "Not sure"),
        ]

    def clean_legal_trading_name(self):
        name = self.cleaned_data["legal_trading_name"].strip()
        if not name:
            raise forms.ValidationError(
                "Legal/trading name is required and cannot be empty."
            )
        return name


class OrganisationProfileStage2SupplementaryForm(forms.ModelForm):
    """
    Stage 2 - Your People & Workplaces (M008B-STAGES-1-3-CATALOGUE.md
    Stage 2), the two NEW dedicated facts this stage owns directly
    (§2.3 "People with system access", §2.4 "Remote/offsite access").

    Work pattern/workplaces (§2.1-2.2) and governance roles (§2.5) are
    deliberately NOT fields on this form - Stage 2 reuses the existing
    `workplace` and `governance` apps' own, already-structured flows
    unchanged (organisations/views.py's stage2 view links out to them; see
    this dispatch's report for the "link out, come back" judgement call).
    """

    class Meta:
        model = OrganisationProfile
        fields = ["people_with_system_access_count", "has_remote_or_offsite_access"]
        labels = {
            "people_with_system_access_count": (
                "How many people - including contractors or anyone else, "
                "not just staff - have access to your business systems or "
                "accounts?"
            ),
            "has_remote_or_offsite_access": (
                "Does anyone access business systems or data from outside "
                "your normal workplace(s), even occasionally - for "
                "example from home, while travelling, or on a personal "
                "device?"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)
        # M008B §2.4's explicit per-option label table
        # (OFFSITE_ACCESS_YES/NO/NOT_SURE) - full custom wording for every
        # option, not just the UNKNOWN relabel §1.5 needed above. Stored
        # values are unchanged ("yes"/"no"/"unknown").
        self.fields["has_remote_or_offsite_access"].choices = [
            (YES, "Yes, at least sometimes"),
            (NO, "No, never"),
            (UNKNOWN, "Not sure"),
        ]


class OrganisationProfileStage3Form(forms.ModelForm):
    """
    Stage 3 - Your Technology & Data (M008B-STAGES-1-3-CATALOGUE.md Stage
    3, questions 3.1-3.6 - 3.7 "Key assets" links out to the existing
    `key_assets` app, same pattern as Stage 2's links, and is not a field
    on this form). Every option set here is explicitly unchanged from the
    model's own existing choices per the catalogue's own wording ("unchanged"
    appears against 3.1, 3.2, 3.3, 3.4, 3.5, 3.6) - no choice-order override
    needed, unlike Stage 1's sector/driver fields.
    """

    class Meta:
        model = OrganisationProfile
        fields = [
            "productivity_platform",
            "primary_cloud_provider",
            "endpoint_management",
            "develops_hosts_own_software",
            "handles_personal_data",
            "handles_confidential_business_data",
            "handles_payment_card_data",
            "handles_special_category_data",
            "cyber_essentials_status",
            "iso27001_status",
        ]
        labels = {
            "productivity_platform": "Which productivity/email platform do you mainly use?",
            "primary_cloud_provider": (
                "Do you use any cloud infrastructure providers - for "
                "example for hosting, servers or storage - beyond your "
                "productivity platform?"
            ),
            "endpoint_management": "How are the devices staff use for work managed?",
            "develops_hosts_own_software": (
                "Does your business develop or host its own software or "
                "service - for example a product you sell, or a "
                "customer-facing application?"
            ),
            "handles_personal_data": "Personal data about customers or individuals",
            "handles_confidential_business_data": (
                "Confidential business information (e.g. financial "
                "records, contracts)"
            ),
            "handles_payment_card_data": "Payment card data",
            "handles_special_category_data": (
                "Special category data (e.g. health, biometric, or "
                "similarly sensitive personal data)"
            ),
            "cyber_essentials_status": "Cyber Essentials",
            "iso27001_status": "ISO 27001",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)
