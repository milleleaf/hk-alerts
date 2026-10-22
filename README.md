# hk-alerts

An [Milleleaf](https://github.com/milleleaf) pipeline: Hong Kong feeds for WorldViews, every 15 minutes, to the Hugging Face
bucket `milleleaf/hk-alerts` (CORS, HTTP Range). Two jobs: republish feeds a web page cannot read itself (no CORS, or field
names about to change), and keep a history of live road feeds that the sources themselves do not keep.

| File on the bucket | From | Contents |
|---|---|---|
| `live/aqhi.json` | EPD AQHI RSS (`aqhi.gov.hk`), station positions from the CSDI layer "Air Quality Monitoring Network of Hong Kong" | GeoJSON: one point per station with AQHI, health risk, general or roadside, time |
| `live/press.json` | Government press releases RSS (`info.gov.hk`) | the newest 100: title, link, time (no body text) |
| `live/ev-chargers.json` | EPD "Electric Vehicle Chargers for Public Access" (CSDI) | GeoJSON, every source field, plus `_name`, `_address`, `_district`, `_chargers`, `_by_kind` that survive EPD's field renames (14-16 Oct 2026) |
| `live/clp-chargers.json` | CLP Power "Electric Vehicle Charging Stations" | as received, only if CLP's API answers the runner (it returns 403 to a Mac in Hong Kong) |
| `live/speeds-YYYY-MM-DD.parquet` | TD "Traffic Data of Strategic / Major Roads", processed (`irnAvgSpeed-all.xml`) | one row per road segment per snapshot: speed, valid, the feed's date, time and IRN version. `segment_id` = `ROUTE_ID` of the TD road network centreline in milleleaf/hk-roads |
| `live/detectors-YYYY-MM-DD.parquet` | same dataset, raw (`rawSpeedVol-all.xml`) | one row per lane per 30 s period per snapshot: speed, occupancy, volume, s.d. (`sd`), valid. Locations: TD's `traffic_speed_volume_occ_info.csv` |
| `live/journeytimes-YYYY-MM-DD.parquet` | TD "Journey time indicators (2nd generation)" (`Journeytimev2.xml`) | one row per indicator and destination per snapshot, every field |
| `live/roadworks-YYYY-MM-DD.parquet` | TD/HyD "Roadworks location data" | GeoParquet, one row per roadworks per snapshot, every field |

History files: one per feed per Hong Kong day, appended each run, every source field, `snapshot` = the run's UTC time. A
snapshot every 15 minutes samples feeds that change every 30 s to 2 min; it is not every reading. Each complete Hong Kong month
moves to its own Kaggle dataset, `helenkwok/hk-alerts-<feed>-YYYY-MM`, and leaves the bucket only once Kaggle lists every day.

| File | Does |
|---|---|
| `live.py` | Fetches everything; a failing source keeps its last file. `python3 live.py test` writes `./data/` and uploads nothing |
| `live.yml` | Every 15 minutes, dispatched by `milleleaf/heartbeat`; its cron is the backup |
| `kaggle_archive.py`, `archive.yml` | Weekly: complete months of history to Kaggle (`python3 kaggle_archive.py test`: self-test) |
| `kaggle_mirror.py` | Shared with the other pipelines: uploads a Kaggle dataset (description = `hf/README.md`) |

Data: Government of the HKSAR (DATA.GOV.HK terms of use; CSDI terms for the CSDI layers), CLP Power Hong Kong (DATA.GOV.HK
terms), free reuse with attribution. Code: Apache-2.0.
