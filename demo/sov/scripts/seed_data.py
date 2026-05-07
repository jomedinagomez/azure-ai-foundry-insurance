"""
Single source of truth for all 6 fictional SOV accounts used in the SOV demo.

All account/location data is fictional. Anomalies are deliberately seeded so the
demo can show extraction, normalization, validation, and risk scoring.

Run this module standalone to regenerate the ground-truth JSON files under
reference/expected-output/.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_DIR = ROOT / "reference" / "expected-output"


# --------------------------------------------------------------------------- #
# Data model (mirrors reference/target-schema.json)
# --------------------------------------------------------------------------- #

@dataclass
class Location:
    location_number: int
    street: str
    city: str
    state: str
    zip: Optional[str]
    construction_type: Optional[str]
    occupancy: Optional[str]
    operations_description: Optional[str]
    year_built: Optional[int]
    stories: Optional[int]
    square_footage: Optional[int]
    unit_count: Optional[int]
    building_value: Optional[float]
    bpp_value: Optional[float]
    bi_ee_value: Optional[float]
    sprinklered: Optional[bool] = None
    protection_class: Optional[int] = None
    roof_year: Optional[int] = None
    flood_zone: Optional[str] = None
    distance_to_coast_mi: Optional[float] = None
    cat_zone_flags: list[str] = field(default_factory=list)
    notes: Optional[str] = None
    building_number: Optional[int] = None
    county: Optional[str] = None

    @property
    def tiv(self) -> float:
        return sum(v or 0 for v in (self.building_value, self.bpp_value, self.bi_ee_value))


@dataclass
class Broker:
    name: str
    contact: str
    email: str
    phone: str
    domain: str          # used for logo + email From
    color: str           # logo color (hex)
    tagline: str


@dataclass
class Account:
    key: str             # short slug, e.g. "acme"
    insured_name: str
    dba: Optional[str]
    mailing_address: str
    effective_date: str  # YYYY-MM-DD
    expiration_date: str
    primary_operations: str
    naics: Optional[str]
    currency: str
    valuation_date: str
    broker: Broker
    prepared_by: str
    prepared_date: str
    locations: list[Location]
    # demo-only metadata:
    template_style: str
    seeded_anomalies: list[dict]


# --------------------------------------------------------------------------- #
# 1. Acme Manufacturing & Distribution  (HERO — Excel header block + table)
# --------------------------------------------------------------------------- #

ACME = Account(
    key="acme",
    insured_name="Acme Manufacturing & Distribution, Inc.",
    dba="Acme Industrial",
    mailing_address="4500 Industrial Pkwy, Cleveland, OH 44109",
    effective_date="2026-07-01",
    expiration_date="2027-07-01",
    primary_operations="Manufacturing of industrial fasteners and distribution of fastening hardware to commercial and retail channels.",
    naics="332722",
    currency="USD",
    valuation_date="2026-04-30",
    broker=Broker(
        name="Sterling Risk Partners",
        contact="Jennifer Walsh",
        email="jwalsh@sterlingrisk.example.com",
        phone="(216) 555-0142",
        domain="sterlingrisk.example.com",
        color="#1F3A68",
        tagline="Commercial Property & Specialty Brokerage",
    ),
    prepared_by="Jennifer Walsh, CPCU",
    prepared_date="2026-05-02",
    template_style="excel_header_block_with_image",
    seeded_anomalies=[
        {"location_number": 4, "field": "construction_type", "issue": "missing", "severity": "warning",
         "detail": "Construction type left blank by broker."},
        {"location_number": 7, "field": "year_built", "issue": "missing", "severity": "info",
         "detail": "Year built not provided."},
        {"location_number": None, "field": "building_value", "issue": "flat_duplicate", "severity": "warning",
         "detail": "Locations 11-14 all report identical $5,000,000 building value — likely placeholder."},
        {"location_number": 18, "field": "building_value", "issue": "under_valuation", "severity": "critical",
         "detail": "85,000 sqft warehouse reported at $850,000 building value (~$10/sqft, far below $75-110/sqft benchmark)."},
        {"location_number": None, "field": "notes", "issue": "annotation", "severity": "info",
         "detail": "Embedded image contains 3 additional locations (20-22) appended by broker."},
    ],
    locations=[
        Location(1,  "4500 Industrial Pkwy",   "Cleveland",      "OH", "44109", "Masonry Non-Combustible", "Manufacturing", "Fastener manufacturing — main plant", 1998, 2,  185000, None, 28500000, 12400000, 8200000, True, 3, 2018, "X",   None, [],          "Headquarters / primary manufacturing"),
        Location(2,  "812 Foundry Rd",         "Akron",          "OH", "44307", "Masonry Non-Combustible", "Manufacturing", "Heat treatment and finishing operations",  1985, 1,  92000,  None, 14200000, 6100000,  3800000, True, 4, 2015, "X",   None, [],          None),
        Location(3,  "1200 Distribution Ct",   "Columbus",       "OH", "43219", "Non-Combustible",         "Warehouse",     "Regional distribution center",            2008, 1,  240000, None, 21800000, 4200000,  2100000, True, 3, 2020, "X",   None, [],          None),
        Location(4,  "55 Logistics Way",       "Indianapolis",   "IN", "46241", None,                       "Warehouse",     "Cross-dock and storage",                  2012, 1,  165000, None, 14500000, 2800000,  1400000, True, 4, None, "X",   None, [],          "Construction details pending broker confirmation"),
        Location(5,  "3300 Commerce Dr",       "Louisville",     "KY", "40213", "Non-Combustible",         "Warehouse",     "Distribution and light assembly",         2005, 1,  180000, None, 16200000, 3100000,  1600000, True, 3, 2019, "X",   None, [],          None),
        Location(6,  "1450 Production Blvd",   "Pittsburgh",     "PA", "15233", "Joisted Masonry",         "Manufacturing", "Specialty fastener machining",            1972, 2,  78000,  None, 9800000,  4400000,  2200000, True, 5, 2010, "X",   None, [],          None),
        Location(7,  "920 Industrial Ave",     "Buffalo",        "NY", "14206", "Joisted Masonry",         "Manufacturing", "Coating and plating operations",          None, 1,  62000,  None, 7400000,  3200000,  1500000, False,5, None, "X",   None, [],          None),
        Location(8,  "2200 Warehouse Row",     "Detroit",        "MI", "48211", "Non-Combustible",         "Warehouse",     "Bulk storage",                            2001, 1,  155000, None, 11900000, 1800000,  900000,  True, 4, 2017, "X",   None, [],          None),
        Location(9,  "780 Manufacturing Ln",   "Toledo",         "OH", "43605", "Masonry Non-Combustible", "Manufacturing", "Secondary manufacturing line",            1995, 2,  88000,  None, 12100000, 5200000,  2800000, True, 4, 2016, "X",   None, [],          None),
        Location(10, "4100 Logistics Pkwy",    "Chicago",        "IL", "60638", "Non-Combustible",         "Warehouse",     "Midwest hub distribution",                2010, 1,  220000, None, 19400000, 3600000,  1800000, True, 3, 2021, "X",   None, [],          None),
        # Locations 11-14: flat-duplicate building value anomaly
        Location(11, "501 Industrial Park Rd",  "Cincinnati",    "OH", "45232", "Joisted Masonry",         "Warehouse",     "Satellite distribution",                  2000, 1,  62000,  None, 5000000,  900000,   500000,  True, 4, 2014, "X",   None, [],          None),
        Location(12, "775 Industrial Park Rd",  "Cincinnati",    "OH", "45232", "Joisted Masonry",         "Warehouse",     "Satellite distribution",                  2000, 1,  64000,  None, 5000000,  900000,   500000,  True, 4, 2014, "X",   None, [],          None),
        Location(13, "910 Industrial Park Rd",  "Cincinnati",    "OH", "45232", "Joisted Masonry",         "Warehouse",     "Satellite distribution",                  2001, 1,  61000,  None, 5000000,  900000,   500000,  True, 4, 2014, "X",   None, [],          None),
        Location(14, "1140 Industrial Park Rd", "Cincinnati",    "OH", "45232", "Joisted Masonry",         "Warehouse",     "Satellite distribution",                  2002, 1,  63000,  None, 5000000,  900000,   500000,  True, 4, 2014, "X",   None, [],          None),
        Location(15, "650 Commerce St",        "St. Louis",      "MO", "63110", "Non-Combustible",         "Warehouse",     "Regional storage",                        2007, 1,  140000, None, 10200000, 1900000,  1000000, True, 4, 2018, "X",   None, [],          None),
        Location(16, "8800 Trade Center Dr",   "Memphis",        "TN", "38132", "Non-Combustible",         "Warehouse",     "Southern distribution hub",               2014, 1,  280000, None, 24500000, 4800000,  2400000, True, 3, 2022, "X",   None, [],          None),
        Location(17, "2500 Industrial Dr",     "Nashville",      "TN", "37210", "Joisted Masonry",         "Warehouse",     "Regional distribution",                   1990, 1,  95000,  None, 7800000,  1500000,  800000,  True, 5, 2012, "X",   None, [],          None),
        # Location 18: under-valuation anomaly
        Location(18, "1850 Old Mill Rd",       "Birmingham",     "AL", "35211", "Frame",                   "Warehouse",     "Legacy storage facility",                 1968, 1,  85000,  None, 850000,   200000,   100000,  False,7, None, "X",   None, [],          "Acquired 2024 — values pending appraisal"),
        Location(19, "445 Distribution Way",   "Atlanta",        "GA", "30336", "Non-Combustible",         "Warehouse",     "Southeast distribution",                  2009, 1,  175000, None, 15800000, 2900000,  1500000, True, 3, 2020, "X",   None, [],          None),
        # Locations 20-22: appear ONLY in embedded image on Acme spreadsheet
        Location(20, "320 Industrial Way",     "Charlotte",      "NC", "28269", "Non-Combustible",         "Warehouse",     "Carolina distribution (added late)",      2018, 1,  130000, None, 11200000, 2100000,  1100000, True, 3, 2022, "X",   None, [],          "Appears only in embedded image on SOV"),
        Location(21, "1070 Logistics Cir",     "Greenville",     "SC", "29605", "Non-Combustible",         "Warehouse",     "Cross-dock (added late)",                 2019, 1,  110000, None, 9400000,  1700000,  900000,  True, 3, 2021, "X",   None, [],          "Appears only in embedded image on SOV"),
        Location(22, "2200 Commerce Park Dr",  "Knoxville",      "TN", "37932", "Non-Combustible",         "Warehouse",     "TN secondary hub (added late)",           2016, 1,  120000, None, 10100000, 1900000,  950000,  True, 4, 2020, "X",   None, [],          "Appears only in embedded image on SOV"),
    ],
)


# --------------------------------------------------------------------------- #
# 2. Cascade Cold Storage  (Excel — clean flat table; baseline)
# --------------------------------------------------------------------------- #

CASCADE = Account(
    key="cascade",
    insured_name="Cascade Cold Storage LLC",
    dba=None,
    mailing_address="1500 Marine View Dr, Tacoma, WA 98422",
    effective_date="2026-08-15",
    expiration_date="2027-08-15",
    primary_operations="Refrigerated and frozen warehousing for food and pharmaceutical clients.",
    naics="493120",
    currency="USD",
    valuation_date="2026-05-01",
    broker=Broker(
        name="Pacific Northwest Brokers",
        contact="David Chen",
        email="dchen@pnwbrokers.example.com",
        phone="(253) 555-0188",
        domain="pnwbrokers.example.com",
        color="#0E7C66",
        tagline="Northwest Commercial Insurance Specialists",
    ),
    prepared_by="David Chen",
    prepared_date="2026-05-04",
    template_style="excel_flat_table",
    seeded_anomalies=[
        {"location_number": 5, "field": "building_value", "issue": "under_valuation", "severity": "critical",
         "detail": "80,000 sqft cold storage facility reported at $200,000 building value (~$2.50/sqft vs $140-185/sqft benchmark)."},
    ],
    locations=[
        Location(1, "1500 Marine View Dr", "Tacoma",       "WA", "98422", "Non-Combustible", "Cold Storage", "Refrigerated warehousing — main facility",   2012, 1, 145000, None, 22400000, 3200000, 1800000, True, 3, 2020, "X", None, [], None),
        Location(2, "2200 Port Way",       "Seattle",      "WA", "98134", "Non-Combustible", "Cold Storage", "Frozen storage and blast freezing",          2008, 1,  98000, None, 16100000, 2100000, 1100000, True, 3, 2018, "X", None, [], None),
        Location(3, "850 Commerce Blvd",   "Portland",     "OR", "97218", "Non-Combustible", "Cold Storage", "Refrigerated distribution",                  2015, 1, 120000, None, 19800000, 2700000, 1400000, True, 3, 2021, "X", None, [], None),
        Location(4, "4400 Industrial Dr",  "Salem",        "OR", "97301", "Non-Combustible", "Cold Storage", "Pharmaceutical-grade cold storage",          2018, 1,  72000, None, 14200000, 1900000, 1000000, True, 4, 2022, "X", None, [], None),
        # Anomaly: massive under-valuation
        Location(5, "1200 Bayshore Way",   "Oakland",      "CA", "94607", "Non-Combustible", "Cold Storage", "Bay Area distribution facility",             2005, 1,  80000, None, 200000,   1200000, 800000,  True, 3, 2017, "X", None, [], "Building value appears to be a typo — please confirm with insured"),
        Location(6, "300 Harbor Industrial Way", "Long Beach", "CA", "90802", "Non-Combustible", "Cold Storage", "Port-side refrigerated storage",         2010, 1,  95000, None, 17600000, 2300000, 1200000, True, 3, 2019, "X", None, [], None),
        Location(7, "750 Distribution Ct", "Sacramento",   "CA", "95828", "Non-Combustible", "Cold Storage", "Central Valley cold storage",                2014, 1, 105000, None, 18400000, 2500000, 1300000, True, 4, 2020, "X", None, [], None),
        Location(8, "2100 Cold Spring Ln", "Reno",         "NV", "89506", "Non-Combustible", "Cold Storage", "Inland distribution",                        2017, 1,  68000, None, 12800000, 1700000, 900000,  True, 4, 2021, "X", None, [], None),
    ],
)


# --------------------------------------------------------------------------- #
# 3. Magnolia Hospitality Group  (Excel — multi-sheet; CAT clustering)
# --------------------------------------------------------------------------- #

MAGNOLIA = Account(
    key="magnolia",
    insured_name="Magnolia Hospitality Group LLC",
    dba="Magnolia Hotels & Restaurants",
    mailing_address="200 Bourbon St, New Orleans, LA 70130",
    effective_date="2026-09-01",
    expiration_date="2027-09-01",
    primary_operations="Owner and operator of boutique hotels and full-service restaurants across the Gulf Coast region.",
    naics="721110",
    currency="USD",
    valuation_date="2026-05-15",
    broker=Broker(
        name="Crescent Insurance Services",
        contact="Marie Boudreaux",
        email="mboudreaux@crescentins.example.com",
        phone="(504) 555-0167",
        domain="crescentins.example.com",
        color="#7A1F3D",
        tagline="Gulf Coast Commercial Insurance",
    ),
    prepared_by="Marie Boudreaux, CIC",
    prepared_date="2026-05-10",
    template_style="excel_multi_sheet",
    seeded_anomalies=[
        {"location_number": 3, "field": "building_value", "issue": "over_valuation", "severity": "warning",
         "detail": "12,000 sqft restaurant reported at $9.8M building value (~$815/sqft, far above benchmark)."},
        {"location_number": None, "field": "construction_type", "issue": "label_inconsistency", "severity": "info",
         "detail": "Summary tab uses 'Bldg Type'; Locations tab uses 'Construction Class' — same field, different labels."},
        {"location_number": None, "field": "cat_concentration", "issue": "annotation", "severity": "critical",
         "detail": "9 of 15 locations sit in FL/LA Gulf Coast hurricane zones; ~62% of TIV in named-storm region."},
    ],
    locations=[
        Location(1,  "200 Bourbon St",            "New Orleans",   "LA", "70130", "Masonry Non-Combustible", "Hotel",      "Boutique hotel — French Quarter flagship",      1925, 4, 65000,  120, 22400000, 4800000, 6200000, True,  3, 2019, "AE",  0.5,  ["hurricane","named_storm","flood"], "Historic structure, post-Katrina retrofit"),
        Location(2,  "418 Royal St",              "New Orleans",   "LA", "70130", "Joisted Masonry",         "Restaurant", "Fine dining — French Quarter",                  1890, 2, 8500,   None, 4200000,  1100000, 1800000, True,  3, 2018, "AE",  0.5,  ["hurricane","named_storm","flood"], None),
        # Anomaly: over-valuation
        Location(3,  "555 Magazine St",           "New Orleans",   "LA", "70130", "Joisted Masonry",         "Restaurant", "Upscale steakhouse",                            1905, 2, 12000,  None, 9800000,  1400000, 2200000, True,  3, 2020, "X",   1.2,  ["hurricane","named_storm"],         "Recent renovation — verify replacement cost"),
        Location(4,  "1200 Decatur St",           "New Orleans",   "LA", "70116", "Masonry Non-Combustible", "Hotel",      "Mid-scale hotel — riverfront",                  1998, 6, 88000,  155, 28600000, 5400000, 7100000, True,  3, 2017, "AE",  0.3,  ["hurricane","named_storm","flood"], None),
        Location(5,  "100 Beachfront Dr",         "Gulfport",      "MS", "39507", "Masonry Non-Combustible", "Hotel",      "Beachfront resort hotel",                       2010, 5, 110000, 180, 32400000, 6200000, 8800000, True,  3, 2018, "VE",  0.05, ["hurricane","named_storm","storm_surge","wind_tier_1"], "Post-Katrina rebuild"),
        Location(6,  "850 Casino Way",            "Biloxi",        "MS", "39530", "Masonry Non-Combustible", "Hotel",      "Hotel adjacent to casino",                      2008, 8, 145000, 220, 41200000, 7800000, 11400000, True, 3, 2019, "VE",  0.1,  ["hurricane","named_storm","storm_surge","wind_tier_1"], None),
        Location(7,  "1500 Beach Blvd",           "Pensacola",     "FL", "32507", "Masonry Non-Combustible", "Hotel",      "Beachside hotel",                               2005, 4, 95000,  140, 24800000, 4600000, 6400000, True,  4, 2016, "VE",  0.08, ["hurricane","named_storm","storm_surge","wind_tier_1"], None),
        Location(8,  "200 Pier Dr",               "Destin",        "FL", "32541", "Masonry Non-Combustible", "Hotel",      "Pier hotel and restaurant",                     2012, 4, 78000,  115, 21600000, 4100000, 5800000, True,  4, 2020, "VE",  0.02, ["hurricane","named_storm","storm_surge","wind_tier_1"], None),
        Location(9,  "440 Gulfshore Pkwy",        "Naples",        "FL", "34102", "Fire Resistive",          "Hotel",      "Luxury beachfront resort",                      2018, 7, 125000, 200, 48400000, 9200000, 13200000, True, 3, 2021, "VE",  0.1,  ["hurricane","named_storm","storm_surge","wind_tier_1"], None),
        Location(10, "1100 Beach Rd",             "Sarasota",      "FL", "34242", "Masonry Non-Combustible", "Hotel",      "Boutique beach hotel",                          2006, 3, 62000,  90,  18200000, 3400000, 4800000, True,  4, 2017, "VE",  0.5,  ["hurricane","named_storm","wind_tier_1"], None),
        Location(11, "300 Ocean Dr",              "Miami Beach",   "FL", "33139", "Fire Resistive",          "Hotel",      "Art Deco district hotel",                       1937, 5, 72000,  105, 26400000, 5100000, 7400000, True,  3, 2015, "AE",  0.05, ["hurricane","named_storm","storm_surge","wind_tier_1"], "Historic landmark"),
        Location(12, "850 Restaurant Row",        "Miami",         "FL", "33132", "Joisted Masonry",         "Restaurant", "Seafood restaurant",                            1995, 1, 9500,   None, 3800000,  900000,  1500000, True,  3, 2019, "X",   0.8,  ["hurricane","named_storm"],         None),
        Location(13, "75 Inland Ave",             "Atlanta",       "GA", "30308", "Fire Resistive",          "Hotel",      "Downtown business hotel",                       2014, 12,180000, 240, 52800000, 9800000, 14200000, True, 3, 2021, "X",   None, [],                                 None),
        Location(14, "200 Peachtree Way",         "Atlanta",       "GA", "30309", "Joisted Masonry",         "Restaurant", "Upscale Southern restaurant",                   2008, 2, 11000,  None, 4400000,  1100000, 1700000, True,  3, 2020, "X",   None, [],                                 None),
        Location(15, "1450 Mountain View Dr",     "Asheville",     "NC", "28804", "Joisted Masonry",         "Hotel",      "Mountain inn",                                  1925, 3, 38000,  56,  9800000,  1900000, 2400000, True,  5, 2018, "X",   None, [],                                 "Historic property"),
    ],
)


# --------------------------------------------------------------------------- #
# 4. Summit Outdoor Retail  (Native PDF; firearms/range = "shooting" flag)
# --------------------------------------------------------------------------- #

SUMMIT = Account(
    key="summit",
    insured_name="Summit Outdoor Retail Co.",
    dba="Summit Outdoors",
    mailing_address="2400 Mountain Way, Boulder, CO 80301",
    effective_date="2026-10-01",
    expiration_date="2027-10-01",
    primary_operations="Retail sale of outdoor recreation equipment, apparel, and sporting goods including firearms and ammunition at select locations.",
    naics="451110",
    currency="USD",
    valuation_date="2026-05-20",
    broker=Broker(
        name="Rocky Mountain Brokerage",
        contact="Tyler Brennan",
        email="tbrennan@rockymtnbrokerage.example.com",
        phone="(303) 555-0119",
        domain="rockymtnbrokerage.example.com",
        color="#2D5F3F",
        tagline="Specialty & Recreation Insurance",
    ),
    prepared_by="Tyler Brennan, AAI",
    prepared_date="2026-05-15",
    template_style="pdf_native_with_footnotes",
    seeded_anomalies=[
        {"location_number": 8, "field": "operations_description", "issue": "annotation", "severity": "critical",
         "detail": "Location 8 includes a 25-lane indoor firearms range — 'shooting' operations flag."},
        {"location_number": 11, "field": "notes", "issue": "annotation", "severity": "info",
         "detail": "Footnote indicates building under renovation; reported value reflects post-completion."},
    ],
    locations=[
        Location(1,  "2400 Mountain Way",     "Boulder",         "CO", "80301", "Joisted Masonry",         "Retail", "Flagship retail store — outdoor gear and apparel",                                          2008, 1, 28000, None, 5400000, 2800000, 1200000, True, 3, 2018, "X", None, [], None),
        Location(2,  "1500 Pearl St",         "Denver",          "CO", "80203", "Joisted Masonry",         "Retail", "Urban retail store",                                                                        2012, 2, 22000, None, 4600000, 2400000, 1100000, True, 3, 2019, "X", None, [], None),
        Location(3,  "8800 Park Meadows Dr",  "Lone Tree",       "CO", "80124", "Non-Combustible",         "Retail", "Suburban big-box retail",                                                                   2015, 1, 42000, None, 6800000, 3600000, 1500000, True, 3, 2020, "X", None, [], None),
        Location(4,  "550 Main St",           "Vail",            "CO", "81657", "Joisted Masonry",         "Retail", "Resort-town outdoor retail",                                                                1998, 2, 14000, None, 3200000, 1800000, 800000,  True, 4, 2017, "X", None, [], None),
        Location(5,  "1200 Lincoln Way",      "Salt Lake City",  "UT", "84101", "Joisted Masonry",         "Retail", "Outdoor and ski equipment retail",                                                          2010, 1, 30000, None, 5700000, 3000000, 1300000, True, 3, 2018, "X", None, [], None),
        Location(6,  "440 Cottonwood Pkwy",   "Park City",       "UT", "84098", "Joisted Masonry",         "Retail", "Resort retail",                                                                             2014, 1, 18000, None, 3800000, 2100000, 950000,  True, 4, 2020, "X", None, [], None),
        Location(7,  "2200 Rainier Ave",      "Bend",            "OR", "97702", "Joisted Masonry",         "Retail", "Pacific Northwest outdoor retail",                                                          2011, 1, 26000, None, 5100000, 2700000, 1200000, True, 4, 2018, "X", None, [], None),
        # Location 8: HIGH HAZARD — indoor firearms range buried mid-list
        Location(8,  "5500 Industrial Pkwy",  "Colorado Springs","CO", "80906", "Non-Combustible",         "Retail", "Retail store with attached 25-lane indoor firearms range and gunsmith services",            2016, 1, 36000, None, 7400000, 3900000, 2100000, True, 3, 2020, "X", None, [], "Includes indoor shooting range — see schedule of safety equipment"),
        Location(9,  "1100 University Ave",   "Albuquerque",     "NM", "87102", "Joisted Masonry",         "Retail", "Outdoor and hunting retail",                                                                2007, 1, 24000, None, 4400000, 2300000, 1000000, True, 4, 2017, "X", None, [], None),
        Location(10, "750 Cheyenne Mountain Blvd","Cheyenne",    "WY", "82001", "Joisted Masonry",         "Retail", "Outdoor retail",                                                                            2009, 1, 20000, None, 3800000, 2000000, 900000,  True, 4, 2018, "X", None, [], None),
        # Location 11: renovation footnote
        Location(11, "330 Mountain View Rd",  "Bozeman",         "MT", "59715", "Joisted Masonry",         "Retail", "Outdoor retail — Montana flagship",                                                         2003, 1, 28000, None, 5800000, 2900000, 1300000, True, 4, None, "X", None, [], "Building under renovation through Q3 2026; reported value reflects post-completion replacement cost"),
        Location(12, "2200 Snake River Way",  "Idaho Falls",     "ID", "83401", "Joisted Masonry",         "Retail", "Outdoor and fishing retail",                                                                2013, 1, 19000, None, 3600000, 1900000, 850000,  True, 4, 2019, "X", None, [], None),
    ],
)


# --------------------------------------------------------------------------- #
# 5. Heartland Agri-Processors  (Scanned PDF; address quality issues)
# --------------------------------------------------------------------------- #

HEARTLAND = Account(
    key="heartland",
    insured_name="Heartland Agri-Processors Inc.",
    dba=None,
    mailing_address="PO Box 4400, Cedar Rapids, IA 52406",
    effective_date="2026-11-15",
    expiration_date="2027-11-15",
    primary_operations="Grain handling, food-grade processing, and packaging of corn and soy-based ingredients for industrial bakery and feed customers.",
    naics="311221",
    currency="USD",
    valuation_date="2026-06-01",
    broker=Broker(
        name="Prairie State Insurance Agency",
        contact="Robert Kowalski",
        email="rkowalski@prairiestateins.example.com",
        phone="(319) 555-0144",
        domain="prairiestateins.example.com",
        color="#A8762B",
        tagline="Agricultural & Food Processing Risk",
    ),
    prepared_by="Robert Kowalski",
    prepared_date="2026-06-03",
    template_style="pdf_scanned",
    seeded_anomalies=[
        {"location_number": 1, "field": "mailing_address", "issue": "address_quality", "severity": "info",
         "detail": "Account mailing address is a PO Box — not suitable for inspection scheduling."},
        {"location_number": 4, "field": "zip", "issue": "missing", "severity": "warning",
         "detail": "ZIP code missing for Location 4."},
        {"location_number": 6, "field": "year_built", "issue": "missing", "severity": "info",
         "detail": "Year built not provided."},
        {"location_number": 9, "field": "notes", "issue": "annotation", "severity": "info",
         "detail": "Margin annotation: 'New silo addition Q4 2026 — values to be updated at renewal'."},
    ],
    locations=[
        Location(1,  "1200 Mill Rd",           "Cedar Rapids",  "IA", "52404", "Non-Combustible",         "Food Processing", "Corn wet milling and processing",     1995, 3, 185000, None, 28400000, 14200000, 9800000, True,  4, 2018, "X", None, [], None),
        Location(2,  "850 Grain Elevator Way", "Davenport",     "IA", "52806", "Non-Combustible",         "Food Processing", "Grain elevator and storage",          1988, 2, 95000,  None, 12600000, 4200000,  2800000, True,  4, 2015, "X", None, [], None),
        Location(3,  "440 Soybean Rd",         "Decatur",       "IL", "62526", "Masonry Non-Combustible", "Food Processing", "Soybean processing and oil extraction", 2002, 3, 220000, None, 36800000, 18400000, 11200000, True, 3, 2020, "X", None, [], None),
        # Location 4: ZIP missing
        Location(4,  "2200 Industrial Park",   "Lincoln",       "NE", None,    "Non-Combustible",         "Food Processing", "Bakery ingredient production",       2008, 2, 140000, None, 22400000, 9800000,  6200000, True,  4, 2019, "X", None, [], None),
        Location(5,  "775 Mill St",            "Topeka",        "KS", "66608", "Non-Combustible",         "Food Processing", "Flour milling",                       1998, 3, 110000, None, 16800000, 7400000,  4800000, True,  4, 2017, "X", None, [], None),
        # Location 6: year_built missing
        Location(6,  "3300 Processing Way",    "Sioux Falls",   "SD", "57104", "Non-Combustible",         "Food Processing", "Animal feed manufacturing",           None, 2, 88000,  None, 11200000, 4900000,  3100000, True,  5, 2014, "X", None, [], None),
        Location(7,  "1500 Agriculture Dr",    "Fargo",         "ND", "58102", "Joisted Masonry",         "Warehouse",       "Bulk grain warehousing",              1985, 1, 72000,  None, 6400000,  1200000,  600000,  True,  5, 2012, "X", None, [], None),
        Location(8,  "640 Co-op Ln",           "Mason City",    "IA", "50401", "Joisted Masonry",         "Warehouse",       "Co-op storage facility",              1978, 1, 58000,  None, 4800000,  900000,   500000,  False, 6, None, "X", None, [], None),
        # Location 9: margin annotation about new silo
        Location(9,  "920 Granary Rd",         "Omaha",         "NE", "68102", "Non-Combustible",         "Food Processing", "Specialty grain processing",          2011, 2, 125000, None, 19400000, 8400000,  5200000, True,  4, 2019, "X", None, [], "MARGIN NOTE: New silo addition Q4 2026 — values to be updated at renewal"),
        Location(10, "1850 Farm Center Way",   "Wichita",       "KS", "67220", "Non-Combustible",         "Food Processing", "Pet food ingredient processing",      2014, 2, 102000, None, 17200000, 7600000,  4800000, True,  4, 2021, "X", None, [], None),
    ],
)


# --------------------------------------------------------------------------- #
# 6. Coastal Marine Services  (Messy broker Excel; mixed currency; CAT)
# --------------------------------------------------------------------------- #

COASTAL = Account(
    key="coastal",
    insured_name="Coastal Marine Services Inc.",
    dba="Coastal Marine",
    mailing_address="850 Harbor Way, Wilmington, NC 28401",
    effective_date="2026-12-01",
    expiration_date="2027-12-01",
    primary_operations="Marine services including boatyard operations, dockside warehousing, and marine equipment storage along the southeastern Atlantic coast.",
    naics="488330",
    currency="USD",  # mostly USD; one CAD location triggers anomaly
    valuation_date="2026-06-15",
    broker=Broker(
        name="Atlantic Specialty Brokers",
        contact="Sarah Whitfield",
        email="swhitfield@atlanticspecialty.example.com",
        phone="(910) 555-0173",
        domain="atlanticspecialty.example.com",
        color="#1B5A8E",
        tagline="Marine & Coastal Property Specialists",
    ),
    prepared_by="Sarah Whitfield, ARM",
    prepared_date="2026-06-18",
    template_style="excel_messy_broker",
    seeded_anomalies=[
        {"location_number": None, "field": "construction_type", "issue": "label_inconsistency", "severity": "warning",
         "detail": "Same column appears as 'Bldg Val' in some rows, 'Building Replacement Cost' in others, and 'RC Bldg' in subtotal block."},
        {"location_number": 6, "field": "currency", "issue": "currency_mismatch", "severity": "critical",
         "detail": "Location 6 (Halifax) reports values in CAD; account currency is USD — needs FX normalization."},
        {"location_number": None, "field": "cat_concentration", "issue": "annotation", "severity": "critical",
         "detail": "100% of US locations are within 5 miles of Atlantic coast — concentrated named-storm exposure."},
    ],
    locations=[
        Location(1, "850 Harbor Way",        "Wilmington",  "NC", "28401", "Joisted Masonry", "Marine/Boatyard", "Boatyard operations and dockside warehouse",       1992, 1, 48000, None, 5800000, 1400000, 800000, True, 5, 2016, "AE", 0.05, ["hurricane","named_storm","storm_surge","wind_tier_1"], None),
        Location(2, "1200 Marina Dr",        "Morehead City","NC", "28557", "Joisted Masonry", "Marine/Boatyard", "Marina storage and service facility",              1998, 1, 32000, None, 4200000, 1100000, 600000, True, 5, 2018, "VE", 0.02, ["hurricane","named_storm","storm_surge","wind_tier_1"], None),
        Location(3, "750 Waterfront Ave",    "Charleston",  "SC", "29401", "Joisted Masonry", "Marine/Boatyard", "Historic district boat works and storage",         1965, 2, 28000, None, 3800000, 950000,  500000, True, 5, 2014, "AE", 0.1,  ["hurricane","named_storm","storm_surge","wind_tier_1"], "Historic structure — limited retrofit"),
        Location(4, "440 Dock St",           "Savannah",    "GA", "31401", "Joisted Masonry", "Marine/Boatyard", "Riverfront marine services",                       2005, 1, 35000, None, 4600000, 1200000, 700000, True, 5, 2019, "AE", 1.5,  ["hurricane","named_storm","wind_tier_1"], None),
        Location(5, "2100 Ocean Hwy",        "Jacksonville","FL", "32218", "Non-Combustible", "Marine/Boatyard", "Coastal warehouse and equipment storage",          2012, 1, 52000, None, 6800000, 1600000, 900000, True, 4, 2020, "AE", 0.5,  ["hurricane","named_storm","storm_surge","wind_tier_1"], None),
        # Location 6: CAD currency anomaly
        Location(6, "1500 Halifax Harbour Rd","Halifax",    "NS", "B3J 1S9","Joisted Masonry", "Marine/Boatyard", "Canadian operations — Atlantic hub",               2008, 1, 38000, None, 4400000, 1100000, 600000, True, 5, 2017, None, 0.1, ["hurricane","named_storm"], "VALUES IN CAD — convert at renewal FX rate"),
    ],
)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

ACCOUNTS: list[Account] = [ACME, CASCADE, MAGNOLIA, SUMMIT, HEARTLAND, COASTAL]


# --------------------------------------------------------------------------- #
# Serialization → expected-output JSON (ground truth)
# --------------------------------------------------------------------------- #

def _account_to_dict(acc: Account) -> dict:
    locations = [asdict(loc) for loc in acc.locations]

    tiv = sum(loc.tiv for loc in acc.locations)
    location_count = len(acc.locations)

    # Derived flags
    shooting = any(
        "shoot" in (loc.operations_description or "").lower() or
        "firearms" in (loc.operations_description or "").lower() or
        "range" in (loc.notes or "").lower() and "indoor" in (loc.operations_description or "").lower()
        for loc in acc.locations
    ) or any("firearms" in (loc.operations_description or "").lower() for loc in acc.locations)

    # Simple high-hazard detection
    high_hazard = shooting or any(
        any(kw in (loc.operations_description or "").lower() for kw in ["chemical", "explosive", "ammunition"])
        for loc in acc.locations
    )

    # CAT concentration: group by state for hurricane-flagged locations
    cat_locs = [loc for loc in acc.locations if any("hurricane" in f or "named_storm" in f for f in loc.cat_zone_flags)]
    cat_tiv = sum(loc.tiv for loc in cat_locs)
    cat_concentration = []
    if cat_locs and tiv > 0:
        cat_concentration.append({
            "peril": "Named Windstorm / Hurricane",
            "region": "Atlantic & Gulf Coast",
            "location_count": len(cat_locs),
            "tiv_in_region": round(cat_tiv, 2),
            "pct_of_total_tiv": round(cat_tiv / tiv * 100, 1),
        })

    # Top risk locations: rank by composite of TIV + CAT exposure + hazard
    def risk_score(loc: Location) -> tuple[float, list[str]]:
        score = 0.0
        drivers = []
        if loc.tiv >= 20_000_000:
            score += 35; drivers.append("PML driver — high TIV")
        elif loc.tiv >= 10_000_000:
            score += 20; drivers.append("Significant TIV")
        if any(f in loc.cat_zone_flags for f in ["storm_surge", "wind_tier_1"]):
            score += 30; drivers.append("Coastal CAT zone")
        elif loc.cat_zone_flags:
            score += 15; drivers.append("CAT exposure")
        if loc.flood_zone in ("AE", "VE"):
            score += 10; drivers.append(f"Flood zone {loc.flood_zone}")
        if loc.year_built and loc.year_built < 1980:
            score += 10; drivers.append("Older construction")
        if loc.sprinklered is False:
            score += 10; drivers.append("Unsprinklered")
        if "firearms" in (loc.operations_description or "").lower() or "shoot" in (loc.operations_description or "").lower():
            score += 25; drivers.append("Firearms / shooting operations")
        return score, drivers

    scored = [(loc, *risk_score(loc)) for loc in acc.locations]
    scored.sort(key=lambda t: t[1], reverse=True)
    top_risk = [
        {"location_number": loc.location_number, "risk_score": round(score, 1), "drivers": drivers}
        for loc, score, drivers in scored[:10] if score > 0
    ]

    return {
        "account": {
            "insured_name":         acc.insured_name,
            "dba":                  acc.dba,
            "mailing_address":      acc.mailing_address,
            "effective_date":       acc.effective_date,
            "expiration_date":      acc.expiration_date,
            "primary_operations":   acc.primary_operations,
            "naics":                acc.naics,
            "sic":                  None,
            "currency":             acc.currency,
            "valuation_date":       acc.valuation_date,
            "total_insured_value":  round(tiv, 2),
            "location_count":       location_count,
            "broker_name":          acc.broker.name,
            "broker_contact":       acc.broker.contact,
            "broker_email":         acc.broker.email,
            "broker_phone":         acc.broker.phone,
            "prepared_by":          acc.prepared_by,
            "prepared_date":        acc.prepared_date,
        },
        "locations": locations,
        "derived_flags": {
            "in_appetite":          not shooting,  # demo simplification
            "shooting_involved":    shooting,
            "high_hazard_present":  high_hazard,
            "gl_class_codes":       [],  # placeholder — would be derived from operations_description
            "data_quality_issues":  acc.seeded_anomalies,
            "cat_concentration":    cat_concentration,
            "top_risk_locations":   top_risk,
        },
        "_demo_metadata": {
            "key":             acc.key,
            "template_style":  acc.template_style,
        },
    }


def write_expected_outputs() -> None:
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    for i, acc in enumerate(ACCOUNTS, start=1):
        out = EXPECTED_DIR / f"{i:02d}_{acc.key}.json"
        out.write_text(json.dumps(_account_to_dict(acc), indent=2), encoding="utf-8")
        print(f"  wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    print("Writing expected-output ground-truth JSON files...")
    write_expected_outputs()
    print("Done.")
