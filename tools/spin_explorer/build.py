"""Bundle the spin explorer into one self-contained HTML file.

python tools/spin_explorer/build.py            -> tools/spin_explorer/spin_explorer.html
python tools/spin_explorer/build.py --fragment out.html   (body-only variant, no <html>/<head> wrapper)

Inlines template.html, engine.js, app.js and every sequences/*.seq file.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def bundle():
    seqs = {p.stem: p.read_text() for p in sorted((HERE / 'sequences').glob('*.seq'))}
    payload = 'window.SEQ_FILES = ' + json.dumps(seqs).replace('</', '<\\/') + ';'
    html = (HERE / 'template.html').read_text()
    for marker, text in (('/*@SEQS@*/', payload),
                         ('/*@ENGINE@*/', (HERE / 'engine.js').read_text()),
                         ('/*@APP@*/', (HERE / 'app.js').read_text())):
        assert marker in html, marker
        html = html.replace(marker, text.replace('</script', '<\\/script'))
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fragment', help='also write the page without the document wrapper')
    args = ap.parse_args()
    body = bundle()
    page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    out = HERE / 'spin_explorer.html'
    out.write_text(page)
    print(f'wrote {out} ({len(page) / 1024:.0f} kB)')
    if args.fragment:
        Path(args.fragment).write_text(body)
        print(f'wrote {args.fragment}')


if __name__ == '__main__':
    main()
