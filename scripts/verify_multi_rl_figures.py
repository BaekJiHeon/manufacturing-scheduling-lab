import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.campaign import ROOT
from PIL import Image
rid=(ROOT/'reports/latest_multi_rl_run.txt').read_text().strip();folder=ROOT/'figures/publication'/rid
manifest=json.loads((folder/'manifest.json').read_text());checks=[]
for name in manifest['figures']:
    with Image.open(folder/(name+'.png')) as im:
        dpi=im.info.get('dpi');assert dpi and min(dpi)>599
        size=im.size
    assert '<image' not in (folder/(name+'.svg')).read_text()
    assert b'/Subtype /Image' not in (folder/(name+'.pdf')).read_bytes()
    checks.append(dict(name=name,dpi=dpi,size=size,svg_pdf_vector=True))
(ROOT/'reports/multi_rl_figure_validation.json').write_text(json.dumps(checks,indent=2));print('Verified figures:',len(checks))
