# `in_use.product_chunks` — Schema & Sample Rows

Database: `cs_electric` · Schema: `in_use` · Table: `product_chunks`

## Table schema

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `integer` | NOT NULL | GENERATED ALWAYS AS IDENTITY | Primary key |
| `product_id` | `integer` | NULL | — | Related product identifier |
| `taxonomy` | `jsonb` | NOT NULL | — | Taxonomy metadata (category, node_type, decoded, etc.) |
| `product` | `jsonb` | NOT NULL | — | Product metadata (sku_code, etc.) |
| `details` | `jsonb` | NOT NULL | `'{}'::jsonb` | Additional details |
| `content` | `text` | NOT NULL | — | Chunk text content used for search |
| `embedding` | `vector(384)` | NULL | — | Embedding vector (384 dimensions) |
| `is_active` | `boolean` | NOT NULL | `true` | Active flag |
| `create_datetime` | `timestamp without time zone` | NOT NULL | — | Created at |
| `lastchange_datetime` | `timestamp without time zone` | NOT NULL | — | Last updated at |
| `chunk_type` | `text` | NULL | — | Chunk type (identity, price, specs, technical) |

### Constraints

- **PRIMARY KEY**: `product_chunk_pk` on `id`

### Indexes

| Index | Definition |
|---|---|
| `product_chunk_pk` | UNIQUE btree (`id`) — PRIMARY KEY |
| `idx_pc_ctype` | btree (`chunk_type`) |
| `idx_pc_details` | gin (`details` jsonb_path_ops) |
| `idx_pc_node` | btree ((`taxonomy` ->> 'node_type')) |
| `idx_pc_sku` | btree ((`product` ->> 'sku_code')) |
| `idx_pc_sku_trgm` | gin ((`product` ->> 'sku_code') gin_trgm_ops) |

## Row counts (filtered categories)

| `taxonomy->>'category'` | Rows |
|---|---|
| `ACB – AH-AHA` | 6,887 |
| `ACB – WiNmaster 2` | 4,302 |
| `ACB – WiNmaster 3` | 2,380 |
| **Total** | **13,569** |

Observed `chunk_type` values in these categories: `identity`, `price`, `specs`, `technical`.

## Sample rows

One sample row per `(category, chunk_type)` pair (12 rows total). The `embedding` column is omitted; presence is shown as `has_embedding`. Long `content` values are truncated for readability.

### Category: `ACB – AH-AHA` · chunk_type: `identity`

- **id**: `25490`
- **product_id**: `101530`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:28:59.200664`
- **lastchange_datetime**: `2026-08-11T16:28:59.200664`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "path": [],
  "decoded": {
    "poles": {
      "code": null,
      "source": "default",
      "meaning": 3
    },
    "release": {
      "code": "MP3.1",
      "meaning": "MicroPro 3.1 (LSIG, true-RMS, fault indication)"
    },
    "mounting": {
      "code": "MF",
      "meaning": "manual_fixed"
    },
    "rating_idx": {
      "code": "06",
      "meaning": 630
    },
    "frame_class": {
      "code": "B",
      "meaning": "unknown"
    },
    "std_accessories": {
      "code": "(S)",
      "meaning": "supplied with standard accessories"
    }
  },
  "category": "ACB – AH-AHA",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/",
  "family": "ACB – AH-AHA",
  "sku_code": "AH06BCSMP3.1MF(S)",
  "more_info": {
    "2_4": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "2, 4",
      "value": null,
      "display": "R phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "6_8": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "6, 8",
      "value": null,
      "display": "Y phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "10_12": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "10, 12",
      "value": null,
      "display": "B phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "14_16": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "14, 16",
      "value": null,
      "display": "N phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "18_20": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "18, 20",
      "value": null,
      "display": "MHT coil",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "22_24": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "22, 24",
      "value": 24.0,
      "display": "24V DC supply from power supply module",
      "numeric": true,
      "value_max": 24.0,
      "value_min": 24.0,
      "value_kind": "scalar"
    },
    "surge": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Surge",
      "value": null,
      "display": "IEC 801 - 5",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "zi_d19": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "Zi ~ D19",
      "value": null,
      "display": "DI & DO outputs",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Impulse",
      "value": null,
      "display": "IEC 255 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "o_p_gnd": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": "V",
      "label": "O/P + & GND",
      "value": 24.0,
      "display": "Output 24 V DC supply, can be used for MicroPro auxiliary supply",
      "numeric": true,
      "value_max": 24.0,
      "value_min": 24.0,
      "value_kind": "scalar"
    },
    "testing": {
      "from": "brochure",
      "unit": null,
      "label": "Testing",
      "value": null,
      "display": "Tested at CPRI / ERTL; tested for most onerous environmental conditions",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "compliance": {
      "from": "brochure",
      "unit": null,
      "label": "Compliance",
      "value": null,
      "display": "RoHS compliant",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "frame_sizes": {
      "from": "brochure",
      "unit": null,
      "label": "Frame sizes",
      "value": 3.0,
      "display": "3 frame sizes for the entire range (maximum interchangeability, minimum spares inventory)",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "closing_time": {
      "from": "brochure",
      "unit": "ms",
      "label": "Closing time",
      "value": 40.0,
      "display": "40 ms",
      "numeric": true,
      "value_max": 40.0,
      "value_min": 40.0,
      "value_kind": "scalar"
    },
    "zo_common_do": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "ZO / COMMON / DO",
      "value": null,
      "display": "Zone selectivity",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "dry_heat_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Dry Heat Test",
      "value": 9000.0,
      "display": "IS 9000 - PG3",
      "numeric": true,
      "value_max": 9000.0,
      "value_min": 9000.0,
      "value_kind": "scalar"
    },
    "damp_heat_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Damp Heat Test",
      "value": 9000.0,
      "display": "IS 9000 - PG4",
      "numeric": true,
      "value_max": 9000.0,
      "value_min": 9000.0,
      "value_kind": "scalar"
    },
    "earth_terminal": {
      "from": "brochure",
      "unit": null,
      "label": "Earth terminal",
      "value": 8.0,
      "display": "M8",
      "numeric": true,
      "value_max": 8.0,
      "value_min": 8.0,
      "value_kind": "scalar"
    },
    "overload_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Overload delay",
      "value": null,
      "display": "2.5–35 sec at 6 Ir in 14 steps: 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35",
      "numeric": true,
      "value_max": 35.0,
      "value_min": 2.5,
      "value_kind": "range"
    },
    "safety_shutter": {
      "from": "brochure",
      "unit": null,
      "label": "Safety shutter",
      "value": null,
      "display": "Fibre glass, main-circuit safety shutters on draw-out type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "vibration_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Vibration Test",
      "value": null,
      "display": "IEC 255 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "m_pro_d_m_pro_d": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "M-PRO D(+) & M-PRO D(-)",
      "value": null,
      "display": "To be connected with MicroPro release for communication to ACB",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "spring_charging": {
      "from": "brochure",
      "unit": null,
      "label": "Spring charging",
      "value": null,
      "display": "Manual charging or motor charging",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "contact_material": {
      "from": "brochure",
      "unit": null,
      "label": "Contact material",
      "value": null,
      "display": "Special sintered metal contacts",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mounting_options": {
      "from": "brochure",
      "unit": null,
      "label": "Mounting options",
      "value": null,
      "display": "Fixed or draw-out",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "overload_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Overload pick up",
      "value": null,
      "display": "0.4–1.1 In with OFF, in 9 steps: OFF, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1",
      "numeric": true,
      "value_max": 1.1,
      "value_min": 0.4,
      "value_kind": "range"
    },
    "pollution_degree": {
      "from": "brochure",
      "unit": null,
      "label": "Pollution degree",
      "value": 3.0,
      "display": "3",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "earth_fault_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Earth fault delay",
      "value": null,
      "display": "0.05–0.8 sec in 16 steps: 0.05 to 0.80 in 0.05 sec increments",
      "numeric": true,
      "value_max": 0.8,
      "value_min": 0.05,
      "value_kind": "range"
    },
    "master_d_master_d": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "Master D (+) & Master D (-)",
      "value": [
        485.0,
        232.0
      ],
      "display": "To be connected with RS 485/232 converter to master PC",
      "numeric": true,
      "value_max": 485.0,
      "value_min": 232.0,
      "value_kind": "set"
    },
    "neutral_protection": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Neutral protection",
      "value": 3.1,
      "display": "Not available on 3.1",
      "numeric": true,
      "value_max": 3.1,
      "value_min": 3.1,
      "value_kind": "scalar"
    },
    "applicable_standard": {
      "from": "brochure",
      "unit": null,
      "label": "Applicable standard",
      "value": null,
      "display": "Conforms to IS/IEC 60947-2 (brochure). The website product page states IEC 60947-2 / IS 13947-2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "earth_fault_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Earth fault pick up",
      "value": null,
      "display": "0.2–0.9 In with OFF, in 9 steps: OFF, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9",
      "numeric": true,
      "value_max": 0.9,
      "value_min": 0.2,
      "value_kind": "range"
    },
    "short_circuit_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Short circuit delay",
      "value": null,
      "display": "0.05–0.8 sec in 16 steps: 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80",
      "numeric": true,
      "value_max": 0.8,
      "value_min": 0.05,
      "value_kind": "range"
    },
    "total_breaking_time": {
      "from": "brochure",
      "unit": "ms",
      "label": "Total breaking time",
      "value": 30.0,
      "display": "Less than 30 ms (including arcing time of less than 10 ms)",
      "numeric": true,
      "value_max": 30.0,
      "value_min": 30.0,
      "value_kind": "scalar"
    },
    "insulating_materials": {
      "from": "brochure",
      "unit": null,
      "label": "Insulating materials",
      "value": null,
      "display": "Class 'B' and class 'F' (high dielectric strength in hot and humid conditions)",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "instantaneous_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Instantaneous pick up",
      "value": null,
      "display": "3.0–10 In with OFF, in 9 steps: OFF, 3, 4, 5, 6, 7, 8, 9, 10",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "short_circuit_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Short circuit pick up",
      "value": null,
      "display": "1.5–9.0 Ir in 16 steps: 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0",
      "numeric": true,
      "value_max": 9.0,
      "value_min": 1.5,
      "value_kind": "range"
    },
    "230_v_i_p_l_i_p_n_i_p_e": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": "V",
      "label": "230 V I/P L … I/P N … I/P E",
      "value": 230.0,
      "display": "Input supply 230 V AC for communication module; phase to L, neutral to N, earth to E",
      "numeric": true,
      "value_max": 230.0,
      "value_min": 230.0,
      "value_kind": "scalar"
    },
    "ampere_frame_designation": {
      "from": "brochure",
      "unit": null,
      "label": "Ampere frame designation",
      "value": null,
      "display": "As per IEC 60947-2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "electrostatic_discharge_esd": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Electrostatic Discharge (ESD)",
      "value": null,
      "display": "IEC 801 - 2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "electrical_fast_transient_eft": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Electrical Fast Transient (EFT)",
      "value": null,
      "display": "IEC 801 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "neutral_pole_behaviour_4_pole": {
      "from": "brochure",
      "unit": null,
      "label": "Neutral pole behaviour (4 pole)",
      "value": null,
      "display": "Closes early and opens later, preventing transient over-voltages between live and neutral",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "l_t_d_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "L.T.D time delay setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "control_circuit_terminal_blocks": {
      "from": "brochure",
      "unit": null,
      "label": "Control-circuit terminal blocks",
      "value": 36.0,
      "display": "36-M4",
      "numeric": true,
      "value_max": 36.0,
      "value_min": 36.0,
      "value_kind": "scalar"
    },
    "inst_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "INST trip current setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "l_t_d_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "L.T.D trip current setting range",
      "value": 5.0,
      "display": "±5%",
      "numeric": true,
      "value_max": 5.0,
      "value_min": 5.0,
      "value_kind": "scalar"
    },
    "radio_frequency_interference_rfi": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Radio Frequency Interference (RFI)",
      "value": null,
      "display": "IEC 801 - 3",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "s_t_d_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": "S",
      "label": "S.T.D trip current setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "s_t_d_trip_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": "S",
      "label": "S.T.D trip time delay setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "earth_fault_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "Earth fault trip current setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "earth_fault_trip_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "Earth fault trip time delay setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "reference_voltage_for_breaking_capacity_data": {
      "from": "brochure",
      "unit": "V",
      "label": "Reference voltage for breaking-capacity data",
      "value": 415.0,
      "display": "415 V AC",
      "numeric": true,
      "value_max": 415.0,
      "value_min": 415.0,
      "value_kind": "scalar"
    }
  },
  "description": null,
  "price_status": "por",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": []
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-001",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Width in modules",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 modules.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "modules"
    },
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-002",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 poles.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "A",
      "value": 630.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-003",
      "value_max": 630.0,
      "value_min": 630.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a rated current (in) of 630 A.",
      "value_display": "630 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-004",
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a utilisation category of B.",
      "value_display": "B",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "INR",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-price",
      "spec_label": "MRP",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "sources": [
    "Brochure: ACB_AHA.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/"
  ],
  "completeness": {
    "chunks": 11,
    "decoded": true,
    "missing": [
      "price_inr",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 4
  }
}
```

**content** (376 chars)

```
AH06BCSMP3.1MF(S) — ACB – AH-AHA
Ordering code breakdown: rating idx 06 = 630; frame class B = unknown; release MP3.1 = MicroPro 3.1 (LSIG, true-RMS, fault indication); mounting MF = manual_fixed; std accessories (S) = supplied with standard accessories; poles None = 3.
Used in: Distribution & Transmission, Industries, Infrastructure, Original Equipment Manufacturers (OEM).
```

### Category: `ACB – AH-AHA` · chunk_type: `price`

- **id**: `25491`
- **product_id**: `101530`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:28:59.200664`
- **lastchange_datetime**: `2026-08-11T16:28:59.200664`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "path": [],
  "decoded": {
    "poles": {
      "code": null,
      "source": "default",
      "meaning": 3
    },
    "release": {
      "code": "MP3.1",
      "meaning": "MicroPro 3.1 (LSIG, true-RMS, fault indication)"
    },
    "mounting": {
      "code": "MF",
      "meaning": "manual_fixed"
    },
    "rating_idx": {
      "code": "06",
      "meaning": 630
    },
    "frame_class": {
      "code": "B",
      "meaning": "unknown"
    },
    "std_accessories": {
      "code": "(S)",
      "meaning": "supplied with standard accessories"
    }
  },
  "category": "ACB – AH-AHA",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/",
  "family": "ACB – AH-AHA",
  "sku_code": "AH06BCSMP3.1MF(S)",
  "more_info": {
    "2_4": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "2, 4",
      "value": null,
      "display": "R phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "6_8": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "6, 8",
      "value": null,
      "display": "Y phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "10_12": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "10, 12",
      "value": null,
      "display": "B phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "14_16": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "14, 16",
      "value": null,
      "display": "N phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "18_20": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "18, 20",
      "value": null,
      "display": "MHT coil",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "22_24": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "22, 24",
      "value": 24.0,
      "display": "24V DC supply from power supply module",
      "numeric": true,
      "value_max": 24.0,
      "value_min": 24.0,
      "value_kind": "scalar"
    },
    "surge": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Surge",
      "value": null,
      "display": "IEC 801 - 5",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "zi_d19": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "Zi ~ D19",
      "value": null,
      "display": "DI & DO outputs",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Impulse",
      "value": null,
      "display": "IEC 255 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "o_p_gnd": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": "V",
      "label": "O/P + & GND",
      "value": 24.0,
      "display": "Output 24 V DC supply, can be used for MicroPro auxiliary supply",
      "numeric": true,
      "value_max": 24.0,
      "value_min": 24.0,
      "value_kind": "scalar"
    },
    "testing": {
      "from": "brochure",
      "unit": null,
      "label": "Testing",
      "value": null,
      "display": "Tested at CPRI / ERTL; tested for most onerous environmental conditions",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "compliance": {
      "from": "brochure",
      "unit": null,
      "label": "Compliance",
      "value": null,
      "display": "RoHS compliant",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "frame_sizes": {
      "from": "brochure",
      "unit": null,
      "label": "Frame sizes",
      "value": 3.0,
      "display": "3 frame sizes for the entire range (maximum interchangeability, minimum spares inventory)",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "closing_time": {
      "from": "brochure",
      "unit": "ms",
      "label": "Closing time",
      "value": 40.0,
      "display": "40 ms",
      "numeric": true,
      "value_max": 40.0,
      "value_min": 40.0,
      "value_kind": "scalar"
    },
    "zo_common_do": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "ZO / COMMON / DO",
      "value": null,
      "display": "Zone selectivity",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "dry_heat_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Dry Heat Test",
      "value": 9000.0,
      "display": "IS 9000 - PG3",
      "numeric": true,
      "value_max": 9000.0,
      "value_min": 9000.0,
      "value_kind": "scalar"
    },
    "damp_heat_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Damp Heat Test",
      "value": 9000.0,
      "display": "IS 9000 - PG4",
      "numeric": true,
      "value_max": 9000.0,
      "value_min": 9000.0,
      "value_kind": "scalar"
    },
    "earth_terminal": {
      "from": "brochure",
      "unit": null,
      "label": "Earth terminal",
      "value": 8.0,
      "display": "M8",
      "numeric": true,
      "value_max": 8.0,
      "value_min": 8.0,
      "value_kind": "scalar"
    },
    "overload_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Overload delay",
      "value": null,
      "display": "2.5–35 sec at 6 Ir in 14 steps: 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35",
      "numeric": true,
      "value_max": 35.0,
      "value_min": 2.5,
      "value_kind": "range"
    },
    "safety_shutter": {
      "from": "brochure",
      "unit": null,
      "label": "Safety shutter",
      "value": null,
      "display": "Fibre glass, main-circuit safety shutters on draw-out type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "vibration_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Vibration Test",
      "value": null,
      "display": "IEC 255 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "m_pro_d_m_pro_d": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "M-PRO D(+) & M-PRO D(-)",
      "value": null,
      "display": "To be connected with MicroPro release for communication to ACB",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "spring_charging": {
      "from": "brochure",
      "unit": null,
      "label": "Spring charging",
      "value": null,
      "display": "Manual charging or motor charging",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "contact_material": {
      "from": "brochure",
      "unit": null,
      "label": "Contact material",
      "value": null,
      "display": "Special sintered metal contacts",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mounting_options": {
      "from": "brochure",
      "unit": null,
      "label": "Mounting options",
      "value": null,
      "display": "Fixed or draw-out",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "overload_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Overload pick up",
      "value": null,
      "display": "0.4–1.1 In with OFF, in 9 steps: OFF, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1",
      "numeric": true,
      "value_max": 1.1,
      "value_min": 0.4,
      "value_kind": "range"
    },
    "pollution_degree": {
      "from": "brochure",
      "unit": null,
      "label": "Pollution degree",
      "value": 3.0,
      "display": "3",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "earth_fault_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Earth fault delay",
      "value": null,
      "display": "0.05–0.8 sec in 16 steps: 0.05 to 0.80 in 0.05 sec increments",
      "numeric": true,
      "value_max": 0.8,
      "value_min": 0.05,
      "value_kind": "range"
    },
    "master_d_master_d": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "Master D (+) & Master D (-)",
      "value": [
        485.0,
        232.0
      ],
      "display": "To be connected with RS 485/232 converter to master PC",
      "numeric": true,
      "value_max": 485.0,
      "value_min": 232.0,
      "value_kind": "set"
    },
    "neutral_protection": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Neutral protection",
      "value": 3.1,
      "display": "Not available on 3.1",
      "numeric": true,
      "value_max": 3.1,
      "value_min": 3.1,
      "value_kind": "scalar"
    },
    "applicable_standard": {
      "from": "brochure",
      "unit": null,
      "label": "Applicable standard",
      "value": null,
      "display": "Conforms to IS/IEC 60947-2 (brochure). The website product page states IEC 60947-2 / IS 13947-2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "earth_fault_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Earth fault pick up",
      "value": null,
      "display": "0.2–0.9 In with OFF, in 9 steps: OFF, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9",
      "numeric": true,
      "value_max": 0.9,
      "value_min": 0.2,
      "value_kind": "range"
    },
    "short_circuit_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Short circuit delay",
      "value": null,
      "display": "0.05–0.8 sec in 16 steps: 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80",
      "numeric": true,
      "value_max": 0.8,
      "value_min": 0.05,
      "value_kind": "range"
    },
    "total_breaking_time": {
      "from": "brochure",
      "unit": "ms",
      "label": "Total breaking time",
      "value": 30.0,
      "display": "Less than 30 ms (including arcing time of less than 10 ms)",
      "numeric": true,
      "value_max": 30.0,
      "value_min": 30.0,
      "value_kind": "scalar"
    },
    "insulating_materials": {
      "from": "brochure",
      "unit": null,
      "label": "Insulating materials",
      "value": null,
      "display": "Class 'B' and class 'F' (high dielectric strength in hot and humid conditions)",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "instantaneous_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Instantaneous pick up",
      "value": null,
      "display": "3.0–10 In with OFF, in 9 steps: OFF, 3, 4, 5, 6, 7, 8, 9, 10",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "short_circuit_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Short circuit pick up",
      "value": null,
      "display": "1.5–9.0 Ir in 16 steps: 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0",
      "numeric": true,
      "value_max": 9.0,
      "value_min": 1.5,
      "value_kind": "range"
    },
    "230_v_i_p_l_i_p_n_i_p_e": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": "V",
      "label": "230 V I/P L … I/P N … I/P E",
      "value": 230.0,
      "display": "Input supply 230 V AC for communication module; phase to L, neutral to N, earth to E",
      "numeric": true,
      "value_max": 230.0,
      "value_min": 230.0,
      "value_kind": "scalar"
    },
    "ampere_frame_designation": {
      "from": "brochure",
      "unit": null,
      "label": "Ampere frame designation",
      "value": null,
      "display": "As per IEC 60947-2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "electrostatic_discharge_esd": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Electrostatic Discharge (ESD)",
      "value": null,
      "display": "IEC 801 - 2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "electrical_fast_transient_eft": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Electrical Fast Transient (EFT)",
      "value": null,
      "display": "IEC 801 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "neutral_pole_behaviour_4_pole": {
      "from": "brochure",
      "unit": null,
      "label": "Neutral pole behaviour (4 pole)",
      "value": null,
      "display": "Closes early and opens later, preventing transient over-voltages between live and neutral",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "l_t_d_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "L.T.D time delay setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "control_circuit_terminal_blocks": {
      "from": "brochure",
      "unit": null,
      "label": "Control-circuit terminal blocks",
      "value": 36.0,
      "display": "36-M4",
      "numeric": true,
      "value_max": 36.0,
      "value_min": 36.0,
      "value_kind": "scalar"
    },
    "inst_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "INST trip current setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "l_t_d_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "L.T.D trip current setting range",
      "value": 5.0,
      "display": "±5%",
      "numeric": true,
      "value_max": 5.0,
      "value_min": 5.0,
      "value_kind": "scalar"
    },
    "radio_frequency_interference_rfi": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Radio Frequency Interference (RFI)",
      "value": null,
      "display": "IEC 801 - 3",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "s_t_d_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": "S",
      "label": "S.T.D trip current setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "s_t_d_trip_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": "S",
      "label": "S.T.D trip time delay setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "earth_fault_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "Earth fault trip current setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "earth_fault_trip_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "Earth fault trip time delay setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "reference_voltage_for_breaking_capacity_data": {
      "from": "brochure",
      "unit": "V",
      "label": "Reference voltage for breaking-capacity data",
      "value": 415.0,
      "display": "415 V AC",
      "numeric": true,
      "value_max": 415.0,
      "value_min": 415.0,
      "value_kind": "scalar"
    }
  },
  "description": null,
  "price_status": "por",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": []
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-001",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Width in modules",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 modules.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "modules"
    },
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-002",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 poles.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "A",
      "value": 630.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-003",
      "value_max": 630.0,
      "value_min": 630.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a rated current (in) of 630 A.",
      "value_display": "630 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-004",
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a utilisation category of B.",
      "value_display": "B",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "INR",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-price",
      "spec_label": "MRP",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "sources": [
    "Brochure: ACB_AHA.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/"
  ],
  "completeness": {
    "chunks": 11,
    "decoded": true,
    "missing": [
      "price_inr",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 4
  }
}
```

**content** (174 chars)

```
AH06BCSMP3.1MF(S) — ACB – AH-AHA
Price and availability:
No list price: this page of the C&S pricelist states the price is on request — contact the nearest C&S branch office.
```

### Category: `ACB – AH-AHA` · chunk_type: `specs`

- **id**: `25492`
- **product_id**: `101530`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:28:59.200664`
- **lastchange_datetime**: `2026-08-11T16:28:59.200664`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "part": 1,
  "path": [],
  "parts": 2,
  "decoded": {
    "poles": {
      "code": null,
      "source": "default",
      "meaning": 3
    },
    "release": {
      "code": "MP3.1",
      "meaning": "MicroPro 3.1 (LSIG, true-RMS, fault indication)"
    },
    "mounting": {
      "code": "MF",
      "meaning": "manual_fixed"
    },
    "rating_idx": {
      "code": "06",
      "meaning": 630
    },
    "frame_class": {
      "code": "B",
      "meaning": "unknown"
    },
    "std_accessories": {
      "code": "(S)",
      "meaning": "supplied with standard accessories"
    }
  },
  "category": "ACB – AH-AHA",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/",
  "family": "ACB – AH-AHA",
  "sku_code": "AH06BCSMP3.1MF(S)",
  "more_info": {
    "2_4": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "2, 4",
      "value": null,
      "display": "R phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "6_8": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "6, 8",
      "value": null,
      "display": "Y phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "10_12": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "10, 12",
      "value": null,
      "display": "B phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "14_16": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "14, 16",
      "value": null,
      "display": "N phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "18_20": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "18, 20",
      "value": null,
      "display": "MHT coil",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "22_24": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "22, 24",
      "value": 24.0,
      "display": "24V DC supply from power supply module",
      "numeric": true,
      "value_max": 24.0,
      "value_min": 24.0,
      "value_kind": "scalar"
    },
    "surge": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Surge",
      "value": null,
      "display": "IEC 801 - 5",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "zi_d19": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "Zi ~ D19",
      "value": null,
      "display": "DI & DO outputs",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Impulse",
      "value": null,
      "display": "IEC 255 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "o_p_gnd": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": "V",
      "label": "O/P + & GND",
      "value": 24.0,
      "display": "Output 24 V DC supply, can be used for MicroPro auxiliary supply",
      "numeric": true,
      "value_max": 24.0,
      "value_min": 24.0,
      "value_kind": "scalar"
    },
    "testing": {
      "from": "brochure",
      "unit": null,
      "label": "Testing",
      "value": null,
      "display": "Tested at CPRI / ERTL; tested for most onerous environmental conditions",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "compliance": {
      "from": "brochure",
      "unit": null,
      "label": "Compliance",
      "value": null,
      "display": "RoHS compliant",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "frame_sizes": {
      "from": "brochure",
      "unit": null,
      "label": "Frame sizes",
      "value": 3.0,
      "display": "3 frame sizes for the entire range (maximum interchangeability, minimum spares inventory)",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "closing_time": {
      "from": "brochure",
      "unit": "ms",
      "label": "Closing time",
      "value": 40.0,
      "display": "40 ms",
      "numeric": true,
      "value_max": 40.0,
      "value_min": 40.0,
      "value_kind": "scalar"
    },
    "zo_common_do": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "ZO / COMMON / DO",
      "value": null,
      "display": "Zone selectivity",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "dry_heat_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Dry Heat Test",
      "value": 9000.0,
      "display": "IS 9000 - PG3",
      "numeric": true,
      "value_max": 9000.0,
      "value_min": 9000.0,
      "value_kind": "scalar"
    },
    "damp_heat_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Damp Heat Test",
      "value": 9000.0,
      "display": "IS 9000 - PG4",
      "numeric": true,
      "value_max": 9000.0,
      "value_min": 9000.0,
      "value_kind": "scalar"
    },
    "earth_terminal": {
      "from": "brochure",
      "unit": null,
      "label": "Earth terminal",
      "value": 8.0,
      "display": "M8",
      "numeric": true,
      "value_max": 8.0,
      "value_min": 8.0,
      "value_kind": "scalar"
    },
    "overload_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Overload delay",
      "value": null,
      "display": "2.5–35 sec at 6 Ir in 14 steps: 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35",
      "numeric": true,
      "value_max": 35.0,
      "value_min": 2.5,
      "value_kind": "range"
    },
    "safety_shutter": {
      "from": "brochure",
      "unit": null,
      "label": "Safety shutter",
      "value": null,
      "display": "Fibre glass, main-circuit safety shutters on draw-out type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "vibration_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Vibration Test",
      "value": null,
      "display": "IEC 255 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "m_pro_d_m_pro_d": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "M-PRO D(+) & M-PRO D(-)",
      "value": null,
      "display": "To be connected with MicroPro release for communication to ACB",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "spring_charging": {
      "from": "brochure",
      "unit": null,
      "label": "Spring charging",
      "value": null,
      "display": "Manual charging or motor charging",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "contact_material": {
      "from": "brochure",
      "unit": null,
      "label": "Contact material",
      "value": null,
      "display": "Special sintered metal contacts",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mounting_options": {
      "from": "brochure",
      "unit": null,
      "label": "Mounting options",
      "value": null,
      "display": "Fixed or draw-out",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "overload_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Overload pick up",
      "value": null,
      "display": "0.4–1.1 In with OFF, in 9 steps: OFF, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1",
      "numeric": true,
      "value_max": 1.1,
      "value_min": 0.4,
      "value_kind": "range"
    },
    "pollution_degree": {
      "from": "brochure",
      "unit": null,
      "label": "Pollution degree",
      "value": 3.0,
      "display": "3",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "earth_fault_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Earth fault delay",
      "value": null,
      "display": "0.05–0.8 sec in 16 steps: 0.05 to 0.80 in 0.05 sec increments",
      "numeric": true,
      "value_max": 0.8,
      "value_min": 0.05,
      "value_kind": "range"
    },
    "master_d_master_d": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "Master D (+) & Master D (-)",
      "value": [
        485.0,
        232.0
      ],
      "display": "To be connected with RS 485/232 converter to master PC",
      "numeric": true,
      "value_max": 485.0,
      "value_min": 232.0,
      "value_kind": "set"
    },
    "neutral_protection": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Neutral protection",
      "value": 3.1,
      "display": "Not available on 3.1",
      "numeric": true,
      "value_max": 3.1,
      "value_min": 3.1,
      "value_kind": "scalar"
    },
    "applicable_standard": {
      "from": "brochure",
      "unit": null,
      "label": "Applicable standard",
      "value": null,
      "display": "Conforms to IS/IEC 60947-2 (brochure). The website product page states IEC 60947-2 / IS 13947-2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "earth_fault_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Earth fault pick up",
      "value": null,
      "display": "0.2–0.9 In with OFF, in 9 steps: OFF, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9",
      "numeric": true,
      "value_max": 0.9,
      "value_min": 0.2,
      "value_kind": "range"
    },
    "short_circuit_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Short circuit delay",
      "value": null,
      "display": "0.05–0.8 sec in 16 steps: 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80",
      "numeric": true,
      "value_max": 0.8,
      "value_min": 0.05,
      "value_kind": "range"
    },
    "total_breaking_time": {
      "from": "brochure",
      "unit": "ms",
      "label": "Total breaking time",
      "value": 30.0,
      "display": "Less than 30 ms (including arcing time of less than 10 ms)",
      "numeric": true,
      "value_max": 30.0,
      "value_min": 30.0,
      "value_kind": "scalar"
    },
    "insulating_materials": {
      "from": "brochure",
      "unit": null,
      "label": "Insulating materials",
      "value": null,
      "display": "Class 'B' and class 'F' (high dielectric strength in hot and humid conditions)",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "instantaneous_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Instantaneous pick up",
      "value": null,
      "display": "3.0–10 In with OFF, in 9 steps: OFF, 3, 4, 5, 6, 7, 8, 9, 10",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "short_circuit_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Short circuit pick up",
      "value": null,
      "display": "1.5–9.0 Ir in 16 steps: 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0",
      "numeric": true,
      "value_max": 9.0,
      "value_min": 1.5,
      "value_kind": "range"
    },
    "230_v_i_p_l_i_p_n_i_p_e": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": "V",
      "label": "230 V I/P L … I/P N … I/P E",
      "value": 230.0,
      "display": "Input supply 230 V AC for communication module; phase to L, neutral to N, earth to E",
      "numeric": true,
      "value_max": 230.0,
      "value_min": 230.0,
      "value_kind": "scalar"
    },
    "ampere_frame_designation": {
      "from": "brochure",
      "unit": null,
      "label": "Ampere frame designation",
      "value": null,
      "display": "As per IEC 60947-2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "electrostatic_discharge_esd": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Electrostatic Discharge (ESD)",
      "value": null,
      "display": "IEC 801 - 2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "electrical_fast_transient_eft": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Electrical Fast Transient (EFT)",
      "value": null,
      "display": "IEC 801 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "neutral_pole_behaviour_4_pole": {
      "from": "brochure",
      "unit": null,
      "label": "Neutral pole behaviour (4 pole)",
      "value": null,
      "display": "Closes early and opens later, preventing transient over-voltages between live and neutral",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "l_t_d_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "L.T.D time delay setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "control_circuit_terminal_blocks": {
      "from": "brochure",
      "unit": null,
      "label": "Control-circuit terminal blocks",
      "value": 36.0,
      "display": "36-M4",
      "numeric": true,
      "value_max": 36.0,
      "value_min": 36.0,
      "value_kind": "scalar"
    },
    "inst_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "INST trip current setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "l_t_d_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "L.T.D trip current setting range",
      "value": 5.0,
      "display": "±5%",
      "numeric": true,
      "value_max": 5.0,
      "value_min": 5.0,
      "value_kind": "scalar"
    },
    "radio_frequency_interference_rfi": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Radio Frequency Interference (RFI)",
      "value": null,
      "display": "IEC 801 - 3",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "s_t_d_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": "S",
      "label": "S.T.D trip current setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "s_t_d_trip_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": "S",
      "label": "S.T.D trip time delay setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "earth_fault_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "Earth fault trip current setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "earth_fault_trip_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "Earth fault trip time delay setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "reference_voltage_for_breaking_capacity_data": {
      "from": "brochure",
      "unit": "V",
      "label": "Reference voltage for breaking-capacity data",
      "value": 415.0,
      "display": "415 V AC",
      "numeric": true,
      "value_max": 415.0,
      "value_min": 415.0,
      "value_kind": "scalar"
    }
  },
  "description": null,
  "price_status": "por",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": []
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-001",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Width in modules",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 modules.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "modules"
    },
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-002",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 poles.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "A",
      "value": 630.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-003",
      "value_max": 630.0,
      "value_min": 630.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a rated current (in) of 630 A.",
      "value_display": "630 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-004",
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a utilisation category of B.",
      "value_display": "B",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "INR",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-price",
      "spec_label": "MRP",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "sources": [
    "Brochure: ACB_AHA.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/"
  ],
  "completeness": {
    "chunks": 11,
    "decoded": true,
    "missing": [
      "price_inr",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 4
  }
}
```

**content** (282 chars)

```
AH06BCSMP3.1MF(S) — ACB – AH-AHA
AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 modules.
AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 poles.
```

### Category: `ACB – AH-AHA` · chunk_type: `technical`

- **id**: `25494`
- **product_id**: `101530`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:28:59.200664`
- **lastchange_datetime**: `2026-08-11T16:28:59.200664`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "part": 1,
  "path": [],
  "parts": 2,
  "decoded": {
    "poles": {
      "code": null,
      "source": "default",
      "meaning": 3
    },
    "release": {
      "code": "MP3.1",
      "meaning": "MicroPro 3.1 (LSIG, true-RMS, fault indication)"
    },
    "mounting": {
      "code": "MF",
      "meaning": "manual_fixed"
    },
    "rating_idx": {
      "code": "06",
      "meaning": 630
    },
    "frame_class": {
      "code": "B",
      "meaning": "unknown"
    },
    "std_accessories": {
      "code": "(S)",
      "meaning": "supplied with standard accessories"
    }
  },
  "heading": "Salient features",
  "category": "ACB – AH-AHA",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/",
  "family": "ACB – AH-AHA",
  "sku_code": "AH06BCSMP3.1MF(S)",
  "more_info": {
    "2_4": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "2, 4",
      "value": null,
      "display": "R phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "6_8": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "6, 8",
      "value": null,
      "display": "Y phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "10_12": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "10, 12",
      "value": null,
      "display": "B phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "14_16": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "14, 16",
      "value": null,
      "display": "N phase CT",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "18_20": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "18, 20",
      "value": null,
      "display": "MHT coil",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "22_24": {
      "from": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "unit": null,
      "label": "22, 24",
      "value": 24.0,
      "display": "24V DC supply from power supply module",
      "numeric": true,
      "value_max": 24.0,
      "value_min": 24.0,
      "value_kind": "scalar"
    },
    "surge": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Surge",
      "value": null,
      "display": "IEC 801 - 5",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "zi_d19": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "Zi ~ D19",
      "value": null,
      "display": "DI & DO outputs",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Impulse",
      "value": null,
      "display": "IEC 255 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "o_p_gnd": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": "V",
      "label": "O/P + & GND",
      "value": 24.0,
      "display": "Output 24 V DC supply, can be used for MicroPro auxiliary supply",
      "numeric": true,
      "value_max": 24.0,
      "value_min": 24.0,
      "value_kind": "scalar"
    },
    "testing": {
      "from": "brochure",
      "unit": null,
      "label": "Testing",
      "value": null,
      "display": "Tested at CPRI / ERTL; tested for most onerous environmental conditions",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "compliance": {
      "from": "brochure",
      "unit": null,
      "label": "Compliance",
      "value": null,
      "display": "RoHS compliant",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "frame_sizes": {
      "from": "brochure",
      "unit": null,
      "label": "Frame sizes",
      "value": 3.0,
      "display": "3 frame sizes for the entire range (maximum interchangeability, minimum spares inventory)",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "closing_time": {
      "from": "brochure",
      "unit": "ms",
      "label": "Closing time",
      "value": 40.0,
      "display": "40 ms",
      "numeric": true,
      "value_max": 40.0,
      "value_min": 40.0,
      "value_kind": "scalar"
    },
    "zo_common_do": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "ZO / COMMON / DO",
      "value": null,
      "display": "Zone selectivity",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "dry_heat_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Dry Heat Test",
      "value": 9000.0,
      "display": "IS 9000 - PG3",
      "numeric": true,
      "value_max": 9000.0,
      "value_min": 9000.0,
      "value_kind": "scalar"
    },
    "damp_heat_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Damp Heat Test",
      "value": 9000.0,
      "display": "IS 9000 - PG4",
      "numeric": true,
      "value_max": 9000.0,
      "value_min": 9000.0,
      "value_kind": "scalar"
    },
    "earth_terminal": {
      "from": "brochure",
      "unit": null,
      "label": "Earth terminal",
      "value": 8.0,
      "display": "M8",
      "numeric": true,
      "value_max": 8.0,
      "value_min": 8.0,
      "value_kind": "scalar"
    },
    "overload_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Overload delay",
      "value": null,
      "display": "2.5–35 sec at 6 Ir in 14 steps: 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35",
      "numeric": true,
      "value_max": 35.0,
      "value_min": 2.5,
      "value_kind": "range"
    },
    "safety_shutter": {
      "from": "brochure",
      "unit": null,
      "label": "Safety shutter",
      "value": null,
      "display": "Fibre glass, main-circuit safety shutters on draw-out type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "vibration_test": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Vibration Test",
      "value": null,
      "display": "IEC 255 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "m_pro_d_m_pro_d": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "M-PRO D(+) & M-PRO D(-)",
      "value": null,
      "display": "To be connected with MicroPro release for communication to ACB",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "spring_charging": {
      "from": "brochure",
      "unit": null,
      "label": "Spring charging",
      "value": null,
      "display": "Manual charging or motor charging",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "contact_material": {
      "from": "brochure",
      "unit": null,
      "label": "Contact material",
      "value": null,
      "display": "Special sintered metal contacts",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mounting_options": {
      "from": "brochure",
      "unit": null,
      "label": "Mounting options",
      "value": null,
      "display": "Fixed or draw-out",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "overload_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Overload pick up",
      "value": null,
      "display": "0.4–1.1 In with OFF, in 9 steps: OFF, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1",
      "numeric": true,
      "value_max": 1.1,
      "value_min": 0.4,
      "value_kind": "range"
    },
    "pollution_degree": {
      "from": "brochure",
      "unit": null,
      "label": "Pollution degree",
      "value": 3.0,
      "display": "3",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "earth_fault_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Earth fault delay",
      "value": null,
      "display": "0.05–0.8 sec in 16 steps: 0.05 to 0.80 in 0.05 sec increments",
      "numeric": true,
      "value_max": 0.8,
      "value_min": 0.05,
      "value_kind": "range"
    },
    "master_d_master_d": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": null,
      "label": "Master D (+) & Master D (-)",
      "value": [
        485.0,
        232.0
      ],
      "display": "To be connected with RS 485/232 converter to master PC",
      "numeric": true,
      "value_max": 485.0,
      "value_min": 232.0,
      "value_kind": "set"
    },
    "neutral_protection": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Neutral protection",
      "value": 3.1,
      "display": "Not available on 3.1",
      "numeric": true,
      "value_max": 3.1,
      "value_min": 3.1,
      "value_kind": "scalar"
    },
    "applicable_standard": {
      "from": "brochure",
      "unit": null,
      "label": "Applicable standard",
      "value": null,
      "display": "Conforms to IS/IEC 60947-2 (brochure). The website product page states IEC 60947-2 / IS 13947-2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "earth_fault_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Earth fault pick up",
      "value": null,
      "display": "0.2–0.9 In with OFF, in 9 steps: OFF, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9",
      "numeric": true,
      "value_max": 0.9,
      "value_min": 0.2,
      "value_kind": "range"
    },
    "short_circuit_delay": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Short circuit delay",
      "value": null,
      "display": "0.05–0.8 sec in 16 steps: 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80",
      "numeric": true,
      "value_max": 0.8,
      "value_min": 0.05,
      "value_kind": "range"
    },
    "total_breaking_time": {
      "from": "brochure",
      "unit": "ms",
      "label": "Total breaking time",
      "value": 30.0,
      "display": "Less than 30 ms (including arcing time of less than 10 ms)",
      "numeric": true,
      "value_max": 30.0,
      "value_min": 30.0,
      "value_kind": "scalar"
    },
    "insulating_materials": {
      "from": "brochure",
      "unit": null,
      "label": "Insulating materials",
      "value": null,
      "display": "Class 'B' and class 'F' (high dielectric strength in hot and humid conditions)",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "instantaneous_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Instantaneous pick up",
      "value": null,
      "display": "3.0–10 In with OFF, in 9 steps: OFF, 3, 4, 5, 6, 7, 8, 9, 10",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "short_circuit_pick_up": {
      "from": "MicroPro 3.1 release",
      "unit": null,
      "label": "Short circuit pick up",
      "value": null,
      "display": "1.5–9.0 Ir in 16 steps: 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0",
      "numeric": true,
      "value_max": 9.0,
      "value_min": 1.5,
      "value_kind": "range"
    },
    "230_v_i_p_l_i_p_n_i_p_e": {
      "from": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "unit": "V",
      "label": "230 V I/P L … I/P N … I/P E",
      "value": 230.0,
      "display": "Input supply 230 V AC for communication module; phase to L, neutral to N, earth to E",
      "numeric": true,
      "value_max": 230.0,
      "value_min": 230.0,
      "value_kind": "scalar"
    },
    "ampere_frame_designation": {
      "from": "brochure",
      "unit": null,
      "label": "Ampere frame designation",
      "value": null,
      "display": "As per IEC 60947-2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "electrostatic_discharge_esd": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Electrostatic Discharge (ESD)",
      "value": null,
      "display": "IEC 801 - 2",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "electrical_fast_transient_eft": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Electrical Fast Transient (EFT)",
      "value": null,
      "display": "IEC 801 - 4",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "neutral_pole_behaviour_4_pole": {
      "from": "brochure",
      "unit": null,
      "label": "Neutral pole behaviour (4 pole)",
      "value": null,
      "display": "Closes early and opens later, preventing transient over-voltages between live and neutral",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "l_t_d_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "L.T.D time delay setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "control_circuit_terminal_blocks": {
      "from": "brochure",
      "unit": null,
      "label": "Control-circuit terminal blocks",
      "value": 36.0,
      "display": "36-M4",
      "numeric": true,
      "value_max": 36.0,
      "value_min": 36.0,
      "value_kind": "scalar"
    },
    "inst_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "INST trip current setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "l_t_d_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "L.T.D trip current setting range",
      "value": 5.0,
      "display": "±5%",
      "numeric": true,
      "value_max": 5.0,
      "value_min": 5.0,
      "value_kind": "scalar"
    },
    "radio_frequency_interference_rfi": {
      "from": "MicroPro release — ERTL certification tests",
      "unit": null,
      "label": "Radio Frequency Interference (RFI)",
      "value": null,
      "display": "IEC 801 - 3",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "s_t_d_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": "S",
      "label": "S.T.D trip current setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "s_t_d_trip_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": "S",
      "label": "S.T.D trip time delay setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "earth_fault_trip_current_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "Earth fault trip current setting range",
      "value": 20.0,
      "display": "±20%",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "earth_fault_trip_time_delay_setting_range": {
      "from": "Intelligent release tripping curves and setting tolerances",
      "unit": null,
      "label": "Earth fault trip time delay setting range",
      "value": 10.0,
      "display": "±10%",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "reference_voltage_for_breaking_capacity_data": {
      "from": "brochure",
      "unit": "V",
      "label": "Reference voltage for breaking-capacity data",
      "value": 415.0,
      "display": "415 V AC",
      "numeric": true,
      "value_max": 415.0,
      "value_min": 415.0,
      "value_kind": "scalar"
    }
  },
  "description": null,
  "price_status": "por",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": []
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-001",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Width in modules",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 modules.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "modules"
    },
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-002",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has 3 poles.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "A",
      "value": 630.0,
      "source": null,
      "derived": true,
      "fact_id": "AH06BCSMP3.1MF_S_-003",
      "value_max": 630.0,
      "value_min": 630.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a rated current (in) of 630 A.",
      "value_display": "630 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-004",
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a utilisation category of B.",
      "value_display": "B",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "INR",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-price",
      "spec_label": "MRP",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "sources": [
    "Brochure: ACB_AHA.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/"
  ],
  "completeness": {
    "chunks": 11,
    "decoded": true,
    "missing": [
      "price_inr",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 4
  }
}
```

**content** (780 chars)

```
AH06BCSMP3.1MF(S) — ACB – AH-AHA
Salient features
- Available in 3 or 4 pole for the entire range
- Only 3 frame sizes in the entire range, 800A to 4000A, resulting in maximum interchangeability and minimum inventory of spares
- High value of service breaking capacity, 50kA to 65kA, and making capacity, 105kA to 143kA at 415V AC
- Total breaking time less than 30ms (including arcing time of less than 10ms) & closing time of 40ms
- Highest values of mechanical and electrical endurance due to robust mechanism design and special sintered metal contacts
- Neutral pole (in 4 pole) closes early and opens later to prevent transient over voltages in loads connected between live and neutral lines
- Highest degree of system protection and coordination due to the use of microproce
```

### Category: `ACB – WiNmaster 2` · chunk_type: `identity`

- **id**: `32377`
- **product_id**: `101840`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:35:42.932644`
- **lastchange_datetime**: `2026-08-11T16:35:42.932644`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "path": [],
  "decoded": {
    "group": {
      "code": "WM2",
      "meaning": "WiNmaster2 / WiNmaster3 ACB accessory"
    },
    "detail": {
      "code": "AKI-1-AB",
      "meaning": "unknown"
    }
  },
  "category": "ACB – WiNmaster 2",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/winmaster2-power-circuit-breakers/",
  "family": "ACB – WiNmaster 2",
  "sku_code": "CS-WM2-AKI-1-AB",
  "more_info": {
    "a": {
      "from": "How to order — C&S ordering-code key",
      "unit": "A",
      "label": "A",
      "value": null,
      "display": "Basic Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "b": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "B",
      "value": null,
      "display": "Medium Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "c": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "C",
      "value": null,
      "display": "High End Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "N",
      "value": 50.0,
      "display": "50kA",
      "numeric": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "value_kind": "scalar"
    },
    "ef": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EF",
      "value": null,
      "display": "Electrical Fix",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mf": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MF",
      "value": null,
      "display": "Manual Fix",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "wx": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "WX",
      "value": 2.0,
      "display": "WiNmaster 2",
      "numeric": true,
      "value_max": 2.0,
      "value_min": 2.0,
      "value_kind": "scalar"
    },
    "edo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EDO",
      "value": null,
      "display": "Electrical Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mdo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MDO",
      "value": null,
      "display": "Manual Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "3p_n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "3P+N",
      "value": 3.0,
      "display": "3 Pole + Neutral",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "630_800a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "630–800A",
      "value": 10.0,
      "display": "10",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "1000_1600a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "1000–1600A",
      "value": 15.0,
      "display": "15",
      "numeric": true,
      "value_max": 15.0,
      "value_min": 15.0,
      "value_kind": "scalar"
    },
    "2000_2500a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "2000–2500A",
      "value": 20.0,
      "display": "20",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "time_setting": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Time setting",
      "value": null,
      "display": "Instantaneous",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "characteristic": {
      "from": "brochure",
      "unit": null,
      "label": "Characteristic",
      "value": null,
      "display": "Symbol",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "thermal_memory": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Thermal memory",
      "value": 300.0,
      "display": "300 min",
      "numeric": true,
      "value_max": 300.0,
      "value_min": 300.0,
      "value_kind": "scalar"
    },
    "pick_up_a_isd_ir_x": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": "A",
      "label": "Pick-up (A): Isd = Ir x",
      "value": 0.4,
      "display": "0.4 ......... 15, OFF",
      "numeric": true,
      "value_max": 0.4,
      "value_min": 0.4,
      "value_kind": "scalar"
    },
    "rated_making_capacity": {
      "from": "brochure",
      "unit": null,
      "label": "Rated making capacity",
      "value": null,
      "display": "Icm",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "output_do_single_alarm": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Output DO single alarm",
      "value": null,
      "display": "Available",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_insulation_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Rated insulation voltage",
      "value": null,
      "display": "Ui",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse_withstand_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Impulse withstand voltage",
      "value": null,
      "display": "Uimp",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_operational_voltage_ac_50_hz": {
      "from": "brochure",
      "unit": "Hz",
      "label": "Rated operational voltage (AC 50 Hz)",
      "value": null,
      "display": "Ue",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_short_time_withstand_current": {
      "from": "brochure",
      "unit": null,
      "label": "Rated short-time withstand current",
      "value": null,
      "display": "Icw",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    }
  },
  "description": null,
  "price_status": "listed",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": [
    {
      "price": 10960,
      "column": "MRP (`)",
      "context": "WM2/ WM3 | [HSN Code: 8538] | 3. Accessories",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 13,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    }
  ]
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "INR",
      "value": 10960.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 13
      },
      "derived": false,
      "fact_id": "CS-WM2-AKI-1-AB-001",
      "value_max": 10960.0,
      "value_min": 10960.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has an MRP of ₹10,960 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹10,960",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "A",
      "value": 0.2,
      "source": null,
      "derived": false,
      "fact_id": "CS-WM2-AKI-1-AB-002",
      "value_max": 0.2,
      "value_min": 0.2,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has a rated current (in) of 0.2 ......... 1, OFF.",
      "value_display": "0.2 ......... 1, OFF",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_current_a"
    }
  ],
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p13",
    "Brochure: Air-circuit-Breaker-WiNmaster-2.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/winmaster2-power-circuit-breakers/"
  ],
  "completeness": {
    "chunks": 19,
    "decoded": true,
    "missing": [
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 2
  }
}
```

**content** (244 chars)

```
CS-WM2-AKI-1-AB — ACB – WiNmaster 2
Ordering code breakdown: group WM2 = WiNmaster2 / WiNmaster3 ACB accessory; detail AKI-1-AB = unknown.
Used in: Distribution & Transmission, Industries, Infrastructure, Original Equipment Manufacturers (OEM).
```

### Category: `ACB – WiNmaster 2` · chunk_type: `price`

- **id**: `32378`
- **product_id**: `101840`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:35:42.932644`
- **lastchange_datetime**: `2026-08-11T16:35:42.932644`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "path": [],
  "decoded": {
    "group": {
      "code": "WM2",
      "meaning": "WiNmaster2 / WiNmaster3 ACB accessory"
    },
    "detail": {
      "code": "AKI-1-AB",
      "meaning": "unknown"
    }
  },
  "category": "ACB – WiNmaster 2",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/winmaster2-power-circuit-breakers/",
  "family": "ACB – WiNmaster 2",
  "sku_code": "CS-WM2-AKI-1-AB",
  "more_info": {
    "a": {
      "from": "How to order — C&S ordering-code key",
      "unit": "A",
      "label": "A",
      "value": null,
      "display": "Basic Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "b": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "B",
      "value": null,
      "display": "Medium Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "c": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "C",
      "value": null,
      "display": "High End Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "N",
      "value": 50.0,
      "display": "50kA",
      "numeric": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "value_kind": "scalar"
    },
    "ef": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EF",
      "value": null,
      "display": "Electrical Fix",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mf": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MF",
      "value": null,
      "display": "Manual Fix",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "wx": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "WX",
      "value": 2.0,
      "display": "WiNmaster 2",
      "numeric": true,
      "value_max": 2.0,
      "value_min": 2.0,
      "value_kind": "scalar"
    },
    "edo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EDO",
      "value": null,
      "display": "Electrical Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mdo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MDO",
      "value": null,
      "display": "Manual Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "3p_n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "3P+N",
      "value": 3.0,
      "display": "3 Pole + Neutral",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "630_800a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "630–800A",
      "value": 10.0,
      "display": "10",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "1000_1600a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "1000–1600A",
      "value": 15.0,
      "display": "15",
      "numeric": true,
      "value_max": 15.0,
      "value_min": 15.0,
      "value_kind": "scalar"
    },
    "2000_2500a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "2000–2500A",
      "value": 20.0,
      "display": "20",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "time_setting": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Time setting",
      "value": null,
      "display": "Instantaneous",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "characteristic": {
      "from": "brochure",
      "unit": null,
      "label": "Characteristic",
      "value": null,
      "display": "Symbol",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "thermal_memory": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Thermal memory",
      "value": 300.0,
      "display": "300 min",
      "numeric": true,
      "value_max": 300.0,
      "value_min": 300.0,
      "value_kind": "scalar"
    },
    "pick_up_a_isd_ir_x": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": "A",
      "label": "Pick-up (A): Isd = Ir x",
      "value": 0.4,
      "display": "0.4 ......... 15, OFF",
      "numeric": true,
      "value_max": 0.4,
      "value_min": 0.4,
      "value_kind": "scalar"
    },
    "rated_making_capacity": {
      "from": "brochure",
      "unit": null,
      "label": "Rated making capacity",
      "value": null,
      "display": "Icm",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "output_do_single_alarm": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Output DO single alarm",
      "value": null,
      "display": "Available",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_insulation_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Rated insulation voltage",
      "value": null,
      "display": "Ui",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse_withstand_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Impulse withstand voltage",
      "value": null,
      "display": "Uimp",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_operational_voltage_ac_50_hz": {
      "from": "brochure",
      "unit": "Hz",
      "label": "Rated operational voltage (AC 50 Hz)",
      "value": null,
      "display": "Ue",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_short_time_withstand_current": {
      "from": "brochure",
      "unit": null,
      "label": "Rated short-time withstand current",
      "value": null,
      "display": "Icw",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    }
  },
  "description": null,
  "price_status": "listed",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": [
    {
      "price": 10960,
      "column": "MRP (`)",
      "context": "WM2/ WM3 | [HSN Code: 8538] | 3. Accessories",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 13,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    }
  ]
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "INR",
      "value": 10960.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 13
      },
      "derived": false,
      "fact_id": "CS-WM2-AKI-1-AB-001",
      "value_max": 10960.0,
      "value_min": 10960.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has an MRP of ₹10,960 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹10,960",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "A",
      "value": 0.2,
      "source": null,
      "derived": false,
      "fact_id": "CS-WM2-AKI-1-AB-002",
      "value_max": 0.2,
      "value_min": 0.2,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has a rated current (in) of 0.2 ......... 1, OFF.",
      "value_display": "0.2 ......... 1, OFF",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_current_a"
    }
  ],
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p13",
    "Brochure: Air-circuit-Breaker-WiNmaster-2.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/winmaster2-power-circuit-breakers/"
  ],
  "completeness": {
    "chunks": 19,
    "decoded": true,
    "missing": [
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 2
  }
}
```

**content** (180 chars)

```
CS-WM2-AKI-1-AB — ACB – WiNmaster 2
Price and availability:
- Rs 10,960 in the LV pricelist (WM2/ WM3 | [HSN Code: 8538] | 3. Accessories), LV-Pricelist-WEF-1st-June26.pdf page 13.
```

### Category: `ACB – WiNmaster 2` · chunk_type: `specs`

- **id**: `32379`
- **product_id**: `101840`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:35:42.932644`
- **lastchange_datetime**: `2026-08-11T16:35:42.932644`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "path": [],
  "decoded": {
    "group": {
      "code": "WM2",
      "meaning": "WiNmaster2 / WiNmaster3 ACB accessory"
    },
    "detail": {
      "code": "AKI-1-AB",
      "meaning": "unknown"
    }
  },
  "category": "ACB – WiNmaster 2",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/winmaster2-power-circuit-breakers/",
  "family": "ACB – WiNmaster 2",
  "sku_code": "CS-WM2-AKI-1-AB",
  "more_info": {
    "a": {
      "from": "How to order — C&S ordering-code key",
      "unit": "A",
      "label": "A",
      "value": null,
      "display": "Basic Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "b": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "B",
      "value": null,
      "display": "Medium Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "c": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "C",
      "value": null,
      "display": "High End Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "N",
      "value": 50.0,
      "display": "50kA",
      "numeric": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "value_kind": "scalar"
    },
    "ef": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EF",
      "value": null,
      "display": "Electrical Fix",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mf": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MF",
      "value": null,
      "display": "Manual Fix",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "wx": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "WX",
      "value": 2.0,
      "display": "WiNmaster 2",
      "numeric": true,
      "value_max": 2.0,
      "value_min": 2.0,
      "value_kind": "scalar"
    },
    "edo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EDO",
      "value": null,
      "display": "Electrical Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mdo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MDO",
      "value": null,
      "display": "Manual Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "3p_n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "3P+N",
      "value": 3.0,
      "display": "3 Pole + Neutral",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "630_800a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "630–800A",
      "value": 10.0,
      "display": "10",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "1000_1600a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "1000–1600A",
      "value": 15.0,
      "display": "15",
      "numeric": true,
      "value_max": 15.0,
      "value_min": 15.0,
      "value_kind": "scalar"
    },
    "2000_2500a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "2000–2500A",
      "value": 20.0,
      "display": "20",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "time_setting": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Time setting",
      "value": null,
      "display": "Instantaneous",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "characteristic": {
      "from": "brochure",
      "unit": null,
      "label": "Characteristic",
      "value": null,
      "display": "Symbol",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "thermal_memory": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Thermal memory",
      "value": 300.0,
      "display": "300 min",
      "numeric": true,
      "value_max": 300.0,
      "value_min": 300.0,
      "value_kind": "scalar"
    },
    "pick_up_a_isd_ir_x": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": "A",
      "label": "Pick-up (A): Isd = Ir x",
      "value": 0.4,
      "display": "0.4 ......... 15, OFF",
      "numeric": true,
      "value_max": 0.4,
      "value_min": 0.4,
      "value_kind": "scalar"
    },
    "rated_making_capacity": {
      "from": "brochure",
      "unit": null,
      "label": "Rated making capacity",
      "value": null,
      "display": "Icm",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "output_do_single_alarm": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Output DO single alarm",
      "value": null,
      "display": "Available",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_insulation_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Rated insulation voltage",
      "value": null,
      "display": "Ui",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse_withstand_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Impulse withstand voltage",
      "value": null,
      "display": "Uimp",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_operational_voltage_ac_50_hz": {
      "from": "brochure",
      "unit": "Hz",
      "label": "Rated operational voltage (AC 50 Hz)",
      "value": null,
      "display": "Ue",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_short_time_withstand_current": {
      "from": "brochure",
      "unit": null,
      "label": "Rated short-time withstand current",
      "value": null,
      "display": "Icw",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    }
  },
  "description": null,
  "price_status": "listed",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": [
    {
      "price": 10960,
      "column": "MRP (`)",
      "context": "WM2/ WM3 | [HSN Code: 8538] | 3. Accessories",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 13,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    }
  ]
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "INR",
      "value": 10960.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 13
      },
      "derived": false,
      "fact_id": "CS-WM2-AKI-1-AB-001",
      "value_max": 10960.0,
      "value_min": 10960.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has an MRP of ₹10,960 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹10,960",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "A",
      "value": 0.2,
      "source": null,
      "derived": false,
      "fact_id": "CS-WM2-AKI-1-AB-002",
      "value_max": 0.2,
      "value_min": 0.2,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has a rated current (in) of 0.2 ......... 1, OFF.",
      "value_display": "0.2 ......... 1, OFF",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_current_a"
    }
  ],
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p13",
    "Brochure: Air-circuit-Breaker-WiNmaster-2.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/winmaster2-power-circuit-breakers/"
  ],
  "completeness": {
    "chunks": 19,
    "decoded": true,
    "missing": [
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 2
  }
}
```

**content** (235 chars)

```
CS-WM2-AKI-1-AB — ACB – WiNmaster 2
CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has an MRP of ₹10,960 in the LV pricelist effective 2026-06-01.
CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has a rated current (in) of 0.2 ......... 1, OFF.
```

### Category: `ACB – WiNmaster 2` · chunk_type: `technical`

- **id**: `32380`
- **product_id**: `101840`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:35:42.932644`
- **lastchange_datetime**: `2026-08-11T16:35:42.932644`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "part": 1,
  "path": [],
  "parts": 2,
  "decoded": {
    "group": {
      "code": "WM2",
      "meaning": "WiNmaster2 / WiNmaster3 ACB accessory"
    },
    "detail": {
      "code": "AKI-1-AB",
      "meaning": "unknown"
    }
  },
  "heading": "How to order — C&S ordering-code key",
  "category": "ACB – WiNmaster 2",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/winmaster2-power-circuit-breakers/",
  "family": "ACB – WiNmaster 2",
  "sku_code": "CS-WM2-AKI-1-AB",
  "more_info": {
    "a": {
      "from": "How to order — C&S ordering-code key",
      "unit": "A",
      "label": "A",
      "value": null,
      "display": "Basic Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "b": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "B",
      "value": null,
      "display": "Medium Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "c": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "C",
      "value": null,
      "display": "High End Release",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "N",
      "value": 50.0,
      "display": "50kA",
      "numeric": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "value_kind": "scalar"
    },
    "ef": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EF",
      "value": null,
      "display": "Electrical Fix",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mf": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MF",
      "value": null,
      "display": "Manual Fix",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "wx": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "WX",
      "value": 2.0,
      "display": "WiNmaster 2",
      "numeric": true,
      "value_max": 2.0,
      "value_min": 2.0,
      "value_kind": "scalar"
    },
    "edo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EDO",
      "value": null,
      "display": "Electrical Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mdo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MDO",
      "value": null,
      "display": "Manual Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "3p_n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "3P+N",
      "value": 3.0,
      "display": "3 Pole + Neutral",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "630_800a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "630–800A",
      "value": 10.0,
      "display": "10",
      "numeric": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "value_kind": "scalar"
    },
    "1000_1600a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "1000–1600A",
      "value": 15.0,
      "display": "15",
      "numeric": true,
      "value_max": 15.0,
      "value_min": 15.0,
      "value_kind": "scalar"
    },
    "2000_2500a": {
      "from": "Dimensions — drawout type, 630–2500 A, 3P/4P",
      "unit": null,
      "label": "2000–2500A",
      "value": 20.0,
      "display": "20",
      "numeric": true,
      "value_max": 20.0,
      "value_min": 20.0,
      "value_kind": "scalar"
    },
    "time_setting": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Time setting",
      "value": null,
      "display": "Instantaneous",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "characteristic": {
      "from": "brochure",
      "unit": null,
      "label": "Characteristic",
      "value": null,
      "display": "Symbol",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "thermal_memory": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Thermal memory",
      "value": 300.0,
      "display": "300 min",
      "numeric": true,
      "value_max": 300.0,
      "value_min": 300.0,
      "value_kind": "scalar"
    },
    "pick_up_a_isd_ir_x": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": "A",
      "label": "Pick-up (A): Isd = Ir x",
      "value": 0.4,
      "display": "0.4 ......... 15, OFF",
      "numeric": true,
      "value_max": 0.4,
      "value_min": 0.4,
      "value_kind": "scalar"
    },
    "rated_making_capacity": {
      "from": "brochure",
      "unit": null,
      "label": "Rated making capacity",
      "value": null,
      "display": "Icm",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "output_do_single_alarm": {
      "from": "MicroPro2 4.1 — protection parameters and curves",
      "unit": null,
      "label": "Output DO single alarm",
      "value": null,
      "display": "Available",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_insulation_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Rated insulation voltage",
      "value": null,
      "display": "Ui",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse_withstand_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Impulse withstand voltage",
      "value": null,
      "display": "Uimp",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_operational_voltage_ac_50_hz": {
      "from": "brochure",
      "unit": "Hz",
      "label": "Rated operational voltage (AC 50 Hz)",
      "value": null,
      "display": "Ue",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_short_time_withstand_current": {
      "from": "brochure",
      "unit": null,
      "label": "Rated short-time withstand current",
      "value": null,
      "display": "Icw",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    }
  },
  "description": null,
  "price_status": "listed",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": [
    {
      "price": 10960,
      "column": "MRP (`)",
      "context": "WM2/ WM3 | [HSN Code: 8538] | 3. Accessories",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 13,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    }
  ]
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "INR",
      "value": 10960.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 13
      },
      "derived": false,
      "fact_id": "CS-WM2-AKI-1-AB-001",
      "value_max": 10960.0,
      "value_min": 10960.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has an MRP of ₹10,960 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹10,960",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "A",
      "value": 0.2,
      "source": null,
      "derived": false,
      "fact_id": "CS-WM2-AKI-1-AB-002",
      "value_max": 0.2,
      "value_min": 0.2,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "CS-WM2-AKI-1-AB (ACB – WiNmaster 2, 0.2 A) has a rated current (in) of 0.2 ......... 1, OFF.",
      "value_display": "0.2 ......... 1, OFF",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_current_a"
    }
  ],
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p13",
    "Brochure: Air-circuit-Breaker-WiNmaster-2.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/winmaster2-power-circuit-breakers/"
  ],
  "completeness": {
    "chunks": 19,
    "decoded": true,
    "missing": [
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 2
  }
}
```

**content** (259 chars)

```

| Code | Description |
|---|---|
| WX | WiNmaster 2 |
| Code | Description |
|---|---|
| 06 | 630A |
| 08 | 800A |
| 10 | 1000A |
| 12 | 1250A |
| 16 | 1600A |
| 20 | 2000A |
| 25 | 2500A |
| Code | Description |
|---|---|
| N | 50kA |
| Code | Description |
```

### Category: `ACB – WiNmaster 3` · chunk_type: `identity`

- **id**: `36679`
- **product_id**: `101941`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:35:42.932644`
- **lastchange_datetime**: `2026-08-11T16:35:42.932644`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "path": [],
  "decoded": {
    "frame": {
      "code": "1",
      "meaning": "I Frame"
    },
    "poles": {
      "code": "3P",
      "meaning": {
        "poles": 3
      }
    },
    "release": {
      "code": "A",
      "meaning": "Micropro3-3.1"
    },
    "acb_type": {
      "code": "MDO",
      "meaning": "Manual Draw Out Type"
    },
    "breaking": {
      "code": "L",
      "meaning": {
        "ka": 80,
        "volts": 415
      }
    },
    "rating_idx": {
      "code": "06",
      "meaning": 630
    },
    "std_accessories": {
      "code": "(S)",
      "meaning": "supplied with standard accessories"
    }
  },
  "category": "ACB – WiNmaster 3",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-winmaster-3/",
  "family": "ACB – WiNmaster 3",
  "sku_code": "WX306L3P1MDOA(S)",
  "more_info": {
    "a": {
      "from": "How to order — C&S ordering-code key",
      "unit": "A",
      "label": "A",
      "value": null,
      "display": "Micropro3-3.1",
      "numeric": true,
      "value_max": 3.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "b": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "B",
      "value": null,
      "display": "Micropro3-4.1",
      "numeric": true,
      "value_max": 4.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "c": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "C",
      "value": null,
      "display": "Micropro3-5.1",
      "numeric": true,
      "value_max": 5.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "d": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "D",
      "value": null,
      "display": "Micropro3-7.1",
      "numeric": true,
      "value_max": 7.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "h": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "H",
      "value": 100.0,
      "display": "100kA",
      "numeric": true,
      "value_max": 100.0,
      "value_min": 100.0,
      "value_kind": "scalar"
    },
    "l": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "L",
      "value": 80.0,
      "display": "80kA",
      "numeric": true,
      "value_max": 80.0,
      "value_min": 80.0,
      "value_kind": "scalar"
    },
    "n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "N",
      "value": 50.0,
      "display": "50kA*",
      "numeric": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "value_kind": "scalar"
    },
    "s": {
      "from": "How to order — C&S ordering-code key",
      "unit": "S",
      "label": "S",
      "value": 65.0,
      "display": "65kA#",
      "numeric": true,
      "value_max": 65.0,
      "value_min": 65.0,
      "value_kind": "scalar"
    },
    "ef": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EF",
      "value": null,
      "display": "Electrical Fixed Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mf": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MF",
      "value": null,
      "display": "Manual Fixed Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "3pn": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "3PN",
      "value": 3.0,
      "display": "3 Pole with NCT",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "edo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EDO",
      "value": null,
      "display": "Electrical Draw Out Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mdo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MDO",
      "value": null,
      "display": "Manual Draw Out Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "display": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Display",
      "value": null,
      "display": "— (no digital display)",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "parameter": {
      "from": "brochure",
      "unit": null,
      "label": "Parameter",
      "value": null,
      "display": "Symbol",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "indication": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Indication",
      "value": null,
      "display": "LED indication for load current in percentage",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "protection": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Protection",
      "value": null,
      "display": "Basic LSIG & Neutral Protection",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "closing_time": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Closing time",
      "value": 60.0,
      "display": "60 msec (max)",
      "numeric": true,
      "value_max": 60.0,
      "value_min": 60.0,
      "value_kind": "scalar"
    },
    "opening_time": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Opening time",
      "value": 25.0,
      "display": "25 msec",
      "numeric": true,
      "value_max": 25.0,
      "value_min": 25.0,
      "value_kind": "scalar"
    },
    "power_supply": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Power supply",
      "value": null,
      "display": "Self powered and compatible with external auxiliary power supply with AC or DC input",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "remote_reset": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Remote reset",
      "value": null,
      "display": "Optional",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mounting_type": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Mounting type",
      "value": null,
      "display": "Fixed / Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "thermal_memory": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Thermal memory",
      "value": null,
      "display": "Thermal memory for LT & ST",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "self_diagnostics": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Self diagnostics",
      "value": null,
      "display": "Self diagnostics in test mode",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "termination_type": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Termination type",
      "value": null,
      "display": "Universal",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "additional_protection": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Additional protection",
      "value": null,
      "display": "MCR & HSISC Protection",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_insulation_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Rated insulation voltage",
      "value": null,
      "display": "Ui",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "breaking_capacity_classes": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": "S",
      "label": "Breaking capacity classes",
      "value": null,
      "display": "N / S / L",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse_withstand_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Impulse withstand voltage",
      "value": null,
      "display": "Uimp",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "trip_unit_healthy_indication": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Trip unit healthy indication",
      "value": null,
      "display": "Yes",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_operational_voltage_v_ac_50_60_hz": {
      "from": "brochure",
      "unit": "V",
      "label": "Rated operational voltage (V ac 50/60 Hz)",
      "value": null,
      "display": "Ue",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "service_life_electrical_with_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — electrical (with maintenance)",
      "value": 20000.0,
      "display": "20000",
      "numeric": true,
      "value_max": 20000.0,
      "value_min": 20000.0,
      "value_kind": "scalar"
    },
    "service_life_mechanical_with_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — mechanical (with maintenance)",
      "value": 20000.0,
      "display": "20000",
      "numeric": true,
      "value_max": 20000.0,
      "value_min": 20000.0,
      "value_kind": "scalar"
    },
    "service_life_electrical_without_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — electrical (without maintenance)",
      "value": 10000.0,
      "display": "10000",
      "numeric": true,
      "value_max": 10000.0,
      "value_min": 10000.0,
      "value_kind": "scalar"
    }
  },
  "description": null,
  "price_status": "por",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": [
    {
      "price": null,
      "column": null,
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 8,
      "price_status": "por",
      "effective_date": "2026-06-01"
    }
  ]
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "kA",
      "value": 80.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-001",
      "value_max": 80.0,
      "value_min": 80.0,
      "spec_label": "Ultimate breaking capacity (Icu)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a ultimate breaking capacity (icu) of 80 kA.",
      "value_display": "80 kA",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "breaking_capacity_ka"
    },
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-002",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has 3 poles.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "A",
      "value": 630.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-003",
      "value_max": 630.0,
      "value_min": 630.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a rated current (in) of 630 A.",
      "value_display": "630 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "V",
      "value": 415.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-004",
      "value_max": 415.0,
      "value_min": 415.0,
      "spec_label": "Rated operational voltage (Ue)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a rated operational voltage (ue) of 415 V.",
      "value_display": "415 V",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_voltage_v"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "WX306L3P1MDOA_S_-005",
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a utilisation category of B.",
      "value_display": "B",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "INR",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "WX306L3P1MDOA_S_-price",
      "spec_label": "MRP",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p8",
    "Brochure: WiNmaster3-Flyer-2023.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-winmaster-3/"
  ],
  "completeness": {
    "chunks": 8,
    "decoded": true,
    "missing": [
      "price_inr",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 5
  }
}
```

**content** (379 chars)

```
WX306L3P1MDOA(S) — ACB – WiNmaster 3
Ordering code breakdown: rating idx 06 = 630; breaking L = ka 80 volts 415; poles 3P = poles 3; frame 1 = I Frame; acb type MDO = Manual Draw Out Type; release A = Micropro3-3.1; std accessories (S) = supplied with standard accessories.
Used in: Distribution & Transmission, Industries, Infrastructure, Original Equipment Manufacturers (OEM).
```

### Category: `ACB – WiNmaster 3` · chunk_type: `price`

- **id**: `36680`
- **product_id**: `101941`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:35:42.932644`
- **lastchange_datetime**: `2026-08-11T16:35:42.932644`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "path": [],
  "decoded": {
    "frame": {
      "code": "1",
      "meaning": "I Frame"
    },
    "poles": {
      "code": "3P",
      "meaning": {
        "poles": 3
      }
    },
    "release": {
      "code": "A",
      "meaning": "Micropro3-3.1"
    },
    "acb_type": {
      "code": "MDO",
      "meaning": "Manual Draw Out Type"
    },
    "breaking": {
      "code": "L",
      "meaning": {
        "ka": 80,
        "volts": 415
      }
    },
    "rating_idx": {
      "code": "06",
      "meaning": 630
    },
    "std_accessories": {
      "code": "(S)",
      "meaning": "supplied with standard accessories"
    }
  },
  "category": "ACB – WiNmaster 3",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-winmaster-3/",
  "family": "ACB – WiNmaster 3",
  "sku_code": "WX306L3P1MDOA(S)",
  "more_info": {
    "a": {
      "from": "How to order — C&S ordering-code key",
      "unit": "A",
      "label": "A",
      "value": null,
      "display": "Micropro3-3.1",
      "numeric": true,
      "value_max": 3.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "b": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "B",
      "value": null,
      "display": "Micropro3-4.1",
      "numeric": true,
      "value_max": 4.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "c": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "C",
      "value": null,
      "display": "Micropro3-5.1",
      "numeric": true,
      "value_max": 5.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "d": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "D",
      "value": null,
      "display": "Micropro3-7.1",
      "numeric": true,
      "value_max": 7.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "h": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "H",
      "value": 100.0,
      "display": "100kA",
      "numeric": true,
      "value_max": 100.0,
      "value_min": 100.0,
      "value_kind": "scalar"
    },
    "l": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "L",
      "value": 80.0,
      "display": "80kA",
      "numeric": true,
      "value_max": 80.0,
      "value_min": 80.0,
      "value_kind": "scalar"
    },
    "n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "N",
      "value": 50.0,
      "display": "50kA*",
      "numeric": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "value_kind": "scalar"
    },
    "s": {
      "from": "How to order — C&S ordering-code key",
      "unit": "S",
      "label": "S",
      "value": 65.0,
      "display": "65kA#",
      "numeric": true,
      "value_max": 65.0,
      "value_min": 65.0,
      "value_kind": "scalar"
    },
    "ef": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EF",
      "value": null,
      "display": "Electrical Fixed Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mf": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MF",
      "value": null,
      "display": "Manual Fixed Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "3pn": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "3PN",
      "value": 3.0,
      "display": "3 Pole with NCT",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "edo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EDO",
      "value": null,
      "display": "Electrical Draw Out Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mdo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MDO",
      "value": null,
      "display": "Manual Draw Out Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "display": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Display",
      "value": null,
      "display": "— (no digital display)",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "parameter": {
      "from": "brochure",
      "unit": null,
      "label": "Parameter",
      "value": null,
      "display": "Symbol",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "indication": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Indication",
      "value": null,
      "display": "LED indication for load current in percentage",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "protection": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Protection",
      "value": null,
      "display": "Basic LSIG & Neutral Protection",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "closing_time": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Closing time",
      "value": 60.0,
      "display": "60 msec (max)",
      "numeric": true,
      "value_max": 60.0,
      "value_min": 60.0,
      "value_kind": "scalar"
    },
    "opening_time": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Opening time",
      "value": 25.0,
      "display": "25 msec",
      "numeric": true,
      "value_max": 25.0,
      "value_min": 25.0,
      "value_kind": "scalar"
    },
    "power_supply": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Power supply",
      "value": null,
      "display": "Self powered and compatible with external auxiliary power supply with AC or DC input",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "remote_reset": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Remote reset",
      "value": null,
      "display": "Optional",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mounting_type": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Mounting type",
      "value": null,
      "display": "Fixed / Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "thermal_memory": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Thermal memory",
      "value": null,
      "display": "Thermal memory for LT & ST",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "self_diagnostics": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Self diagnostics",
      "value": null,
      "display": "Self diagnostics in test mode",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "termination_type": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Termination type",
      "value": null,
      "display": "Universal",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "additional_protection": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Additional protection",
      "value": null,
      "display": "MCR & HSISC Protection",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_insulation_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Rated insulation voltage",
      "value": null,
      "display": "Ui",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "breaking_capacity_classes": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": "S",
      "label": "Breaking capacity classes",
      "value": null,
      "display": "N / S / L",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse_withstand_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Impulse withstand voltage",
      "value": null,
      "display": "Uimp",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "trip_unit_healthy_indication": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Trip unit healthy indication",
      "value": null,
      "display": "Yes",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_operational_voltage_v_ac_50_60_hz": {
      "from": "brochure",
      "unit": "V",
      "label": "Rated operational voltage (V ac 50/60 Hz)",
      "value": null,
      "display": "Ue",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "service_life_electrical_with_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — electrical (with maintenance)",
      "value": 20000.0,
      "display": "20000",
      "numeric": true,
      "value_max": 20000.0,
      "value_min": 20000.0,
      "value_kind": "scalar"
    },
    "service_life_mechanical_with_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — mechanical (with maintenance)",
      "value": 20000.0,
      "display": "20000",
      "numeric": true,
      "value_max": 20000.0,
      "value_min": 20000.0,
      "value_kind": "scalar"
    },
    "service_life_electrical_without_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — electrical (without maintenance)",
      "value": 10000.0,
      "display": "10000",
      "numeric": true,
      "value_max": 10000.0,
      "value_min": 10000.0,
      "value_kind": "scalar"
    }
  },
  "description": null,
  "price_status": "por",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": [
    {
      "price": null,
      "column": null,
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 8,
      "price_status": "por",
      "effective_date": "2026-06-01"
    }
  ]
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "kA",
      "value": 80.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-001",
      "value_max": 80.0,
      "value_min": 80.0,
      "spec_label": "Ultimate breaking capacity (Icu)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a ultimate breaking capacity (icu) of 80 kA.",
      "value_display": "80 kA",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "breaking_capacity_ka"
    },
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-002",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has 3 poles.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "A",
      "value": 630.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-003",
      "value_max": 630.0,
      "value_min": 630.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a rated current (in) of 630 A.",
      "value_display": "630 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "V",
      "value": 415.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-004",
      "value_max": 415.0,
      "value_min": 415.0,
      "spec_label": "Rated operational voltage (Ue)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a rated operational voltage (ue) of 415 V.",
      "value_display": "415 V",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_voltage_v"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "WX306L3P1MDOA_S_-005",
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a utilisation category of B.",
      "value_display": "B",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "INR",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "WX306L3P1MDOA_S_-price",
      "spec_label": "MRP",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p8",
    "Brochure: WiNmaster3-Flyer-2023.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-winmaster-3/"
  ],
  "completeness": {
    "chunks": 8,
    "decoded": true,
    "missing": [
      "price_inr",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 5
  }
}
```

**content** (178 chars)

```
WX306L3P1MDOA(S) — ACB – WiNmaster 3
Price and availability:
No list price: this page of the C&S pricelist states the price is on request — contact the nearest C&S branch office.
```

### Category: `ACB – WiNmaster 3` · chunk_type: `specs`

- **id**: `36681`
- **product_id**: `101941`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:35:42.932644`
- **lastchange_datetime**: `2026-08-11T16:35:42.932644`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "part": 1,
  "path": [],
  "parts": 2,
  "decoded": {
    "frame": {
      "code": "1",
      "meaning": "I Frame"
    },
    "poles": {
      "code": "3P",
      "meaning": {
        "poles": 3
      }
    },
    "release": {
      "code": "A",
      "meaning": "Micropro3-3.1"
    },
    "acb_type": {
      "code": "MDO",
      "meaning": "Manual Draw Out Type"
    },
    "breaking": {
      "code": "L",
      "meaning": {
        "ka": 80,
        "volts": 415
      }
    },
    "rating_idx": {
      "code": "06",
      "meaning": 630
    },
    "std_accessories": {
      "code": "(S)",
      "meaning": "supplied with standard accessories"
    }
  },
  "category": "ACB – WiNmaster 3",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-winmaster-3/",
  "family": "ACB – WiNmaster 3",
  "sku_code": "WX306L3P1MDOA(S)",
  "more_info": {
    "a": {
      "from": "How to order — C&S ordering-code key",
      "unit": "A",
      "label": "A",
      "value": null,
      "display": "Micropro3-3.1",
      "numeric": true,
      "value_max": 3.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "b": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "B",
      "value": null,
      "display": "Micropro3-4.1",
      "numeric": true,
      "value_max": 4.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "c": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "C",
      "value": null,
      "display": "Micropro3-5.1",
      "numeric": true,
      "value_max": 5.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "d": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "D",
      "value": null,
      "display": "Micropro3-7.1",
      "numeric": true,
      "value_max": 7.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "h": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "H",
      "value": 100.0,
      "display": "100kA",
      "numeric": true,
      "value_max": 100.0,
      "value_min": 100.0,
      "value_kind": "scalar"
    },
    "l": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "L",
      "value": 80.0,
      "display": "80kA",
      "numeric": true,
      "value_max": 80.0,
      "value_min": 80.0,
      "value_kind": "scalar"
    },
    "n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "N",
      "value": 50.0,
      "display": "50kA*",
      "numeric": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "value_kind": "scalar"
    },
    "s": {
      "from": "How to order — C&S ordering-code key",
      "unit": "S",
      "label": "S",
      "value": 65.0,
      "display": "65kA#",
      "numeric": true,
      "value_max": 65.0,
      "value_min": 65.0,
      "value_kind": "scalar"
    },
    "ef": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EF",
      "value": null,
      "display": "Electrical Fixed Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mf": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MF",
      "value": null,
      "display": "Manual Fixed Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "3pn": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "3PN",
      "value": 3.0,
      "display": "3 Pole with NCT",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "edo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EDO",
      "value": null,
      "display": "Electrical Draw Out Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mdo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MDO",
      "value": null,
      "display": "Manual Draw Out Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "display": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Display",
      "value": null,
      "display": "— (no digital display)",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "parameter": {
      "from": "brochure",
      "unit": null,
      "label": "Parameter",
      "value": null,
      "display": "Symbol",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "indication": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Indication",
      "value": null,
      "display": "LED indication for load current in percentage",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "protection": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Protection",
      "value": null,
      "display": "Basic LSIG & Neutral Protection",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "closing_time": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Closing time",
      "value": 60.0,
      "display": "60 msec (max)",
      "numeric": true,
      "value_max": 60.0,
      "value_min": 60.0,
      "value_kind": "scalar"
    },
    "opening_time": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Opening time",
      "value": 25.0,
      "display": "25 msec",
      "numeric": true,
      "value_max": 25.0,
      "value_min": 25.0,
      "value_kind": "scalar"
    },
    "power_supply": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Power supply",
      "value": null,
      "display": "Self powered and compatible with external auxiliary power supply with AC or DC input",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "remote_reset": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Remote reset",
      "value": null,
      "display": "Optional",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mounting_type": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Mounting type",
      "value": null,
      "display": "Fixed / Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "thermal_memory": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Thermal memory",
      "value": null,
      "display": "Thermal memory for LT & ST",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "self_diagnostics": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Self diagnostics",
      "value": null,
      "display": "Self diagnostics in test mode",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "termination_type": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Termination type",
      "value": null,
      "display": "Universal",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "additional_protection": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Additional protection",
      "value": null,
      "display": "MCR & HSISC Protection",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_insulation_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Rated insulation voltage",
      "value": null,
      "display": "Ui",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "breaking_capacity_classes": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": "S",
      "label": "Breaking capacity classes",
      "value": null,
      "display": "N / S / L",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse_withstand_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Impulse withstand voltage",
      "value": null,
      "display": "Uimp",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "trip_unit_healthy_indication": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Trip unit healthy indication",
      "value": null,
      "display": "Yes",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_operational_voltage_v_ac_50_60_hz": {
      "from": "brochure",
      "unit": "V",
      "label": "Rated operational voltage (V ac 50/60 Hz)",
      "value": null,
      "display": "Ue",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "service_life_electrical_with_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — electrical (with maintenance)",
      "value": 20000.0,
      "display": "20000",
      "numeric": true,
      "value_max": 20000.0,
      "value_min": 20000.0,
      "value_kind": "scalar"
    },
    "service_life_mechanical_with_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — mechanical (with maintenance)",
      "value": 20000.0,
      "display": "20000",
      "numeric": true,
      "value_max": 20000.0,
      "value_min": 20000.0,
      "value_kind": "scalar"
    },
    "service_life_electrical_without_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — electrical (without maintenance)",
      "value": 10000.0,
      "display": "10000",
      "numeric": true,
      "value_max": 10000.0,
      "value_min": 10000.0,
      "value_kind": "scalar"
    }
  },
  "description": null,
  "price_status": "por",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": [
    {
      "price": null,
      "column": null,
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 8,
      "price_status": "por",
      "effective_date": "2026-06-01"
    }
  ]
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "kA",
      "value": 80.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-001",
      "value_max": 80.0,
      "value_min": 80.0,
      "spec_label": "Ultimate breaking capacity (Icu)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a ultimate breaking capacity (icu) of 80 kA.",
      "value_display": "80 kA",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "breaking_capacity_ka"
    },
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-002",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has 3 poles.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "A",
      "value": 630.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-003",
      "value_max": 630.0,
      "value_min": 630.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a rated current (in) of 630 A.",
      "value_display": "630 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "V",
      "value": 415.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-004",
      "value_max": 415.0,
      "value_min": 415.0,
      "spec_label": "Rated operational voltage (Ue)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a rated operational voltage (ue) of 415 V.",
      "value_display": "415 V",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_voltage_v"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "WX306L3P1MDOA_S_-005",
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a utilisation category of B.",
      "value_display": "B",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "INR",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "WX306L3P1MDOA_S_-price",
      "spec_label": "MRP",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p8",
    "Brochure: WiNmaster3-Flyer-2023.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-winmaster-3/"
  ],
  "completeness": {
    "chunks": 8,
    "decoded": true,
    "missing": [
      "price_inr",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 5
  }
}
```

**content** (232 chars)

```
WX306L3P1MDOA(S) — ACB – WiNmaster 3
WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a ultimate breaking capacity (icu) of 80 kA.
WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has 3 poles.
```

### Category: `ACB – WiNmaster 3` · chunk_type: `technical`

- **id**: `36683`
- **product_id**: `101941`
- **is_active**: `True`
- **create_datetime**: `2026-08-11T16:35:42.932644`
- **lastchange_datetime**: `2026-08-11T16:35:42.932644`
- **has_embedding**: `True`

**taxonomy**

```json
{
  "part": 1,
  "path": [],
  "parts": 3,
  "decoded": {
    "frame": {
      "code": "1",
      "meaning": "I Frame"
    },
    "poles": {
      "code": "3P",
      "meaning": {
        "poles": 3
      }
    },
    "release": {
      "code": "A",
      "meaning": "Micropro3-3.1"
    },
    "acb_type": {
      "code": "MDO",
      "meaning": "Manual Draw Out Type"
    },
    "breaking": {
      "code": "L",
      "meaning": {
        "ka": 80,
        "volts": 415
      }
    },
    "rating_idx": {
      "code": "06",
      "meaning": 630
    },
    "std_accessories": {
      "code": "(S)",
      "meaning": "supplied with standard accessories"
    }
  },
  "heading": "How to order — C&S ordering-code key",
  "category": "ACB – WiNmaster 3",
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-winmaster-3/",
  "family": "ACB – WiNmaster 3",
  "sku_code": "WX306L3P1MDOA(S)",
  "more_info": {
    "a": {
      "from": "How to order — C&S ordering-code key",
      "unit": "A",
      "label": "A",
      "value": null,
      "display": "Micropro3-3.1",
      "numeric": true,
      "value_max": 3.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "b": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "B",
      "value": null,
      "display": "Micropro3-4.1",
      "numeric": true,
      "value_max": 4.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "c": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "C",
      "value": null,
      "display": "Micropro3-5.1",
      "numeric": true,
      "value_max": 5.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "d": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "D",
      "value": null,
      "display": "Micropro3-7.1",
      "numeric": true,
      "value_max": 7.1,
      "value_min": 3.0,
      "value_kind": "range"
    },
    "h": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "H",
      "value": 100.0,
      "display": "100kA",
      "numeric": true,
      "value_max": 100.0,
      "value_min": 100.0,
      "value_kind": "scalar"
    },
    "l": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "L",
      "value": 80.0,
      "display": "80kA",
      "numeric": true,
      "value_max": 80.0,
      "value_min": 80.0,
      "value_kind": "scalar"
    },
    "n": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "N",
      "value": 50.0,
      "display": "50kA*",
      "numeric": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "value_kind": "scalar"
    },
    "s": {
      "from": "How to order — C&S ordering-code key",
      "unit": "S",
      "label": "S",
      "value": 65.0,
      "display": "65kA#",
      "numeric": true,
      "value_max": 65.0,
      "value_min": 65.0,
      "value_kind": "scalar"
    },
    "ef": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EF",
      "value": null,
      "display": "Electrical Fixed Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mf": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MF",
      "value": null,
      "display": "Manual Fixed Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "3pn": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "3PN",
      "value": 3.0,
      "display": "3 Pole with NCT",
      "numeric": true,
      "value_max": 3.0,
      "value_min": 3.0,
      "value_kind": "scalar"
    },
    "edo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "EDO",
      "value": null,
      "display": "Electrical Draw Out Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mdo": {
      "from": "How to order — C&S ordering-code key",
      "unit": null,
      "label": "MDO",
      "value": null,
      "display": "Manual Draw Out Type",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "display": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Display",
      "value": null,
      "display": "— (no digital display)",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "parameter": {
      "from": "brochure",
      "unit": null,
      "label": "Parameter",
      "value": null,
      "display": "Symbol",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "indication": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Indication",
      "value": null,
      "display": "LED indication for load current in percentage",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "protection": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Protection",
      "value": null,
      "display": "Basic LSIG & Neutral Protection",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "closing_time": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Closing time",
      "value": 60.0,
      "display": "60 msec (max)",
      "numeric": true,
      "value_max": 60.0,
      "value_min": 60.0,
      "value_kind": "scalar"
    },
    "opening_time": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Opening time",
      "value": 25.0,
      "display": "25 msec",
      "numeric": true,
      "value_max": 25.0,
      "value_min": 25.0,
      "value_kind": "scalar"
    },
    "power_supply": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Power supply",
      "value": null,
      "display": "Self powered and compatible with external auxiliary power supply with AC or DC input",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "remote_reset": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Remote reset",
      "value": null,
      "display": "Optional",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "mounting_type": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Mounting type",
      "value": null,
      "display": "Fixed / Drawout",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "thermal_memory": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Thermal memory",
      "value": null,
      "display": "Thermal memory for LT & ST",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "self_diagnostics": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Self diagnostics",
      "value": null,
      "display": "Self diagnostics in test mode",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "termination_type": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Termination type",
      "value": null,
      "display": "Universal",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "additional_protection": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Additional protection",
      "value": null,
      "display": "MCR & HSISC Protection",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_insulation_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Rated insulation voltage",
      "value": null,
      "display": "Ui",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "breaking_capacity_classes": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": "S",
      "label": "Breaking capacity classes",
      "value": null,
      "display": "N / S / L",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "impulse_withstand_voltage": {
      "from": "brochure",
      "unit": null,
      "label": "Impulse withstand voltage",
      "value": null,
      "display": "Uimp",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "trip_unit_healthy_indication": {
      "from": "MicroPro3-3.1 release (release code A)",
      "unit": null,
      "label": "Trip unit healthy indication",
      "value": null,
      "display": "Yes",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "rated_operational_voltage_v_ac_50_60_hz": {
      "from": "brochure",
      "unit": "V",
      "label": "Rated operational voltage (V ac 50/60 Hz)",
      "value": null,
      "display": "Ue",
      "numeric": false,
      "value_max": null,
      "value_min": null,
      "value_kind": "text"
    },
    "service_life_electrical_with_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — electrical (with maintenance)",
      "value": 20000.0,
      "display": "20000",
      "numeric": true,
      "value_max": 20000.0,
      "value_min": 20000.0,
      "value_kind": "scalar"
    },
    "service_life_mechanical_with_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — mechanical (with maintenance)",
      "value": 20000.0,
      "display": "20000",
      "numeric": true,
      "value_max": 20000.0,
      "value_min": 20000.0,
      "value_kind": "scalar"
    },
    "service_life_electrical_without_maintenance": {
      "from": "FRAME-1 (I Frame) technical characteristics",
      "unit": null,
      "label": "Service life — electrical (without maintenance)",
      "value": 10000.0,
      "display": "10000",
      "numeric": true,
      "value_max": 10000.0,
      "value_min": 10000.0,
      "value_kind": "scalar"
    }
  },
  "description": null,
  "price_status": "por",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "price_observations": [
    {
      "price": null,
      "column": null,
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 8,
      "price_status": "por",
      "effective_date": "2026-06-01"
    }
  ]
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "kA",
      "value": 80.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-001",
      "value_max": 80.0,
      "value_min": 80.0,
      "spec_label": "Ultimate breaking capacity (Icu)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a ultimate breaking capacity (icu) of 80 kA.",
      "value_display": "80 kA",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "breaking_capacity_ka"
    },
    {
      "unit": "count",
      "value": 3.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-002",
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has 3 poles.",
      "value_display": "3",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "A",
      "value": 630.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-003",
      "value_max": 630.0,
      "value_min": 630.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a rated current (in) of 630 A.",
      "value_display": "630 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "V",
      "value": 415.0,
      "source": null,
      "derived": true,
      "fact_id": "WX306L3P1MDOA_S_-004",
      "value_max": 415.0,
      "value_min": 415.0,
      "spec_label": "Rated operational voltage (Ue)",
      "value_kind": "scalar",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a rated operational voltage (ue) of 415 V.",
      "value_display": "415 V",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_voltage_v"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "WX306L3P1MDOA_S_-005",
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) has a utilisation category of B.",
      "value_display": "B",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "INR",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "WX306L3P1MDOA_S_-price",
      "spec_label": "MRP",
      "fact_sentence": "WX306L3P1MDOA(S) (ACB – WiNmaster 3, 630 A, 3-pole, Micropro3-3.1) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p8",
    "Brochure: WiNmaster3-Flyer-2023.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-winmaster-3/"
  ],
  "completeness": {
    "chunks": 8,
    "decoded": true,
    "missing": [
      "price_inr",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 5
  }
}
```

**content** (477 chars)

```

| Code segment | Example value | Meaning |
|---|---|---|
| 1 | WX3 | Product family (WiNmaster3) |
| 2 | 06 | Current Ratings (see table below) |
| 3 | S | Breaking Capacity (see table below) |
| 4 | 3P | Poles (see table below) |
| 5 | 1 | Frame (see table below) |
| 6 | EDO | ACB Type (see table below) |
| 7 | A | Release (see table below) |
| Code | Rating |
|---|---|
| 06 | 630A |
| 08 | 800A |
| 10 | 1000A |
| 12 | 1250A |
| 16 | 1600A |
| 20 | 2000A |
| 25 | 2500A |
```
