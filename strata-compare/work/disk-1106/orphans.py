import os, json
hub='/home/USER/.cache/huggingface/hub'
ref=set()
for repo in os.listdir(hub):
    if repo.startswith('models--'):
        for root,ds,fs in os.walk(os.path.join(hub,repo,'snapshots')):
            for f in fs: ref.add(os.path.realpath(os.path.join(root,f)))
out={}
for root,ds,fs in os.walk(os.path.join(hub,'blobs')):
    for f in fs:
        if f.endswith('.lock') or f.endswith('.refs'): continue
        p=os.path.join(root,f)
        if p in ref: continue
        rf=p+'.refs'; owner=open(rf).read().split('/blobs/')[0].strip() if os.path.exists(rf) else '?'
        out.setdefault(owner,[]).append(p)
        if os.path.exists(rf): out[owner].append(rf)
json.dump(out,open('/home/USER/ai-speed-testing/strata-compare/work/disk-1106/orphans.json','w'),indent=1)
for k,v in out.items(): print(k, len(v))
