"""The ``detail`` codes an application answers when it refuses a request for want of a login or
of first-run setup, which ``@jmerhar/jigkit/api`` names the same way, so an interface can tell
them apart from every other refusal. It imports nothing.
"""

#: 401: the request needs a logged-in session and has none.
NOT_AUTHENTICATED = "not_authenticated"

#: 409: the application has no administrator yet, and first-run setup comes first.
SETUP_REQUIRED = "setup_required"

__all__ = ["NOT_AUTHENTICATED", "SETUP_REQUIRED"]
