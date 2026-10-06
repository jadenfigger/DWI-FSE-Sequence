"""Hash the delivered RF research artifacts without runtime private files."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
excluded={'provenance_manifest.json','__pycache__'}
private_suffixes={'.pem','.p12','.key'}
files={}
for p in sorted(root.rglob('*')):
    if not p.is_file() or any(x in excluded for x in p.relative_to(root).parts):continue
    if p.suffix.lower() in private_suffixes:raise RuntimeError('Private runtime artifact in RF deliverables: '+str(p))
    files[p.relative_to(root).as_posix()]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
manifest={'scope':'RF requirements, bounded author-toolbox designs and sampled validation; no console qualification',
  'source_repository':'https://github.com/LarsonLab/Spectral-Spatial-RF-Pulse-Design',
  'source_commit':'59f4f3a2f404dad147ef292a16cc00be63a77cd7',
  'source_archive_sha256':'21ccaecbbb6cd1e99a0e5384b2d0a34cbbb2d066cf8a277dc8a16fd6815d18f2',
  'runtime_preferences_excluded':'tmp/v19_matlab_prefs',
  'runtime_cache_excluded':'tmp/v19_rf_python_cache',
  'exact_Gibbons_replication':False,'console_verified':False,'files':files}
(root/'provenance_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('RF provenance hashes:',len(files),'files; private artifact suffix check passed.')
