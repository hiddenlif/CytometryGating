"""Check committed report integrity without downloading or opening raw FCS data."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    assets = ROOT / 'docs/assets/testing'
    manifest = json.loads((assets / 'plot-manifest.json').read_text())
    source = ROOT / 'data/manifests/public-files.json'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['source_manifest_sha256'], 'Plot source manifest changed'
    with (assets / 'file-results.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == manifest['files_plotted'], 'File result count differs'
    # Resolve only safe repository-relative references; raw data remain excluded.
    figures = []
    for row in rows:
        image = (assets / row['image']).resolve()
        assert image.is_relative_to(assets.resolve()), 'Figure path escapes assets'
        assert image.is_file(), f'Missing figure: {image.name}'
        figures.append(image)
    review_dir = assets / 'reviews/nk-her2-v1'
    review = json.loads((review_dir / 'results.json').read_text())
    for name, digest in review['figure_sha256'].items():
        image = (review_dir / name).resolve()
        assert image.is_relative_to(review_dir.resolve()), 'Review figure escapes assets'
        assert hashlib.sha256(image.read_bytes()).hexdigest() == digest, f'Review figure changed: {name}'
    assert hashlib.sha256((review_dir / 'configuration.json').read_bytes()).hexdigest() == review['configuration_sha256'], 'Review configuration changed'
    print(json.dumps({'file_figures_present': len(figures), 'review_figures_verified': len(review['figure_sha256']), 'source_manifest_verified': True}))


if __name__ == '__main__':
    main()
