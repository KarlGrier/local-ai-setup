import os, collections, time
hub='/home/USER/.cache/huggingface/hub'
ref=collections.defaultdict(list)
for repo in sorted(os.listdir(hub)):
    if not repo.startswith('models--'): continue
    for root,dirs,files in os.walk(os.path.join(hub,repo,'snapshots')):
        for f in files:
            p=os.path.join(root,f)
            t=os.path.realpath(p)
            ref[t].append(os.path.relpath(p,hub))
by=collections.defaultdict(int); mt={}
allblob={}
for root,dirs,files in os.walk(os.path.join(hub,'blobs')):
    for f in files:
        if f.endswith('.lock') or f.endswith('.refs'): continue
        p=os.path.join(root,f); st=os.stat(p); allblob[p]=st
for p,st in allblob.items():
    sz=st.st_blocks*512
    if p in ref:
        rs=ref[p]
        keys=set()
        for r in rs:
            parts=r.split('/')
            keys.add(parts[0][8:]+' | rev '+parts[2][:8]+' | '+('/'.join(parts[3:-1]) or '.'))
        k=' + '.join(sorted(keys))
    else:
        k='ORPHAN'
    by[k]+=sz; mt[k]=max(mt.get(k,0),st.st_mtime)
for k,v in sorted(by.items(), key=lambda x:-x[1]):
    print('%8.1f GB  %s  %s'%(v/1e9,time.strftime('%Y-%m-%d',time.localtime(mt[k])),k))
print('missing targets:', [ (t,r[:1]) for t,r in ref.items() if not os.path.exists(t)][:5])
print('per-repo blobs dirs:')
for repo in sorted(os.listdir(hub)):
    b=os.path.join(hub,repo,'blobs')
    if os.path.isdir(b):
        n=0;s=0
        for f in os.listdir(b):
            q=os.path.join(b,f)
            if os.path.islink(q): n+=1
            elif os.path.isfile(q): s+=os.stat(q).st_blocks*512
        print(repo, 'links',n,'real bytes %.1f GB'%(s/1e9))
