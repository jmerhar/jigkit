"""The web app manifest: what a phone needs to add the application to its home screen."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from fastapi.responses import JSONResponse

#: The PNG icons a manifest lists, by size; the largest is also offered as maskable.
ICON_SIZES = (192, 512)


def preferred_language(accept_language: str | None, languages: Iterable[str], default: str) -> str:
    """The first of ``languages`` an Accept-Language header asks for, by primary subtag.

    ``pt-BR`` and ``pt`` both choose ``pt-PT`` when that is the offered Portuguese. Quality
    values are not weighed; browsers list languages in order of preference anyway.
    """
    offered = {language.split("-")[0].lower(): language for language in languages}
    for part in (accept_language or "").split(","):
        tag = part.split(";")[0].strip().lower()
        if not tag:
            continue
        match = offered.get(tag.split("-")[0])
        if match is not None:
            return match
    return default


def web_manifest(
    *,
    name: str,
    description: str,
    lang: str,
    background_color: str,
    theme_color: str,
    short_name: str | None = None,
    icon: str = "/icons/icon-{size}.png",
) -> dict[str, object]:
    """A manifest for an application served from the root of its origin.

    ``icon`` is a path pattern with ``{size}``. The largest icon is offered as maskable too: an
    icon drawn to keep to its centre survives a launcher's crop whole.
    """
    icons: list[Mapping[str, str]] = [
        {"src": icon.format(size=s), "sizes": f"{s}x{s}", "type": "image/png", "purpose": "any"}
        for s in ICON_SIZES
    ]
    largest = max(ICON_SIZES)
    icons.append(
        {
            "src": icon.format(size=largest),
            "sizes": f"{largest}x{largest}",
            "type": "image/png",
            "purpose": "maskable",
        }
    )
    return {
        "name": name,
        "short_name": short_name or name,
        "description": description,
        "lang": lang,
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": background_color,
        "theme_color": theme_color,
        "icons": icons,
    }


def manifest_response(manifest: Mapping[str, object]) -> JSONResponse:
    """The manifest as a response a browser will re-check on every load.

    The browser fetches it itself, with no session, so it varies by Accept-Language rather than
    by account; and an application that can be renamed must not leave the old name cached on a
    home screen.
    """
    return JSONResponse(
        dict(manifest),
        media_type="application/manifest+json",
        headers={
            "Cache-Control": "no-cache",
            "Content-Language": str(manifest.get("lang", "")),
            "Vary": "Accept-Language",
        },
    )
