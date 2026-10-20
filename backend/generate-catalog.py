import random
import sqlite3

random.seed(42)  

CITIES = ["Pune", "Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad"]


MODELS = [
    ("Tata", "Ace Gold", "mini_truck", ["diesel", "petrol", "cng"], 550000, 750, 1610),
    ("Tata", "Ace EV", "mini_truck", ["electric"], 800000, 600, 1610),
    ("Mahindra", "Jeeto", "mini_truck", ["diesel", "cng"], 450000, 715, 1500),
    ("Maruti", "Super Carry", "mini_truck", ["petrol", "cng"], 650000, 740, 1500),
    ("Ashok Leyland", "Dost", "pickup", ["diesel"], 780000, 1250, 2800),
    ("Mahindra", "Bolero Pickup", "pickup", ["diesel"], 900000, 1500, 2900),
    ("Tata", "Yodha", "pickup", ["diesel"], 900000, 1700, 3000),
    ("Eicher", "Pro 2049", "truck", ["diesel"], 1500000, 2900, 4995),
    ("Tata", "407", "truck", ["diesel"], 1400000, 2300, 4670),
    ("Ashok Leyland", "Partner", "truck", ["diesel"], 1900000, 4000, 6950),
    ("Piaggio", "Ape Xtra LDX", "three_wheeler", ["diesel"], 300000, 600, 1300),
    ("Bajaj", "Maxima Cargo", "three_wheeler", ["cng", "diesel"], 280000, 500, 1200),
    ("Mahindra", "Treo Zor", "three_wheeler", ["electric"], 360000, 600, 1250),
    ("Maruti", "Eeco Cargo", "van", ["petrol", "cng"], 500000, 550, 1510),
    ("Tata", "Winger Cargo", "van", ["diesel"], 1100000, 1000, 3000),
]

conn = sqlite3.connect("catalog.db")
conn.execute("DROP TABLE IF EXISTS vehicles")
conn.execute("""
CREATE TABLE vehicles (
    id INTEGER PRIMARY KEY,
    make TEXT, model TEXT, year INTEGER, price INTEGER, km_driven INTEGER,
    fuel TEXT, payload_kg INTEGER, gvw_kg INTEGER, body_type TEXT,
    city TEXT, papers_verified INTEGER
)""")

print('Exxecuting query.....')

for _ in range(150):
    make, model, body, fuels, new_price, payload, gvw = random.choice(MODELS)
    year = random.randint(2015, 2024)
    age = 2026 - year
    price = int(round(new_price * (0.88 ** age) * random.uniform(0.85, 1.15), -3))
    km = int(round(age * random.randint(8000, 25000), -2))
    conn.execute(
        "INSERT INTO vehicles (make, model, year, price, km_driven, fuel, payload_kg,"
        " gvw_kg, body_type, city, papers_verified) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (make, model, year, price, km, random.choice(fuels), payload, gvw, body,
         random.choice(CITIES), 1 if random.random() < 0.8 else 0),
    )

conn.commit()
print("rows:", conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0])
conn.close()