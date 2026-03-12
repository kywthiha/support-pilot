"""Django forms for agent management and authentication."""

from django import forms
import re


class EmailRegistrationForm(forms.Form):
    """Registration form using email as the unique identifier."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "you@company.com",
            "autofocus": True,
        }),
    )
    password1 = forms.CharField(
        label="Password",
        min_length=8,
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Minimum 8 characters",
        }),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Repeat your password",
        }),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        from .firestore_client import _get_db
        db = _get_db()
        users_ref = db.collection("users")
        query = users_ref.where("email", "==", email).limit(1)
        if list(query.stream()):
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned



class EmailLoginForm(forms.Form):
    """Login form using email and password."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "you@company.com",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your password",
        }),
    )


class AgentForm(forms.Form):
    """Form for creating and editing agents."""

    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. CloudSupport",
        }),
    )
    agent_key = forms.SlugField(
        max_length=100,
        required=False,
        help_text="URL-safe identifier. Auto-generated from name if left blank.",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. cloud-support",
        }),
    )

    def clean_name(self):
        name = self.cleaned_data.get("name", "")
        if not re.match(r'^[a-zA-Z0-9]+$', name):
            raise forms.ValidationError("Agent name must contain only letters and numbers (no spaces).")
        return name

    def clean_agent_key(self):
        agent_key = self.cleaned_data.get("agent_key", "")
        if agent_key:
            if not re.match(r'^[a-z0-9\-]+$', agent_key):
                raise forms.ValidationError("Agent key must contain only lowercase letters, numbers, and hyphens.")
        return agent_key

    description = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "placeholder": "Short description of what this agent does",
        }),
    )
    instruction = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 15,
            "placeholder": "Full system prompt / instruction for the agent...",
        }),
        help_text="The agent's system instruction. Supports markdown-style formatting.",
    )
    voice_name = forms.ChoiceField(
        choices=[
            ("Kore", "Kore"),
            ("Puck", "Puck"),
            ("Charon", "Charon"),
            ("Fenrir", "Fenrir"),
            ("Aoede", "Aoede"),
            ("Leda", "Leda"),
            ("Orus", "Orus"),
            ("Zephyr", "Zephyr"),
        ],
        initial="Kore",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # ── Google Search Settings ──────────────────────────────────────
    google_search_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
        help_text="Enable Google Search tool for this agent.",
    )

    search_domains = forms.CharField(
        max_length=500,
        required=False,
        help_text="Comma-separated list of domains (e.g. cloud.google.com/docs, docs.example.com).",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. cloud.google.com/docs, docs.example.com",
        }),
    )

    # ── Knowledge Base Settings ─────────────────────────────────────
    knowledge_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
        help_text="Enable custom knowledge base (RAG) for this agent.",
    )


class DocumentUploadForm(forms.Form):
    """Form for uploading documents to an agent's RAG corpus."""

    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            "class": "form-control",
            "accept": ".txt,.pdf,.md,.html,.csv,.json,.docx",
        }),
        help_text="Supported: TXT, PDF, MD, HTML, CSV, JSON, DOCX (max 10MB)",
    )
