# `in_use.product_chunks` — Schema & Sample Rows (`cs_electric_v2`)

Database: `cs_electric_v2` · Schema: `in_use` · Table: `product_chunks`

## Table schema

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `integer` | NOT NULL | `GENERATED ALWAYS AS IDENTITY` | Primary key |
| `product_id` | `integer` | NULL | — | Related product identifier |
| `taxonomy` | `jsonb` | NOT NULL | — | Taxonomy metadata (path, levels, node_type, depth, headings). Note: no `category` key in this DB — family lives on `product`. |
| `product` | `jsonb` | NOT NULL | — | Product metadata (sku_code, family, decoded, attributes, prices, etc.) |
| `details` | `jsonb` | NOT NULL | `'{}'::jsonb` | Additional details |
| `content` | `text` | NOT NULL | — | Chunk text content used for search |
| `embedding` | `vector(384)` | NULL | — | Embedding vector — column currently typed as vector(384); **no rows loaded yet**. When loaded, embeddings will be **768-dimensional** (column type will need to match). |
| `is_active` | `boolean` | NOT NULL | `true` | Active flag |
| `create_datetime` | `timestamp without time zone` | NOT NULL | — | Created at |
| `lastchange_datetime` | `timestamp without time zone` | NOT NULL | — | Last updated at |
| `chunk_type` | `text` | NULL | — | Chunk type (identity, price, specs, technical, …) |

### Constraints

- **PRIMARY KEY**: `product_chunk_pk` on `(id)`

### Indexes

| Index | Definition |
|---|---|
| `idx_pc_ctype` | btree (`chunk_type`) |
| `idx_pc_details` | gin (`details` jsonb_path_ops) |
| `idx_pc_node` | btree (((`taxonomy` ->> 'node_type'))) |
| `idx_pc_sku` | btree (((`product` ->> 'sku_code'))) |
| `idx_pc_sku_trgm` | gin (((`product` ->> 'sku_code')) gin_trgm_ops) |
| `product_chunk_pk` | UNIQUE btree (`id`) — PRIMARY KEY |

## Embedding status

- Total rows: **79,297**
- Rows with embedding: **0**
- Rows without embedding: **79,297** (all rows)
- Column type in DB today: `vector(384)`
- Expected when loaded: **768-dimension** vectors (alter column type to `vector(768)` before loading)

## Taxonomy shape notes

Unlike `cs_electric`, this database's `taxonomy` jsonb does **not** include a `category` key. Observed keys:

| Key | Rows present |
|---|---|
| `path` | 79,297 |
| `levels` | 79,297 |
| `node_type` | 79,297 |
| `depth` | 79,297 |
| `headings` | 52,319 |

All rows have `taxonomy->>'node_type' = 'sku'`. Product family is on `product->>'family'`.

## Row counts by `chunk_type`

| `chunk_type` | Rows |
|---|---|
| `price` | 9,115 |
| `specs` | 9,115 |
| `identity` | 8,748 |
| `ordering` | 7,174 |
| `features` | 5,323 |
| `accessories` | 5,063 |
| `product_range` | 4,552 |
| `environment` | 3,763 |
| `ratings` | 3,457 |
| `application` | 3,373 |
| `technical` | 3,357 |
| `technical_data` | 3,183 |
| `dimensions` | 3,014 |
| `construction` | 2,597 |
| `installation` | 2,177 |
| `standards` | 2,065 |
| `variants` | 2,006 |
| `losses` | 664 |
| `commercial` | 551 |
| **Total** | **79,297** |

Observed `chunk_type` values: `price`, `specs`, `identity`, `ordering`, `features`, `accessories`, `product_range`, `environment`, `ratings`, `application`, `technical`, `technical_data`, `dimensions`, `construction`, `installation`, `standards`, `variants`, `losses`, `commercial`.

## Row counts by `product->>'family'`

| Family | Distinct SKUs | Rows |
|---|---|---|
| `robusTa Contactors & Overload Relays` | 1,205 | 11,528 |
| `Control & Signalling Devices` | 730 | 8,042 |
| `MCCB – Winbreak1` | 431 | 6,465 |
| `Distribution Boards` | 622 | 6,240 |
| `Anmol Motor Starter` | 724 | 5,109 |
| `exceeD Contactors` | 786 | 4,716 |
| `WiNtrip2 MCB & Isolator` | 408 | 4,009 |
| `Industrial Motor Starters` | 548 | 3,775 |
| `Switch Disconnector Fuse` | 207 | 3,260 |
| `ACB – AH-AHA` | 316 | 3,026 |
| `Switch Disconnectors` | 284 | 2,846 |
| `ACB – WiNmaster 3` | 157 | 1,724 |
| `WiNtrip MCB & Isolator` | 178 | 1,650 |
| `Primo Plus Switches` | 144 | 1,440 |
| `Mini Contactor` | 259 | 1,309 |
| `DIVINO Switches` | 157 | 1,256 |
| `ACB – WiNmaster 2` | 101 | 1,184 |
| `Primo Switches` | 173 | 1,038 |
| `Bridgg Modular Switches` | 100 | 800 |
| `Elusio Switches` | 80 | 797 |
| `HRC Fuse` | 92 | 782 |
| `Definite Purpose Contactors 1, 2, 3 & 4 Poles` | 221 | 663 |
| `Motor Protection Circuit Breakers` | 58 | 551 |
| `D Range Contactors` | 57 | 509 |
| `Industrial Plugs and Sockets` | 62 | 496 |
| `New Changeover Switches` | 50 | 450 |
| `mPRO-200` | 46 | 449 |
| `2 & 4 Pole Contactors` | 63 | 441 |
| `RCBO` | 69 | 414 |
| `MCCB – Winbreak` | 50 | 400 |
| `MCCB – Winbreak2` | 50 | 395 |
| `robusTa2 Contactors` | 41 | 328 |
| `Changeover Switch (with & without fuse)` | 37 | 301 |
| `Lighting Trunking (LB) – LV` | 40 | 246 |
| `On-Load By Pass Switches` | 40 | 240 |
| `Automatic Transfer Switch` | 34 | 238 |
| `Capacitor Duty Contactor` | 30 | 210 |
| `Power Capacitor` | 43 | 187 |
| `Power Quality Device` | 83 | 166 |
| `Motor Starter - Selection Chart` | 50 | 152 |
| `Meter` | 30 | 150 |
| `ELR 1.0 (7 segment display)` | 16 | 144 |
| `WiNtrip2 DC MCB` | 46 | 143 |
| `COMBI Weather Proof Enclosures` | 23 | 135 |
| `Anmol Smart Mobile Pump Controller` | 18 | 125 |
| `Sandwich Bustrunking (SB) – LV` | 35 | 105 |
| `WiNtrip ‘S’ Modular MCB` | 24 | 72 |
| `CD 2.0` | 17 | 68 |
| `Accessories` | 33 | 66 |
| `Rewirable` | 21 | 63 |
| `mPRO-100` | 17 | 50 |
| `ACCL` | 15 | 45 |
| `Compact Air Bustrunking (CB)-LV` | 15 | 45 |
| `Alarm Annunciator` | 14 | 42 |
| `CSPTD Series SPD’s` | 14 | 42 |
| `mPRO-90` | 11 | 32 |
| `CSPF-100` | 4 | 31 |
| `Relay Range & Contactor Ratings Used in Motor Starters` | 10 | 24 |
| `Residual Current Circuit Breaker` | 6 | 18 |
| `WiNtrip – MCB Changeover Switch` | 6 | 18 |
| `IRP-V3` | 6 | 15 |
| `DC Fuse` | 7 | 14 |
| `CSPF-200` | 3 | 6 |
| `MRN2(Mains De-coupling Device)` | 2 | 6 |
| `EGC-250` | 2 | 4 |
| `ELR 3.0` | 1 | 2 |
| **Total** | — | **79,297** |

## Sample rows

One sample row per `chunk_type` (lowest `id` for that type; 19 rows total). The `embedding` column is omitted; presence is shown as `has_embedding`. Long `content` values are truncated for readability.

### Family: `WiNtrip MCB & Isolator` · chunk_type: `accessories`

- **id**: `1275685`
- **product_id**: `100623`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:16.548743`
- **lastchange_datetime**: `2026-08-12T15:07:16.548743`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "MCB & Isolators",
    "WiNtrip MCB & Isolator"
  ],
  "depth": 3,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/",
      "name": "MCB & Isolators",
      "level": 2,
      "is_leaf": false,
      "contents": [
        {
          "name": "WiNtrip MCB & Isolator",
          "note": "MCB upto 125A with finger touch proof terminals with a Breaking Capacity of 10kA"
        },
        {
          "name": "WiNtrip2 MCB & Isolator",
          "note": "With breaking Capacity of 10kA and low power consumption"
        },
        {
          "name": "SmartSol Mini MCB",
          "note": "Mini MCB upto 32A with compact & space saving design"
        },
        {
          "name": "WiNtrip – MCB Changeover Switch",
          "note": "Compact design with shrouded terminals and double break contacts"
        },
        {
          "name": "WiNtrip ‘S’ Modular MCB",
          "note": "Compact & space saving design with rapid closing mechanism"
        },
        {
          "name": "WiNtrip2 DC MCB",
          "note": "Dual Connection possibility for both cable and busbar"
        }
      ],
      "has_page": true,
      "markdown": "# MCB & Isolators\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Miniature Circuit Breakers\n\nMiniature circuit breaker is an electromechanical device that is designed to protect an electrical circuit from overload or short circuit, prevent the equipment from damage & potential hazards like fire.\n\nC&S offers various types of MCBs for different household & industrial application as mentioned below.\n\n## Contents\n- [WiNtrip MCB & Isolator](./WiNtrip MCB & Isolator/) — MCB upto 125A with finger touch proof terminals with a Breaking Capacity of 10kA\n- [WiNtrip2 MCB & Isolator](./WiNtrip2 MCB & Isolator/) — With breaking Capacity of 10kA and low power consumption\n- [SmartSol Mini MCB](./SmartSol Mini MCB/) — Mini MCB upto 32A with compact & space saving design\n- [WiNtrip – MCB Changeover Switch](./WiNtrip – MCB Changeover Switch/) — Compact design with shrouded terminals and double break contacts\n- [WiNtrip ‘S’ Modular MCB](./WiNtrip ‘S’ Modular MCB/) — Compact & space saving design with rapid closing mechanism\n- [WiNtrip2 DC MCB](./WiNtrip2 DC MCB/) — Dual Connection possibility for both cable and busbar",
      "page_type": "_category.md",
      "description": "Miniature circuit breaker is an electromechanical device that is designed to protect an electrical circuit from overload or short circuit, prevent the equipment from damage & potential hazards like fire.\nC&S offers various types of MCBs for different household & industrial application as mentioned below.",
      "source_file": "Final Distribution Products/MCB & Isolators/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/",
      "name": "WiNtrip MCB & Isolator",
      "level": 3,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# WiNtrip MCB & Isolator\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Miniature Circuit Breakers > WiNtrip MCB & Isolator\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/Wintrip-MCB-2.jpg (saved as `Wintrip-MCB-2.jpg`)\n\n## Presentation\nAs power distribution needs play a pivotal role in all the significant sectors namely Commercial, Industrial and Residential, improved Breaker performance through better electrical safety, higher operational endurance, continued service and reduced cost have become of paramount importance. C&S MCBs have been engineered to constantly fulfill the above requirements. With these features C&S is setting new standards for user friendly and superlative electrical circuit protection.\nThe C&S MCB is a high performing Thermal Magnetic current limiting device with the ability to disconnect short circuits up to 10kA. The range is available in tripping characteristics types B, C and D for 1P, 1P+N, 2P, 3P, 3P+N & 4P configurations in 0.5 – 125A current ratings. All metal components for operating mechanism of WiNtrip circuit breaker are specially treated for high self lubrication leading to repeat accuracy during service life. The MCBs conform to Standards: IEC 60898-1995 and IS/IEC 60898-1:2002 and stand guaranteed for best quality for optimum performance.\n\n## Benefits\nElectrical safety\nHigher operational endurance\nDurable and reduced cost\nPlays a pivotal role in all the significant sectors namely Commercial, Industrial and Residential areas\nEnsures circuit identification and enhanced safety\nClear indication of the operational status of device\n\n## Brochure\n- [MCB_.pdf](./MCB_.pdf) (source: https://cselectric.co.in/wp-content/uploads/2025/03/MCB_.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/MCB & Isolators/WiNtrip MCB & Isolator/product.md"
    }
  ],
  "headings": [
    "Accessories — auxiliary contact and shunt trip"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": null,
  "family": "WiNtrip MCB & Isolator",
  "decoded": null,
  "sku_code": "CSBHIC100N",
  "attributes": null,
  "peer_group": "WiNtrip MCB & Isolator | brochure-only",
  "description": "Double Pole (1, 3 / 2, 4) | 100 | CSBHIC100N",
  "alias_reason": null,
  "price_status": "not_in_pricelist",
  "comparable_on": [
    "rated_insulation_voltage_ui_v",
    "rated_voltage_v"
  ],
  "related_codes": [
    "CSBHIC125N",
    "CSBHIC80N",
    "CSMB2SDC0.5",
    "CSMB2SDC1",
    "CSMB2SDC10",
    "CSMB2SDC16",
    "CSMB2SDC2",
    "CSMB2SDC20",
    "CSMB2SDC25",
    "CSMB2SDC3",
    "CSMB2SDC32",
    "CSMB2SDC4",
    "CSMB2SDC40",
    "CSMB2SDC5",
    "CSMB2SDC50",
    "CSMB2SDC6",
    "CSMB2SDC63",
    "CSMB3ISO100",
    "CSMB3ISO125",
    "CSMB3ISO25",
    "CSMB3ISO40",
    "CSMB3ISO63",
    "CSMB3ISO80",
    "CSMBL1B10",
    "CSMBL1B10N",
    "CSMBL1B16",
    "CSMBL1B16N",
    "CSMBL1B20",
    "CSMBL1B20N",
    "CSMBL1B25",
    "CSMBL1B25N",
    "CSMBL1B32",
    "CSMBL1B32N",
    "CSMBL1B40",
    "CSMBL1B40N",
    "CSMBL1B6",
    "CSMBL1B6N",
    "CSMBL1C0.5",
    "CSMBL1C0.5N",
    "CSMBL1C1",
    "CSMBL1C1N",
    "CSMBL1C2",
    "CSMBL1C2N",
    "CSMBL1C3",
    "CSMBL1C3N",
    "CSMBL1C4",
    "CSMBL1C4N",
    "CSMBL1C5",
    "CSMBL1C5N",
    "CSMBL2B10",
    "CSMBL2B16",
    "CSMBL2B20",
    "CSMBL2B25",
    "CSMBL2B32",
    "CSMBL2B40",
    "CSMBL2B6",
    "CSMBL2C0.5",
    "CSMBL2C1",
    "CSMBL2C2",
    "CSMBL2C3"
  ],
  "canonical_code": "CSBHIC100N",
  "market_segments": null,
  "also_published_as": null,
  "price_observations": []
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "",
      "value": "IP 20",
      "source": null,
      "derived": false,
      "fact_id": "CSBHIC100N-001",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Degree of protection (IP)",
      "value_kind": "text",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a degree of protection (ip) of IP 20.",
      "value_display": "IP 20",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "ip_rating"
    },
    {
      "unit": "V",
      "value": 660.0,
      "source": null,
      "derived": false,
      "fact_id": "CSBHIC100N-002",
      "canonical": true,
      "value_max": 660.0,
      "value_min": 660.0,
      "spec_label": "Rated insulation voltage (Ui)",
      "value_kind": "scalar",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a rated insulation voltage (ui) of 660 V.",
      "value_display": "660 V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_insulation_voltage_ui_v"
    },
    {
      "unit": "V",
      "value": [
        240.0,
        415.0
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSBHIC100N-003",
      "canonical": true,
      "value_max": 415.0,
      "value_min": 240.0,
      "spec_label": "Rated operational voltage (Ue)",
      "value_kind": "set",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a rated operational voltage (ue) of 240/415 V.",
      "value_display": "240/415 V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_voltage_v"
    },
    {
      "unit": "°C",
      "value": 30.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-004",
      "canonical": false,
      "value_max": 30.0,
      "value_min": 30.0,
      "spec_label": "Ambient reference temperature",
      "value_kind": "scalar",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a ambient reference temperature of 30 °C.",
      "value_display": "30 °C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ambient_reference_temperature"
    },
    {
      "unit": "°C",
      "value": null,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-005",
      "canonical": false,
      "value_max": 70.0,
      "value_min": -25.0,
      "spec_label": "Ambient working temperature",
      "value_kind": "range",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a ambient working temperature of -25 °C to +70 °C.",
      "value_display": "-25 °C to +70 °C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ambient_working_temperature"
    },
    {
      "unit": "",
      "value": "Vertical / Horizontal",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Installation position",
      "value_kind": "text",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a installation position of Vertical / Horizontal.",
      "value_display": "Vertical / Horizontal",
      "source_of_truth": "brochure",
      "canonical_spec_id": "installation_position"
    },
    {
      "unit": "mm",
      "value": [
        17.8,
        35.6,
        53.4,
        71.2
      ],
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-007",
      "canonical": false,
      "value_max": 71.2,
      "value_min": 17.8,
      "spec_label": "Module width",
      "value_kind": "set",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a module width of SP 17.8 mm, DP 35.6 mm, TP 53.4 mm, FP 71.2 mm.",
      "value_display": "SP 17.8 mm, DP 35.6 mm, TP 53.4 mm, FP 71.2 mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "module_width"
    },
    {
      "unit": "mm",
      "value": 35.5,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-008",
      "canonical": false,
      "value_max": 35.5,
      "value_min": 35.5,
      "spec_label": "Mounting",
      "value_kind": "scalar",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a mounting of DIN rail, size 35.5 mm.",
      "value_display": "DIN rail, size 35.5 mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": [
        1.0,
        1.0,
        2.0,
        3.0,
        3.0,
        4.0,
        2.0,
        3.0,
        4.0
      ],
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-009",
      "canonical": false,
      "value_max": 4.0,
      "value_min": 1.0,
      "spec_label": "Pole executions offered",
      "value_kind": "set",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a pole executions offered of MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P.",
      "value_display": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pole_executions_offered"
    },
    {
      "unit": "mm",
      "value": 40.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-010",
      "canonical": false,
      "value_max": 40.0,
      "value_min": 40.0,
      "spec_label": "Resistance to shock",
      "value_kind": "scalar",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a resistance to shock of 40 mm free fall.",
      "value_display": "40 mm free fall",
      "source_of_truth": "brochure",
      "canonical_spec_id": "resistance_to_shock"
    },
    {
      "unit": "",
      "value": "Combination head captive screws (+/– screwdriver)",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-011",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Terminal screws",
      "value_kind": "text",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a terminal screws of Combination head captive screws (+/– screwdriver).",
      "value_display": "Combination head captive screws (+/– screwdriver)",
      "source_of_truth": "brochure",
      "canonical_spec_id": "terminal_screws"
    },
    {
      "unit": "INR",
      "value": "NOT_IN_PRICELIST",
      "source": null,
      "derived": false,
      "fact_id": "CSBHIC100N-price",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "MRP",
      "value_kind": "text",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has price status not_in_pricelist.",
      "value_display": "NOT_IN_PRICELIST",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "derived": null,
  "sources": [
    "Brochure: MCB_.md"
  ],
  "spec_ids": [
    "ambient_reference_temperature",
    "ambient_working_temperature",
    "installation_position",
    "ip_rating",
    "module_width",
    "mounting",
    "pole_executions_offered",
    "price_inr",
    "rated_insulation_voltage_ui_v",
    "rated_voltage_v",
    "resistance_to_shock",
    "terminal_screws"
  ],
  "extraction": {
    "chunks": 5,
    "source": "brochure_only",
    "decoded": false,
    "has_price": false,
    "confidence": "medium",
    "has_profile": true,
    "spec_fields": 3
  }
}
```

**content**

```
Category: Final Distribution Products > MCB & Isolators > WiNtrip MCB & Isolator.
CSBHIC100N — WiNtrip MCB & Isolator
Accessories — auxiliary contact and shunt trip
**Auxiliary Contact** — Attachment fitted with the MCB, used for interlocking, signalling and indication. The auxiliary switch is switched on or off along with the MCB through internal linkage.

| Standard Conformity | IEC 60974-5-1 |
| --- | --- |
| Current Rating | 5A |
| Voltage Rating | 240V AC |
| Contact Configuration | 1NO+1NC |
| Contact Configuration | 2NO+2NC |
| Contact Configuration | 1NO+NC (Potential) |
| Protection | IP 20 |
| Electrical Endurance (nos) | 10000 |
| Fitment | Factory/Site Fitted Right Side of MCB |

**Shunt Trip** — Controls the remote tripping of the MCB to which it is attached.

| Standard Conformity | IEC 60947-5-1 |
| --- | --- |
| Rated Voltage AC | 110V, 220V |
| DC | 12V, 24V, 48V |
| Operating Voltage | 70-110% of Rated Voltage |
| Protection | IP 20 |
| Electrical Endurance (nos.) | 10000 |
| Fitment Left Side of MCB | Factory/Site Fitted |

**Accessory dimensions (WiNtrip 1 section, mm)** — Auxiliary Contact: 45.2, 72.1, 47.5, 50, 6, 35.4, 84, 9. Shunt Trip: 45.2, 71.8, 47.5, 50, 6, 35.4, 84, 17.8.
```

### Family: `COMBI Weather Proof Enclosures` · chunk_type: `application`

- **id**: `1282376`
- **product_id**: `101379`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:22.765611`
- **lastchange_datetime**: `2026-08-12T15:07:22.765611`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Modular Switches",
    "COMBI Weather Proof Enclosures"
  ],
  "depth": 3,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/",
      "name": "Modular Switches",
      "level": 2,
      "is_leaf": false,
      "contents": [
        {
          "name": "Elusio Switches",
          "note": "Born Green. Elegant, Sleek, Smart and Break Free Design"
        },
        {
          "name": "DIVINO Switches",
          "note": "Available in 1 module to 18 module options"
        },
        {
          "name": "Primo Plus Switches",
          "note": "Available with Anti Bacterial features"
        },
        {
          "name": "Primo Switches",
          "note": "25 Amps. switch socket for air-conditioners and geysers"
        },
        {
          "name": "COMBI Weather Proof Enclosures",
          "note": "Available in IP40 & IP55"
        },
        {
          "name": "Bridgg Modular Switches",
          "note": "Switch to Elegance"
        }
      ],
      "has_page": true,
      "markdown": "# Modular Switches\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Modular Switches\n\n## Contents\n- [Elusio Switches](./Elusio Switches/) — Born Green. Elegant, Sleek, Smart and Break Free Design\n- [DIVINO Switches](./DIVINO Switches/) — Available in 1 module to 18 module options\n- [Primo Plus Switches](./Primo Plus Switches/) — Available with Anti Bacterial features\n- [Primo Switches](./Primo Switches/) — 25 Amps. switch socket for air-conditioners and geysers\n- [COMBI Weather Proof Enclosures](./COMBI Weather Proof Enclosures/) — Available in IP40 & IP55\n- [Bridgg Modular Switches](./Bridgg Modular Switches/) — Switch to Elegance",
      "page_type": "_category.md",
      "description": null,
      "source_file": "Final Distribution Products/Modular Switches/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/combi/",
      "name": "COMBI Weather Proof Enclosures",
      "level": 3,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# COMBI Weather Proof Enclosures\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/combi/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Modular Switches > Modular Switches – COMBI\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/Combi.jpg (saved as `Combi.jpg`)\n\n## Presentation\nA perfect home is not complete without ensuring the safety factor. That’s where Combi range of switches from C&S Electric come to play a major role. They are designed to ensure safety for everyone not just inside the house but outside as well. The range offers you uniquely designed switches that can withstand extreme weather conditions, be it the dusty summer or the torrential monsoon. But the best part? It is easy to install on the wall thanks to its surface mounting feature.\nCombi-IP55 has a moulded outer shell that works as a protection cover against dust. The PVC membrane at the front keeps it dry even under wet climatic conditions, offering you absolute safety to operate the switch. Yes, a two-way champion, making it the perfect choice for your house, whether it is for the balcony, living room, kitchen, bathroom, garden or swimming pool. It can even be installed in more demanding places such as shipyards, sterile labs and more.\n\n## Benefits\nComplete weather proof solution\nEasy to install\nHigh impact resistant material construction\nLong Life & Durability\nAvailable in 1M-12M options both in vertical and horizontal design.\n\n## Brochure\n- [COMBI-Catalog-2015.pdf](./COMBI-Catalog-2015.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/COMBI-Catalog-2015.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Modular Switches/COMBI Weather Proof Enclosures/product.md"
    }
  ],
  "headings": [
    "Typical applications"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/combi/",
  "family": "COMBI Weather Proof Enclosures",
  "decoded": {
    "item": {
      "code": "025",
      "meaning": "unknown"
    },
    "brand": {
      "code": "CG",
      "meaning": "DIVINO"
    },
    "finish": {
      "code": "W",
      "meaning": "unknown"
    },
    "finish_series": {
      "code": "24",
      "value": 24,
      "meaning": 24
    }
  },
  "sku_code": "CG24025W",
  "attributes": {
    "finish": {
      "code": "W",
      "label": "unknown"
    },
    "finish_series": {
      "code": "24",
      "label": "24"
    }
  },
  "peer_group": "COMBI Weather Proof Enclosures",
  "description": null,
  "alias_reason": "pricelist prints this code with an NR suffix",
  "price_status": "not_listed",
  "comparable_on": [],
  "related_codes": [
    "CG26000W",
    "CG26400W",
    "CG26016W",
    "CG28017",
    "CG28015",
    "CG28020"
  ],
  "canonical_code": "CG24025WNR",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": [
    "CG24025WNR"
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
      "value": 10.0,
      "source": null,
      "derived": false,
      "fact_id": "CG24025WNR-001",
      "canonical": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "spec_label": "Standard packing quantity",
      "value_kind": "scalar",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a standard packing quantity of 10.",
      "value_display": "10",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "pack_qty"
    },
    {
      "unit": "INR",
      "value": 860.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 147
      },
      "derived": false,
      "fact_id": "CG24025WNR-002",
      "canonical": true,
      "value_max": 860.0,
      "value_min": 860.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has an MRP of ₹860 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹860",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Non resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Acetone (solvent)",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a acetone (solvent) of Non resistant.",
      "value_display": "Non resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "acetone_solvent"
    },
    {
      "unit": "",
      "value": "Non resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Benzol (solvent)",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a benzol (solvent) of Non resistant.",
      "value_display": "Non resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "benzol_solvent"
    },
    {
      "unit": "",
      "value": 7035.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CG24025WNR-005",
      "canonical": false,
      "value_max": 7035.0,
      "value_min": 7035.0,
      "spec_label": "Body colour",
      "value_kind": "scalar",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a body colour of White (RAL 7035).",
      "value_display": "White (RAL 7035)",
      "source_of_truth": "brochure",
      "canonical_spec_id": "body_colour"
    },
    {
      "unit": "",
      "value": "Limited resistance",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Concentrated acid",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a concentrated acid of Limited resistance.",
      "value_display": "Limited resistance",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "concentrated_acid"
    },
    {
      "unit": "",
      "value": "Resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Concentrated base",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a concentrated base of Resistant.",
      "value_display": "Resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "concentrated_base"
    },
    {
      "unit": "",
      "value": "Resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-008",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Diluted acid",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a diluted acid of Resistant.",
      "value_display": "Resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "diluted_acid"
    },
    {
      "unit": "",
      "value": "Resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Diluted base",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a diluted base of Resistant.",
      "value_display": "Resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "diluted_base"
    },
    {
      "unit": "",
      "value": "Non resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-010",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Ethyl alcohol",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a ethyl alcohol of Non resistant.",
      "value_display": "Non resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "ethyl_alcohol"
    },
    {
      "unit": "°C",
      "value": 650.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CG24025WNR-011",
      "canonical": false,
      "value_max": 650.0,
      "value_min": 650.0,
      "spec_label": "Glow wire test",
      "value_kind": "scalar",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a glow wire test of 650°C.",
      "value_display": "650°C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "glow_wire_test"
    },
    {
      "unit": "",
      "value": "Limited resistance",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-012",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Hexane",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a hexane of Limited resistance.",
      "value_display": "Limited resistance",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "hexane"
    },
    {
      "unit": "",
      "value": "IP55",
      "source": "brochure",
      "derived": false,
      "fact_id": "CG24025WNR-013",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "IP protection rating",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a ip protection rating of IP55.",
      "value_display": "IP55",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ip_protection_rating"
    },
    {
      "unit": "°C",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CG24025WNR-014",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Maximum temperature",
      "value_kind": "scalar",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a maximum temperature of +60°C.",
      "value_display": "+60°C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "maximum_temperature"
    },
    {
      "unit": "",
      "value": "Limited resistance",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-015",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mineral oil",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a mineral oil of Limited resistance.",
      "value_display": "Limited resistance",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "mineral_oil"
    },
    {
      "unit": "°C",
      "value": -25.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CG24025WNR-016",
      "canonical": false,
      "value_max": -25.0,
      "value_min": -25.0,
      "spec_label": "Minimum installation temperature",
      "value_kind": "scalar",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a minimum installation temperature of -25°C.",
      "value_display": "-25°C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "minimum_installation_temperature"
    },
    {
      "unit": "",
      "value": "Surface mounted / semi-concealed",
      "source": "brochure",
      "derived": false,
      "fact_id": "CG24025WNR-017",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a mounting of Surface mounted / semi-concealed.",
      "value_display": "Surface mounted / semi-concealed",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": "CEI 23-48, IEC 60670, IS: 12063-1987",
      "source": "brochure",
      "derived": false,
      "fact_id": "CG24025WNR-018",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Reference standards",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a reference standards of CEI 23-48, IEC 60670, IS: 12063-1987.",
      "value_display": "CEI 23-48, IEC 60670, IS: 12063-1987",
      "source_of_truth": "brochure",
      "canonical_spec_id": "reference_standards"
    },
    {
      "unit": "",
      "value": "Resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-019",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Saline solution",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a saline solution of Resistant.",
      "value_display": "Resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "saline_solution"
    },
    {
      "unit": "°C",
      "value": 70.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CG24025WNR-020",
      "canonical": false,
      "value_max": 70.0,
      "value_min": 70.0,
      "spec_label": "Thermo-pressure test (ball)",
      "value_kind": "scalar",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a thermo-pressure test (ball) of 70°C.",
      "value_display": "70°C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "thermo_pressure_test_ball"
    },
    {
      "unit": "",
      "value": "Resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-021",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "UV rays",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a uv rays of Resistant.",
      "value_display": "Resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "uv_rays"
    },
    {
      "unit": "",
      "value": "Resistant",
      "source": "Chemical / environmental resistance (COMBI IP55 enclosure material)",
      "derived": false,
      "fact_id": "CG24025WNR-022",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Water",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) has a water of Resistant.",
      "value_display": "Resistant",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "water"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CG24025WNR-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CG24025WNR-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CG24025WNR (COMBI Weather Proof Enclosures) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": {
    "price_per_unit_inr": 86.0
  },
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p147",
    "Brochure: COMBI-Catalog-2015.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/combi/"
  ],
  "spec_ids": [
    "acetone_solvent",
    "benzol_solvent",
    "body_colour",
    "concentrated_acid",
    "concentrated_base",
    "diluted_acid",
    "diluted_base",
    "ethyl_alcohol",
    "glow_wire_test",
    "gst_rate_pct",
    "hexane",
    "ip_protection_rating",
    "market_segments",
    "maximum_temperature",
    "mineral_oil",
    "minimum_installation_temperature",
    "mounting",
    "pack_qty",
    "price_inr",
    "reference_standards",
    "saline_solution",
    "thermo_pressure_test_ball",
    "uv_rays",
    "water"
  ],
  "extraction": {
    "chunks": 3,
    "decoded": true,
    "missing": [
      "rated_current_a",
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

**content**

```
Category: Final Distribution Products > Modular Switches > COMBI Weather Proof Enclosures.
CG24025W — COMBI Weather Proof Enclosures
Typical applications
Bell Push, Kitchen, Bathroom, Children's Room, Swimming Pool, Parks & Garden, Street Lamps, Parking Lights, Chemical Laboratories, Industries.
Category: Final Distribution Products > Modular Switches > COMBI Weather Proof Enclosures.
CG24025WNR — COMBI Weather Proof Enclosures
Typical applications
Bell Push, Kitchen, Bathroom, Children's Room, Swimming Pool, Parks & Garden, Street Lamps, Parking Lights, Chemical Laboratories, Industries.
```

### Family: `Bridgg Modular Switches` · chunk_type: `commercial`

- **id**: `1281578`
- **product_id**: `101279`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:22.765611`
- **lastchange_datetime**: `2026-08-12T15:07:22.765611`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Modular Switches",
    "Bridgg Modular Switches"
  ],
  "depth": 3,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/",
      "name": "Modular Switches",
      "level": 2,
      "is_leaf": false,
      "contents": [
        {
          "name": "Elusio Switches",
          "note": "Born Green. Elegant, Sleek, Smart and Break Free Design"
        },
        {
          "name": "DIVINO Switches",
          "note": "Available in 1 module to 18 module options"
        },
        {
          "name": "Primo Plus Switches",
          "note": "Available with Anti Bacterial features"
        },
        {
          "name": "Primo Switches",
          "note": "25 Amps. switch socket for air-conditioners and geysers"
        },
        {
          "name": "COMBI Weather Proof Enclosures",
          "note": "Available in IP40 & IP55"
        },
        {
          "name": "Bridgg Modular Switches",
          "note": "Switch to Elegance"
        }
      ],
      "has_page": true,
      "markdown": "# Modular Switches\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Modular Switches\n\n## Contents\n- [Elusio Switches](./Elusio Switches/) — Born Green. Elegant, Sleek, Smart and Break Free Design\n- [DIVINO Switches](./DIVINO Switches/) — Available in 1 module to 18 module options\n- [Primo Plus Switches](./Primo Plus Switches/) — Available with Anti Bacterial features\n- [Primo Switches](./Primo Switches/) — 25 Amps. switch socket for air-conditioners and geysers\n- [COMBI Weather Proof Enclosures](./COMBI Weather Proof Enclosures/) — Available in IP40 & IP55\n- [Bridgg Modular Switches](./Bridgg Modular Switches/) — Switch to Elegance",
      "page_type": "_category.md",
      "description": null,
      "source_file": "Final Distribution Products/Modular Switches/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/bridgg-switches/",
      "name": "Bridgg Modular Switches",
      "level": 3,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Bridgg Modular Switches – Anywhere, Everywhere\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/bridgg-switches/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Modular Switches > Bridgg Switches\n**Image:** https://cselectric.co.in/wp-content/uploads/2025/09/1.webp (saved as `1.webp`)\n\n## Presentation\nBridgg is the elegant modular switch range, designed to seamlessly blend style and affordability, elevating any space.\nCrafted with precision engineering and a keen eye for design, Bridgg modular switches boast a sleek and modern aesthetic that complements any interior décor. From minimalist elegance to bold statements, Bridgg suits all kinds of décor.\nWhat sets Bridgg apart is its versatility and adaptability—whether you’re renovating your home or upgrading your office.\n\n## Benefits\nSingle-lock design\nLong-lasting and durable\nModular design, easy to install\nAdaptable to existing market-size boxes\nSockets fitted with safety shutters for extra protection\n\n## Brochure\n- [Bridgg-Modular-Switches.pdf](./Bridgg-Modular-Switches.pdf) (source: https://cselectric.co.in/wp-content/uploads/2025/09/Bridgg-Modular-Switches.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Modular Switches/Bridgg Modular Switches/product.md"
    }
  ],
  "headings": [
    "General terms and conditions"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/bridgg-switches/",
  "family": "Bridgg Modular Switches",
  "decoded": {
    "item": {
      "code": "056",
      "meaning": "unknown"
    },
    "brand": {
      "code": "CB",
      "meaning": "BRIDGG / BRIDGG 2.0"
    },
    "modules": {
      "code": "2",
      "value": 2,
      "meaning": 2
    },
    "finish_series": {
      "code": "20",
      "meaning": "pure white / white base plate"
    }
  },
  "sku_code": "CB20056-2",
  "attributes": {
    "finish_series": {
      "code": "20",
      "label": "pure white / white base plate"
    }
  },
  "peer_group": "Bridgg Modular Switches",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "modules",
    "price_inr"
  ],
  "related_codes": [
    "CB20631-2",
    "CB20228-2",
    "CB20251-2",
    "CB20272-2",
    "CB20275-2",
    "CB20278-2",
    "CB20279-2",
    "CB20815-2"
  ],
  "canonical_code": "CB20056-2",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 29,
      "column": "MRP (`)",
      "context": "CB20826-2 | Fan Regulator 100W | Accessories",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 44,
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
      "unit": "count",
      "value": 2.0,
      "source": null,
      "derived": true,
      "fact_id": "CB20056-2-001",
      "canonical": true,
      "value_max": 2.0,
      "value_min": 2.0,
      "spec_label": "Width in modules",
      "value_kind": "scalar",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has 2 modules.",
      "value_display": "2",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "modules"
    },
    {
      "unit": "INR",
      "value": 29.0,
      "source": {
        "pdf": "Retail-Pricelist-wef-1st-June26.pdf",
        "page": 44
      },
      "derived": false,
      "fact_id": "CB20056-2-002",
      "canonical": true,
      "value_max": 29.0,
      "value_min": 29.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has an MRP of ₹29 in the RETAIL pricelist effective 2026-06-01.",
      "value_display": "₹29",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Adaptable to existing market-size boxes",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Box compatibility",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a box compatibility of Adaptable to existing market-size boxes.",
      "value_display": "Adaptable to existing market-size boxes",
      "source_of_truth": "brochure",
      "canonical_spec_id": "box_compatibility"
    },
    {
      "unit": "",
      "value": "Flame retardant, sleek design, unbreakable design, smooth to touch",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Design characteristics",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a design characteristics of Flame retardant, sleek design, unbreakable design, smooth to touch.",
      "value_display": "Flame retardant, sleek design, unbreakable design, smooth to touch",
      "source_of_truth": "brochure",
      "canonical_spec_id": "design_characteristics"
    },
    {
      "unit": "",
      "value": "Single-lock design; modular, easy to install",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Locking / assembly",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a locking / assembly of Single-lock design; modular, easy to install.",
      "value_display": "Single-lock design; modular, easy to install",
      "source_of_truth": "brochure",
      "canonical_spec_id": "locking_assembly"
    },
    {
      "unit": "",
      "value": "Items rated in module widths (1M upward); mounted on a support plate behind a matching cover plate",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Module sizing",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a module sizing of Items rated in module widths (1M upward); mounted on a support plate behind a matching cover plate.",
      "value_display": "Items rated in module widths (1M upward); mounted on a support plate behind a matching cover plate",
      "source_of_truth": "brochure",
      "canonical_spec_id": "module_sizing"
    },
    {
      "unit": "",
      "value": "MRP in Indian Rupees, inclusive of GST; subject to revision without prior notice",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Price basis",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a price basis of MRP in Indian Rupees, inclusive of GST; subject to revision without prior notice.",
      "value_display": "MRP in Indian Rupees, inclusive of GST; subject to revision without prior notice",
      "source_of_truth": "brochure",
      "canonical_spec_id": "price_basis"
    },
    {
      "unit": "",
      "value": "Bridgg modular switch range, C&S Electric",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-008",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Range",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a range of Bridgg modular switch range, C&S Electric.",
      "value_display": "Bridgg modular switch range, C&S Electric",
      "source_of_truth": "brochure",
      "canonical_spec_id": "range"
    },
    {
      "unit": "",
      "value": "Sockets fitted with safety shutters",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Socket protection",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a socket protection of Sockets fitted with safety shutters.",
      "value_display": "Sockets fitted with safety shutters",
      "source_of_truth": "brochure",
      "canonical_spec_id": "socket_protection"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CB20056-2-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CB20056-2-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "Retail-Pricelist-wef-1st-June26.pdf p44",
    "Brochure: Bridgg-Modular-Switches.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/bridgg-switches/"
  ],
  "spec_ids": [
    "box_compatibility",
    "design_characteristics",
    "gst_rate_pct",
    "locking_assembly",
    "market_segments",
    "module_sizing",
    "modules",
    "price_basis",
    "price_inr",
    "range",
    "socket_protection"
  ],
  "extraction": {
    "chunks": 11,
    "decoded": true,
    "missing": [
      "rated_current_a",
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

**content**

```
Category: Final Distribution Products > Modular Switches > Bridgg Modular Switches.
CB20056-2 — Bridgg Modular Switches
General terms and conditions
- Prices are subject to revision without prior notice and will be applicable as prevailing at the time of dispatch.
- Maximum Retail Prices (MRP) mentioned are maximum recommended selling prices inclusive of GST.
- All prices are in Indian Rupees.
```

### Family: `Distribution Boards` · chunk_type: `construction`

- **id**: `1269442`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "headings": [
    "Construction and finish"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
Construction and finish
- Fully equipped DBs supplied with busbar, earth links, neutral links and inter-connecting links.
- Choice of multiple incomer in the form of Isolator, MCB, RCCB + MCB, Isolator + MCB.
- In all modules of SPN, heavy duty gasket has been inserted for weather proofing.
- All doors and frames are deep drawn for better aesthetics and long life, with no welding joints.
- Steel nut inserts with deep screw to give a firm hold and grip to the door.
- Earthing provision, basically required for protection against stray charges producing leakage current — an additional safety factor.
- These Distribution Boards undergo a seven tank phosphating process to ensure anti-rust conditioning, superior finish and long lasting strength.
- 60 micron premium quality powder coating is applied for an extra smooth finish.
- The boards are of universal type, which means they can be both flush or wall mounted based on the requirement.
- Extra protection to the DB during masonry work through a masking sheet.
- Insulated neutral links, insulated copper bus bar, earth bar and inter-connecting links with lugs are part of the unit.
```

### Family: `Distribution Boards` · chunk_type: `dimensions`

- **id**: `1269446`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "headings": [
    "TPN Horizontal PPI Double Door DB (IP42) — ways and dimensions",
    "Seven Segment Double Door DB (IP42) — ways and dimensions",
    "SPN Acrylic window Double Door DB (IP42) — ways and dimensions",
    "Polycarbonate Cover Consumer Unit DB — ways and dimensions",
    "Plug & Socket DB units (IP20 single door) — dimensions",
    "Metal clad plugs and sockets — dimensions"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
TPN Horizontal PPI Double Door DB (IP42) — ways and dimensions
TPN horizontal PPI double door distribution board with IP42 protection.


Dimensions — front door 396.0 wide; side view 290.0 / 380.0; bottom 96.0, 100.0, 4.0. Mounting hole details: Ø6.25, Ø10.25, Ø32.0, Ø24.0, 16.0.


All dimensions are in mm.
CSDB7SEGDD04 — Distribution Boards
Seven Segment Double Door DB (IP42) — ways and dimensions
7 Segment TPN double door DB with provision for FP MCB / Isolator / RCCB as incomer, DP MCB / Isolator / RCCB as sub-incomer and SP MCBs as outgoing. IP42 protection.

| Product Code | No. of Ways | No. of Modules |
| --- | --- | --- |
| CSDB7SEGDD04 | 4 | 8+(12+12) |

Dimensions — front door 642.0; side view 492.0 / 622.0; bottom 7.0, 101, 5.0. Mounting hole details: Ø39.0, Ø29.0, Ø8.0.

| Product Code | No. of Ways | A | B | C | TOP — Ø32 Knockout | BOTTOM — Ø32 Knockout |
| --- | --- | --- | --- | --- | --- | --- |
| CSDB7SEGDD04 | 4 | 440.0 | 460.0 | 365.0 | 6 | 6 |

All dimensions are in mm.
CSDB7SEGDD04 — Distribution Boards
SPN Acrylic window Double Door DB (IP42) — ways and dimensions
SPN double door distribution board with acrylic window in the door, IP42 protection.


Dimensions — front door height 256.0; side view 181.0 / 240.0; bottom 88.0 / 3.5.


* Can be used as a 16 way standard distribution board. All dimensions are in mm.
CSDB7SEGDD04 — Distribution Boards
Polycarbonate
… [truncated; full length 2153 chars]
```

### Family: `Distribution Boards` · chunk_type: `environment`

- **id**: `1269445`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "headings": [
    "Doors, gland plates and degree of protection"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
Doors, gland plates and degree of protection
- For enhancing conduit flexibility, detachable gland plates at top and bottom with knock-outs on the two sides, enabling easy installation and connection of conduits of all sizes.
- Two finger holes to lift the plate have been duly plugged, making the board dust free and safe.
- Double door DB with hinge mechanism: on larger DBs the door can be removed temporarily so a fault can be cleared with ease.
- The door can be opened in any direction suitable for the location — just unhinge it from the left side and hinge it on the right side.
- Lock and key mechanism on the front door for better aesthetic value along with additional safety.
- IP42 protection with provision for IP43 on double door boards; single door boards are IP20.
```

### Family: `Distribution Boards` · chunk_type: `features`

- **id**: `1269447`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "headings": [
    "Plug & Socket DB — features"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
Plug & Socket DB — features
- Deep drawn sheet metal powder coated Plug & Socket Distribution Boards
- Range available in 10 & 20 A SPN and 20 & 30 A TP
- Adjustable 35 sq. mm din rail with connecting links
- Insulated neutral link in SPN boards
- SPN plug & socket in 250 V and TP in 440 V
- SPN & TP boards with one blanking plate each & sockets with plastic cover
- Connecting links cross-width section: SPN 2.5 sq. mm flexible cable, TP 6.0 sq. mm flexible cable
- Provision for both flush & wall mounting
- Heavy duty screw type outgoing wire nozzle
- Body in matt finish and cover in semi-glossy finish
- Paint: 60 micron powder coating
- Plug & socket internal material: SPN PBT, TP PBT & porcelain
- Plug & socket also available loose
```

### Family: `Distribution Boards` · chunk_type: `identity`

- **id**: `1269439`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
Ordering code breakdown: config 7SEG = 7-segment TPN DB; door DD = double door; ways 04 = 4.
Used in: Commercial, Residential.
```

### Family: `Distribution Boards` · chunk_type: `installation`

- **id**: `1269444`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "headings": [
    "PAN assembly and wiring space"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
PAN assembly and wiring space
- Unique feature of PAN assembly. This is an added advantage during maintenance.
- All the MCBs mounted inside the DB can be taken out in just one shot by the easy removal of four screws.
- Adequate wiring space has been provided below the pan assembly for proper termination and safety.
- In fully loaded pre-wired DBs, wiring is done with thimble pin for better safety and aesthetics.
```

### Family: `WiNtrip MCB & Isolator` · chunk_type: `losses`

- **id**: `1275970`
- **product_id**: `100658`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:16.548743`
- **lastchange_datetime**: `2026-08-12T15:07:16.548743`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "MCB & Isolators",
    "WiNtrip MCB & Isolator"
  ],
  "depth": 3,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/",
      "name": "MCB & Isolators",
      "level": 2,
      "is_leaf": false,
      "contents": [
        {
          "name": "WiNtrip MCB & Isolator",
          "note": "MCB upto 125A with finger touch proof terminals with a Breaking Capacity of 10kA"
        },
        {
          "name": "WiNtrip2 MCB & Isolator",
          "note": "With breaking Capacity of 10kA and low power consumption"
        },
        {
          "name": "SmartSol Mini MCB",
          "note": "Mini MCB upto 32A with compact & space saving design"
        },
        {
          "name": "WiNtrip – MCB Changeover Switch",
          "note": "Compact design with shrouded terminals and double break contacts"
        },
        {
          "name": "WiNtrip ‘S’ Modular MCB",
          "note": "Compact & space saving design with rapid closing mechanism"
        },
        {
          "name": "WiNtrip2 DC MCB",
          "note": "Dual Connection possibility for both cable and busbar"
        }
      ],
      "has_page": true,
      "markdown": "# MCB & Isolators\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Miniature Circuit Breakers\n\nMiniature circuit breaker is an electromechanical device that is designed to protect an electrical circuit from overload or short circuit, prevent the equipment from damage & potential hazards like fire.\n\nC&S offers various types of MCBs for different household & industrial application as mentioned below.\n\n## Contents\n- [WiNtrip MCB & Isolator](./WiNtrip MCB & Isolator/) — MCB upto 125A with finger touch proof terminals with a Breaking Capacity of 10kA\n- [WiNtrip2 MCB & Isolator](./WiNtrip2 MCB & Isolator/) — With breaking Capacity of 10kA and low power consumption\n- [SmartSol Mini MCB](./SmartSol Mini MCB/) — Mini MCB upto 32A with compact & space saving design\n- [WiNtrip – MCB Changeover Switch](./WiNtrip – MCB Changeover Switch/) — Compact design with shrouded terminals and double break contacts\n- [WiNtrip ‘S’ Modular MCB](./WiNtrip ‘S’ Modular MCB/) — Compact & space saving design with rapid closing mechanism\n- [WiNtrip2 DC MCB](./WiNtrip2 DC MCB/) — Dual Connection possibility for both cable and busbar",
      "page_type": "_category.md",
      "description": "Miniature circuit breaker is an electromechanical device that is designed to protect an electrical circuit from overload or short circuit, prevent the equipment from damage & potential hazards like fire.\nC&S offers various types of MCBs for different household & industrial application as mentioned below.",
      "source_file": "Final Distribution Products/MCB & Isolators/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/",
      "name": "WiNtrip MCB & Isolator",
      "level": 3,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# WiNtrip MCB & Isolator\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Miniature Circuit Breakers > WiNtrip MCB & Isolator\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/Wintrip-MCB-2.jpg (saved as `Wintrip-MCB-2.jpg`)\n\n## Presentation\nAs power distribution needs play a pivotal role in all the significant sectors namely Commercial, Industrial and Residential, improved Breaker performance through better electrical safety, higher operational endurance, continued service and reduced cost have become of paramount importance. C&S MCBs have been engineered to constantly fulfill the above requirements. With these features C&S is setting new standards for user friendly and superlative electrical circuit protection.\nThe C&S MCB is a high performing Thermal Magnetic current limiting device with the ability to disconnect short circuits up to 10kA. The range is available in tripping characteristics types B, C and D for 1P, 1P+N, 2P, 3P, 3P+N & 4P configurations in 0.5 – 125A current ratings. All metal components for operating mechanism of WiNtrip circuit breaker are specially treated for high self lubrication leading to repeat accuracy during service life. The MCBs conform to Standards: IEC 60898-1995 and IS/IEC 60898-1:2002 and stand guaranteed for best quality for optimum performance.\n\n## Benefits\nElectrical safety\nHigher operational endurance\nDurable and reduced cost\nPlays a pivotal role in all the significant sectors namely Commercial, Industrial and Residential areas\nEnsures circuit identification and enhanced safety\nClear indication of the operational status of device\n\n## Brochure\n- [MCB_.pdf](./MCB_.pdf) (source: https://cselectric.co.in/wp-content/uploads/2025/03/MCB_.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/MCB & Isolators/WiNtrip MCB & Isolator/product.md"
    }
  ],
  "headings": [
    "Watt loss"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/",
  "family": "WiNtrip MCB & Isolator",
  "decoded": {
    "type": {
      "code": "C",
      "meaning": "C curve - inductive load with surge current, motor circuits"
    },
    "poles": {
      "code": "1",
      "meaning": 1
    },
    "range": {
      "code": "L",
      "meaning": "WiNtrip1 MCB / Isolator"
    },
    "rating": {
      "code": "10",
      "value": 10,
      "meaning": 10
    }
  },
  "sku_code": "CSMBL1C10",
  "attributes": {
    "type": {
      "code": "C",
      "label": "C curve - inductive load with surge current, motor circuits"
    },
    "range": {
      "code": "L",
      "label": "WiNtrip1 MCB / Isolator"
    }
  },
  "peer_group": "WiNtrip MCB & Isolator | type=C",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "modules",
    "poles",
    "price_inr",
    "rated_current_a",
    "rated_insulation_voltage_ui_v",
    "rated_voltage_v"
  ],
  "related_codes": [
    "CSMBL1C6",
    "CSMBL1C16",
    "CSMBL1C20",
    "CSMBL1C25",
    "CSMBL1C32",
    "CSMBL1C40",
    "CSMBL1C63",
    "CSMBL1C6N",
    "CSMBL1C10N",
    "CSMBL1C16N",
    "CSMBL1C20N",
    "CSMBL1C25N",
    "CSMBL1C32N",
    "CSMBL1C40N",
    "CSMBL1C63N",
    "CSMBL2C6",
    "CSMBL2C10",
    "CSMBL2C16",
    "CSMBL2C20",
    "CSMBL2C25",
    "CSMBL2C32",
    "CSMBL2C40",
    "CSMBL2C63"
  ],
  "canonical_code": "CSMBL1C10",
  "market_segments": null,
  "also_published_as": null,
  "price_observations": [
    {
      "price": 260,
      "column": "MRP",
      "context": "W i Ntrip1 Miniature Circuit Breaker",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 5,
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
      "unit": "",
      "value": "IP 20",
      "source": null,
      "derived": false,
      "fact_id": "CSMBL1C10-001",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Degree of protection (IP)",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a degree of protection (ip) of IP 20.",
      "value_display": "IP 20",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "ip_rating"
    },
    {
      "unit": "count",
      "value": 1.0,
      "source": null,
      "derived": true,
      "fact_id": "CSMBL1C10-002",
      "canonical": true,
      "value_max": 1.0,
      "value_min": 1.0,
      "spec_label": "Width in modules",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has 1 module.",
      "value_display": "1",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "modules"
    },
    {
      "unit": "count",
      "value": 1.0,
      "source": null,
      "derived": true,
      "fact_id": "CSMBL1C10-003",
      "canonical": true,
      "value_max": 1.0,
      "value_min": 1.0,
      "spec_label": "Number of poles",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has 1 pole.",
      "value_display": "1",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "INR",
      "value": 260.0,
      "source": {
        "pdf": "Retail-Pricelist-wef-1st-June26.pdf",
        "page": 5
      },
      "derived": false,
      "fact_id": "CSMBL1C10-004",
      "canonical": true,
      "value_max": 260.0,
      "value_min": 260.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has an MRP of ₹260 in the RETAIL pricelist effective 2026-06-01.",
      "value_display": "₹260",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "A",
      "value": 10.0,
      "source": null,
      "derived": true,
      "fact_id": "CSMBL1C10-005",
      "canonical": true,
      "value_max": 10.0,
      "value_min": 10.0,
      "spec_label": "Rated current (In)",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a rated current (in) of 10 A.",
      "value_display": "10 A",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "V",
      "value": 660.0,
      "source": null,
      "derived": false,
      "fact_id": "CSMBL1C10-006",
      "canonical": true,
      "value_max": 660.0,
      "value_min": 660.0,
      "spec_label": "Rated insulation voltage (Ui)",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a rated insulation voltage (ui) of 660 V.",
      "value_display": "660 V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_insulation_voltage_ui_v"
    },
    {
      "unit": "V",
      "value": [
        240.0,
        415.0
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSMBL1C10-007",
      "canonical": true,
      "value_max": 415.0,
      "value_min": 240.0,
      "spec_label": "Rated operational voltage (Ue)",
      "value_kind": "set",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a rated operational voltage (ue) of 240/415 V.",
      "value_display": "240/415 V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_voltage_v"
    },
    {
      "unit": "°C",
      "value": 30.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-008",
      "canonical": false,
      "value_max": 30.0,
      "value_min": 30.0,
      "spec_label": "Ambient reference temperature",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a ambient reference temperature of 30 °C.",
      "value_display": "30 °C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ambient_reference_temperature"
    },
    {
      "unit": "°C",
      "value": null,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-009",
      "canonical": false,
      "value_max": 70.0,
      "value_min": -25.0,
      "spec_label": "Ambient working temperature",
      "value_kind": "range",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a ambient working temperature of -25 °C to +70 °C.",
      "value_display": "-25 °C to +70 °C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ambient_working_temperature"
    },
    {
      "unit": "",
      "value": 1.0,
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-010",
      "canonical": false,
      "value_max": 1.0,
      "value_min": 1.0,
      "spec_label": "Contact Configuration",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a contact configuration of 1NO+NC (Potential).",
      "value_display": "1NO+NC (Potential)",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "contact_configuration"
    },
    {
      "unit": "A",
      "value": 5.0,
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-011",
      "canonical": false,
      "value_max": 5.0,
      "value_min": 5.0,
      "spec_label": "Current Rating",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a current rating of 5A.",
      "value_display": "5A",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "current_rating"
    },
    {
      "unit": "V",
      "value": [
        12.0,
        24.0,
        48.0
      ],
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-012",
      "canonical": false,
      "value_max": 48.0,
      "value_min": 12.0,
      "spec_label": "DC",
      "value_kind": "set",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a dc of 12V, 24V, 48V.",
      "value_display": "12V, 24V, 48V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "dc"
    },
    {
      "unit": "",
      "value": 10000.0,
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-013",
      "canonical": false,
      "value_max": 10000.0,
      "value_min": 10000.0,
      "spec_label": "Electrical Endurance (nos.)",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a electrical endurance (nos.) of 10000.",
      "value_display": "10000",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "electrical_endurance_nos"
    },
    {
      "unit": "",
      "value": "Factory/Site Fitted Right Side of MCB",
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-014",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fitment",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a fitment of Factory/Site Fitted Right Side of MCB.",
      "value_display": "Factory/Site Fitted Right Side of MCB",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "fitment"
    },
    {
      "unit": "",
      "value": "Factory/Site Fitted",
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-015",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fitment Left Side of MCB",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a fitment left side of mcb of Factory/Site Fitted.",
      "value_display": "Factory/Site Fitted",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "fitment_left_side_of_mcb"
    },
    {
      "unit": "",
      "value": [
        17.8,
        35.6,
        53.4,
        71.2
      ],
      "source": "Installation dimensions — WiNtrip 1 MCB",
      "derived": false,
      "fact_id": "CSMBL1C10-016",
      "canonical": false,
      "value_max": 71.2,
      "value_min": 17.8,
      "spec_label": "Front view — module widths",
      "value_kind": "set",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a front view — module widths of SP 17.8, DP 35.6, TP 53.4, FP 71.2.",
      "value_display": "SP 17.8, DP 35.6, TP 53.4, FP 71.2",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "front_view_module_widths"
    },
    {
      "unit": "",
      "value": "Vertical / Horizontal",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-017",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Installation position",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a installation position of Vertical / Horizontal.",
      "value_display": "Vertical / Horizontal",
      "source_of_truth": "brochure",
      "canonical_spec_id": "installation_position"
    },
    {
      "unit": "",
      "value": "Intertek ISO 9001:2015, ISO 14001:2015, ISO 45001:2018 — Haridwar, Uttarakhand (MCB & RCCB manufacture)",
      "source": "Standards and certification",
      "derived": false,
      "fact_id": "CSMBL1C10-018",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Manufacturing site management systems",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a manufacturing site management systems of Intertek ISO 9001:2015, ISO 14001:2015, ISO 45001:2018 — Haridwar, Uttarakhand (MCB & RCCB manufacture).",
      "value_display": "Intertek ISO 9001:2015, ISO 14001:2015, ISO 45001:2018 — Haridwar, Uttarakhand (MCB & RCCB manufacture)",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "manufacturing_site_management_systems"
    },
    {
      "unit": "mm",
      "value": [
        17.8,
        35.6,
        53.4,
        71.2
      ],
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-019",
      "canonical": false,
      "value_max": 71.2,
      "value_min": 17.8,
      "spec_label": "Module width",
      "value_kind": "set",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a module width of SP 17.8 mm, DP 35.6 mm, TP 53.4 mm, FP 71.2 mm.",
      "value_display": "SP 17.8 mm, DP 35.6 mm, TP 53.4 mm, FP 71.2 mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "module_width"
    },
    {
      "unit": "mm",
      "value": 35.5,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-020",
      "canonical": false,
      "value_max": 35.5,
      "value_min": 35.5,
      "spec_label": "Mounting",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a mounting of DIN rail, size 35.5 mm.",
      "value_display": "DIN rail, size 35.5 mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "%",
      "value": null,
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-021",
      "canonical": false,
      "value_max": 110.0,
      "value_min": 70.0,
      "spec_label": "Operating Voltage",
      "value_kind": "range",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a operating voltage of 70-110% of Rated Voltage.",
      "value_display": "70-110% of Rated Voltage",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "operating_voltage"
    },
    {
      "unit": "",
      "value": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-022",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Pole executions offered",
      "value_kind": "composite",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a pole executions offered of MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P.",
      "value_display": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pole_executions_offered"
    },
    {
      "unit": "",
      "value": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-023",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Pole executions offered (MCB: 1P, 1P+N, 2P, 3P, 3P+N)",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a pole executions offered (mcb: 1p, 1p+n, 2p, 3p, 3p+n) of MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P.",
      "value_display": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pole_executions_offered_1"
    },
    {
      "unit": "",
      "value": [
        1.0,
        2.0,
        3.0,
        4.0
      ],
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-024",
      "canonical": false,
      "value_max": 4.0,
      "value_min": 1.0,
      "spec_label": "Pole executions offered (Isolator: 1P, 2P, 3P & 4P)",
      "value_kind": "set",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a pole executions offered (isolator: 1p, 2p, 3p & 4p) of Isolator: 1P, 2P, 3P & 4P.",
      "value_display": "Isolator: 1P, 2P, 3P & 4P",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pole_executions_offered_2"
    },
    {
      "unit": "",
      "value": "IP 20",
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-025",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Protection",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a protection of IP 20.",
      "value_display": "IP 20",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "protection"
    },
    {
      "unit": "V",
      "value": [
        110.0,
        220.0
      ],
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-026",
      "canonical": false,
      "value_max": 220.0,
      "value_min": 110.0,
      "spec_label": "Rated Voltage AC",
      "value_kind": "set",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a rated voltage ac of 110V, 220V.",
      "value_display": "110V, 220V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_voltage_ac"
    },
    {
      "unit": "mm",
      "value": 40.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-027",
      "canonical": false,
      "value_max": 40.0,
      "value_min": 40.0,
      "spec_label": "Resistance to shock",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a resistance to shock of 40 mm free fall.",
      "value_display": "40 mm free fall",
      "source_of_truth": "brochure",
      "canonical_spec_id": "resistance_to_shock"
    },
    {
      "unit": "",
      "value": [
        45.2,
        73.1,
        47.5,
        50.0,
        6.0,
        35.5,
        84.0
      ],
      "source": "Installation dimensions — WiNtrip 1 MCB",
      "derived": false,
      "fact_id": "CSMBL1C10-028",
      "canonical": false,
      "value_max": 84.0,
      "value_min": 6.0,
      "spec_label": "Side / section view",
      "value_kind": "set",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a side / section view of 45.2, 73.1, 47.5, 50, 6, 35.5, 84.",
      "value_display": "45.2, 73.1, 47.5, 50, 6, 35.5, 84",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "side_section_view"
    },
    {
      "unit": "",
      "value": "Combination head captive screws (+/– screwdriver)",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMBL1C10-029",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Terminal screws",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a terminal screws of Combination head captive screws (+/– screwdriver).",
      "value_display": "Combination head captive screws (+/– screwdriver)",
      "source_of_truth": "brochure",
      "canonical_spec_id": "terminal_screws"
    },
    {
      "unit": "V",
      "value": 240.0,
      "source": "Accessories — auxiliary contact and shunt trip",
      "derived": false,
      "fact_id": "CSMBL1C10-030",
      "canonical": false,
      "value_max": 240.0,
      "value_min": 240.0,
      "spec_label": "Voltage Rating",
      "value_kind": "scalar",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole) has a voltage rating of 240V AC.",
      "value_display": "240V AC",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "voltage_rating"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSMBL1C10-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSMBL1C10 (WiNtrip MCB & Isolator, 10 A, 1-pole): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    }
  ],
  "derived": {
    "price_per_rated_amp_inr": 26.0
  },
  "sources": [
    "Retail-Pricelist-wef-1st-June26.pdf p5",
    "Brochure: MCB_.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/"
  ],
  "spec_ids": [
    "ambient_reference_temperature",
    "ambient_working_temperature",
    "contact_configuration",
    "current_rating",
    "dc",
    "electrical_endurance_nos",
    "fitment",
    "fitment_left_side_of_mcb",
    "front_view_module_widths",
    "gst_rate_pct",
    "installation_position",
    "ip_rating",
    "manufacturing_site_management_systems",
    "module_width",
    "modules",
    "mounting",
    "operating_voltage",
    "pole_executions_offered",
    "pole_executions_offered_1",
    "pole_executions_offered_2",
    "poles",
    "price_inr",
    "protection",
    "rated_current_a",
    "rated_insulation_voltage_ui_v",
    "rated_voltage_ac",
    "rated_voltage_v",
    "resistance_to_shock",
    "side_section_view",
    "terminal_screws",
    "voltage_rating"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "standards",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 7
  }
}
```

**content**

```
Category: Final Distribution Products > MCB & Isolators > WiNtrip MCB & Isolator.
CSMBL1C10 — WiNtrip MCB & Isolator
Watt loss
| Rating (Amp) | Maximum Watt Loss | Maximum watt loss in SP |
| --- | --- | --- |
| 6 | 3.0W | 1.12W |
| 10 | 3.0W | 1.83W |
| 16 | 3.5W | 2.44W |
| 20 | 4.5W | 3.07W |
| 25 | 4.5W | 2.96W |
| 32 | 6.0W | 3.92W |
| 40 | 7.5W | 4.2W |
| 63 | 13.0W | 6.06W |
| 80 | 15.0W | 8.2W |
| 100 | 15.0W | 9.5W |
| 125 | 20.0W | 14.0W |

Note: 80A, 100A, 125A as per IEC 60947-2.
```

### Family: `Distribution Boards` · chunk_type: `ordering`

- **id**: `1269448`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "headings": [
    "MCB selection chart for outgoing circuits"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
MCB selection chart for outgoing circuits
Guide for choosing the outgoing MCB rating and curve when populating the board.

| Appliances | Capacity / Approx. Wattage | Rating (A) | MCB Type |
| --- | --- | --- | --- |
| Air-Conditioner | 1.0 T / 1.5 T / 2.0 T | 16A / 20A / 32A | C Type |
| Refrigerator | 165 L / 350 L | 3A / 4A | C Type |
| Oven + Griller | 4500 W / 1750 W | 25A / 10A | B Type |
| Oven | 750 W | 6A | B Type |
| Toaster | 1200 W | 10A | B Type |
| Electric Kettle | 1500 W | 10A | B Type |
| Electric Iron | 750 W | 6A | B Type |
| Electric Geyser | 4000 W | 20A | B Type |
| Mixer | 200 W | 2A | C Type |
| Washing Machine | 1300 W | 10A | C Type |
```

### Family: `Distribution Boards` · chunk_type: `price`

- **id**: `1269440`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
Price and availability:
- Rs 17,550 in the LV pricelist (CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board), LV-Pricelist-WEF-1st-June26.pdf page 136.
- Rs 17,550 in the RETAIL pricelist (CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board), Retail-Pricelist-wef-1st-June26.pdf page 22.
```

### Family: `Distribution Boards` · chunk_type: `product_range`

- **id**: `1269443`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "headings": [
    "Insulated busbar, neutral and earth links",
    "MCB enclosures (IP55, metal and plastic)"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
Insulated busbar, neutral and earth links
- Insulated / captive busbar and neutral links, for better safety and protection.
- While handling the DB in the event of any fault, the insulated busbar and neutral links will provide protection to the electrician.
- High degree plastic insulated neutral links.
- Brass earth links.
- 100 Amp insulated busbar.
CSDB7SEGDD04 — Distribution Boards
MCB enclosures (IP55, metal and plastic)
**MCB Enclosure IP 55**


Drawing callouts: 105, 170, 5, 7, 115, 95, 2, 41 (front marked IP 55).

**Metal Enclosure (with Din Rail)**


**Plastic Enclosure**


Enclosure dimensions — SP/DP: 52.00 wide, 130.00 high, 113.50, 36.00, with 2 × Ø5.7 mounting holes. TP/FP: 86.50, 70.50, 114.00, 130.00, with 2 × Ø5.7 mounting holes.

All dimensions are in mm.
```

### Family: `Bridgg Modular Switches` · chunk_type: `ratings`

- **id**: `1281577`
- **product_id**: `101279`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:22.765611`
- **lastchange_datetime**: `2026-08-12T15:07:22.765611`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Modular Switches",
    "Bridgg Modular Switches"
  ],
  "depth": 3,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/",
      "name": "Modular Switches",
      "level": 2,
      "is_leaf": false,
      "contents": [
        {
          "name": "Elusio Switches",
          "note": "Born Green. Elegant, Sleek, Smart and Break Free Design"
        },
        {
          "name": "DIVINO Switches",
          "note": "Available in 1 module to 18 module options"
        },
        {
          "name": "Primo Plus Switches",
          "note": "Available with Anti Bacterial features"
        },
        {
          "name": "Primo Switches",
          "note": "25 Amps. switch socket for air-conditioners and geysers"
        },
        {
          "name": "COMBI Weather Proof Enclosures",
          "note": "Available in IP40 & IP55"
        },
        {
          "name": "Bridgg Modular Switches",
          "note": "Switch to Elegance"
        }
      ],
      "has_page": true,
      "markdown": "# Modular Switches\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Modular Switches\n\n## Contents\n- [Elusio Switches](./Elusio Switches/) — Born Green. Elegant, Sleek, Smart and Break Free Design\n- [DIVINO Switches](./DIVINO Switches/) — Available in 1 module to 18 module options\n- [Primo Plus Switches](./Primo Plus Switches/) — Available with Anti Bacterial features\n- [Primo Switches](./Primo Switches/) — 25 Amps. switch socket for air-conditioners and geysers\n- [COMBI Weather Proof Enclosures](./COMBI Weather Proof Enclosures/) — Available in IP40 & IP55\n- [Bridgg Modular Switches](./Bridgg Modular Switches/) — Switch to Elegance",
      "page_type": "_category.md",
      "description": null,
      "source_file": "Final Distribution Products/Modular Switches/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/bridgg-switches/",
      "name": "Bridgg Modular Switches",
      "level": 3,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Bridgg Modular Switches – Anywhere, Everywhere\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/bridgg-switches/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Modular Switches > Bridgg Switches\n**Image:** https://cselectric.co.in/wp-content/uploads/2025/09/1.webp (saved as `1.webp`)\n\n## Presentation\nBridgg is the elegant modular switch range, designed to seamlessly blend style and affordability, elevating any space.\nCrafted with precision engineering and a keen eye for design, Bridgg modular switches boast a sleek and modern aesthetic that complements any interior décor. From minimalist elegance to bold statements, Bridgg suits all kinds of décor.\nWhat sets Bridgg apart is its versatility and adaptability—whether you’re renovating your home or upgrading your office.\n\n## Benefits\nSingle-lock design\nLong-lasting and durable\nModular design, easy to install\nAdaptable to existing market-size boxes\nSockets fitted with safety shutters for extra protection\n\n## Brochure\n- [Bridgg-Modular-Switches.pdf](./Bridgg-Modular-Switches.pdf) (source: https://cselectric.co.in/wp-content/uploads/2025/09/Bridgg-Modular-Switches.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Modular Switches/Bridgg Modular Switches/product.md"
    }
  ],
  "headings": [
    "Power unit combos",
    "Power extension boards and door bells"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/bridgg-switches/",
  "family": "Bridgg Modular Switches",
  "decoded": {
    "item": {
      "code": "056",
      "meaning": "unknown"
    },
    "brand": {
      "code": "CB",
      "meaning": "BRIDGG / BRIDGG 2.0"
    },
    "modules": {
      "code": "2",
      "value": 2,
      "meaning": 2
    },
    "finish_series": {
      "code": "20",
      "meaning": "pure white / white base plate"
    }
  },
  "sku_code": "CB20056-2",
  "attributes": {
    "finish_series": {
      "code": "20",
      "label": "pure white / white base plate"
    }
  },
  "peer_group": "Bridgg Modular Switches",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "modules",
    "price_inr"
  ],
  "related_codes": [
    "CB20631-2",
    "CB20228-2",
    "CB20251-2",
    "CB20272-2",
    "CB20275-2",
    "CB20278-2",
    "CB20279-2",
    "CB20815-2"
  ],
  "canonical_code": "CB20056-2",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 29,
      "column": "MRP (`)",
      "context": "CB20826-2 | Fan Regulator 100W | Accessories",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 44,
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
      "unit": "count",
      "value": 2.0,
      "source": null,
      "derived": true,
      "fact_id": "CB20056-2-001",
      "canonical": true,
      "value_max": 2.0,
      "value_min": 2.0,
      "spec_label": "Width in modules",
      "value_kind": "scalar",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has 2 modules.",
      "value_display": "2",
      "source_of_truth": "code_grammar",
      "canonical_spec_id": "modules"
    },
    {
      "unit": "INR",
      "value": 29.0,
      "source": {
        "pdf": "Retail-Pricelist-wef-1st-June26.pdf",
        "page": 44
      },
      "derived": false,
      "fact_id": "CB20056-2-002",
      "canonical": true,
      "value_max": 29.0,
      "value_min": 29.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has an MRP of ₹29 in the RETAIL pricelist effective 2026-06-01.",
      "value_display": "₹29",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Adaptable to existing market-size boxes",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Box compatibility",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a box compatibility of Adaptable to existing market-size boxes.",
      "value_display": "Adaptable to existing market-size boxes",
      "source_of_truth": "brochure",
      "canonical_spec_id": "box_compatibility"
    },
    {
      "unit": "",
      "value": "Flame retardant, sleek design, unbreakable design, smooth to touch",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Design characteristics",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a design characteristics of Flame retardant, sleek design, unbreakable design, smooth to touch.",
      "value_display": "Flame retardant, sleek design, unbreakable design, smooth to touch",
      "source_of_truth": "brochure",
      "canonical_spec_id": "design_characteristics"
    },
    {
      "unit": "",
      "value": "Single-lock design; modular, easy to install",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Locking / assembly",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a locking / assembly of Single-lock design; modular, easy to install.",
      "value_display": "Single-lock design; modular, easy to install",
      "source_of_truth": "brochure",
      "canonical_spec_id": "locking_assembly"
    },
    {
      "unit": "",
      "value": "Items rated in module widths (1M upward); mounted on a support plate behind a matching cover plate",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Module sizing",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a module sizing of Items rated in module widths (1M upward); mounted on a support plate behind a matching cover plate.",
      "value_display": "Items rated in module widths (1M upward); mounted on a support plate behind a matching cover plate",
      "source_of_truth": "brochure",
      "canonical_spec_id": "module_sizing"
    },
    {
      "unit": "",
      "value": "MRP in Indian Rupees, inclusive of GST; subject to revision without prior notice",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Price basis",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a price basis of MRP in Indian Rupees, inclusive of GST; subject to revision without prior notice.",
      "value_display": "MRP in Indian Rupees, inclusive of GST; subject to revision without prior notice",
      "source_of_truth": "brochure",
      "canonical_spec_id": "price_basis"
    },
    {
      "unit": "",
      "value": "Bridgg modular switch range, C&S Electric",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-008",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Range",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a range of Bridgg modular switch range, C&S Electric.",
      "value_display": "Bridgg modular switch range, C&S Electric",
      "source_of_truth": "brochure",
      "canonical_spec_id": "range"
    },
    {
      "unit": "",
      "value": "Sockets fitted with safety shutters",
      "source": "brochure",
      "derived": false,
      "fact_id": "CB20056-2-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Socket protection",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) has a socket protection of Sockets fitted with safety shutters.",
      "value_display": "Sockets fitted with safety shutters",
      "source_of_truth": "brochure",
      "canonical_spec_id": "socket_protection"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CB20056-2-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CB20056-2-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CB20056-2 (Bridgg Modular Switches) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "Retail-Pricelist-wef-1st-June26.pdf p44",
    "Brochure: Bridgg-Modular-Switches.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/modular-switches/bridgg-switches/"
  ],
  "spec_ids": [
    "box_compatibility",
    "design_characteristics",
    "gst_rate_pct",
    "locking_assembly",
    "market_segments",
    "module_sizing",
    "modules",
    "price_basis",
    "price_inr",
    "range",
    "socket_protection"
  ],
  "extraction": {
    "chunks": 11,
    "decoded": true,
    "missing": [
      "rated_current_a",
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

**content**

```
Category: Final Distribution Products > Modular Switches > Bridgg Modular Switches.
CB20056-2 — Bridgg Modular Switches
Power unit combos

Surface-mounted 4-module combination unit: a white plate carrying a socket, a switch and an MCB, supplied on a PVC or metal box.
CB20056-2 — Bridgg Modular Switches
Power extension boards and door bells

Extension boards (**ACEXB**) are corded 4-socket boards, offered with individual switches, a single master switch, or a master switch plus a thermal protection switch. Door bells (**ACDB**) are surface units with a ding-dong sound, in a textured "Jewell" pattern or a square-grid "Curvy" pattern.

*(HSN is printed as "8581010" in the brochure - reproduced here exactly as printed.)*
```

### Family: `Distribution Boards` · chunk_type: `specs`

- **id**: `1269441`
- **product_id**: `100001`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "7SEG",
      "meaning": "7-segment TPN DB"
    }
  },
  "sku_code": "CSDB7SEGDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "listed",
  "comparable_on": [
    "price_inr"
  ],
  "related_codes": [
    "CSDB7SEGDD06",
    "CSDB7SEGDD08",
    "CSDB7SEGDD12"
  ],
  "canonical_code": "CSDB7SEGDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": [
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "LV",
      "source_pdf": "LV-Pricelist-WEF-1st-June26.pdf",
      "source_page": 136,
      "price_status": "listed",
      "effective_date": "2026-06-01"
    },
    {
      "price": 17550,
      "column": "MRP (`)",
      "context": "CSDBPHSCDD12 | [HSN Code: 8537] | 7 Segment Distribution Board",
      "price_list": "RETAIL",
      "source_pdf": "Retail-Pricelist-wef-1st-June26.pdf",
      "source_page": 22,
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
      "value": 17550.0,
      "source": {
        "pdf": "LV-Pricelist-WEF-1st-June26.pdf",
        "page": 136
      },
      "derived": false,
      "fact_id": "CSDB7SEGDD04-001",
      "canonical": true,
      "value_max": 17550.0,
      "value_min": 17550.0,
      "spec_label": "MRP",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.",
      "value_display": "₹17,550",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    },
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-008",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDB7SEGDD04-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-gst",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "GST",
      "value_kind": "text",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.",
      "value_display": "MRP is inclusive of GST; rate not printed here",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "gst_rate_pct"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDB7SEGDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p136",
    "Retail-Pricelist-wef-1st-June26.pdf p22",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "gst_rate_pct",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 13,
    "decoded": true,
    "missing": [
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": true,
    "has_profile": true,
    "spec_fields": 1
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDB7SEGDD04 — Distribution Boards
CSDB7SEGDD04 (Distribution Boards) has an MRP of ₹17,550 in the LV pricelist effective 2026-06-01.
CSDB7SEGDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.
CSDB7SEGDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.
CSDB7SEGDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.
CSDB7SEGDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.
CSDB7SEGDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.
CSDB7SEGDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.
CSDB7SEGDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.
CSDB7SEGDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.
CSDB7SEGDD04 (Distribution Boards): The published MRP is inclusive of GST.
CSDB7SEGDD04 (Distribution Boards) is used in Commercial, Residential.
```

### Family: `WiNtrip MCB & Isolator` · chunk_type: `standards`

- **id**: `1275686`
- **product_id**: `100623`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:16.548743`
- **lastchange_datetime**: `2026-08-12T15:07:16.548743`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "MCB & Isolators",
    "WiNtrip MCB & Isolator"
  ],
  "depth": 3,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/",
      "name": "MCB & Isolators",
      "level": 2,
      "is_leaf": false,
      "contents": [
        {
          "name": "WiNtrip MCB & Isolator",
          "note": "MCB upto 125A with finger touch proof terminals with a Breaking Capacity of 10kA"
        },
        {
          "name": "WiNtrip2 MCB & Isolator",
          "note": "With breaking Capacity of 10kA and low power consumption"
        },
        {
          "name": "SmartSol Mini MCB",
          "note": "Mini MCB upto 32A with compact & space saving design"
        },
        {
          "name": "WiNtrip – MCB Changeover Switch",
          "note": "Compact design with shrouded terminals and double break contacts"
        },
        {
          "name": "WiNtrip ‘S’ Modular MCB",
          "note": "Compact & space saving design with rapid closing mechanism"
        },
        {
          "name": "WiNtrip2 DC MCB",
          "note": "Dual Connection possibility for both cable and busbar"
        }
      ],
      "has_page": true,
      "markdown": "# MCB & Isolators\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Miniature Circuit Breakers\n\nMiniature circuit breaker is an electromechanical device that is designed to protect an electrical circuit from overload or short circuit, prevent the equipment from damage & potential hazards like fire.\n\nC&S offers various types of MCBs for different household & industrial application as mentioned below.\n\n## Contents\n- [WiNtrip MCB & Isolator](./WiNtrip MCB & Isolator/) — MCB upto 125A with finger touch proof terminals with a Breaking Capacity of 10kA\n- [WiNtrip2 MCB & Isolator](./WiNtrip2 MCB & Isolator/) — With breaking Capacity of 10kA and low power consumption\n- [SmartSol Mini MCB](./SmartSol Mini MCB/) — Mini MCB upto 32A with compact & space saving design\n- [WiNtrip – MCB Changeover Switch](./WiNtrip – MCB Changeover Switch/) — Compact design with shrouded terminals and double break contacts\n- [WiNtrip ‘S’ Modular MCB](./WiNtrip ‘S’ Modular MCB/) — Compact & space saving design with rapid closing mechanism\n- [WiNtrip2 DC MCB](./WiNtrip2 DC MCB/) — Dual Connection possibility for both cable and busbar",
      "page_type": "_category.md",
      "description": "Miniature circuit breaker is an electromechanical device that is designed to protect an electrical circuit from overload or short circuit, prevent the equipment from damage & potential hazards like fire.\nC&S offers various types of MCBs for different household & industrial application as mentioned below.",
      "source_file": "Final Distribution Products/MCB & Isolators/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/",
      "name": "WiNtrip MCB & Isolator",
      "level": 3,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# WiNtrip MCB & Isolator\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Miniature Circuit Breakers > WiNtrip MCB & Isolator\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/Wintrip-MCB-2.jpg (saved as `Wintrip-MCB-2.jpg`)\n\n## Presentation\nAs power distribution needs play a pivotal role in all the significant sectors namely Commercial, Industrial and Residential, improved Breaker performance through better electrical safety, higher operational endurance, continued service and reduced cost have become of paramount importance. C&S MCBs have been engineered to constantly fulfill the above requirements. With these features C&S is setting new standards for user friendly and superlative electrical circuit protection.\nThe C&S MCB is a high performing Thermal Magnetic current limiting device with the ability to disconnect short circuits up to 10kA. The range is available in tripping characteristics types B, C and D for 1P, 1P+N, 2P, 3P, 3P+N & 4P configurations in 0.5 – 125A current ratings. All metal components for operating mechanism of WiNtrip circuit breaker are specially treated for high self lubrication leading to repeat accuracy during service life. The MCBs conform to Standards: IEC 60898-1995 and IS/IEC 60898-1:2002 and stand guaranteed for best quality for optimum performance.\n\n## Benefits\nElectrical safety\nHigher operational endurance\nDurable and reduced cost\nPlays a pivotal role in all the significant sectors namely Commercial, Industrial and Residential areas\nEnsures circuit identification and enhanced safety\nClear indication of the operational status of device\n\n## Brochure\n- [MCB_.pdf](./MCB_.pdf) (source: https://cselectric.co.in/wp-content/uploads/2025/03/MCB_.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/MCB & Isolators/WiNtrip MCB & Isolator/product.md"
    }
  ],
  "headings": [
    "Standards and certification"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": null,
  "family": "WiNtrip MCB & Isolator",
  "decoded": null,
  "sku_code": "CSBHIC100N",
  "attributes": null,
  "peer_group": "WiNtrip MCB & Isolator | brochure-only",
  "description": "Double Pole (1, 3 / 2, 4) | 100 | CSBHIC100N",
  "alias_reason": null,
  "price_status": "not_in_pricelist",
  "comparable_on": [
    "rated_insulation_voltage_ui_v",
    "rated_voltage_v"
  ],
  "related_codes": [
    "CSBHIC125N",
    "CSBHIC80N",
    "CSMB2SDC0.5",
    "CSMB2SDC1",
    "CSMB2SDC10",
    "CSMB2SDC16",
    "CSMB2SDC2",
    "CSMB2SDC20",
    "CSMB2SDC25",
    "CSMB2SDC3",
    "CSMB2SDC32",
    "CSMB2SDC4",
    "CSMB2SDC40",
    "CSMB2SDC5",
    "CSMB2SDC50",
    "CSMB2SDC6",
    "CSMB2SDC63",
    "CSMB3ISO100",
    "CSMB3ISO125",
    "CSMB3ISO25",
    "CSMB3ISO40",
    "CSMB3ISO63",
    "CSMB3ISO80",
    "CSMBL1B10",
    "CSMBL1B10N",
    "CSMBL1B16",
    "CSMBL1B16N",
    "CSMBL1B20",
    "CSMBL1B20N",
    "CSMBL1B25",
    "CSMBL1B25N",
    "CSMBL1B32",
    "CSMBL1B32N",
    "CSMBL1B40",
    "CSMBL1B40N",
    "CSMBL1B6",
    "CSMBL1B6N",
    "CSMBL1C0.5",
    "CSMBL1C0.5N",
    "CSMBL1C1",
    "CSMBL1C1N",
    "CSMBL1C2",
    "CSMBL1C2N",
    "CSMBL1C3",
    "CSMBL1C3N",
    "CSMBL1C4",
    "CSMBL1C4N",
    "CSMBL1C5",
    "CSMBL1C5N",
    "CSMBL2B10",
    "CSMBL2B16",
    "CSMBL2B20",
    "CSMBL2B25",
    "CSMBL2B32",
    "CSMBL2B40",
    "CSMBL2B6",
    "CSMBL2C0.5",
    "CSMBL2C1",
    "CSMBL2C2",
    "CSMBL2C3"
  ],
  "canonical_code": "CSBHIC100N",
  "market_segments": null,
  "also_published_as": null,
  "price_observations": []
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "",
      "value": "IP 20",
      "source": null,
      "derived": false,
      "fact_id": "CSBHIC100N-001",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Degree of protection (IP)",
      "value_kind": "text",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a degree of protection (ip) of IP 20.",
      "value_display": "IP 20",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "ip_rating"
    },
    {
      "unit": "V",
      "value": 660.0,
      "source": null,
      "derived": false,
      "fact_id": "CSBHIC100N-002",
      "canonical": true,
      "value_max": 660.0,
      "value_min": 660.0,
      "spec_label": "Rated insulation voltage (Ui)",
      "value_kind": "scalar",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a rated insulation voltage (ui) of 660 V.",
      "value_display": "660 V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_insulation_voltage_ui_v"
    },
    {
      "unit": "V",
      "value": [
        240.0,
        415.0
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSBHIC100N-003",
      "canonical": true,
      "value_max": 415.0,
      "value_min": 240.0,
      "spec_label": "Rated operational voltage (Ue)",
      "value_kind": "set",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a rated operational voltage (ue) of 240/415 V.",
      "value_display": "240/415 V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_voltage_v"
    },
    {
      "unit": "°C",
      "value": 30.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-004",
      "canonical": false,
      "value_max": 30.0,
      "value_min": 30.0,
      "spec_label": "Ambient reference temperature",
      "value_kind": "scalar",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a ambient reference temperature of 30 °C.",
      "value_display": "30 °C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ambient_reference_temperature"
    },
    {
      "unit": "°C",
      "value": null,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-005",
      "canonical": false,
      "value_max": 70.0,
      "value_min": -25.0,
      "spec_label": "Ambient working temperature",
      "value_kind": "range",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a ambient working temperature of -25 °C to +70 °C.",
      "value_display": "-25 °C to +70 °C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ambient_working_temperature"
    },
    {
      "unit": "",
      "value": "Vertical / Horizontal",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Installation position",
      "value_kind": "text",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a installation position of Vertical / Horizontal.",
      "value_display": "Vertical / Horizontal",
      "source_of_truth": "brochure",
      "canonical_spec_id": "installation_position"
    },
    {
      "unit": "mm",
      "value": [
        17.8,
        35.6,
        53.4,
        71.2
      ],
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-007",
      "canonical": false,
      "value_max": 71.2,
      "value_min": 17.8,
      "spec_label": "Module width",
      "value_kind": "set",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a module width of SP 17.8 mm, DP 35.6 mm, TP 53.4 mm, FP 71.2 mm.",
      "value_display": "SP 17.8 mm, DP 35.6 mm, TP 53.4 mm, FP 71.2 mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "module_width"
    },
    {
      "unit": "mm",
      "value": 35.5,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-008",
      "canonical": false,
      "value_max": 35.5,
      "value_min": 35.5,
      "spec_label": "Mounting",
      "value_kind": "scalar",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a mounting of DIN rail, size 35.5 mm.",
      "value_display": "DIN rail, size 35.5 mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": [
        1.0,
        1.0,
        2.0,
        3.0,
        3.0,
        4.0,
        2.0,
        3.0,
        4.0
      ],
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-009",
      "canonical": false,
      "value_max": 4.0,
      "value_min": 1.0,
      "spec_label": "Pole executions offered",
      "value_kind": "set",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a pole executions offered of MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P.",
      "value_display": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pole_executions_offered"
    },
    {
      "unit": "mm",
      "value": 40.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-010",
      "canonical": false,
      "value_max": 40.0,
      "value_min": 40.0,
      "spec_label": "Resistance to shock",
      "value_kind": "scalar",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a resistance to shock of 40 mm free fall.",
      "value_display": "40 mm free fall",
      "source_of_truth": "brochure",
      "canonical_spec_id": "resistance_to_shock"
    },
    {
      "unit": "",
      "value": "Combination head captive screws (+/– screwdriver)",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSBHIC100N-011",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Terminal screws",
      "value_kind": "text",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has a terminal screws of Combination head captive screws (+/– screwdriver).",
      "value_display": "Combination head captive screws (+/– screwdriver)",
      "source_of_truth": "brochure",
      "canonical_spec_id": "terminal_screws"
    },
    {
      "unit": "INR",
      "value": "NOT_IN_PRICELIST",
      "source": null,
      "derived": false,
      "fact_id": "CSBHIC100N-price",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "MRP",
      "value_kind": "text",
      "fact_sentence": "CSBHIC100N (WiNtrip MCB & Isolator) has price status not_in_pricelist.",
      "value_display": "NOT_IN_PRICELIST",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "derived": null,
  "sources": [
    "Brochure: MCB_.md"
  ],
  "spec_ids": [
    "ambient_reference_temperature",
    "ambient_working_temperature",
    "installation_position",
    "ip_rating",
    "module_width",
    "mounting",
    "pole_executions_offered",
    "price_inr",
    "rated_insulation_voltage_ui_v",
    "rated_voltage_v",
    "resistance_to_shock",
    "terminal_screws"
  ],
  "extraction": {
    "chunks": 5,
    "source": "brochure_only",
    "decoded": false,
    "has_price": false,
    "confidence": "medium",
    "has_profile": true,
    "spec_fields": 3
  }
}
```

**content**

```
Category: Final Distribution Products > MCB & Isolators > WiNtrip MCB & Isolator.
CSBHIC100N — WiNtrip MCB & Isolator
Standards and certification
| Item | Detail |
| --- | --- |
| Manufacturing site management systems | Intertek ISO 9001:2015, ISO 14001:2015, ISO 45001:2018 — Haridwar, Uttarakhand (MCB & RCCB manufacture) |
```

### Family: `Distribution Boards` · chunk_type: `technical`

- **id**: `1269527`
- **product_id**: `100009`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:12.056494`
- **lastchange_datetime**: `2026-08-12T15:07:12.056494`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "Distribution Boards"
  ],
  "depth": 2,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
      "name": "Distribution Boards",
      "level": 2,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# Distribution Boards\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > WiNtrip Distribution Boards\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/DB.jpg (saved as `DB.jpg`)\n\n## Range\n- SPN/TPN distribution board horizontal – single & double door\n- WiNclass SPN/TPN distribution board horizontal-single & double door\n- VTPN distribution board with MCB & MCCB as incomer\n- PPI distribution board/TPN phase selector DB\n- 7 Segment distribution board / flexy (tier) DB\n- Polycarbonate cover consumer unit DB / acrylic SPN DB\n- Telephone & TV socket SPN/TPN distribution board/plug & socket distribution board – metal clad & plastic\n- Metal & plastic enclosures/cable end box distribution board\n- Acrylic TPN distribution board/pre-wired distribution board\n- Vertical/horizontal TPN transparent DB with acrylic cover\n\n## Features\n- Fully equipped DBs supplied with busbar, earth links, neutral links and inter connecting links.\n- Insulated/captive busbar and neutral links, for safety and protection\n- Unique feature of PAN assembly with adequate wiring space.\n- Knock outs on all sides\n- Double door DB with IP42 /IP43\n\n## Presentation\nThe Board design is specially engineered for meeting the requirements of all the segments namely industrial, commercial and residential. For effective and safe power distribution/sub distribution, insulated neutral links, insulated copper bus bar, earth bar and inter connecting links with lugs are part of the unit. These Boards are equipped with top and bottom removable gland plates with adequate number of knock outs, which enable easy installation and connection of conduits of all sizes. Double door construction of Distribution Boards enables easy removal and reversal of the door by just unhinging two springs. These boards are a comprehensive system in itself. The Boards are backed by the technological expertise of C&S which excels globally in all low voltage products.\nThe boards are of universal type, which means they can be both flush or wall mounted based on the requirement. These Distribution Boards undergo a seven tank phosphating process to ensure an anti rust conditioning, superior finish and long lasting strength. 60 micron premium quality powder coating is applied for extra smooth finish. In addition to complying with all necessary minute technical parameters, C&S WiNtrip Distribution Boards are highly user friendly and aesthetically par excellence. Double Door DBs meet all the requirements of IP 42/43.\n\n## Benefits\nFully equipped DBs supplied with Busbar, Earth Links, Neutral Links and inter connecting links\nAll doors and frames are deep drawn for better aesthetics and long life with no welding joints\nFor enhancing the conduit flexibility detachable gland plates at top and bottom with knock outs on the two sides\nTwo finger holes to lift the plate have been duly plugged for making the board dust free and safe\n\n## Brochure\n- [Final-Distribution-Products.pdf](./Final-Distribution-Products.pdf) (source: https://cselectric.co.in/wp-content/uploads/2016/05/Final-Distribution-Products.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/Distribution Boards/product.md"
    }
  ],
  "headings": [
    "Cable End Boxes (SPN, TPNH, TPNV)"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/",
  "family": "Distribution Boards",
  "decoded": {
    "door": {
      "code": "DD",
      "meaning": "double door"
    },
    "ways": {
      "code": "04",
      "value": 4,
      "meaning": 4
    },
    "config": {
      "code": "SPN",
      "meaning": "SPN (single phase + neutral)"
    },
    "variant": {
      "code": "P",
      "meaning": "EPiC-F range"
    },
    "cable_end_box": {
      "code": "CB",
      "meaning": "cable end box only (no DB)"
    }
  },
  "sku_code": "CSDBCBSPNPDD04",
  "attributes": null,
  "peer_group": "Distribution Boards",
  "description": null,
  "alias_reason": null,
  "price_status": "not_listed",
  "comparable_on": [],
  "related_codes": [
    "CSDBCBTPNVPPIWXDD06",
    "CSDBCBTPNVPPIWXDD08",
    "CSDBCBTPNVPPIWXDD12",
    "CSDBCBSPNPDD06",
    "CSDBCBSPNPDD08",
    "CSDBCBSPNPDD12",
    "CSDBCBSPNPDD16",
    "CSDBCBTPNHPDD04",
    "CSDBCBTPNHPDD06",
    "CSDBCBTPNHPDD08",
    "CSDBCBTPNHPDD12",
    "CSDBPPPIKT01",
    "CSDBPPPIKT02",
    "CSDBPPPIKT03",
    "CSDBPPPIKT04"
  ],
  "canonical_code": "CSDBCBSPNPDD04",
  "market_segments": [
    "Commercial",
    "Residential"
  ],
  "also_published_as": null,
  "price_observations": []
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "",
      "value": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-001",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Cable entry",
      "value_kind": "text",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has a cable entry of Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides.",
      "value_display": "Detachable gland plates at top and bottom, with Ø25 and Ø32 knock-outs on top, bottom and sides",
      "source_of_truth": "brochure",
      "canonical_spec_id": "cable_entry"
    },
    {
      "unit": "",
      "value": "All dimensions given in mm",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-002",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dimensions",
      "value_kind": "text",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has a dimensions of All dimensions given in mm.",
      "value_display": "All dimensions given in mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "dimensions"
    },
    {
      "unit": "",
      "value": "Dedicated earthing provision against stray charges / leakage current",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-003",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Earthing",
      "value_kind": "text",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has a earthing of Dedicated earthing provision against stray charges / leakage current.",
      "value_display": "Dedicated earthing provision against stray charges / leakage current",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earthing"
    },
    {
      "unit": "",
      "value": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-004",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Enclosure construction",
      "value_kind": "text",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has a enclosure construction of Deep drawn sheet steel; doors and frames deep drawn with no welding joints.",
      "value_display": "Deep drawn sheet steel; doors and frames deep drawn with no welding joints",
      "source_of_truth": "brochure",
      "canonical_spec_id": "enclosure_construction"
    },
    {
      "unit": "",
      "value": "Steel nut inserts with deep screw for a firm hold on the door",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Fixings",
      "value_kind": "text",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has a fixings of Steel nut inserts with deep screw for a firm hold on the door.",
      "value_display": "Steel nut inserts with deep screw for a firm hold on the door",
      "source_of_truth": "brochure",
      "canonical_spec_id": "fixings"
    },
    {
      "unit": "",
      "value": "Universal type — suitable for both flush and wall mounting",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting",
      "value_kind": "text",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has a mounting of Universal type — suitable for both flush and wall mounting.",
      "value_display": "Universal type — suitable for both flush and wall mounting",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": 60.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-007",
      "canonical": false,
      "value_max": 60.0,
      "value_min": 60.0,
      "spec_label": "Paint finish",
      "value_kind": "scalar",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has a paint finish of 60 micron premium quality powder coating.",
      "value_display": "60 micron premium quality powder coating",
      "source_of_truth": "brochure",
      "canonical_spec_id": "paint_finish"
    },
    {
      "unit": "",
      "value": "Seven tank phosphating process for anti-rust conditioning",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-008",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surface treatment",
      "value_kind": "text",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has a surface treatment of Seven tank phosphating process for anti-rust conditioning.",
      "value_display": "Seven tank phosphating process for anti-rust conditioning",
      "source_of_truth": "brochure",
      "canonical_spec_id": "surface_treatment"
    },
    {
      "unit": "",
      "value": [
        "Commercial",
        "Residential"
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) is used in Commercial, Residential.",
      "value_display": "Commercial, Residential",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    },
    {
      "unit": "INR",
      "value": "NOT_LISTED",
      "source": null,
      "derived": false,
      "fact_id": "CSDBCBSPNPDD04-price",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "MRP",
      "value_kind": "text",
      "fact_sentence": "CSDBCBSPNPDD04 (Distribution Boards) has no published price in either 2026 pricelist.",
      "value_display": "NOT_LISTED",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p137",
    "Retail-Pricelist-wef-1st-June26.pdf p23",
    "Brochure: Final-Distribution-Products.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/final-distribution-products/distribution-boards/"
  ],
  "spec_ids": [
    "cable_entry",
    "dimensions",
    "earthing",
    "enclosure_construction",
    "fixings",
    "market_segments",
    "mounting",
    "paint_finish",
    "price_inr",
    "surface_treatment"
  ],
  "extraction": {
    "chunks": 14,
    "decoded": true,
    "missing": [
      "price_inr",
      "rated_current_a",
      "poles",
      "standards",
      "ip_rating",
      "mechanical_endurance_ops"
    ],
    "has_price": false,
    "has_profile": true,
    "spec_fields": 0
  }
}
```

**content**

```
Category: Final Distribution Products > Distribution Boards.
CSDBCBSPNPDD04 — Distribution Boards
Cable End Boxes (SPN, TPNH, TPNV)
Cable end boxes are shallow sheet-metal boxes matched to the corresponding distribution board size, mounted to give extra cable termination space. Common drawing callouts: 112.5 high, 98.0 (SPN/TPNV) or 96.0 (TPNH) wide, 4.0, 105.0; mounting hole detail R3.1, 16.0, Ø24.0/Ø25, Ø32.0, Ø10.3.

**TPNH Cable End Box**


**TPNV Cable End Box** (codes CSDBCBTPNVDD04 / 08 / 12)


**SPN Cable End Box**


All dimensions are in mm.
```

### Family: `WiNtrip MCB & Isolator` · chunk_type: `technical_data`

- **id**: `1275808`
- **product_id**: `100516`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:16.548743`
- **lastchange_datetime**: `2026-08-12T15:07:16.548743`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Final Distribution Products",
    "MCB & Isolators",
    "WiNtrip MCB & Isolator"
  ],
  "depth": 3,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/",
      "name": "Final Distribution Products",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Modular Switches",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "MCB & Isolators",
          "note": "100% isolated switching chambers"
        },
        {
          "name": "Residual Current Circuit Breaker",
          "note": "High short-circuit current withstand capacity 6kA"
        },
        {
          "name": "Distribution Boards",
          "note": "Unique feature of PAN assembly with adequate wiring space"
        }
      ],
      "has_page": true,
      "markdown": "# Final Distribution Products\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products\n\nFinal distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.\n\n## Contents\n- [Modular Switches](./Modular Switches/) — 100% isolated switching chambers\n- [MCB & Isolators](./MCB & Isolators/) — 100% isolated switching chambers\n- [Residual Current Circuit Breaker](./Residual Current Circuit Breaker/) — High short-circuit current withstand capacity 6kA\n- [Distribution Boards](./Distribution Boards/) — Unique feature of PAN assembly with adequate wiring space",
      "page_type": "_category.md",
      "description": "Final distribution products are the electrical equipments that are used to supply power from the main supply to individual circuit in industry or residential places. Products like MCCB ,RCCB, RCBO, ELCB, modular switches, are used to distribute the power supply throughout the home to feed lights, sockets, and other users. C&S design & manufacture these products that provide reliable & safe power and circuit protection.",
      "source_file": "Final Distribution Products/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/",
      "name": "MCB & Isolators",
      "level": 2,
      "is_leaf": false,
      "contents": [
        {
          "name": "WiNtrip MCB & Isolator",
          "note": "MCB upto 125A with finger touch proof terminals with a Breaking Capacity of 10kA"
        },
        {
          "name": "WiNtrip2 MCB & Isolator",
          "note": "With breaking Capacity of 10kA and low power consumption"
        },
        {
          "name": "SmartSol Mini MCB",
          "note": "Mini MCB upto 32A with compact & space saving design"
        },
        {
          "name": "WiNtrip – MCB Changeover Switch",
          "note": "Compact design with shrouded terminals and double break contacts"
        },
        {
          "name": "WiNtrip ‘S’ Modular MCB",
          "note": "Compact & space saving design with rapid closing mechanism"
        },
        {
          "name": "WiNtrip2 DC MCB",
          "note": "Dual Connection possibility for both cable and busbar"
        }
      ],
      "has_page": true,
      "markdown": "# MCB & Isolators\n\n**Page:** https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Miniature Circuit Breakers\n\nMiniature circuit breaker is an electromechanical device that is designed to protect an electrical circuit from overload or short circuit, prevent the equipment from damage & potential hazards like fire.\n\nC&S offers various types of MCBs for different household & industrial application as mentioned below.\n\n## Contents\n- [WiNtrip MCB & Isolator](./WiNtrip MCB & Isolator/) — MCB upto 125A with finger touch proof terminals with a Breaking Capacity of 10kA\n- [WiNtrip2 MCB & Isolator](./WiNtrip2 MCB & Isolator/) — With breaking Capacity of 10kA and low power consumption\n- [SmartSol Mini MCB](./SmartSol Mini MCB/) — Mini MCB upto 32A with compact & space saving design\n- [WiNtrip – MCB Changeover Switch](./WiNtrip – MCB Changeover Switch/) — Compact design with shrouded terminals and double break contacts\n- [WiNtrip ‘S’ Modular MCB](./WiNtrip ‘S’ Modular MCB/) — Compact & space saving design with rapid closing mechanism\n- [WiNtrip2 DC MCB](./WiNtrip2 DC MCB/) — Dual Connection possibility for both cable and busbar",
      "page_type": "_category.md",
      "description": "Miniature circuit breaker is an electromechanical device that is designed to protect an electrical circuit from overload or short circuit, prevent the equipment from damage & potential hazards like fire.\nC&S offers various types of MCBs for different household & industrial application as mentioned below.",
      "source_file": "Final Distribution Products/MCB & Isolators/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/",
      "name": "WiNtrip MCB & Isolator",
      "level": 3,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# WiNtrip MCB & Isolator\n\n**Product page:** https://cselectric.co.in/products-solutions/final-distribution-products/miniature-circuit-breakers/miniature-circuit-breakermcb/\n**Breadcrumb:** Home > Products & Solutions > Final distribution products > Miniature Circuit Breakers > WiNtrip MCB & Isolator\n**Image:** https://cselectric.co.in/wp-content/uploads/2016/03/Wintrip-MCB-2.jpg (saved as `Wintrip-MCB-2.jpg`)\n\n## Presentation\nAs power distribution needs play a pivotal role in all the significant sectors namely Commercial, Industrial and Residential, improved Breaker performance through better electrical safety, higher operational endurance, continued service and reduced cost have become of paramount importance. C&S MCBs have been engineered to constantly fulfill the above requirements. With these features C&S is setting new standards for user friendly and superlative electrical circuit protection.\nThe C&S MCB is a high performing Thermal Magnetic current limiting device with the ability to disconnect short circuits up to 10kA. The range is available in tripping characteristics types B, C and D for 1P, 1P+N, 2P, 3P, 3P+N & 4P configurations in 0.5 – 125A current ratings. All metal components for operating mechanism of WiNtrip circuit breaker are specially treated for high self lubrication leading to repeat accuracy during service life. The MCBs conform to Standards: IEC 60898-1995 and IS/IEC 60898-1:2002 and stand guaranteed for best quality for optimum performance.\n\n## Benefits\nElectrical safety\nHigher operational endurance\nDurable and reduced cost\nPlays a pivotal role in all the significant sectors namely Commercial, Industrial and Residential areas\nEnsures circuit identification and enhanced safety\nClear indication of the operational status of device\n\n## Brochure\n- [MCB_.pdf](./MCB_.pdf) (source: https://cselectric.co.in/wp-content/uploads/2025/03/MCB_.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Final Distribution Products/MCB & Isolators/WiNtrip MCB & Isolator/product.md"
    }
  ],
  "headings": [
    "Isolator — technical data"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": null,
  "family": "WiNtrip MCB & Isolator",
  "decoded": null,
  "sku_code": "CSMB3ISO100",
  "attributes": null,
  "peer_group": "WiNtrip MCB & Isolator | brochure-only",
  "description": "| Three Pole | 100 | CSMB3ISO100 |",
  "alias_reason": null,
  "price_status": "not_in_pricelist",
  "comparable_on": [
    "electrical_endurance_ops",
    "mechanical_endurance_ops",
    "rated_frequency_hz",
    "rated_impulse_voltage_uimp_kv",
    "rated_insulation_voltage_ui_v",
    "rated_voltage_v"
  ],
  "related_codes": [
    "CSMB3ISO125",
    "CSMB3ISO25",
    "CSMB3ISO40",
    "CSMB3ISO63",
    "CSMB3ISO80"
  ],
  "canonical_code": "CSMB3ISO100",
  "market_segments": null,
  "also_published_as": null,
  "price_observations": []
}
```

**details**

```json
{
  "facts": [
    {
      "unit": "operations",
      "value": 10000.0,
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-001",
      "canonical": true,
      "value_max": 10000.0,
      "value_min": 10000.0,
      "spec_label": "Electrical endurance / lifecycle",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a electrical endurance / lifecycle of 10,000.",
      "value_display": "10,000",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "electrical_endurance_ops"
    },
    {
      "unit": "",
      "value": "IP 20",
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-002",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Degree of protection (IP)",
      "value_kind": "text",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a degree of protection (ip) of IP 20.",
      "value_display": "IP 20",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "ip_rating"
    },
    {
      "unit": "kA",
      "value": "500A for 25A & 2200A for 125A",
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-003",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Rated making capacity (Icm)",
      "value_kind": "composite",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a rated making capacity (icm) of 500A for 25A & 2200A for 125A.",
      "value_display": "500A for 25A & 2200A for 125A",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "making_capacity_icm_ka"
    },
    {
      "unit": "operations",
      "value": 10000.0,
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-004",
      "canonical": true,
      "value_max": 10000.0,
      "value_min": 10000.0,
      "spec_label": "Mechanical endurance / lifecycle",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a mechanical endurance / lifecycle of 10,000.",
      "value_display": "10,000",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "mechanical_endurance_ops"
    },
    {
      "unit": "degC",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-005",
      "canonical": true,
      "value_max": 70.0,
      "value_min": -25.0,
      "spec_label": "Operating temperature maximum",
      "value_kind": "range",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a operating temperature maximum of -25°C to +70°C.",
      "value_display": "-25°C to +70°C",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "operating_temp_max_c"
    },
    {
      "unit": "A",
      "value": null,
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-006",
      "canonical": true,
      "value_max": 125.0,
      "value_min": 25.0,
      "spec_label": "Rated current (In)",
      "value_kind": "range",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a rated current (in) of 25-125A.",
      "value_display": "25-125A",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_current_a"
    },
    {
      "unit": "Hz",
      "value": 50.0,
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-007",
      "canonical": true,
      "value_max": 50.0,
      "value_min": 50.0,
      "spec_label": "Rated frequency",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a rated frequency of 50Hz.",
      "value_display": "50Hz",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_frequency_hz"
    },
    {
      "unit": "kV",
      "value": 6.0,
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-008",
      "canonical": true,
      "value_max": 6.0,
      "value_min": 6.0,
      "spec_label": "Rated impulse withstand voltage (Uimp)",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a rated impulse withstand voltage (uimp) of 6kV.",
      "value_display": "6kV",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_impulse_voltage_uimp_kv"
    },
    {
      "unit": "V",
      "value": 660.0,
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-009",
      "canonical": true,
      "value_max": 660.0,
      "value_min": 660.0,
      "spec_label": "Rated insulation voltage (Ui)",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a rated insulation voltage (ui) of 660V.",
      "value_display": "660V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_insulation_voltage_ui_v"
    },
    {
      "unit": "V",
      "value": [
        240.0,
        415.0
      ],
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-010",
      "canonical": true,
      "value_max": 415.0,
      "value_min": 240.0,
      "spec_label": "Rated operational voltage (Ue)",
      "value_kind": "set",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a rated operational voltage (ue) of 240/415V.",
      "value_display": "240/415V",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "rated_voltage_v"
    },
    {
      "unit": "kA",
      "value": "300A for 25A, 1500A for 125A; withstand duration 1 sec",
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-011",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Rated short-time withstand current (Icw, 1s)",
      "value_kind": "composite",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a rated short-time withstand current (icw, 1s) of 300A for 25A, 1500A for 125A; withstand duration 1 sec.",
      "value_display": "300A for 25A, 1500A for 125A; withstand duration 1 sec",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "short_time_withstand_icw_ka"
    },
    {
      "unit": "",
      "value": "AC22A",
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-012",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Utilisation category",
      "value_kind": "text",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a utilisation category of AC22A.",
      "value_display": "AC22A",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "utilisation_category"
    },
    {
      "unit": "°C",
      "value": 30.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-013",
      "canonical": false,
      "value_max": 30.0,
      "value_min": 30.0,
      "spec_label": "Ambient reference temperature",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a ambient reference temperature of 30 °C.",
      "value_display": "30 °C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ambient_reference_temperature"
    },
    {
      "unit": "°C",
      "value": null,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-014",
      "canonical": false,
      "value_max": 70.0,
      "value_min": -25.0,
      "spec_label": "Ambient working temperature",
      "value_kind": "range",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a ambient working temperature of -25 °C to +70 °C.",
      "value_display": "-25 °C to +70 °C",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ambient_working_temperature"
    },
    {
      "unit": "",
      "value": "Three Pole",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-015",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "description",
      "value_kind": "text",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a description of Three Pole.",
      "value_display": "Three Pole",
      "source_of_truth": "brochure",
      "canonical_spec_id": "description"
    },
    {
      "unit": "",
      "value": "Vertical / Horizontal",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-016",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Installation position",
      "value_kind": "text",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a installation position of Vertical / Horizontal.",
      "value_display": "Vertical / Horizontal",
      "source_of_truth": "brochure",
      "canonical_spec_id": "installation_position"
    },
    {
      "unit": "mm",
      "value": [
        17.8,
        35.6,
        53.4,
        71.2
      ],
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-017",
      "canonical": false,
      "value_max": 71.2,
      "value_min": 17.8,
      "spec_label": "Module width",
      "value_kind": "set",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a module width of SP 17.8 mm, DP 35.6 mm, TP 53.4 mm, FP 71.2 mm.",
      "value_display": "SP 17.8 mm, DP 35.6 mm, TP 53.4 mm, FP 71.2 mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "module_width"
    },
    {
      "unit": "mm",
      "value": 35.5,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-018",
      "canonical": false,
      "value_max": 35.5,
      "value_min": 35.5,
      "spec_label": "Mounting",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a mounting of DIN rail, size 35.5 mm.",
      "value_display": "DIN rail, size 35.5 mm",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting"
    },
    {
      "unit": "",
      "value": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-019",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Pole executions offered",
      "value_kind": "composite",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a pole executions offered of MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P.",
      "value_display": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P; Isolator: 1P, 2P, 3P & 4P",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pole_executions_offered"
    },
    {
      "unit": "",
      "value": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-020",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Pole executions offered (MCB: 1P, 1P+N, 2P, 3P, 3P+N)",
      "value_kind": "text",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a pole executions offered (mcb: 1p, 1p+n, 2p, 3p, 3p+n) of MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P.",
      "value_display": "MCB: 1P, 1P+N, 2P, 3P, 3P+N & 4P",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pole_executions_offered_1"
    },
    {
      "unit": "",
      "value": [
        1.0,
        2.0,
        3.0,
        4.0
      ],
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-021",
      "canonical": false,
      "value_max": 4.0,
      "value_min": 1.0,
      "spec_label": "Pole executions offered (Isolator: 1P, 2P, 3P & 4P)",
      "value_kind": "set",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a pole executions offered (isolator: 1p, 2p, 3p & 4p) of Isolator: 1P, 2P, 3P & 4P.",
      "value_display": "Isolator: 1P, 2P, 3P & 4P",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pole_executions_offered_2"
    },
    {
      "unit": "",
      "value": 3.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-022",
      "canonical": false,
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "poles",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a poles of 3.",
      "value_display": "3",
      "source_of_truth": "brochure",
      "canonical_spec_id": "poles"
    },
    {
      "unit": "mm",
      "value": 40.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-023",
      "canonical": false,
      "value_max": 40.0,
      "value_min": 40.0,
      "spec_label": "Resistance to shock",
      "value_kind": "scalar",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a resistance to shock of 40 mm free fall.",
      "value_display": "40 mm free fall",
      "source_of_truth": "brochure",
      "canonical_spec_id": "resistance_to_shock"
    },
    {
      "unit": "",
      "value": "Combination head captive screws (+/– screwdriver)",
      "source": "brochure",
      "derived": false,
      "fact_id": "CSMB3ISO100-024",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Terminal screws",
      "value_kind": "text",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has a terminal screws of Combination head captive screws (+/– screwdriver).",
      "value_display": "Combination head captive screws (+/– screwdriver)",
      "source_of_truth": "brochure",
      "canonical_spec_id": "terminal_screws"
    },
    {
      "unit": "INR",
      "value": "NOT_IN_PRICELIST",
      "source": null,
      "derived": false,
      "fact_id": "CSMB3ISO100-price",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "MRP",
      "value_kind": "text",
      "fact_sentence": "CSMB3ISO100 (WiNtrip MCB & Isolator) has price status not_in_pricelist.",
      "value_display": "NOT_IN_PRICELIST",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "derived": null,
  "sources": [
    "Brochure: MCB_.md"
  ],
  "spec_ids": [
    "ambient_reference_temperature",
    "ambient_working_temperature",
    "description",
    "electrical_endurance_ops",
    "installation_position",
    "ip_rating",
    "making_capacity_icm_ka",
    "mechanical_endurance_ops",
    "module_width",
    "mounting",
    "operating_temp_max_c",
    "pole_executions_offered",
    "pole_executions_offered_1",
    "pole_executions_offered_2",
    "poles",
    "price_inr",
    "rated_current_a",
    "rated_frequency_hz",
    "rated_impulse_voltage_uimp_kv",
    "rated_insulation_voltage_ui_v",
    "rated_voltage_v",
    "resistance_to_shock",
    "short_time_withstand_icw_ka",
    "terminal_screws",
    "utilisation_category"
  ],
  "extraction": {
    "chunks": 8,
    "source": "brochure_only",
    "decoded": false,
    "has_price": false,
    "confidence": "medium",
    "has_profile": true,
    "spec_fields": 12
  }
}
```

**content**

```
Category: Final Distribution Products > MCB & Isolators > WiNtrip MCB & Isolator.
CSMB3ISO100 — WiNtrip MCB & Isolator
Isolator — technical data
| WiNtrip Isolator | Value |
| --- | --- |
| Standard Conformity | IS/IEC60947-3 |
| Rated Current (In) | 25-125A |
| Rated Voltage AC (Ue) | 240/415V |
| Utilization Category | AC22A |
| Rated Frequency Hz | 50Hz |
| No. of Poles (Execution) | 1P, 2P, 3P & 4P |
| Rated Insulation Voltage (Ui) | 660V |
| Rated Impulse Voltage (Uimp) | 6kV |
| Electrical/Mechanical Life | 10,000 / 10,000 |
| Ambient Temperature | -25°C to +70°C |
| Energy Limiting Class | N/A |
| Line Terminal Capacity | 50mm² |
| Degree of Protection | IP 20 |
| Resistance to Shock | 40mm free fall |
| Ambient reference temperature | 30°C |
| Installation Position | Vertical/Horizontal |
| Rated Short time withstand Current Icw | 300A for 25A, 1500A for 125A; withstand duration 1 sec |
| Rated Short Circuit Making Capacity (Icm) | 500A for 25A & 2200A for 125A |
```

### Family: `ACB – AH-AHA` · chunk_type: `variants`

- **id**: `1287455`
- **product_id**: `102003`
- **is_active**: `True`
- **create_datetime**: `2026-08-12T15:07:29.215088`
- **lastchange_datetime**: `2026-08-12T15:07:29.215088`
- **has_embedding**: `False`

**taxonomy**

```json
{
  "path": [
    "Low Voltage Products and Solutions",
    "Circuit Breakers",
    "Air Circuit Breakers",
    "ACB – AH-AHA"
  ],
  "depth": 4,
  "levels": [
    {
      "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/",
      "name": "Low Voltage Products and Solutions",
      "level": 1,
      "is_leaf": false,
      "contents": [
        {
          "name": "Circuit Breakers",
          "note": "Modular construction with most compact dimensions"
        },
        {
          "name": "Switches",
          "note": "Modular pole design with compact construction"
        },
        {
          "name": "Fuses & Fuse Bases",
          "note": "Ideally suitable for back up protection to motor starters"
        },
        {
          "name": "Control & Signalling Devices",
          "note": "Illuminated & non- illuminated actuators in metal & polycarbonate"
        },
        {
          "name": "Industrial Plugs and Sockets",
          "note": "Secure & reliable with high grade thermoplastic material"
        },
        {
          "name": "Contactors",
          "note": "High mechanical & electrical endurance"
        },
        {
          "name": "Motor Starters",
          "note": "Intelligent auto transformer starter with wide industrial applications"
        },
        {
          "name": "Surge Protection Devices",
          "note": "Precise Defence Against Every Spike ​"
        }
      ],
      "has_page": true,
      "markdown": "# Low Voltage Products and Solutions\n\n**Page:** https://cselectric.co.in/products-solutions/low-voltage-switchgear/\n**Breadcrumb:** Home > Products & Solutions > Low Voltage Switchgear\n\nLow voltage switchgear are the equipment that are used to switching, protecting, control, & isolate the electrical circuits operating at voltage upto 1000V AC. These include ACB, MCCB, MCB, Contactor, isolator, switch disconnector, Fuses etc. These switchgear is commonly found throughout electric utility transmission and distribution systems as well as in medium to large sized commercial or industrial facilities. C&S offers a wide range of low voltage switchgear for upto 800V AC & 1500V DC. All are tested & certified as per the IEC standard. These products mainly found in transmission & distribution of electricity in various industrial & residential application.\n\n## Contents\n- [Circuit Breakers](./Circuit Breakers/) — Modular construction with most compact dimensions\n- [Switches](./Switches/) — Modular pole design with compact construction\n- [Fuses & Fuse Bases](./Fuses & Fuse Bases/) — Ideally suitable for back up protection to motor starters\n- [Control & Signalling Devices](./Control & Signalling Devices/) — Illuminated & non- illuminated actuators in metal & polycarbonate\n- [Industrial Plugs and Sockets](./Industrial Plugs and Sockets/) — Secure & reliable with high grade thermoplastic material\n- [Contactors](./Contactors/) — High mechanical & electrical endurance\n- [Motor Starters](./Motor Starters/) — Intelligent auto transformer starter with wide industrial applications\n- [Surge Protection Devices](./Surge Protection Devices/) — Precise Defence Against Every Spike ​",
      "page_type": "_category.md",
      "description": "Low voltage switchgear are the equipment that are used to switching, protecting, control, & isolate the electrical circuits operating at voltage upto 1000V AC. These include ACB, MCCB, MCB, Contactor, isolator, switch disconnector, Fuses etc. These switchgear is commonly found throughout electric utility transmission and distribution systems as well as in medium to large sized commercial or industrial facilities. C&S offers a wide range of low voltage switchgear for upto 800V AC & 1500V DC. All are tested & certified as per the IEC standard. These products mainly found in transmission & distribution of electricity in various industrial & residential application.",
      "source_file": "Low Voltage Products and Solutions/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/",
      "name": "Circuit Breakers",
      "level": 2,
      "is_leaf": false,
      "contents": [
        {
          "name": "Air Circuit Breakers",
          "note": "With current rating up to 6300A available in 3 or 4 pole."
        },
        {
          "name": "Moulded Case Circuit Breakers",
          "note": "Designed using latest technology with adjustable thermal and magnetic strips"
        },
        {
          "name": "Motor Protection Circuit Breakers",
          "note": "35 Din rail mounting MPCB upto 690V"
        }
      ],
      "has_page": true,
      "markdown": "# Circuit Breakers\n\n**Page:** https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/\n**Breadcrumb:** Home > Products & Solutions > Low Voltage Switchgear > Circuit Breakers\n\nA circuit breaker is a device which is design to protect our electrical circuits from damages occurred by overload, short circuit, and ground fault etc. Circuit breaker stops the flow of current when protective relay detects any type of fault in electrical circuit. The main function of a circuit breaker is to provide protection, switching & monitoring in a circuit. C&S offers a wide range of circuit breakers like ACB, MCCB, MCB, RCCB, etc. which are used in various residential, commercial, & industrial applications.\n\n## Contents\n- [Air Circuit Breakers](./Air Circuit Breakers/) — With current rating up to 6300A available in 3 or 4 pole.\n- [Moulded Case Circuit Breakers](./Moulded Case Circuit Breakers/) — Designed using latest technology with adjustable thermal and magnetic strips\n- [Motor Protection Circuit Breakers](./Motor Protection Circuit Breakers/) — 35 Din rail mounting MPCB upto 690V",
      "page_type": "_category.md",
      "description": "A circuit breaker is a device which is design to protect our electrical circuits from damages occurred by overload, short circuit, and ground fault etc. Circuit breaker stops the flow of current when protective relay detects any type of fault in electrical circuit. The main function of a circuit breaker is to provide protection, switching & monitoring in a circuit. C&S offers a wide range of circuit breakers like ACB, MCCB, MCB, RCCB, etc. which are used in various residential, commercial, & industrial applications.",
      "source_file": "Low Voltage Products and Solutions/Circuit Breakers/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/",
      "name": "Air Circuit Breakers",
      "level": 3,
      "is_leaf": false,
      "contents": [
        {
          "name": "ACB – AH/AHA",
          "note": "Designed using latest technology with current rating upto 6300A"
        },
        {
          "name": "ACB – WiNmaster 2",
          "note": "User Friendly Circuit Breakers with a compact design"
        },
        {
          "name": "ACB – WiNmaster 3",
          "note": "Latest Generation Circuit Breakers suitable up to 800V AC with a compact design"
        }
      ],
      "has_page": true,
      "markdown": "# Air Circuit Breakers\n\n**Page:** https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/\n**Breadcrumb:** Home > Products & Solutions > Low Voltage Switchgear > Circuit Breakers > Air Circuit Breakers\n\n## Contents\n- [ACB – AH/AHA](./ACB – AH-AHA/) — Designed using latest technology with current rating upto 6300A\n- [ACB – WiNmaster 2](./ACB – WiNmaster 2/) — User Friendly Circuit Breakers with a compact design\n- [ACB – WiNmaster 3](./ACB – WiNmaster 3/) — Latest Generation Circuit Breakers suitable up to 800V AC with a compact design",
      "page_type": "_category.md",
      "description": null,
      "source_file": "Low Voltage Products and Solutions/Circuit Breakers/Air Circuit Breakers/_category.md"
    },
    {
      "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/",
      "name": "ACB – AH-AHA",
      "level": 4,
      "is_leaf": true,
      "contents": null,
      "has_page": true,
      "markdown": "# ACB - AH/AHA\n\n**Product page:** https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/\n**Breadcrumb:** Home > Products & Solutions > Low Voltage Switchgear > Circuit Breakers > Air Circuit Breakers > ACB – AH/AHA\n**Image:** https://cselectric.co.in/wp-content/uploads/2023/05/13.jpg (saved as `13.jpg`)\n\n## Range\n- Rating: 630A~6300A\n- Poles: 3P & 4P\n- Version: Fixed – Manual & Electrical and Drawout – Manual & Electrical\n\n## Features\n- Breaking capacity Ics=Icu=Icw up to 100kA\n- Inbuilt Safety Interlocks & Electrical Anti Pumping\n- Modular construction Unique Slow Close Operation\n- High mechanical & electrical operating Life\n- Intelligent micropro releases with communication protocol (modbus / profibus) RS485\n- Multiple horizontal / vertical terminal connection option\n\n## Presentation\nC&S now introduces the new WiNmaster Air Circuit Breakers meeting complex requirements of electrical systems of today and tomorrow ensuring reliability which can offer un-interrupted service throughout the product life undergoing all the stresses that system encounters. Apart from meeting all the traditional requirement of power circuit breakers ( high breaking capacity, 3pole & 4pole, cool running at higher temperature, selectivity, absolutely no maintenance, draw out option). Winmaster now offers total solution for modern day requirement for measurement, analysis and communications, all in  optimized size.\nWiNmaster circuit breakers use the latest technology to enhance performance and safety. Compact yet offering various connections for ease of installation snap on site fit accessories, enhanced life and intuitive operation makes them a very user friendly range of circuit breaker for any application. Complete range of WiNmaster ACB confirms to the latest IEC 60947-2/IS 13947-2 standard. WiNmaster ACB simplifies the design of switchboard and standardizes the installation of the products. All accessories are common for entire range and now can be easily fitted from the front.\n\n## Benefits\nUses the latest technology to enhance performance and safety\nSimplifies the design of switchboard and standardizes the installation of the products\nUsed in industries and power systems\nUninterrupted service throughout the product life\nTotal solution for modern day requirement for measurement, analysis and communications\n\n## Brochure\n- [ACB_AHA.pdf](./ACB_AHA.pdf) (source: https://cselectric.co.in/wp-content/uploads/2025/12/ACB_AHA.pdf)",
      "page_type": "product.md",
      "description": null,
      "source_file": "Low Voltage Products and Solutions/Circuit Breakers/Air Circuit Breakers/ACB – AH-AHA/product.md"
    }
  ],
  "headings": [
    "Overcurrent release options"
  ],
  "node_type": "sku"
}
```

**product**

```json
{
  "url": "https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/",
  "family": "ACB – AH-AHA",
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
  "sku_code": "AH06BCSMP3.1MF(S)",
  "attributes": {
    "release": {
      "code": "MP3.1",
      "label": "MicroPro 3.1 (LSIG, true-RMS, fault indication)"
    },
    "mounting": {
      "code": "MF",
      "label": "manual_fixed"
    }
  },
  "peer_group": "ACB – AH-AHA | mounting=MF | release=MP3.1",
  "description": null,
  "alias_reason": null,
  "price_status": "por",
  "comparable_on": [
    "modules",
    "poles",
    "rated_current_a"
  ],
  "related_codes": [
    "AH08BCSMP3.1MF(S)",
    "AH10BCSMP3.1MF(S)",
    "AH12BCSMP3.1MF(S)",
    "AH16BCSMP3.1MF(S)",
    "AH20BCSMP3.1MF(S)"
  ],
  "canonical_code": "AH06BCSMP3.1MF(S)",
  "market_segments": [
    "Distribution & Transmission",
    "Industries",
    "Infrastructure",
    "Original Equipment Manufacturers (OEM)"
  ],
  "also_published_as": null,
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
      "canonical": true,
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
      "canonical": true,
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
      "canonical": true,
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
      "value": "B",
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-004",
      "canonical": true,
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
      "unit": "",
      "value": "B phase CT",
      "source": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-005",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "10, 12",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a 10, 12 of B phase CT.",
      "value_display": "B phase CT",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "10_12"
    },
    {
      "unit": "",
      "value": "N phase CT",
      "source": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-006",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "14, 16",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a 14, 16 of N phase CT.",
      "value_display": "N phase CT",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "14_16"
    },
    {
      "unit": "",
      "value": "MHT coil",
      "source": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-007",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "18, 20",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a 18, 20 of MHT coil.",
      "value_display": "MHT coil",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "18_20"
    },
    {
      "unit": "V",
      "value": 24.0,
      "source": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-008",
      "canonical": false,
      "value_max": 24.0,
      "value_min": 24.0,
      "spec_label": "22, 24",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a 22, 24 of 24V DC supply from power supply module.",
      "value_display": "24V DC supply from power supply module",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "22_24"
    },
    {
      "unit": "V",
      "value": "Input supply 230 V AC for communication module; phase to L, neutral to N, earth to E",
      "source": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-009",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "230 V I/P L … I/P N … I/P E",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a 230 v i/p l … i/p n … i/p e of Input supply 230 V AC for communication module; phase to L, neutral to N, earth to E.",
      "value_display": "Input supply 230 V AC for communication module; phase to L, neutral to N, earth to E",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "230_v_i_p_l_i_p_n_i_p_e"
    },
    {
      "unit": "",
      "value": "R phase CT",
      "source": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-010",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "2, 4",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a 2, 4 of R phase CT.",
      "value_display": "R phase CT",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "2_4"
    },
    {
      "unit": "",
      "value": "Y phase CT",
      "source": "Control circuit diagram — MicroPro 3.1 with power supply module and battery unit",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-011",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "6, 8",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a 6, 8 of Y phase CT.",
      "value_display": "Y phase CT",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "6_8"
    },
    {
      "unit": "",
      "value": "As per IEC 60947-2",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-012",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Ampere frame designation",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a ampere frame designation of As per IEC 60947-2.",
      "value_display": "As per IEC 60947-2",
      "source_of_truth": "brochure",
      "canonical_spec_id": "ampere_frame_designation"
    },
    {
      "unit": "",
      "value": "Conforms to IS/IEC 60947-2 (brochure). The website product page states IEC 60947-2 / IS 13947-2",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-013",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Applicable standard",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a applicable standard of Conforms to IS/IEC 60947-2 (brochure). The website product page states IEC 60947-2 / IS 13947-2.",
      "value_display": "Conforms to IS/IEC 60947-2 (brochure). The website product page states IEC 60947-2 / IS 13947-2",
      "source_of_truth": "brochure",
      "canonical_spec_id": "applicable_standard"
    },
    {
      "unit": "ms",
      "value": 40.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-014",
      "canonical": false,
      "value_max": 40.0,
      "value_min": 40.0,
      "spec_label": "Closing time",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a closing time of 40 ms.",
      "value_display": "40 ms",
      "source_of_truth": "brochure",
      "canonical_spec_id": "closing_time"
    },
    {
      "unit": "",
      "value": "RoHS compliant",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-015",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Compliance",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a compliance of RoHS compliant.",
      "value_display": "RoHS compliant",
      "source_of_truth": "brochure",
      "canonical_spec_id": "compliance"
    },
    {
      "unit": "",
      "value": "Special sintered metal contacts",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-016",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Contact material",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a contact material of Special sintered metal contacts.",
      "value_display": "Special sintered metal contacts",
      "source_of_truth": "brochure",
      "canonical_spec_id": "contact_material"
    },
    {
      "unit": "",
      "value": "36-M4",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-017",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Control-circuit terminal blocks",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a control-circuit terminal blocks of 36-M4.",
      "value_display": "36-M4",
      "source_of_truth": "brochure",
      "canonical_spec_id": "control_circuit_terminal_blocks"
    },
    {
      "unit": "",
      "value": "IS 9000 - PG4",
      "source": "MicroPro release — ERTL certification tests",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-018",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Damp Heat Test",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a damp heat test of IS 9000 - PG4.",
      "value_display": "IS 9000 - PG4",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "damp_heat_test"
    },
    {
      "unit": "",
      "value": "IS 9000 - PG3",
      "source": "MicroPro release — ERTL certification tests",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-019",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Dry Heat Test",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a dry heat test of IS 9000 - PG3.",
      "value_display": "IS 9000 - PG3",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "dry_heat_test"
    },
    {
      "unit": "",
      "value": null,
      "source": "MicroPro 3.1 release",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-020",
      "canonical": false,
      "value_max": 0.8,
      "value_min": 0.05,
      "spec_label": "Earth fault delay",
      "value_kind": "range",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a earth fault delay of 0.05–0.8 sec in 16 steps: 0.05 to 0.80 in 0.05 sec increments.",
      "value_display": "0.05–0.8 sec in 16 steps: 0.05 to 0.80 in 0.05 sec increments",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "earth_fault_delay"
    },
    {
      "unit": "",
      "value": null,
      "source": "MicroPro 3.1 release",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-021",
      "canonical": false,
      "value_max": 0.9,
      "value_min": 0.2,
      "spec_label": "Earth fault pick up",
      "value_kind": "range",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a earth fault pick up of 0.2–0.9 In with OFF, in 9 steps: OFF, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9.",
      "value_display": "0.2–0.9 In with OFF, in 9 steps: OFF, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "earth_fault_pick_up"
    },
    {
      "unit": "%",
      "value": 20.0,
      "source": "Intelligent release tripping curves and setting tolerances",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-022",
      "canonical": false,
      "value_max": 20.0,
      "value_min": 20.0,
      "spec_label": "Earth fault trip current setting range",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a earth fault trip current setting range of ±20%.",
      "value_display": "±20%",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "earth_fault_trip_current_setting_range"
    },
    {
      "unit": "%",
      "value": 10.0,
      "source": "Intelligent release tripping curves and setting tolerances",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-023",
      "canonical": false,
      "value_max": 10.0,
      "value_min": 10.0,
      "spec_label": "Earth fault trip time delay setting range",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a earth fault trip time delay setting range of ±10%.",
      "value_display": "±10%",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "earth_fault_trip_time_delay_setting_range"
    },
    {
      "unit": "",
      "value": 8.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-024",
      "canonical": false,
      "value_max": 8.0,
      "value_min": 8.0,
      "spec_label": "Earth terminal",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a earth terminal of M8.",
      "value_display": "M8",
      "source_of_truth": "brochure",
      "canonical_spec_id": "earth_terminal"
    },
    {
      "unit": "",
      "value": "IEC 801 - 4",
      "source": "MicroPro release — ERTL certification tests",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-025",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Electrical Fast Transient (EFT)",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a electrical fast transient (eft) of IEC 801 - 4.",
      "value_display": "IEC 801 - 4",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "electrical_fast_transient_eft"
    },
    {
      "unit": "",
      "value": "IEC 801 - 2",
      "source": "MicroPro release — ERTL certification tests",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-026",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Electrostatic Discharge (ESD)",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a electrostatic discharge (esd) of IEC 801 - 2.",
      "value_display": "IEC 801 - 2",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "electrostatic_discharge_esd"
    },
    {
      "unit": "",
      "value": "3 frame sizes for the entire range (maximum interchangeability, minimum spares inventory)",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-027",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Frame sizes",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a frame sizes of 3 frame sizes for the entire range (maximum interchangeability, minimum spares inventory).",
      "value_display": "3 frame sizes for the entire range (maximum interchangeability, minimum spares inventory)",
      "source_of_truth": "brochure",
      "canonical_spec_id": "frame_sizes"
    },
    {
      "unit": "",
      "value": "IEC 255 - 4",
      "source": "MicroPro release — ERTL certification tests",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-028",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Impulse",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a impulse of IEC 255 - 4.",
      "value_display": "IEC 255 - 4",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "impulse"
    },
    {
      "unit": "%",
      "value": 20.0,
      "source": "Intelligent release tripping curves and setting tolerances",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-029",
      "canonical": false,
      "value_max": 20.0,
      "value_min": 20.0,
      "spec_label": "INST trip current setting range",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a inst trip current setting range of ±20%.",
      "value_display": "±20%",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "inst_trip_current_setting_range"
    },
    {
      "unit": "",
      "value": "3.0–10 In with OFF, in 9 steps: OFF, 3, 4, 5, 6, 7, 8, 9, 10",
      "source": "MicroPro 3.1 release",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-030",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Instantaneous pick up",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a instantaneous pick up of 3.0–10 In with OFF, in 9 steps: OFF, 3, 4, 5, 6, 7, 8, 9, 10.",
      "value_display": "3.0–10 In with OFF, in 9 steps: OFF, 3, 4, 5, 6, 7, 8, 9, 10",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "instantaneous_pick_up"
    },
    {
      "unit": "",
      "value": "Class 'B' and class 'F' (high dielectric strength in hot and humid conditions)",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-031",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Insulating materials",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a insulating materials of Class 'B' and class 'F' (high dielectric strength in hot and humid conditions).",
      "value_display": "Class 'B' and class 'F' (high dielectric strength in hot and humid conditions)",
      "source_of_truth": "brochure",
      "canonical_spec_id": "insulating_materials"
    },
    {
      "unit": "%",
      "value": 20.0,
      "source": "Intelligent release tripping curves and setting tolerances",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-032",
      "canonical": false,
      "value_max": 20.0,
      "value_min": 20.0,
      "spec_label": "L.T.D time delay setting range",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a l.t.d time delay setting range of ±20%.",
      "value_display": "±20%",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "l_t_d_time_delay_setting_range"
    },
    {
      "unit": "%",
      "value": 5.0,
      "source": "Intelligent release tripping curves and setting tolerances",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-033",
      "canonical": false,
      "value_max": 5.0,
      "value_min": 5.0,
      "spec_label": "L.T.D trip current setting range",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a l.t.d trip current setting range of ±5%.",
      "value_display": "±5%",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "l_t_d_trip_current_setting_range"
    },
    {
      "unit": "",
      "value": "To be connected with MicroPro release for communication to ACB",
      "source": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-034",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "M-PRO D(+) & M-PRO D(-)",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a m-pro d(+) & m-pro d(-) of To be connected with MicroPro release for communication to ACB.",
      "value_display": "To be connected with MicroPro release for communication to ACB",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "m_pro_d_m_pro_d"
    },
    {
      "unit": "",
      "value": "To be connected with RS 485/232 converter to master PC",
      "source": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-035",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Master D (+) & Master D (-)",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a master d (+) & master d (-) of To be connected with RS 485/232 converter to master PC.",
      "value_display": "To be connected with RS 485/232 converter to master PC",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "master_d_master_d"
    },
    {
      "unit": "",
      "value": "Fixed or draw-out",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-036",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Mounting options",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a mounting options of Fixed or draw-out.",
      "value_display": "Fixed or draw-out",
      "source_of_truth": "brochure",
      "canonical_spec_id": "mounting_options"
    },
    {
      "unit": "",
      "value": "Closes early and opens later, preventing transient over-voltages between live and neutral",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-037",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Neutral pole behaviour (4 pole)",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a neutral pole behaviour (4 pole) of Closes early and opens later, preventing transient over-voltages between live and neutral.",
      "value_display": "Closes early and opens later, preventing transient over-voltages between live and neutral",
      "source_of_truth": "brochure",
      "canonical_spec_id": "neutral_pole_behaviour_4_pole"
    },
    {
      "unit": "",
      "value": 3.1,
      "source": "MicroPro 3.1 release",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-038",
      "canonical": false,
      "value_max": 3.1,
      "value_min": 3.1,
      "spec_label": "Neutral protection",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a neutral protection of Not available on 3.1.",
      "value_display": "Not available on 3.1",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "neutral_protection"
    },
    {
      "unit": "V",
      "value": "Output 24 V DC supply, can be used for MicroPro auxiliary supply",
      "source": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-039",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "O/P + & GND",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a o/p + & gnd of Output 24 V DC supply, can be used for MicroPro auxiliary supply.",
      "value_display": "Output 24 V DC supply, can be used for MicroPro auxiliary supply",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "o_p_gnd"
    },
    {
      "unit": "",
      "value": null,
      "source": "MicroPro 3.1 release",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-040",
      "canonical": false,
      "value_max": 35.0,
      "value_min": 2.5,
      "spec_label": "Overload delay",
      "value_kind": "range",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a overload delay of 2.5–35 sec at 6 Ir in 14 steps: 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35.",
      "value_display": "2.5–35 sec at 6 Ir in 14 steps: 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "overload_delay"
    },
    {
      "unit": "",
      "value": null,
      "source": "MicroPro 3.1 release",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-041",
      "canonical": false,
      "value_max": 1.1,
      "value_min": 0.4,
      "spec_label": "Overload pick up",
      "value_kind": "range",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a overload pick up of 0.4–1.1 In with OFF, in 9 steps: OFF, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1.",
      "value_display": "0.4–1.1 In with OFF, in 9 steps: OFF, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "overload_pick_up"
    },
    {
      "unit": "",
      "value": 3.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-042",
      "canonical": false,
      "value_max": 3.0,
      "value_min": 3.0,
      "spec_label": "Pollution degree",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a pollution degree of 3.",
      "value_display": "3",
      "source_of_truth": "brochure",
      "canonical_spec_id": "pollution_degree"
    },
    {
      "unit": "",
      "value": "IEC 801 - 3",
      "source": "MicroPro release — ERTL certification tests",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-043",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Radio Frequency Interference (RFI)",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a radio frequency interference (rfi) of IEC 801 - 3.",
      "value_display": "IEC 801 - 3",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "radio_frequency_interference_rfi"
    },
    {
      "unit": "V",
      "value": 415.0,
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-044",
      "canonical": false,
      "value_max": 415.0,
      "value_min": 415.0,
      "spec_label": "Reference voltage for breaking-capacity data",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a reference voltage for breaking-capacity data of 415 V AC.",
      "value_display": "415 V AC",
      "source_of_truth": "brochure",
      "canonical_spec_id": "reference_voltage_for_breaking_capacity_data"
    },
    {
      "unit": "%",
      "value": 10.0,
      "source": "Intelligent release tripping curves and setting tolerances",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-045",
      "canonical": false,
      "value_max": 10.0,
      "value_min": 10.0,
      "spec_label": "S.T.D trip current setting range",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a s.t.d trip current setting range of ±10%.",
      "value_display": "±10%",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "s_t_d_trip_current_setting_range"
    },
    {
      "unit": "%",
      "value": 10.0,
      "source": "Intelligent release tripping curves and setting tolerances",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-046",
      "canonical": false,
      "value_max": 10.0,
      "value_min": 10.0,
      "spec_label": "S.T.D trip time delay setting range",
      "value_kind": "scalar",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a s.t.d trip time delay setting range of ±10%.",
      "value_display": "±10%",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "s_t_d_trip_time_delay_setting_range"
    },
    {
      "unit": "",
      "value": "Fibre glass, main-circuit safety shutters on draw-out type",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-047",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Safety shutter",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a safety shutter of Fibre glass, main-circuit safety shutters on draw-out type.",
      "value_display": "Fibre glass, main-circuit safety shutters on draw-out type",
      "source_of_truth": "brochure",
      "canonical_spec_id": "safety_shutter"
    },
    {
      "unit": "",
      "value": null,
      "source": "MicroPro 3.1 release",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-048",
      "canonical": false,
      "value_max": 0.8,
      "value_min": 0.05,
      "spec_label": "Short circuit delay",
      "value_kind": "range",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a short circuit delay of 0.05–0.8 sec in 16 steps: 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80.",
      "value_display": "0.05–0.8 sec in 16 steps: 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "short_circuit_delay"
    },
    {
      "unit": "",
      "value": null,
      "source": "MicroPro 3.1 release",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-049",
      "canonical": false,
      "value_max": 9.0,
      "value_min": 1.5,
      "spec_label": "Short circuit pick up",
      "value_kind": "range",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a short circuit pick up of 1.5–9.0 Ir in 16 steps: 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0.",
      "value_display": "1.5–9.0 Ir in 16 steps: 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "short_circuit_pick_up"
    },
    {
      "unit": "",
      "value": "Manual charging or motor charging",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-050",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Spring charging",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a spring charging of Manual charging or motor charging.",
      "value_display": "Manual charging or motor charging",
      "source_of_truth": "brochure",
      "canonical_spec_id": "spring_charging"
    },
    {
      "unit": "",
      "value": "IEC 801 - 5",
      "source": "MicroPro release — ERTL certification tests",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-051",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Surge",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a surge of IEC 801 - 5.",
      "value_display": "IEC 801 - 5",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "surge"
    },
    {
      "unit": "",
      "value": "Tested at CPRI / ERTL; tested for most onerous environmental conditions",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-052",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Testing",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a testing of Tested at CPRI / ERTL; tested for most onerous environmental conditions.",
      "value_display": "Tested at CPRI / ERTL; tested for most onerous environmental conditions",
      "source_of_truth": "brochure",
      "canonical_spec_id": "testing"
    },
    {
      "unit": "ms",
      "value": "Less than 30 ms (including arcing time of less than 10 ms)",
      "source": "brochure",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-053",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Total breaking time",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a total breaking time of Less than 30 ms (including arcing time of less than 10 ms).",
      "value_display": "Less than 30 ms (including arcing time of less than 10 ms)",
      "source_of_truth": "brochure",
      "canonical_spec_id": "total_breaking_time"
    },
    {
      "unit": "",
      "value": "IEC 255 - 4",
      "source": "MicroPro release — ERTL certification tests",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-054",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Vibration Test",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a vibration test of IEC 255 - 4.",
      "value_display": "IEC 255 - 4",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "vibration_test"
    },
    {
      "unit": "",
      "value": "DI & DO outputs",
      "source": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-055",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "Zi ~ D19",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a zi ~ d19 of DI & DO outputs.",
      "value_display": "DI & DO outputs",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "zi_d19"
    },
    {
      "unit": "",
      "value": "Zone selectivity",
      "source": "Communication module (MicroPro 4.1 / 5.1 accessory)",
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-056",
      "canonical": false,
      "value_max": null,
      "value_min": null,
      "spec_label": "ZO / COMMON / DO",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) has a zo / common / do of Zone selectivity.",
      "value_display": "Zone selectivity",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "zo_common_do"
    },
    {
      "unit": "",
      "value": [
        "Distribution & Transmission",
        "Industries",
        "Infrastructure",
        "Original Equipment Manufacturers (OEM)"
      ],
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-segments",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "Market segments",
      "value_kind": "set",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) is used in Distribution & Transmission, Industries, Infrastructure, Original Equipment Manufacturers (OEM).",
      "value_display": "Distribution & Transmission, Industries, Infrastructure, Original Equipment Manufacturers (OEM)",
      "source_of_truth": "catalogue",
      "canonical_spec_id": "market_segments"
    },
    {
      "unit": "INR",
      "value": "POR",
      "source": null,
      "derived": false,
      "fact_id": "AH06BCSMP3.1MF_S_-price",
      "canonical": true,
      "value_max": null,
      "value_min": null,
      "spec_label": "MRP",
      "value_kind": "text",
      "fact_sentence": "AH06BCSMP3.1MF(S) (ACB – AH-AHA, 630 A, 3-pole, manual_fixed, MicroPro 3.1 (LSIG, true-RMS, fault indication)) is quoted Price on Request (contact the nearest C&S branch office).",
      "value_display": "POR",
      "source_of_truth": "pricelist_table",
      "canonical_spec_id": "price_inr"
    }
  ],
  "derived": null,
  "sources": [
    "LV-Pricelist-WEF-1st-June26.pdf p19",
    "Brochure: ACB_AHA.md (same folder)",
    "Product page: https://cselectric.co.in/products-solutions/low-voltage-switchgear/circuit-breakers/air-circuit-breakers/acb-ah-aha/"
  ],
  "spec_ids": [
    "10_12",
    "14_16",
    "18_20",
    "22_24",
    "230_v_i_p_l_i_p_n_i_p_e",
    "2_4",
    "6_8",
    "ampere_frame_designation",
    "applicable_standard",
    "closing_time",
    "compliance",
    "contact_material",
    "control_circuit_terminal_blocks",
    "damp_heat_test",
    "dry_heat_test",
    "earth_fault_delay",
    "earth_fault_pick_up",
    "earth_fault_trip_current_setting_range",
    "earth_fault_trip_time_delay_setting_range",
    "earth_terminal",
    "electrical_fast_transient_eft",
    "electrostatic_discharge_esd",
    "frame_sizes",
    "impulse",
    "inst_trip_current_setting_range",
    "instantaneous_pick_up",
    "insulating_materials",
    "l_t_d_time_delay_setting_range",
    "l_t_d_trip_current_setting_range",
    "m_pro_d_m_pro_d",
    "market_segments",
    "master_d_master_d",
    "modules",
    "mounting_options",
    "neutral_pole_behaviour_4_pole",
    "neutral_protection",
    "o_p_gnd",
    "overload_delay",
    "overload_pick_up",
    "poles",
    "pollution_degree",
    "price_inr",
    "radio_frequency_interference_rfi",
    "rated_current_a",
    "reference_voltage_for_breaking_capacity_data",
    "s_t_d_trip_current_setting_range",
    "s_t_d_trip_time_delay_setting_range",
    "safety_shutter",
    "short_circuit_delay",
    "short_circuit_pick_up",
    "spring_charging",
    "surge",
    "testing",
    "total_breaking_time",
    "utilisation_category",
    "vibration_test",
    "zi_d19",
    "zo_common_do"
  ],
  "extraction": {
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

**content**

```
Category: Low Voltage Products and Solutions > Circuit Breakers > Air Circuit Breakers > ACB – AH-AHA.
AH06BCSMP3.1MF(S) — ACB – AH-AHA
Overcurrent release options
Two families of overcurrent release are offered on this range:

- **Thermal Magnetic Trip Device: Type TM**
- **Intelligent Release: Type MicroPro 3.1, 4.1 & 5.1**

The release fitted is stated in the ordering reference. MicroPro 3.1 is the standard intelligent release; MicroPro 4.1 and 5.1 are multi-purpose releases adding an RS485 port and zone selectivity.
```
