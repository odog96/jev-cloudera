#!/usr/bin/env python3
"""
make_claims.py

Generates synthetic first-notice-of-loss (FNOL) claim notes for auto and home
insurance, each with known correct answers to the two questions in
data/questions.json:

  team           standard | injury | fraud_review | coverage
  senior_review  yes | no

All names, addresses, phone numbers, policy numbers and vehicle numbers are
obviously fake (surnames like "Demo", policy numbers "DEMO-######", VINs
"DEMOVIN##########", 555-01xx phone numbers). No real customer data is used.

Labeling rules (the same rules are stated to the model in questions.json):
  team: fraud_review > coverage > injury > standard when more than one fits.
  senior_review = yes if the team is fraud_review, an attorney is already
                  involved, or the estimated loss is $25,000 or more.

About a third of the notes are hard on purpose: a sore neck mentioned in
passing, a new policy with an ordinary well-documented loss, an angry tone on
a small claim, notes that fit two teams, loss totals spread over line items,
and so on. Each record has difficulty "easy" or "hard" and a scenario name.

Two splits with fixed seeds, so each file regenerates exactly:
    python scripts/make_claims.py --split dev     # data/claims_dev.jsonl
    python scripts/make_claims.py --split test    # data/claims_test.jsonl
The development set was used to choose the question wording; the test set was
generated afterwards and is used only for the reported results.
"""

import argparse

import json
import os
import random

SEEDS = {"dev": 20261003, "test": 58217}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENIOR_THRESHOLD = 25_000

FIRST = ["Alex", "Jordan", "Casey", "Morgan", "Riley", "Taylor", "Jamie", "Avery",
         "Quinn", "Robin", "Sam", "Drew", "Jesse", "Kerry", "Lee", "Pat"]
LAST = ["Demo", "Sample", "Placeholder", "Example", "Testcase", "Fakename", "Mockley", "Dummy"]
STREETS = ["Example Ave", "Sample St", "Placeholder Rd", "Demo Lane", "Test Court", "Mock Way"]
TOWNS = ["Sampleville", "Demotown", "Exampleton", "Fakeford"]
CARS = ["2017 sedan", "2019 hatchback", "2021 pickup", "2015 minivan", "2020 SUV", "2018 coupe"]


class Note:
    def __init__(self, rng):
        self.rng = rng
        self.name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        self.policy = f"DEMO-{rng.randint(100000, 999999)}"
        self.vin = f"DEMOVIN{rng.randint(0, 10**10 - 1):010d}"
        self.car = rng.choice(CARS)
        self.address = f"{rng.randint(1, 999)} {rng.choice(STREETS)}, {rng.choice(TOWNS)}"
        self.phone = f"555-01{rng.randint(0, 99):02d}"

    def vehicle(self):
        return f"{self.car}, VIN {self.vin}"

    def wrap(self, body, amount):
        """Put the scenario body inside one of several note formats.
        amount=None leaves the estimate out (the body lists line items)."""
        r = self.rng
        if amount is None:
            return r.choice([
                f"FNOL. Caller {self.name}, policy {self.policy}, cb {self.phone}. {body}",
                f"Insured {self.name} ({self.policy}), {self.address}, called to report a loss. {body}",
            ])
        amt = f"${amount:,}"
        return r.choice([
            f"FNOL. Caller {self.name}, policy {self.policy}, cb {self.phone}. {body} Est. loss {amt}.",
            f"Insured {self.name} ({self.policy}) called to report a loss. {body} Estimate: {amt}.",
            f"Claim reported by {self.name}, policy #{self.policy}, {self.address}. {body} "
            f"Estimated damage approx {amt}.",
            f"{self.name} / {self.policy}. {body} Initial estimate {amt}. Callback {self.phone}.",
        ])


def amount(rng, lo, hi):
    return int(round(rng.randint(lo, hi), -2))


# --- Scenarios ---------------------------------------------------------------
# Each returns (body, amount, team, attorney, fraud). "attorney" means an
# attorney is already involved; a threat to hire one does not count.

def std_auto(n):
    r = n.rng
    amt = amount(r, 800, 9000)
    body = r.choice([
        f"Rear-ended at a red light. Rear bumper and trunk lid damaged on {n.vehicle()}. "
        "Other driver admitted fault, details exchanged. Nobody hurt. Photos uploaded.",
        f"Scraped by another car in a parking lot while parked. Driver-side doors dented on "
        f"{n.vehicle()}. Note left by other driver with their insurer details. No injuries.",
        f"Hail storm overnight dented hood and roof of {n.vehicle()}. Car was parked at home. "
        "No one in vehicle.",
        f"Tree branch fell on {n.vehicle()} during windstorm, cracked windshield and dented roof. "
        "Parked in driveway, no one hurt.",
    ])
    return body, amt, "standard", False, False


def std_home(n):
    r = n.rng
    amt = amount(r, 1500, 18000)
    body = r.choice([
        "Burst pipe under kitchen sink, water damage to cabinets and floor. Plumber already "
        "repaired the pipe, invoice available. No injuries.",
        "Windstorm tore shingles off roof, some water came into attic. Roofer has quoted the "
        "repair. Everyone fine.",
        "Small grease fire on stove, put out with extinguisher. Smoke damage to kitchen walls and "
        "range hood. Nobody hurt, fire dept not needed.",
        "Garage broken into, bicycles and power tools taken. Police report filed same day, "
        "report number provided. Policy in force for years.",
    ])
    return body, amt, "standard", False, False


def std_large(n):
    # Easy for team, but loss >= threshold so senior review is yes.
    r = n.rng
    amt = amount(r, 30000, 140000)
    body = r.choice([
        "Electrical fire in the garage spread to the kitchen. Family got out safely, no injuries. "
        "Fire department report available. Family staying with relatives.",
        f"Large oak fell on the house during a storm, crushing part of the roof and a bedroom. "
        "Nobody was home. Tree service and contractor have been out.",
        f"{n.vehicle()} totaled when a parked delivery truck rolled into it. Truck company has "
        "accepted fault. Nobody in the car.",
    ])
    return body, amt, "standard", False, False


def injury_easy(n):
    r = n.rng
    amt = amount(r, 2000, 20000)
    attorney = r.random() < 0.4
    body = r.choice([
        f"T-boned at an intersection in {n.vehicle()}. Insured taken by ambulance to hospital "
        "with a broken arm. Passenger treated for cuts.",
        "Guest slipped on icy front steps at the insured's home and fractured an ankle. Guest "
        "was treated at urgent care.",
        f"Head-on collision on the highway. Driver of {n.vehicle()} has a concussion and is "
        "still in hospital.",
        "Insured's dog bit a delivery driver on the hand; driver needed stitches at the ER.",
    ])
    if attorney:
        body += r.choice([" Injured party's attorney has already sent a letter.",
                          " Claimant is represented by counsel; lawyer called this morning."])
    return body, amt, "injury", attorney, False


def fraud_easy(n):
    r = n.rng
    amt = amount(r, 3000, 40000)
    body = r.choice([
        f"{n.vehicle()} reported stolen overnight. Policy was purchased 4 days ago. Insured "
        "says both keys are missing and cannot recall where the car was parked.",
        "Jewelry and electronics reported stolen from home. Contents cover was added to the "
        "policy last week. No signs of forced entry, no police report yet.",
        f"Caller says {n.vehicle()} was damaged in a hit-and-run. This is the third "
        "hit-and-run claim on this policy in 12 months, all at night with no witnesses.",
        "Basement flooded from a burst pipe. Insured first said it happened Monday, then said "
        "it was two weeks ago when the house was empty. Photos look older than reported.",
    ])
    return body, amt, "fraud_review", False, True


def coverage_easy(n):
    r = n.rng
    amt = amount(r, 2000, 20000)
    body = r.choice([
        f"Rear-ended in {n.vehicle()}, no injuries. Billing shows the policy lapsed last month "
        "for non-payment and was not reinstated before the accident.",
        "River overflowed and flooded the ground floor with about a foot of water. Policy does "
        "not have a flood endorsement.",
        f"Insured's nephew was driving {n.vehicle()} and hit a fence. The nephew is listed as an "
        "excluded driver on the policy. No one hurt.",
        f"{n.vehicle()} damaged while being used for paid food deliveries. Personal auto policy, "
        "no business-use endorsement on file. No injuries.",
    ])
    return body, amt, "coverage", False, False


# Hard cases ---------------------------------------------------------------

def hard_passing_injury(n):
    # Looks like standard auto damage; injury mentioned only in passing.
    r = n.rng
    amt = amount(r, 1500, 9000)
    body = r.choice([
        f"Rear-ended at low speed, bumper cracked on {n.vehicle()}. Other driver at fault. "
        "Caller mentioned her neck is a bit sore and she might see a doctor. Photos uploaded.",
        f"Sideswiped on the freeway, mirror and door damage to {n.vehicle()}. Details exchanged. "
        "He said his wrist has been aching since, otherwise fine.",
        f"Minor fender bender in a drive-through. {n.vehicle()} needs a new grille. Passenger "
        "went to urgent care later that day to get her back checked, just in case.",
    ])
    return body, amt, "injury", False, False


def hard_new_policy_genuine(n):
    # New policy (a surface fraud signal) but an ordinary, well-documented loss.
    r = n.rng
    amt = amount(r, 1500, 12000)
    weeks = r.choice([3, 4, 5])
    body = r.choice([
        f"Policy started {weeks} weeks ago when the insured bought {n.vehicle()} from a dealer. "
        "Rear-ended at a stop sign; police report filed, other driver cited and has accepted "
        "fault, dashcam footage provided. No injuries.",
        f"New homeowner, policy bound {weeks} weeks ago at closing. Washing machine supply hose "
        "split, water on laundry room floor. Plumber invoice and photos provided, inspection "
        "report from the purchase showed the hose in good condition. No injuries.",
    ])
    return body, amt, "standard", False, False


def hard_angry_small(n):
    # Angry, threatening tone on a routine small claim. No attorney actually involved.
    r = n.rng
    amt = amount(r, 300, 2500)
    body = r.choice([
        f"Caller VERY upset, shouting. Says a shopping cart scratched the door of {n.vehicle()} "
        "and he wants it fixed today or he'll get a lawyer and report us to the regulator. "
        "Scratch is about 6 inches. No one hurt.",
        "Insured furious about wait times, threatened to sue and post online. Loss is a cracked "
        "bathroom window from a stray baseball. Neighbor's kid admitted it. No injuries.",
        f"Caller swore repeatedly, said this is 'the worst company ever' and she'll 'make us pay'. "
        f"Windshield chip on {n.vehicle()} from road gravel. Nobody hurt.",
    ])
    return body, amt, "standard", False, False


def hard_distractor_coverage(n):
    # Coverage is raised but answered within the note; the loss itself is covered.
    r = n.rng
    amt = amount(r, 2000, 15000)
    body = r.choice([
        "Water damage in basement. Caller worried because they don't have flood cover, but the "
        "plumber confirmed the source is a burst supply pipe, not outside water. No injuries.",
        f"Caller asked whether her son is covered to drive. Agent confirmed the son is a listed "
        f"driver. Son backed {n.vehicle()} into a pole, rear bumper damaged. No one hurt.",
        "Insured missed last month's payment but paid it within the grace period, before the "
        "loss. Hail damaged the roof; roofer quote attached. Everyone fine.",
    ])
    return body, amt, "standard", False, False


def hard_unrelated_injury(n):
    # Injury mentioned, but it has nothing to do with this loss.
    r = n.rng
    amt = amount(r, 2000, 15000)
    body = r.choice([
        "Hail damaged the roof and skylights. Caller mentioned she broke her wrist skiing last "
        "month, so her husband will handle the contractor. Nobody hurt in the storm.",
        f"{n.vehicle()} vandalized while parked overnight, two tires slashed and paint keyed. "
        "Insured is recovering from knee surgery from earlier this year and asked for a rental "
        "with automatic transmission. No injuries from the incident.",
    ])
    return body, amt, "standard", False, False


def hard_two_teams_coverage_injury(n):
    # Injury AND a coverage problem: coverage takes priority.
    r = n.rng
    amt = amount(r, 4000, 20000)
    attorney = r.random() < 0.3
    body = r.choice([
        f"Collision at an intersection, insured had whiplash and was seen at the ER. Billing "
        f"shows the auto policy lapsed 3 weeks before the accident for non-payment.",
        f"Insured's roommate was driving {n.vehicle()} and hurt his shoulder in a crash. The "
        "roommate is named as an excluded driver on the policy.",
    ])
    if attorney:
        body += " Injured driver has hired an attorney."
    return body, amt, "coverage", attorney, False


def hard_two_teams_fraud_injury(n):
    # Injury AND fraud signals: fraud review takes priority.
    r = n.rng
    amt = amount(r, 5000, 30000)
    body = r.choice([
        f"Single-car crash in {n.vehicle()}, insured reports back injury and is seeing a "
        "chiropractor. Policy was bought 6 days ago. Accounts differ: caller said he was alone, "
        "the tow driver's note says two people were in the car.",
        "Slip-and-fall claim by a houseguest who says she hurt her hip. The same guest made a "
        "slip-and-fall claim against the previous homeowner last year.",
    ])
    return body, amt, "fraud_review", False, True


def hard_subtle_fraud(n):
    # Ordinary-looking loss; the fraud signal is a small detail.
    r = n.rng
    amt = amount(r, 2000, 15000)
    body = r.choice([
        f"{n.vehicle()} keyed and windows smashed overnight. Insured first said it was parked "
        "in the locked garage, later in the call said it was on the street. No police report.",
        "Laptop and camera dropped down the stairs. Insured mentioned in passing this is the "
        "fourth accidental-damage claim for electronics since spring.",
        f"Front-end damage to {n.vehicle()} from hitting a deer. Damage photos show paint "
        "transfer from another vehicle. Policy effective date was 9 days before the loss.",
    ])
    return body, amt, "fraud_review", False, True


def hard_subtle_coverage(n):
    # Ordinary-looking loss; the coverage problem is a small detail.
    r = n.rng
    amt = amount(r, 2000, 18000)
    body = r.choice([
        f"Backed {n.vehicle()} into a mailbox, minor damage. By the way, my 17-year-old was "
        "driving - he's the one we excluded to keep the premium down. Nobody hurt.",
        "Water came in under the back door during last week's storm when the creek rose, "
        "carpets ruined. Homeowners policy only, caller said they never bought the flood add-on.",
        f"Fender bender in {n.vehicle()}, no injuries. Caller mentioned they were driving for a "
        "rideshare app at the time and had a passenger in the car.",
    ])
    return body, amt, "coverage", False, False


def hard_line_items_over(n):
    # Standard loss whose total is only over the threshold once line items are added.
    r = n.rng
    roof, contents, housing = amount(r, 12000, 15000), amount(r, 8000, 10000), amount(r, 5000, 7000)
    total = roof + contents + housing
    body = (f"Windstorm damage, no injuries. Roof repair quoted at ${roof:,}; damaged contents "
            f"listed at about ${contents:,}; family needs temporary housing, about ${housing:,}.")
    return body, total, "standard", False, False


hard_line_items_over.hide_total = True


def hard_small_attorney(n):
    # Small, routine-looking injury, but an attorney is already involved.
    r = n.rng
    amt = amount(r, 800, 4000)
    body = (f"Very low-speed bump in a parking lot, small dent on {n.vehicle()}. Other driver "
            "says she jarred her shoulder. We received a letter of representation from her "
            "attorney today.")
    return body, amt, "injury", True, False


# (scenario, count, difficulty). Total 300: 200 easy, 100 hard.
PLAN = [
    (std_auto, 45, "easy"), (std_home, 40, "easy"), (std_large, 15, "easy"),
    (injury_easy, 35, "easy"), (fraud_easy, 30, "easy"), (coverage_easy, 35, "easy"),
    (hard_passing_injury, 12, "hard"), (hard_new_policy_genuine, 10, "hard"),
    (hard_angry_small, 10, "hard"), (hard_distractor_coverage, 10, "hard"),
    (hard_unrelated_injury, 7, "hard"), (hard_two_teams_coverage_injury, 9, "hard"),
    (hard_two_teams_fraud_injury, 8, "hard"), (hard_subtle_fraud, 10, "hard"),
    (hard_subtle_coverage, 10, "hard"), (hard_line_items_over, 8, "hard"),
    (hard_small_attorney, 6, "hard"),
]


def senior_label(team, attorney, amt):
    return "yes" if team == "fraud_review" or attorney or amt >= SENIOR_THRESHOLD else "no"


def generate(seed):
    rng = random.Random(seed)
    jobs = [(fn, diff) for fn, count, diff in PLAN for _ in range(count)]
    rng.shuffle(jobs)
    records = []
    for i, (fn, diff) in enumerate(jobs, 1):
        n = Note(rng)
        body, amt, team, attorney, _fraud = fn(n)
        records.append({
            "id": f"claim-{i:03d}",
            "state": n.wrap(body, None if getattr(fn, "hide_total", False) else amt),
            "team": team,
            "senior_review": senior_label(team, attorney, amt),
            "difficulty": diff,
            "scenario": fn.__name__,
        })
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=sorted(SEEDS), required=True)
    args = ap.parse_args()
    seed = SEEDS[args.split]
    out = os.path.join(ROOT, "data", f"claims_{args.split}.jsonl")
    records = generate(seed)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    def counts(key):
        c = {}
        for rec in records:
            c[rec[key]] = c.get(rec[key], 0) + 1
        return dict(sorted(c.items()))

    print(f"Wrote {len(records)} claim notes to {os.path.relpath(out, ROOT)} (seed {seed})")
    for key in ("difficulty", "team", "senior_review"):
        print(f"  {key}: {counts(key)}")


if __name__ == "__main__":
    main()
