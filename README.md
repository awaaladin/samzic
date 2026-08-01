# Samzic Foods Empire

A fullstack Django restaurant ordering system with session-based cart, user authentication, and order management. Built with Django Templates, Tailwind CSS (CDN), and SQLite (structured for PostgreSQL).

## Features

- **Menu browsing** — category filter, search, pagination
- **Session cart** — add, update, remove, view totals with delivery fee
- **User accounts** — signup, login, profile with delivery address
- **Checkout** — prefilled from profile, order placement with atomic transaction
- **Order history** — list, detail, status tracking (pending → confirmed → delivered)
- **Payment abstraction** — Pay on Delivery active; Paystack seam ready
- **Marketing pages** — About, Catering quote form, Contact message form
- **Django Admin** — manage categories, food items, orders, catering/contact enquiries
- **Error pages** — custom 404 (extends base) and standalone 500

## Tech Stack

- **Django 5.1.7** / Python 3.13+
- **Pillow** (image uploads)
- **django-environ** (`.env` configuration)
- **Tailwind CSS** (CDN in development)
- **SQLite** (dev) → PostgreSQL (production, one env var swap)

## Project Structure

```
restura/
├── accounts/       # Signup, login, profile (UserProfile model)
├── menu/           # Category, FoodItem models; home, menu, detail views
├── cart/           # Session-based Cart class; add/update/remove views
├── orders/         # Order, OrderItem models; checkout, list, detail; payments.py
├── pages/          # About, Catering, Contact pages and forms
├── config/         # Settings, root URLs, context processors, error views
├── templates/      # Base template, app templates, partials/_field.html
├── static/
│   ├── css/app.css # Project styles (Tailwind via CDN; see Production note below)
│   └── img/        # hero.jpg, chef.jpg for marketing pages
├── media/
│   └── food_items/ # Nine product photos shipped with the project
├── manage.py
├── requirements.txt
├── .env.example
└── smoke_test.py   # Throwaway verification script (delete after use)
```

## Local Setup

### 1. Clone and install

```bash
git clone <your-repo-url>
cd restura
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

`.env` is git-ignored. The defaults work for local development:

```env
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=django-insecure-dev-only-key-change-in-production
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1]

# Leave DATABASE_URL unset to use SQLite (db.sqlite3).
# For PostgreSQL: DATABASE_URL=postgres://user:pass@localhost:5432/dbname
```

### 3. Migrate and seed

```bash
python manage.py migrate
python manage.py seed_menu
```

`seed_menu` is idempotent (safe to re-run). It creates 7 categories and 28 food items, attaching the 9 photos that ship in `media/food_items/`. Dishes without a photo show a placeholder card.

To wipe the menu and reseed from scratch:

```bash
python manage.py seed_menu --flush
```

Orders are never touched by `seed_menu`.

### 4. Create a superuser

```bash
python manage.py createsuperuser
```

### 5. Run the development server

```bash
python manage.py runserver
```

Visit:

- **Homepage**: http://127.0.0.1:8000/
- **Menu**: http://127.0.0.1:8000/menu/
- **Admin**: http://127.0.0.1:8000/admin/

## Django Admin Tour

Log in at `/admin/` with your superuser account.

- **Menu → Categories** — name, slug (auto-generated), description, display_order
- **Menu → Food items** — name, price, image, category, available/featured toggles
- **Orders → Orders** — reference, user, status (pending/confirmed/delivered/cancelled), totals, created_at
- **Orders → Order items** — historical snapshots (name, price, quantity per order)
- **Pages → Catering requests** — quote enquiries from `/catering/`
- **Pages → Contact messages** — general enquiries from `/contact/`
- **Accounts → User profiles** — full_name, phone_number, delivery_address (created on signup)

## URL Structure

```
/                           # Home (featured items)
/menu/                      # Full menu (paginated, searchable, filterable)
/menu/<slug>/               # Food item detail
/cart/                      # View cart
/orders/checkout/           # Place order (login required)
/orders/                    # Order history (login required)
/orders/<reference>/        # Order detail (owner-scoped)
/orders/success/<reference>/# Order success page
/about/                     # Our story, stats
/catering/                  # Catering packages + quote form
/contact/                   # Contact info + message form
/accounts/signup/
/accounts/login/
/accounts/profile/          # Edit delivery details
/admin/
```

## Configuration Knobs

Adjust in `config/settings.py`:

```python
SITE_NAME = "Samzic Foods Empire"
SITE_TAGLINE = "Hot, homemade Nigerian meals delivered fast."
SITE_PHONE = "+234 800 000 0000"
DELIVERY_FEE = "500.00"              # ₦500
FREE_DELIVERY_THRESHOLD = "20000.00" # Free delivery over ₦20,000
MENU_PAGE_SIZE = 9                   # Items per page
TIME_ZONE = "Africa/Lagos"
```

These are exposed to templates via `config/context_processors.py`.

## Cart Implementation

Session-based. The cart stores only `{item_id: quantity}` in `request.session["cart"]`. Prices are read live from the database on every request, so a price change in the admin is reflected immediately.

Maximum quantity per item: see `cart/cart.py` (`MAX_QUANTITY_PER_ITEM = 20`).

## Orders

- **Atomic placement**: `orders/services.py` wraps order creation in `@transaction.atomic`; the cart is cleared only after a successful database write.
- **Historical snapshots**: `OrderItem` stores the dish name and price at order time, so an order remains correct even if the `FoodItem` is later edited or deleted.
- **Reference format**: `SFE-XXXXXX` (6-character alphanumeric, uppercase, excludes ambiguous chars).
- **Status flow**: `PENDING` (placed) → `CONFIRMED` (kitchen accepts) → `DELIVERED` (rider completes), or `CANCELLED`.

The status trail on the order detail page is driven by `Order.status_trail` (a property in `orders/models.py`).

## Payment Gateway Seam

Right now only **Pay on Delivery** is active. The checkout form's payment-method radio buttons are built from `Order.PaymentMethod.choices`, and checkout talks to gateways through `orders/payments.py:get_gateway()`, never directly.

### Adding Paystack Later

1. Uncomment `requests==2.32.3` in `requirements.txt` and `pip install requests`.
2. Add `PAYSTACK_PUBLIC_KEY` / `PAYSTACK_SECRET_KEY` to `.env` and read them in `config/settings.py`.
3. Uncomment the `PaystackGateway` class in `orders/payments.py` and fill in the `initiate` method (see the inline docstring for details — the API call, kobo conversion, and callback URL are all documented there).
4. Register it in the `GATEWAYS` dict and add its key to `Order.PaymentMethod`.
5. Add a webhook/callback view that verifies the transaction with Paystack, then calls `order.mark_paid()`.

No other file needs to change. The checkout form will automatically render the new radio button from the updated `PaymentMethod` choices.

## Previewing Error Pages

Django only routes to custom error handlers when `DEBUG=False`. To preview them locally:

1. Temporarily set `DJANGO_DEBUG=False` in `.env`.
2. Run `python manage.py collectstatic --noinput` (Django won't serve static files with debug off unless you add `whitenoise`).
3. Restart the server and visit a broken URL for 404, or trigger a 500 by temporarily breaking a view.
4. Set `DJANGO_DEBUG=True` again when done.

**Note**: `templates/404.html` extends `base.html` (nav and context are trustworthy when only the URL is wrong). `templates/500.html` is fully standalone with inline styles and no context processors, so it renders even when the database or settings are broken.

## PostgreSQL Migration

SQLite works for development and small-scale deployment. To switch to PostgreSQL:

1. Uncomment `psycopg[binary]==3.2.4` in `requirements.txt` and `pip install psycopg[binary]`.
2. Set `DATABASE_URL` in `.env`:

   ```env
   DATABASE_URL=postgres://samzic:password@localhost:5432/samzic
   ```

3. Restart the app. `django-environ` reads `DATABASE_URL` and configures `DATABASES` automatically (see `config/settings.py`).

No code change required.

## Production Checklist

Before deploying:

- [ ] Set `DJANGO_DEBUG=False` in production `.env`
- [ ] Generate a strong `DJANGO_SECRET_KEY` (`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] Set `DJANGO_ALLOWED_HOSTS` to your domain(s): `yourdomain.com,www.yourdomain.com`
- [ ] Set `DJANGO_CSRF_TRUSTED_ORIGINS` if behind a proxy: `https://yourdomain.com`
- [ ] Migrate to PostgreSQL via `DATABASE_URL`
- [ ] Configure static file serving (uncomment `whitenoise==6.9.0` in `requirements.txt` and add it to `MIDDLEWARE`, or serve `staticfiles/` via nginx/S3)
- [ ] Configure media file storage (serve `media/` via nginx/S3, or use `django-storages`)
- [ ] Run `python manage.py collectstatic` to gather static files into `staticfiles/`
- [ ] Update `SITE_PHONE` in `settings.py` to your real support number
- [ ] If using Paystack, add live keys to `.env` and switch the gateway from test to live mode

## Tailwind CSS in Production

Right now `templates/base.html` loads Tailwind via CDN:

```html
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
```

This is instant in development but not recommended for production (no caching, custom config lives in an inline `<script>`, and Tailwind's CDN build is larger than a compiled one).

For production, either:

1. **Keep the CDN** (simplest, zero build step), or
2. **Compile Tailwind locally**:
   - Install Node.js + Tailwind CLI: `npm install -D tailwindcss`
   - Add a `tailwind.config.js` that scans your templates
   - Build: `npx tailwindcss -o static/css/tailwind.css --minify`
   - Replace the CDN `<script>` in `base.html` with `<link rel="stylesheet" href="{% static 'css/tailwind.css' %}">`
   - Re-run the build command after template changes

The custom Tailwind config (ink/ember/bone colors, `.display`/`.lift`/`.reveal` utilities, IntersectionObserver script) currently lives in an inline `<script>` at the bottom of `base.html`. If you compile Tailwind, move that config into `tailwind.config.js` and the observer script into a separate `.js` file.

`static/css/app.css` exists but is currently unlinked (no `<link>` in `base.html`). It's reserved for non-Tailwind overrides if you need them.

## Testing

A throwaway smoke test lives in `smoke_test.py` (62 checks covering all routes, cart flow, signup, checkout, order placement, and the enquiry forms). Run it after seeding:

```bash
python smoke_test.py
```

Expected output: `All smoke tests passed.`

Delete `smoke_test.py` after verifying — it's not part of the app and was only written to confirm the design migration worked.

For ongoing testing, Django's built-in test framework is configured but no tests are written yet. Each app has a `tests.py` placeholder.

## License

Specify your license here (e.g., MIT, proprietary, etc.).

## Credits

- **Design system**: Adapted from [savory-serve](https://github.com/awaaladin/savory-serve) (ink/ember/bone palette, Bricolage Grotesque + Inter fonts)
- **Product photos**: Nine dishes ship in `media/food_items/` (jollof.jpg, friedrice.jpg, egusi.jpg, amala.jpg, peppersoup.jpg, suya.jpg, asun.jpg, smallchops.jpg, moimoi.jpg)
- **Django**: [https://www.djangoproject.com/](https://www.djangoproject.com/)
- **Tailwind CSS**: [https://tailwindcss.com/](https://tailwindcss.com/)
#   s a m z i c  
 