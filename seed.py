import sqlite3
import random
import numpy as np
from datetime import datetime, timedelta
import pandas as pd

random.seed(42)
np.random.seed(42)

def init_db():
    conn = sqlite3.connect('interior_revolutions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, budget REAL, 
                    status TEXT DEFAULT 'Live', start_date TEXT, end_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS staff (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, password TEXT, role TEXT, 
                    day_rate REAL, contracted_hours REAL, employment_type TEXT, cis_rate REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS shifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, worker_id INTEGER, project TEXT, hours REAL, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS project_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, project_name TEXT, item_type TEXT, item_name TEXT, quantity REAL, total_cost REAL)''')
    
    cols = ["payment_status", "original_quote", "ai_suggested_quote", "final_accepted_quote", "tier", "amount_received"]
    for col in cols:
        try: c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except: pass
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# 1. THE 100-ITEM MASTER CATALOGUE
# ==============================================================================
CATALOGUE = {
    # TIER 1 MATERIALS (Low Cost, Low Margin)
    "Trade Emulsion - White (10L)": 22.00, "Trade Emulsion - Magnolia (10L)": 22.00, "Standard Gloss Paint (5L)": 18.50,
    "Basic Laminate Flooring (sqm)": 15.00, "Standard Skirting Board (3m)": 12.00, "Basic MDF Sheet (2400x1200)": 28.00,
    "Standard Plasterboard (8x4)": 10.50, "Multi-Finish Plaster (25kg)": 8.00, "Standard PVA Primer (5L)": 14.00,
    "Basic White Sockets (Double)": 4.50, "Basic Light Switch (Single)": 3.00, "Standard Ceiling Rose & Pendant": 6.50,
    "Basic Door Handle (Aluminium)": 9.00, "Standard Internal Door (Hollow)": 35.00, "Standard Door Hinges (Pair)": 4.00,
    "Basic Bath Sealant (White)": 6.00, "Standard Ceramic Wall Tile (sqm)": 18.00, "Basic Tile Adhesive (20kg)": 15.00,
    "Standard Grout (White 5kg)": 9.00, "Basic Plywood (9mm 8x4)": 22.00, "Standard Wood Glue (1L)": 8.50,
    "Basic Decorators Caulk": 2.50, "Standard Masking Tape (50m)": 4.00, "Basic Dust Sheets (Cotton)": 12.00,
    "Standard Paint Rollers (Pack)": 14.00, "Basic Paint Brushes (Set)": 9.00, "Standard Sandpaper (Roll)": 16.00,
    "Basic Screws (Box of 200)": 5.00, "Standard Wall Plugs (Box)": 4.00, "Basic Expanding Foam": 7.50,
    "Standard Silicone Sealant (Clear)": 6.50, "Basic Tap Washer Set": 3.00, "Standard Radiator Valve": 12.00,

    # TIER 2 MATERIALS (Medium Cost, Solid Margin)
    "Farrow & Ball Estate Emulsion (5L)": 85.00, "Dulux Heritage Velvet (5L)": 65.00, "Zinsser BIN Primer (5L)": 75.00,
    "Engineered Oak Flooring (sqm)": 48.00, "Luxury Vinyl Tile (Karndean sqm)": 42.00, "Premium Torus Skirting (3m)": 24.00,
    "Moisture Resistant MDF (8x4)": 45.00, "Soundblock Plasterboard (8x4)": 22.00, "Thistle Bonding Coat (25kg)": 14.00,
    "Brushed Steel Sockets (Double)": 18.00, "Dimmer Switch (Stainless)": 25.00, "LED Downlights (Fire Rated)": 15.00,
    "Solid Brass Door Handle": 45.00, "Solid Oak Internal Door": 140.00, "Heavy Duty Ball Bearing Hinges": 12.00,
    "Premium Anti-Mould Silicone": 12.00, "Porcelain Floor Tile (sqm)": 35.00, "Flexible Tile Adhesive (20kg)": 28.00,
    "Epoxy Grout (Coloured 5kg)": 35.00, "Birch Plywood (18mm 8x4)": 65.00, "Polyurethane Wood Glue": 15.00,
    "Premium Decorators Filler": 18.00, "FrogTape Delicate (50m)": 9.00, "Heavy Duty Polythene Roll": 25.00,
    "Purdy Paint Brush Set": 45.00, "Festool Sanding Discs (Box)": 35.00, "Spax Premium Screws (Box)": 18.00,
    "Fischer DuoPower Plugs": 12.00, "Fire Rated Expanding Foam": 15.00, "Thermostatic Radiator Valve": 28.00,
    "Designer Vertical Radiator": 220.00, "Grohe Basin Mixer Tap": 110.00, "Standard Shower Tray (Stone Resin)": 140.00,
    "Frameless Shower Enclosure": 350.00, "Wall Hung Toilet Frame": 180.00, "Ceramic Belfast Sink": 250.00,

    # TIER 3 MATERIALS (Luxury / Bespoke)
    "Bespoke Structural Oak Beam": 850.00, "Italian Calacatta Marble (sqm)": 280.00, "Herringbone Parquet Oak (sqm)": 110.00,
    "Custom Joinery Wardrobe Carcass": 1200.00, "Bespoke Shaker Kitchen Doors (Set)": 3500.00, "Corian Worktop (Linear Metre)": 450.00,
    "Quooker Boiling Water Tap": 1150.00, "Gaggenau Oven Package": 4500.00, "Bora Induction Hob with Downdraft": 2800.00,
    "Lutron Smart Lighting Hub": 850.00, "Buster & Punch Toggle Switch": 65.00, "Buster & Punch Knurled Door Handle": 120.00,
    "Crittall Internal Glass Partition": 3200.00, "Underfloor Heating Mat (sqm)": 65.00, "Smart Heating Thermostat (Nest)": 220.00,
    "Lusso Stone Freestanding Bath": 1600.00, "Crosswater Brushed Brass Shower Set": 850.00, "Bespoke Frameless Mirror with Demister": 450.00,
    "Tadelakt Plaster Finish (sqm)": 140.00, "Venetian Polished Plaster (sqm)": 180.00, "Acoustic Wall Panelling (sqm)": 110.00,
    "Bespoke Ironmongery Surcharge": 500.00, "Structural Engineer Report": 1200.00, "Architectural Drawing Service": 1800.00,
    "Marylebone Parking/Permit Surcharge": 450.00, "Scaffolding (Front Elevation)": 1500.00, "Luxury Skip Hire (Wait & Load)": 380.00,
    "Premium Project Management Fee": 2500.00, "Bespoke Staircase (Glass/Oak)": 5500.00, "Air Conditioning Unit (Concealed)": 2200.00,
    
    # LABOUR
    "Labour - General Handyman": 220.00, "Labour - Carpenter": 280.00, "Labour - Painter/Decorator": 240.00,
    "Labour - Electrician": 350.00, "Labour - Plumber": 350.00, "Labour - Master Craftsman": 450.00
}

# ==============================================================================
# 2. SETUP WORKFORCE
# ==============================================================================
conn = sqlite3.connect('interior_revolutions.db')
c = conn.cursor()

c.execute("DELETE FROM staff")
carpenters = ["Peter", "Steve", "Rob", "Superman", "Mario"]
painters = ["David", "Teddy", "Bean", "Lee", "Liam"]
labourers = ["Gary", "Voldemort", "Wonder", "Hatton", "T"]

for w in carpenters: c.execute("INSERT INTO staff (name, password, role, day_rate, contracted_hours, employment_type, cis_rate) VALUES (?, 'changeme', 'Carpenter', 180.0, 0, 'CIS', 20)", (w,))
for w in painters: c.execute("INSERT INTO staff (name, password, role, day_rate, contracted_hours, employment_type, cis_rate) VALUES (?, 'changeme', 'Painter', 150.0, 0, 'CIS', 20)", (w,))
for w in labourers: c.execute("INSERT INTO staff (name, password, role, day_rate, contracted_hours, employment_type, cis_rate) VALUES (?, 'changeme', 'Labourer', 120.0, 0, 'CIS', 20)", (w,))
c.execute("UPDATE staff SET employment_type = 'PAYE', contracted_hours = 37.5, cis_rate = 0 WHERE name IN ('Mario', 'Peter')")
c.execute("INSERT INTO staff (name, password, role, day_rate, contracted_hours, employment_type, cis_rate) VALUES ('admin', 'boss123', 'Manager', 0, 0, 'CIS', 0)")

df_staff = pd.read_sql_query("SELECT id, role FROM staff WHERE role != 'Manager'", conn)
staff_ids = df_staff['id'].tolist()

# ==============================================================================
# 3. GENERATE PROJECTS
# ==============================================================================
c.execute("DELETE FROM projects")
c.execute("DELETE FROM project_quotes")
c.execute("DELETE FROM shifts")

start_date_global = datetime(2024, 1, 1)
available_slots = [start_date_global, start_date_global, start_date_global, start_date_global]

areas = ["Baker Street", "Marylebone", "Weymouth Street", "Harley Street", "Croydon", "Enfield", "Camden", "Hackney"]
project_types = ["Fix", "Refresh", "Renovation", "Full Apartment", "Luxury Penthouse", "Studio", "Bespoke Build"]

shift_records = []
NUM_PROJECTS = 800 

print("🏗️ Generating projects...")

tier_1_mats = [k for k in CATALOGUE.keys() if "Basic" in k or "Standard" in k or "Trade" in k]
tier_2_mats = [k for k in CATALOGUE.keys() if "Premium" in k or "Oak" in k or "Farrow" in k or "Luxury" in k]
tier_3_mats = [k for k in CATALOGUE.keys() if "Bespoke" in k or "Marble" in k or "Surcharge" in k or "Smart" in k]
labour_keys = [k for k in CATALOGUE.keys() if "Labour" in k]

for i in range(NUM_PROJECTS):
    raw_budget = np.random.lognormal(mean=7.5, sigma=1.2)
    target_budget = max(250, round(float(raw_budget), -1))
    
    if target_budget < 2500:
        tier = "Tier 1 (<£2.5k)"
        margin = random.uniform(0.12, 0.18)
        duration = random.randint(1, 3)
        mat_pool = tier_1_mats
    elif target_budget < 18000:
        tier = "Tier 2 (£2.5k-£18k)"
        margin = random.uniform(0.18, 0.28)
        duration = random.randint(5, 18)
        mat_pool = tier_1_mats + tier_2_mats
    else:
        tier = "Tier 3 (£18k+)"
        margin = random.uniform(0.28, 0.45) 
        duration = random.randint(25, 80)
        mat_pool = tier_2_mats + tier_3_mats
        
    received = round(target_budget * (1 + margin), -2)
    name = f"{random.choice(areas)} {random.choice(project_types)} #{random.randint(100,9999)}"
    
    earliest_slot_index = available_slots.index(min(available_slots))
    proj_start_date = available_slots[earliest_slot_index]
    proj_end_date = proj_start_date + timedelta(days=duration)
    available_slots[earliest_slot_index] = proj_end_date + timedelta(days=1)

    # --- THE SYNC FIX: Make the most recent projects 'Live' ---
    # This ensures your Dashboard and Financials actually have active data to show.
    current_status = 'Live' if i > (NUM_PROJECTS - 10) else 'Completed'
    end_date_val = None if current_status == 'Live' else proj_end_date.strftime("%Y-%m-%d")
    received_val = 0.0 if current_status == 'Live' else received

    c.execute("""INSERT OR IGNORE INTO projects (name, budget, status, start_date, end_date, amount_received, tier) 
                 VALUES (?,?,?,?,?,?,?)""", 
              (name, target_budget, current_status, proj_start_date.strftime("%Y-%m-%d"), end_date_val, received_val, tier))

    # 4. QUOTE GENERATION
    current_quote_total = 0
    while current_quote_total < (target_budget * 0.7):
        item = random.choice(mat_pool)
        price = CATALOGUE[item]
        qty = random.randint(1, 10) if price < 50 else random.randint(1, 3)
        line_total = price * qty
        c.execute("INSERT INTO project_quotes (project_name, item_type, item_name, quantity, total_cost) VALUES (?,?,?,?,?)", 
                  (name, "Material", item, qty, line_total))
        current_quote_total += line_total
        
    while current_quote_total < target_budget:
        lab_item = random.choice(labour_keys)
        price = CATALOGUE[lab_item]
        qty = random.randint(1, 5) 
        line_total = price * qty
        c.execute("INSERT INTO project_quotes (project_name, item_type, item_name, quantity, total_cost) VALUES (?,?,?,?,?)", 
                  (name, "Labor", lab_item, qty, line_total))
        current_quote_total += line_total

    # 5. GENERATE SHIFTS
    assigned_workers = random.sample(staff_ids, k=random.randint(1, 2))
    for day_offset in range(duration):
        current_shift_date = proj_start_date + timedelta(days=day_offset)
        if current_shift_date.weekday() != 6: 
            for wid in assigned_workers:
                if random.random() < 0.9: 
                    shift_records.append((wid, name, 8.0, current_shift_date.strftime("%Y-%m-%d")))

c.executemany("INSERT INTO shifts (worker_id, project, hours, date) VALUES (?,?,?,?)", shift_records)

conn.commit()
conn.close()

print(f"✅ SEEDING COMPLETE!")