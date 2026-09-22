PRODUCT_NAME = "Infosecurs"


def product(request):
    """Make the product name available to every template without repeating it."""
    return {"product_name": PRODUCT_NAME}
