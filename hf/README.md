---
pretty_name: Hong Kong live road feeds and alerts (Milleleaf hk-alerts)
license: other
---

# Hong Kong live road feeds and alerts

Snapshots every 15 minutes by [milleleaf/hk-alerts](https://github.com/milleleaf/hk-alerts). This Kaggle dataset holds one complete Hong Kong month of one history feed: the day files listed below for that feed.

| File on the bucket | From | Contents |
|---|---|---|
| `live/aqhi.json` | EPD AQHI RSS (`aqhi.gov.hk`), station positions from the CSDI layer "Air Quality Monitoring Network of Hong Kong" | GeoJSON: one point per station with AQHI, health risk, general or roadside, time |
| `live/press.json` | Government press releases RSS (`info.gov.hk`) | the newest 100: title, link, time (no body text) |
| `live/ev-chargers.json` | EPD "Electric Vehicle Chargers for Public Access" (CSDI) | GeoJSON, every source field, plus `_name`, `_address`, `_district`, `_chargers`, `_by_kind` that survive EPD's field renames (14-16 Oct 2026) |
| `live/ev-availability.json` | EPD live charger availability (the CSDI charger layer's `DATA_PATH`) | GeoJSON, one point per car park, every source field: free chargers now, operators (CLPe's 38 sites are here), fees, opening hours |
| `live/status.json` | this pipeline | per source: last try, last success, last error, count, `never_succeeded` |
| `live/speeds-YYYY-MM-DD.parquet` | TD "Traffic Data of Strategic / Major Roads", processed (`irnAvgSpeed-all.xml`) | one row per road segment per snapshot: speed, valid, the feed's date, time and IRN version. `segment_id` = `ROUTE_ID` of the TD road network centreline in milleleaf/hk-roads |
| `live/detectors-YYYY-MM-DD.parquet` | same dataset, raw (`rawSpeedVol-all.xml`) | one row per lane per 30 s period per snapshot: speed, occupancy, volume, s.d. (`sd`), valid. Locations: TD's `traffic_speed_volume_occ_info.csv` |
| `live/journeytimes-YYYY-MM-DD.parquet` | TD "Journey time indicators (2nd generation)" (`Journeytimev2.xml`) | one row per indicator and destination per snapshot, every field |
| `live/roadworks-YYYY-MM-DD.parquet` | TD/HyD "Roadworks location data" | GeoParquet, one row per roadworks per snapshot, every field |

History files: one per feed per Hong Kong day, appended each run, every source field, `snapshot` = the run's UTC time. A
snapshot every 15 minutes samples feeds that change every 30 s to 2 min; it is not every reading. Each complete Hong Kong month
moves to its own Kaggle dataset, `helenkwok/hk-alerts-<feed>-YYYY-MM`, and leaves the bucket only once Kaggle lists every day.


Source terms: DATA.GOV.HK terms of use (https://data.gov.hk/en/terms-and-conditions), Government of the HKSAR (Transport Department, Highways Department). Attribution: "Source: Transport Department / Highways Department, HKSAR Government, via DATA.GOV.HK".
