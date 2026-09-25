"""Structured delivery addresses.

A single free-text box gets riders "Lekki" and nothing else, so the address is
captured in parts — street, area, city, state, landmark — and stored that way on
both the profile and each order. ``delivery_address`` (the full one-line text)
is still kept on both models, built from the parts by :func:`compose_address`:
older orders that pre-date the breakdown, templates, exports and the admin all
keep working off that single string.
"""

NIGERIAN_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "FCT (Abuja)", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina",
    "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo",
    "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
]
STATE_CHOICES = [(name, name) for name in NIGERIAN_STATES]

# Field names shared by Profile and Order, in the order they are shown.
ADDRESS_FIELDS = ("address_line", "area", "city", "state", "landmark")


def compose_address(address_line="", area="", city="", state="", landmark=""):
    """One readable line for the rider: '12 Palm Ave, Lekki Phase 1, Lagos, Lagos (Near Shoprite)'."""
    parts = [p.strip() for p in (address_line, area, city, state) if p and p.strip()]
    text = ", ".join(parts)
    if landmark and landmark.strip():
        text = f"{text} (Near {landmark.strip()})" if text else f"Near {landmark.strip()}"
    return text
