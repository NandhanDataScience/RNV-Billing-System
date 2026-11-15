<<<<<<< HEAD
# RNV STORES — Billing & Inventory Website

A responsive Flask + SQLite point-of-sale website inspired by the supplied billing-screen reference. It includes login, product/inventory management, cart checkout, sales history and Excel export.

## Included
- Login authentication with Werkzeug password hashing and Flask-Login sessions.
- SQLite database created automatically as `rnv_stores.db`.
- Product catalogue: create/edit/hide products, set category, selling price, cost price, stock and upload product images.
- Product image backgrounds are removed automatically on the local server; processed cutouts are stored as transparent PNGs.
- Product search and category filtering on the billing screen.
- POS cart with quantity controls, stock validation and invoice checkout.
- Each sold product line is saved separately. Repeat purchases by the same customer create new sale records and do not overwrite earlier transactions.
- Excel export with the requested columns: Date/Time, Name of the Product, Actual Price, Quantity, Cost, Profit.
- Historical sales use price/cost snapshots, so editing a product later does not change old transactions.

## Run on Windows (VS Code)

1. Install Python 3.11+.
2. Open this folder in VS Code.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```

4. Install packages:

   ```powershell
   pip install -r requirements.txt
   ```

5. Set credentials before the first run (PowerShell example):

   ```powershell
   $env:RNV_SECRET_KEY = "use-a-long-random-secret"
   $env:RNV_ADMIN_USER = "admin"
   $env:RNV_ADMIN_PASSWORD = "Use-A-Strong-Password-Here"
   ```

6. Start the website:

   ```powershell
   python app.py
   ```

7. Open `http://127.0.0.1:5000` and sign in with the username/password you configured.

The first product image upload downloads the background-removal model once. The model runs locally on the server; uploaded images are not sent to an external background-removal service.

**First-run note:** If you do not set environment variables, the demo login is `admin` / `ChangeMe123!`. Set a strong password before using real store data. The first user is created when the database is initialized. If you change the environment password after the user has already been created, it will not automatically overwrite the existing password.

## Excel column definitions
- **Date/Time:** timestamp of the invoice.
- **Name of the Product:** product name saved at checkout.
- **Actual Price:** selling price per unit at the time of sale.
- **Quantity:** units sold in that line item.
- **Cost:** unit purchase cost × quantity.
- **Profit:** (selling price − unit purchase cost) × quantity.

The workbook contains one row per product line sold. The same product/customer can appear on multiple rows across multiple purchases, preserving transaction history.

## Database tables
- `user`: login account and password hash.
- `product`: current product catalogue, pricing, image filename and stock.
- `sale`: invoice header, customer, date/time and total.
- `sale_item`: individual sold product lines, with price/cost snapshots.

## Important before public deployment
This is a local starter application, not a production deployment package. Before exposing it to the internet, use HTTPS, a strong secret key, a production WSGI server, secure database backups, restricted admin access and a proper server-side environment configuration. Consider PostgreSQL for a multi-device/multi-user store deployment. Never commit the database, uploaded customer data, or secrets to GitHub.

## Design notes
The store brand uses Great Vibes (bold black) and the rest of the interface uses Abril Fatface, matching the supplied font references. Google Fonts are loaded online; local fallback fonts are provided by the browser if offline.
=======
# RNV-Billing-System
Billing system for my own shop.
>>>>>>> 4c3917219a9385842a587361c723f818b6ee6d05
