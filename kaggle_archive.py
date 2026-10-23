"""The live archive: every complete Hong Kong month of each live.py feed as its own public Kaggle dataset, created once and never
versioned or deleted (Kaggle public storage is free; Hugging Face keeps only the current month, see hf/README.md).
  helenkwok/hk-alerts-speeds-YYYY-MM        live/speeds-YYYY-MM-DD.parquet for every Hong Kong day of that month on the bucket
  helenkwok/hk-alerts-detectors-YYYY-MM     live/detectors-YYYY-MM-DD.parquet
  helenkwok/hk-alerts-journeytimes-YYYY-MM  live/journeytimes-YYYY-MM-DD.parquet
  helenkwok/hk-alerts-roadworks-YYYY-MM     live/roadworks-YYYY-MM-DD.parquet
A month's day files leave the bucket only after `kaggle datasets files` lists every one of them under its exact path and size. Runs weekly (archive.yml), so a month is archived within a week of ending.
Needs HF_TOKEN and KAGGLE_API_TOKEN. Usage: python3 kaggle_archive.py      (self-test, no network: python3 kaggle_archive.py test)"""
import datetime, json, os, re, subprocess, sys, tempfile, time
from huggingface_hub import batch_bucket_files, download_bucket_files, list_bucket_tree
import kaggle_mirror

REPO = 'milleleaf/hk-alerts'
DAY = re.compile(r'live/(speeds|detectors|journeytimes|roadworks)-(\d{4}-\d{2})-\d{2}\.parquet')
TITLE = {'speeds': 'road segment speeds', 'detectors': 'traffic detectors', 'journeytimes': 'journey times', 'roadworks': 'roadworks'}
slug = lambda feed, month: f"helenkwok/hk-alerts-{feed}-{month}"


def past_months(paths, now):
    """{(feed, month): [day paths]} for every month before now's UTC month"""
    this, out = now.strftime('%Y-%m'), {}
    for p in sorted(paths):
        if (m := DAY.fullmatch(p)) and m.group(2) < this: out.setdefault((m.group(1), m.group(2)), []).append(p)
    return out


def kaggle_files(out):
    """{name: bytes} from `kaggle datasets files -v` (CSV: name,size,creationDate after any warning lines)"""
    rows, seen = {}, False
    for line in out.splitlines():
        if line == 'name,size,creationDate': seen = True; continue
        if seen and (f := line.split(',')) and len(f) >= 3 and f[1].isdigit(): rows[f[0]] = int(f[1])
    return rows


def complete(listing, sizes):
    """every day file is on Kaggle under its exact path with its exact size (no substring or name-only match)"""
    return bool(sizes) and all(listing.get(p) == n for p, n in sizes.items())


def listed(s, sizes):
    r = subprocess.run(['kaggle', 'datasets', 'files', s, '-v', '--page-size', '200'], capture_output=True, text=True)
    return r.returncode == 0 and complete(kaggle_files(r.stdout), sizes)


def main():
    tree = {f.path: f.size for f in list_bucket_tree(REPO, prefix='live', recursive=True)}
    months = past_months(list(tree), datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))))
    done = []
    for (feed, month), paths in months.items():
        s, sizes = slug(feed, month), {p: tree[p] for p in paths}
        if not listed(s, sizes):
            if subprocess.run(['kaggle', 'datasets', 'files', s], capture_output=True).returncode == 0:
                print(f'::warning::{s} exists but does not list all {len(paths)} days: kept on the bucket, check by hand'); continue
            with tempfile.TemporaryDirectory() as root:
                download_bucket_files(REPO, [(p, os.path.join(root, p)) for p in paths])
                kaggle_mirror.mirror(s, f'Milleleaf: HK {TITLE[feed]} {month}', root, paths)
            for _ in range(30):                                        # Kaggle processes an upload before listing its files
                if listed(s, sizes): break
                time.sleep(60)
            else:
                print(f'::warning::{s}: not fully listed after 30 minutes; kept on the bucket'); continue
        batch_bucket_files(REPO, delete=paths)
        done.append({'feed': feed, 'month': month, 'dataset': f'https://www.kaggle.com/datasets/{s}', 'days': len(paths)})
    print(json.dumps({'archived': done}))


if __name__ == '__main__':
    if sys.argv[1:] == ['test']:
        p = ['live/press.json', 'live/speeds-2026-09-30.parquet', 'live/speeds-2026-10-01.parquet', 'live/speeds-2025-12-31.parquet',
             'live/detectors-2026-09-01.parquet', 'live/roadworks-2026-09-02.parquet', 'live/aqhi.json', 'live/ev-chargers.json']
        assert past_months(p, datetime.datetime(2026, 10, 5)) == {('speeds', '2025-12'): [p[3]], ('speeds', '2026-09'): [p[1]],
                                                                  ('detectors', '2026-09'): [p[4]], ('roadworks', '2026-09'): [p[5]]}
        assert slug('journeytimes', '2026-10') == 'helenkwok/hk-alerts-journeytimes-2026-10'
        assert all(6 <= len(f'Milleleaf: HK {t} 2026-10') <= 50 for t in TITLE.values())
        out = 'Warning: outdated\nNext Page Token = x\nname,size,creationDate\nlive/speeds-2026-09-30.parquet,100,2026-10-01 00:00:00\nlive/speeds-2026-09-3.parquet,7,2026-10-01 00:00:00\n'
        k = kaggle_files(out)
        assert k == {'live/speeds-2026-09-30.parquet': 100, 'live/speeds-2026-09-3.parquet': 7}
        assert complete(k, {'live/speeds-2026-09-30.parquet': 100})
        assert not complete(k, {'live/speeds-2026-09-30.parquet': 99})          # size differs
        assert not complete(k, {'speeds-2026-09-30.parquet': 100})              # name only, not the exact path
        assert not complete(k, {'live/speeds-2026-09-3.parquet': 7, 'live/speeds-2026-09-01.parquet': 5})   # one missing
        assert not complete(k, {})
        print('kaggle_archive: self-test ok')
    else:
        main()
