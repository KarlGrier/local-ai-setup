import json, sys, re, os
S='/home/USER/ai-speed-testing/strata-compare'
out=set()
for f in sys.argv[1:]:
    try: c=json.load(open(f))
    except Exception as e: print('ERR',f,e); continue
    s=json.dumps(c)
    paths=set(re.findall(r'/home/USER/[A-Za-z0-9_./@+-]+', s))
    print('==', f.replace(S+'/',''))
    for p in sorted(paths):
        q=p.replace(S+'/','')
        top='/'.join(q.split('/')[:2]) if q.startswith('models/') or q.startswith('bringup/') or q.startswith('results/') else q.split('/')[0]
        out.add(top if not q.startswith('/') else '/'.join(q.split('/')[:7]))
        print('   ', q)
print('TOPS:', sorted(out))
