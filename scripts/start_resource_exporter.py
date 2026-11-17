from pathlib import Path
import os,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]
pid_file=ROOT/'runtime/resource_exporter.pid'
try:
    with urllib.request.urlopen('http://127.0.0.1:9108/metrics',timeout=2) as response:
        if 'manufacturing_cpu_percent' in response.read().decode():
            print('Resource exporter already healthy');raise SystemExit(0)
except OSError:pass
with (ROOT/'logs/resource_exporter.log').open('a') as log:
    process=subprocess.Popen([sys.executable,str(ROOT/'scripts/resource_exporter.py')],cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
pid_file.write_text(str(process.pid)+'\n')
for _ in range(20):
    if process.poll() is not None:raise RuntimeError('Exporter exited; inspect logs/resource_exporter.log')
    try:
        with urllib.request.urlopen('http://127.0.0.1:9108/metrics',timeout=1) as response:
            print(response.read().decode());break
    except OSError:time.sleep(.5)
else:raise RuntimeError('Exporter startup timed out')
