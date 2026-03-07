_VALID_PER_PAGE = (25, 50, 100, 500)
_DEFAULT_PER_PAGE = 50


def get_page_args(request):
    """Parse and validate page/per_page from a Flask request."""
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", _DEFAULT_PER_PAGE) or _DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = _DEFAULT_PER_PAGE
    if per_page not in _VALID_PER_PAGE:
        per_page = _DEFAULT_PER_PAGE
    return page, per_page


def paginate(items, page, per_page):
    """Slice a list for the requested page and return a pagination dict."""
    if per_page not in _VALID_PER_PAGE:
        per_page = _DEFAULT_PER_PAGE
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return {
        "items": items[start : start + per_page],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }
