"""Hong Kong alerts the browser cannot read itself (no CORS), republished every 15 minutes for WorldViews:
  live/aqhi.json   EPD's current AQHI for the 18 monitoring stations (aqhi.gov.hk RSS), each placed at its station from the
                   CSDI "Air Quality Monitoring Network of Hong Kong" layer: GeoJSON, one point per station
  live/press.json  the Government's latest press releases (info.gov.hk RSS, newest 100): title, link, time; no body text
  live/ev-chargers.json  EPD's electric vehicle chargers for public access (CSDI), GeoJSON, every source field kept plus stable
                   names (name, address, district, chargers by kind): EPD renames its CSDI fields 14-16 Oct 2026
  live/clp-chargers.json  CLP Power's EV charging stations, as received, if its API answers this runner (it refused a Mac in HK)
The above are overwritten in place. History, every 15 minutes, one file per feed per Hong Kong day, appended each run (one row
per item per snapshot, every source field; `snapshot` = this run's UTC time):
  live/speeds-YYYY-MM-DD.parquet       TD speeds per road segment (irnAvgSpeed, every 2 min at source; joins hk-roads ROUTE_ID)
  live/detectors-YYYY-MM-DD.parquet    TD detector speed, volume and occupancy per lane (rawSpeedVol, 30 s periods)
  live/journeytimes-YYYY-MM-DD.parquet TD journey time indicators v2 (minutes or a description, colour 1-3)
  live/roadworks-YYYY-MM-DD.parquet    HyD/TD roadworks with lane closures on 70 km/h+ roads (GeoParquet)
Browsers read the live TD files themselves (CORS *); these copies are the history. kaggle_archive.py moves each complete month
to Kaggle. A source that fails keeps its last file (the run warns, exit 0).
Needs HF_TOKEN. `python3 live.py test` writes to ./data/ and uploads nothing."""
import datetime, email.utils, json, os, re, sys, tempfile, urllib.request
import xml.etree.ElementTree as ET

REPO = 'milleleaf/hk-alerts'
UA = {'User-Agent': 'AlreadyOpen hk-alerts (https://github.com/milleleaf/hk-alerts)'}
AQHI = 'https://www.aqhi.gov.hk/epd/ddata/html/out/aqhi_ind_rss_Eng.xml'
STATIONS = ('https://portal.csdi.gov.hk/server/rest/services/common/epd_rcd_1629267205214_40635/FeatureServer/0/query'
            '?where=1%3D1&outFields=*&outSR=4326&f=geojson')   # all fields: EPD renames them 14-16 Oct 2026 (NAME_EN -> NameEN)
PRESS = 'https://www.info.gov.hk/gia/rss/general_en.xml'
EV = ('https://portal.csdi.gov.hk/server/rest/services/common/epd_rcd_1631080339740_69941/FeatureServer/0/query'
      '?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultOffset={offset}')
CLP = 'https://api.clp.com.hk/evcharger/list'
TD = 'https://resource.data.one.gov.hk/td/'
HKT = datetime.timezone(datetime.timedelta(hours=8))


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def aqhi():
    """'Central/Western - General Stations: 5 Moderate - Wed, 14 Oct 2026 08:30' per item, joined to the CSDI station by name"""
    at = {}
    for f in json.loads(get(STATIONS))['features']:
        p = f['properties']
        name = p.get('NameEN') or p.get('NAME_EN') or p.get('FacilityName') or ''   # new name, old name, the AQHI layer's name
        at[re.sub(r'\s+Air Quality Monitoring Station$', '', name).strip().lower()] = f
    out, missing = [], []
    for it in ET.fromstring(get(AQHI)).iter('item'):
        name, desc = it.findtext('title', '').strip(), it.findtext('description', '').strip()
        m = re.match(r'(.+?) - (General|Roadside) Stations?: (\d+\+?) (.+?) - (.+)$', desc)
        f = at.get(name.lower())
        if not m or not f:
            missing.append(name); continue
        t = datetime.datetime.strptime(m[5].strip(), '%a, %d %b %Y %H:%M').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        out.append({'type': 'Feature', 'geometry': f['geometry'], 'properties': {
            'station': name, 'kind': m[2].lower(), 'aqhi': int(m[3].rstrip('+')), 'aqhi_text': m[3], 'risk': m[4], 'time': t.isoformat(),
            'link': it.findtext('link', '')}})
    assert out, 'no AQHI station parsed'
    if missing:
        print(f'::warning::AQHI: no position or no reading for {missing}')
    return {'type': 'FeatureCollection', 'source': 'Environmental Protection Department (AQHI), positions from CSDI', 'features': out}


def press():
    items = []
    for it in ET.fromstring(get(PRESS)).iter('item'):
        when = email.utils.parsedate_to_datetime(it.findtext('pubDate', ''))
        items.append({'title': it.findtext('title', '').strip(), 'link': it.findtext('link', '').strip(), 'time': when.isoformat()})
    assert items, 'no press release parsed'
    return {'source': 'Information Services Department, Government press releases', 'items': items}


def pick(p, *names):
    """the first of several field names (old and new spellings) that the feature has"""
    for n in names:
        if p.get(n) not in (None, ''): return p[n]
    return None


def ev_chargers():
    """all of EPD's charger sites (CSDI pages of up to 2,000), every field, plus stable names for the map"""
    feats, offset = [], 0
    while True:
        d = json.loads(get(EV.format(offset=offset)))
        feats += d['features']
        if not d.get('exceededTransferLimit') and not d.get('properties', {}).get('exceededTransferLimit'): break
        offset = len(feats)
    assert len(feats) > 100, f'only {len(feats)} chargers'
    for f in feats:
        p = f['properties']
        kinds = {k: int(float(v)) for k, v in p.items() if k.lower().endswith('_no') and re.fullmatch(r'\s*\d+(\.0+)?\s*', str(v or ''))}
        f['properties'] = {**p, '_name': pick(p, 'LOCATION_EN', 'LocationEN', 'Location_EN', 'LOCATION'),
                           '_address': pick(p, 'ADDRESS_EN', 'AddressEN', 'Address_EN', 'ADDRESS'),
                           '_district': pick(p, 'NAME_OF_DISTRICT_COUNCIL_DISTRICT_EN', 'DistrictEN', 'District_EN', 'DISTRICT_EN'),
                           '_chargers': sum(kinds.values()),
                           '_by_kind': {k: v for k, v in kinds.items() if v}}
    return {'type': 'FeatureCollection', 'source': 'Environmental Protection Department, EV chargers for public access (CSDI)', 'features': feats}


def clp_chargers():
    """CLP's list as received; the API refused requests from a Mac in Hong Kong (Akamai 403), so this records what CI gets"""
    d = json.loads(get(CLP))
    return {'source': 'CLP Power Hong Kong, EV charging stations', 'data': d, 'features': d if isinstance(d, list) else [d]}


def xml_rows(root, item, keep):
    """one dict per <item> element: its leaf children (namespace stripped) plus `keep`, the document-level fields"""
    rows = []
    for e in root.iter():
        if e.tag.split('}')[-1] != item: continue
        r = dict(keep)
        for c in e:
            if len(c) == 0: r[c.tag.split('}')[-1]] = (c.text or '').strip() or None
        rows.append(r)
    return rows


def speeds():
    root = ET.fromstring(get(TD + 'traffic-detectors/irnAvgSpeed-all.xml'))
    top = {k: root.findtext(k) for k in ('date', 'time', 'irn_version')}
    rows = [{**r, 'speed': float(r['speed']) if r.get('speed') else None} for r in xml_rows(root, 'segment', top)]
    return rows


def detectors():
    """one row per lane per 30 s period"""
    root, rows = ET.fromstring(get(TD + 'traffic-detectors/rawSpeedVol-all.xml')), []
    date = root.findtext('date')
    for per in root.iter('period'):
        for det in per.iter('detector'):
            for lane in det.iter('lane'):
                r = {'date': date, 'period_from': per.findtext('period_from'), 'period_to': per.findtext('period_to'),
                     'detector_id': det.findtext('detector_id'), 'direction': det.findtext('direction')}
                for c in lane: r[c.tag.replace('.', '')] = (c.text or '').strip() or None    # <s.d.> -> sd
                for k in ('speed', 'occupancy', 'volume', 'sd'):
                    r[k] = float(r[k]) if r.get(k) not in (None, '') else None
                rows.append(r)
    return rows


def journeytimes():
    return xml_rows(ET.fromstring(get(TD + 'jss/Journeytimev2.xml')), 'jtis_journey_time', {})


def roadworks():
    d = json.loads(get(TD + 'roadworks-location/get_all_the_roadworks.geojson'))
    return [{**{k: (v if isinstance(v, (str, int, float, bool)) or v is None else json.dumps(v, ensure_ascii=False)) for k, v in f['properties'].items()},
             'geometry_json': json.dumps(f.get('geometry'))} for f in d['features']]


HISTORY = {'speeds': speeds, 'detectors': detectors, 'journeytimes': journeytimes, 'roadworks': roadworks}


def history(name, make, now, w, con, test):
    """this run's rows appended to the feed's Hong Kong day file; returns (local, remote) to upload, or None"""
    rows = make()
    assert rows or name == 'roadworks', f'{name}: no rows'      # roadworks can genuinely be none
    if not rows: return None, 0
    snap = now.isoformat(timespec='seconds')
    src = os.path.join(w, f'{name}.ndjson')
    with open(src, 'w') as f:
        for r in rows: f.write(json.dumps({'snapshot': snap, **r}, ensure_ascii=False) + '\n')
    remote = f'live/{name}-{now.astimezone(HKT).date()}.parquet'
    old, out = os.path.join(w, f'{name}-old.parquet'), os.path.join(w, f'{name}.parquet')
    if not test:
        from huggingface_hub import download_bucket_files
        download_bucket_files(REPO, [(remote, old)], raise_on_missing_files=False)   # absent on the day's first run
    # types fixed by the Python values (float DOUBLE, int BIGINT, else text), never guessed, so a day's snapshots always union
    kind = lambda v: 'DOUBLE' if isinstance(v, float) else 'BOOLEAN' if isinstance(v, bool) else 'BIGINT' if isinstance(v, int) else 'VARCHAR'
    cols = {'snapshot': 'VARCHAR'}
    for row in rows:                         # the first non-null value of each field sets its type
        for k, v in row.items():
            if v is not None: cols.setdefault(k, kind(v))
    for row in rows: cols.update({k: 'VARCHAR' for k in row if k not in cols})   # fields null in every row: text
    # ponytail: a number field that is null in a day's first snapshot becomes text for that day; cast when reading if it bites
    spec = ', '.join(f"'{k}': '{t}'" for k, t in cols.items())
    new = f"SELECT * REPLACE (snapshot::TIMESTAMPTZ AS snapshot) FROM read_json('{src}', format='newline_delimited', columns={{{spec}}})"
    if name == 'roadworks':
        new = f"SELECT *, ST_GeomFromGeoJSON(geometry_json) AS geometry FROM ({new})"
    q = f"SELECT * FROM read_parquet('{old}') UNION ALL BY NAME {new}" if os.path.exists(old) else new
    con.execute(f"COPY ({q}) TO '{out}' (FORMAT parquet, COMPRESSION zstd)")
    return (out, remote), con.execute(f"SELECT count(DISTINCT snapshot) FROM '{out}'").fetchone()[0]


def main():
    test = sys.argv[1:] == ['test']
    out_dir = 'data' if test else '/tmp/hk-alerts'
    os.makedirs(out_dir, exist_ok=True)
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')
    files, report = [], {'run': now}
    for name, make in (('aqhi', aqhi), ('press', press), ('ev-chargers', ev_chargers), ('clp-chargers', clp_chargers)):
        try:
            d = make()
        except Exception as e:                                   # one source down: keep its last file, still publish the other
            print(f'::warning::{name}: {e}; keeping the last file'); report[name] = 'failed'; continue
        d['fetched'] = now
        path = os.path.join(out_dir, f'{name}.json')
        json.dump(d, open(path, 'w'), ensure_ascii=False, separators=(',', ':'))
        files.append((path, f'live/{name}.json'))
        report[name] = len(d.get('features') or d.get('items'))
    import duckdb
    con, w, t = duckdb.connect(), tempfile.mkdtemp(), datetime.datetime.now(datetime.UTC)
    con.execute('INSTALL spatial; LOAD spatial')
    for name, make in HISTORY.items():
        try:
            up, snaps = history(name, make, t, w, con, test)
        except Exception as e:
            print(f'::warning::{name}: {e}; skipped this run'); report[name] = 'failed'; continue
        if up:
            files.append(up)
            if test: os.replace(up[0], os.path.join(out_dir, os.path.basename(up[1])))
        report[name] = {'snapshots_today': snaps}
    if files and not test:
        from huggingface_hub import batch_bucket_files, create_bucket
        create_bucket(REPO, private=False, exist_ok=True)
        batch_bucket_files(REPO, add=files)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
