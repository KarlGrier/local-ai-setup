import os, collections, time
hub='/home/USER/.cache/huggingface/hub'
ref=collections.defaultdict(list)
for repo in sorted(os.listdir(hub)):
    if not repo.startswith('models--'): continue
    for root,dirs,files in os.walk(os.path.join(hub,repo,'snapshots')):
        for f in files:
            p=os.path.join(root,f); ref[os.path.realpath(p)].append(os.path.relpath(p,hub))
for root,dirs,files in os.walk(os.path.join(hub,'blobs')):
    for f in files:
        if f.endswith('.lock') : continue
        p=os.path.join(root,f); st=os.stat(p)
        if f.endswith('.refs'):
            continue
        if st.st_size>1e9 or p not in ref:
            r=ref.get(p,['ORPHAN'])
            rf=p+'.refs'
            rtxt=open(rf).read().strip().replace('\n',' ; ') if os.path.exists(rf) else ''
            print('%6.1f GB nlink=%d ino=%d %s %s  %s'%(st.st_blocks*512/1e9, st.st_nlink, st.st_ino, time.strftime('%m-%d',time.localtime(st.st_mtime)), r[0] if r[0]=='ORPHAN' else r[0].split('/')[-1], rtxt[:160] if r[0]=='ORPHAN' else ''))
