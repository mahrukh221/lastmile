"""Creates FAKE mock data for the identity, programme and payment services.

Run from the project root:   python -m scripts.seed_mock_data

Everything here is invented. CNICs start with 00000 so they can never be
mistaken for real ones. The same data is produced on every run.
"""
import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
rng = random.Random(42)  # fixed seed = same data every run

MALE = ["Muhammad", "Ahmed", "Ali", "Hassan", "Hussain", "Usman", "Bilal",
        "Imran", "Kashif", "Tariq", "Faisal", "Zubair", "Salman", "Abdul Rehman"]
FEMALE = ["Fatima", "Ayesha", "Zainab", "Maryam", "Khadija", "Sana",
          "Nasreen", "Shabana", "Rukhsana", "Bushra", "Samina", "Farida"]
LAST = ["Khan", "Shaikh", "Siddiqui", "Qureshi", "Ansari", "Malik",
        "Baloch", "Memon", "Naqvi", "Rizvi", "Hashmi", "Chaudhry"]
CITIES = ["Karachi", "Hyderabad", "Sukkur", "Lahore", "Multan", "Peshawar", "Quetta"]

# Different spellings of the same name, a classic source of bad data.
VARIANTS = {
    "Muhammad": ["Mohammad", "Muhammed", "Mohammed", "Mohd"],
    "Ahmed": ["Ahmad"],
    "Hussain": ["Hussein", "Husain"],
    "Fatima": ["Fatimah", "Fatema"],
    "Khadija": ["Khadijah", "Khadeeja"],
    "Shaikh": ["Sheikh"],
    "Siddiqui": ["Siddiqi", "Sidiqui"],
    "Qureshi": ["Quraishi", "Koreshi"],
}


def make_cnic(n: int) -> str:
    """Fake CNIC in the 5-7-1 digit shape, always starting with 00000."""
    return f"00000-{n:07d}-{n % 10}"


def random_dob() -> str:
    return f"{rng.randint(1950, 2000)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def vary_name(full_name: str) -> str:
    out = []
    for part in full_name.split():
        options = VARIANTS.get(part)
        out.append(rng.choice(options) if options else part)
    return " ".join(out)


def person(n, truth, name, dob, gender, marital, city, relative, life="alive"):
    return {
        "cnic": make_cnic(n),
        "full_name": name,
        "father_or_husband_name": relative,
        "dob": dob,
        "gender": gender,
        "marital_status": marital,
        "city": city,
        "phone": f"0300-000{n:04d}",
        "life_status": life,
        "_truth_id": truth,  # hidden: the real person behind the record
    }


identity, programme, accounts = [], {}, {}


def add_programme(p, income, household, paid=False, paid_on=None):
    programme[p["cnic"]] = {
        "programme": "Relief Programme 2026 (mock)",
        "monthly_income": income,
        "household_size": household,
        "already_paid": paid,
        "last_paid_on": paid_on,
    }


def add_account(p, status="active", holder=None):
    accounts[p["cnic"]] = {
        "account_id": f"MOCKPAY-{p['cnic'][-9:-2]}",
        "provider": "MockPay",
        "status": status,
        "holder_name": holder or p["full_name"],
    }


# ---- 1. Fixed demo personas (use these in the live demo) -------------------
personas = [
    # (n, name, dob, gender, marital, city, relative, income, household, paid, life)
    (1, "Zainab Bibi", "1968-05-12", "F", "widowed", "Karachi", "Late Abdul Rehman", 12000, 5, False, "alive"),
    (2, "Karim Baloch", "1980-09-03", "M", "married", "Hyderabad", "Ghulam Baloch", 45000, 6, False, "alive"),
    (3, "Rashid Memon", "1985-01-21", "M", "married", "Karachi", "Yusuf Memon", 25000, 4, False, "alive"),
    (4, "Nasreen Akhtar", "1972-11-30", "F", "widowed", "Sukkur", "Late Akhtar Ali", 9000, 4, True, "alive"),
    (5, "Shabana Khan", "1990-07-07", "F", "married", "Lahore", "Imran Khan", 20000, 3, False, "alive"),
    (6, "Muhammad Aslam", "1960-02-14", "M", "married", "Multan", "Late Nazir Ahmed", 15000, 5, False, "deceased"),
]
for n, name, dob, g, marital, city, rel, income, hh, paid, life in personas:
    p = person(n, f"T{n:03d}", name, dob, g, marital, city, rel, life)
    identity.append(p)
    add_programme(p, income, hh, paid, "2026-10-15" if paid else None)
    add_account(p)

# ---- 2. Random people ------------------------------------------------------
random_people = []
for i in range(36):
    n = 100 + i
    gender = rng.choice(["F", "F", "M"])
    first = rng.choice(FEMALE if gender == "F" else MALE)
    name = f"{first} {rng.choice(LAST)}"
    marital = rng.choice(["widowed", "widowed", "married", "single"]) if gender == "F" \
        else rng.choice(["married", "married", "single", "widowed"])
    relative = f"{rng.choice(MALE)} {name.split()[-1]}"
    p = person(n, f"T{n:03d}", name, random_dob(), gender, marital,
               rng.choice(CITIES), relative)
    random_people.append(p)
    identity.append(p)

# ---- 3. Duplicates: same real person, second record with other spellings ---
candidates = [p for p in random_people
              if any(part in VARIANTS for part in p["full_name"].split())]
for j, original in enumerate(rng.sample(candidates, min(6, len(candidates)))):
    n = 200 + j
    dup = person(n, original["_truth_id"], vary_name(original["full_name"]),
                 original["dob"], original["gender"], original["marital_status"],
                 original["city"], vary_name(original["father_or_husband_name"]))
    if j % 2 == 0:  # some duplicates write the date the other way round
        y, m, d = original["dob"].split("-")
        dup["dob"] = f"{d}/{m}/{y}"
    identity.append(dup)

# ---- 4. Messy records: missing fields, odd spacing and capitals ------------
for p in rng.sample(random_people, 3):
    p["dob"] = None
for p in rng.sample(random_people, 3):
    p["father_or_husband_name"] = None
for p in rng.sample(random_people, 3):
    p["full_name"] = "  " + p["full_name"].upper().replace(" ", "   ") + " "

# ---- 5. Programme and payment records for everyone -------------------------
for p in identity:
    if p["cnic"] in programme:
        continue
    if rng.random() < 0.08:        # a few people are missing from the programme data
        continue
    add_programme(p, rng.choice([8000, 12000, 15000, 22000, 30000, 38000, 55000]),
                  rng.randint(2, 8), paid=rng.random() < 0.1)
for p in identity:
    if p["cnic"] in accounts:
        continue
    roll = rng.random()
    if roll < 0.15:                # no account at all
        continue
    holder = vary_name(p["full_name"].strip()) if roll < 0.25 else None
    add_account(p, "closed" if roll > 0.95 else "active", holder)

# ---- 6. Write the files ----------------------------------------------------
DATA_DIR.mkdir(exist_ok=True)
for filename, content in [("mock_identity.json", identity),
                          ("mock_programme.json", programme),
                          ("mock_accounts.json", accounts)]:
    (DATA_DIR / filename).write_text(
        json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"identity records : {len(identity)}")
print(f"programme records: {len(programme)}")
print(f"payment accounts : {len(accounts)}")
print(f"files written to : {DATA_DIR}")