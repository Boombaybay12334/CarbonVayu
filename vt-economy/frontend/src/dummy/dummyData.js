// DUMMY DATA - replace all of this with live Supabase queries as tasks are completed

export const DUMMY_STATES = [
  { id: "s1", name: "Sikkim", vt_balance: 9420, yoy_delta: +340, rank: 1, archetype: "Mountain Carbon Sink", ecosystem: "Alpine Forest + Glacial", area_km2: 7096 },
  { id: "s2", name: "Himachal Pradesh", vt_balance: 8870, yoy_delta: +210, rank: 2, archetype: "Forest Buffer", ecosystem: "Temperate Conifer + River Valley", area_km2: 55673 },
  { id: "s3", name: "Arunachal Pradesh", vt_balance: 8210, yoy_delta: +180, rank: 3, archetype: "Primary Forest Reserve", ecosystem: "Tropical + Subtropical Broadleaf", area_km2: 83743 },
  { id: "s4", name: "Uttarakhand", vt_balance: 7650, yoy_delta: -90, rank: 4, archetype: "Himalayan Watershed", ecosystem: "Alpine + Mixed Forest", area_km2: 53483 },
  { id: "s5", name: "Meghalaya", vt_balance: 7100, yoy_delta: +120, rank: 5, archetype: "Rainforest Sink", ecosystem: "Tropical Moist Broadleaf", area_km2: 22429 },
  { id: "s6", name: "Mizoram", vt_balance: 6800, yoy_delta: +60, rank: 6, archetype: "Bamboo Forest Zone", ecosystem: "Mixed Bamboo + Broadleaf", area_km2: 21081 },
  { id: "s7", name: "Karnataka", vt_balance: 6340, yoy_delta: +420, rank: 7, archetype: "Coastal Carbon Sink", ecosystem: "Tropical Forest + Coastline", area_km2: 191791 },
  { id: "s8", name: "Kerala", vt_balance: 6100, yoy_delta: +200, rank: 8, archetype: "Backwater Ecosystem", ecosystem: "Tropical Moist + Mangrove", area_km2: 38852 },
  { id: "s9", name: "Tamil Nadu", vt_balance: 4900, yoy_delta: -80, rank: 9, archetype: "Coastal Industrial Mix", ecosystem: "Tropical Dry + Coastline", area_km2: 130058 },
  { id: "s10", name: "Odisha", vt_balance: 4500, yoy_delta: -120, rank: 10, archetype: "Transitional Forest", ecosystem: "Dry Deciduous + Coastal", area_km2: 155707 },
  { id: "s11", name: "Rajasthan", vt_balance: 3800, yoy_delta: -200, rank: 11, archetype: "Arid Emitter", ecosystem: "Desert + Scrubland", area_km2: 342239 },
  { id: "s12", name: "Madhya Pradesh", vt_balance: 3500, yoy_delta: -150, rank: 12, archetype: "Deforested Interior", ecosystem: "Tropical Dry Deciduous", area_km2: 308252 },
  { id: "s13", name: "Uttar Pradesh", vt_balance: 2900, yoy_delta: -300, rank: 13, archetype: "Agricultural Emitter", ecosystem: "Indo-Gangetic Plain", area_km2: 240928 },
  { id: "s14", name: "Chhattisgarh", vt_balance: 2750, yoy_delta: -180, rank: 14, archetype: "Mining Zone", ecosystem: "Central Forest + Industrial", area_km2: 135192 },
  { id: "s15", name: "Goa", vt_balance: 2300, yoy_delta: -90, rank: 15, archetype: "Coastal Tourism Emitter", ecosystem: "Tropical + Coastal Strip", area_km2: 3702 },
  { id: "s16", name: "Haryana", vt_balance: 2100, yoy_delta: -250, rank: 16, archetype: "Stubble Burning Zone", ecosystem: "Semi-Arid Agricultural", area_km2: 44212 },
  { id: "s17", name: "Jharkhand", vt_balance: 1580, yoy_delta: -320, rank: 17, archetype: "Heavy Industrial", ecosystem: "Chota Nagpur + Forest", area_km2: 79716 },
  { id: "s18", name: "Delhi", vt_balance: 1200, yoy_delta: -410, rank: 18, archetype: "Urban Heat Emitter", ecosystem: "Urban + Peri-urban", area_km2: 1484 },
];

export const DUMMY_TIMESERIES = {
  Karnataka: [
    { year: 2019, vt_score: 5100, note: "Baseline" },
    { year: 2020, vt_score: 5400, note: "Lockdown reduced industrial output" },
    { year: 2021, vt_score: 5700, note: "Western Ghats afforestation drive" },
    { year: 2022, vt_score: 5900, note: "Port emissions fined" },
    { year: 2023, vt_score: 5920, note: "Stable" },
    { year: 2024, vt_score: 6340, note: "Solar adoption boost" },
  ],
};

export const DUMMY_RELATIONS = {
  Karnataka: {
    affected_by: [
      { state: "Goa", type: "Coastal drift emitter", vt_impact: -80, status: "fine_pending" },
      { state: "Maharashtra", type: "Upwind industrial emissions", vt_impact: -210, status: "fine_pending" },
    ],
    affecting: [
      { state: "Tamil Nadu", type: "Western Ghats river carbon flow", vt_impact: +120, status: "gain" },
    ],
  },
};

export const DUMMY_PROJECTS = [
  { id: "p1", state_name: "Odisha", title: "Mangrove Restoration Belt", description: "Restoring 2000 ha of mangroves along the Mahanadi delta.", vt_gain_estimate: 800, funds_needed: 4000000, funds_raised: 1200000 },
  { id: "p2", state_name: "Rajasthan", title: "Desert Solar Grid", description: "Community solar installations reducing fossil dependence.", vt_gain_estimate: 600, funds_needed: 8000000, funds_raised: 3500000 },
  { id: "p3", state_name: "Jharkhand", title: "Mine Reforestation", description: "Afforestation over 500 ha of retired mine land.", vt_gain_estimate: 1100, funds_needed: 6000000, funds_raised: 800000 },
];
