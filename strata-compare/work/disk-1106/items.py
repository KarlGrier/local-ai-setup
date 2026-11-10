import os, sys, json, glob, time
S='/home/USER/ai-speed-testing/strata-compare'
HF='/home/USER/.cache/huggingface/hub'
QHF=HF+'/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66'
def real(paths):
    out=[]
    for p in paths:
        out+=sorted(glob.glob(p)) if any(c in p for c in '*?[') else [p]
    return out
def files_of(p):
    if os.path.islink(p):
        t=os.path.realpath(p); return [t] if os.path.isfile(t) else []
    if os.path.isfile(p): return [p]
    r=[]
    for root,ds,fs in os.walk(p):
        for f in fs:
            q=os.path.join(root,f)
            if not os.path.islink(q): r.append(q)
            elif '/.cache/huggingface/' in q and os.path.isfile(os.path.realpath(q)): r.append(os.path.realpath(q))
    return r
def measure(paths):
    ino={}; mt=0
    for p in real(paths):
        for f in files_of(p):
            try: st=os.lstat(f)
            except OSError: continue
            k=(st.st_dev,st.st_ino)
            if k not in ino: ino[k]=[st.st_blocks*512,st.st_nlink,0]
            ino[k][2]+=1; mt=max(mt,st.st_mtime)
    freed=sum(v[0] for v in ino.values() if v[2]>=v[1])
    shared=sum(v[0] for v in ino.values() if v[2]<v[1])
    return freed, shared, mt, ino
items=json.load(open(sys.argv[1]))
allino={}
res=[]
for it in items:
    paths=[p.replace('$S',S).replace('$HF',HF).replace('$QHF',QHF) for p in it['paths']]
    missing=[p for p in real(paths) if not os.path.lexists(p)] + [p for p in paths if not real([p])]
    f,s,mt,ino=measure(paths)
    res.append(dict(id=it['id'],verdict=it['verdict'],gb=f/1e9,shared_gb=s/1e9,mtime=time.strftime('%Y-%m-%d',time.localtime(mt)) if mt else '-',missing=missing))
    it['_ino']=ino
json.dump(res,open(sys.argv[2],'w'),indent=1)
# set totals (union by inode, freed only if all links inside the set)
for v in sorted(set(i['verdict'] for i in items)):
    u={}
    for it in items:
        if it['verdict']!=v: continue
        for k,x in it['_ino'].items():
            if k in u: u[k][2]+=x[2]
            else: u[k]=list(x)
    print('SET %-10s %8.2f GB freed (links outside the set: %.2f GB)'%(v, sum(x[0] for x in u.values() if x[2]>=x[1])/1e9, sum(x[0] for x in u.values() if x[2]<x[1])/1e9))
for r in res: print('%8.2f GB shared %6.2f %s %-8s %s %s'%(r['gb'],r['shared_gb'],r['mtime'],r['verdict'],r['id'],('MISSING '+str(r['missing'])) if r['missing'] else ''))
