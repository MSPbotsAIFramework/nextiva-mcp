from .._json import error_envelope

NO_TOKEN = error_envelope(
    "not_configured",
    "No Nextiva credentials. Send the X-Nextiva-Username and X-Nextiva-Password headers.",
    False,
)
