import os, glob, subprocess, time
S='/home/USER/ai-speed-testing/strata-compare'
def du(p):
    r=subprocess.run(['du','-sB1',p],capture_output=True,text=True)
    try: return int(r.stdout.split()[0])
    except: return 0
cfgs=[]
for f in glob.glob(S+'/configs/**/*.json',recursive=True):
    try: cfgs.append((f,open(f,errors='replace').read()))
    except: pass
rows=[]
for d in sorted(glob.glob(S+'/strata')+glob.glob(S+'/strata-*')+glob.glob(S+'/engine-*')):
    if not os.path.isdir(d): continue
    t=du(d); b=sum(du(x) for x in glob.glob(d+'/build*') if os.path.isdir(x))
    g='wt' if os.path.isfile(d+'/.git') else ('repo' if os.path.isdir(d+'/.git') else '-')
    name=os.path.basename(d)
    refs=[f for f,txt in cfgs if '/'+name+'/' in txt]
    newest=max([os.path.getmtime(f) for f in refs], default=0)
    rows.append((t,b,g,time.strftime('%m-%d',time.localtime(os.path.getmtime(d))),len(refs),time.strftime('%m-%d',time.localtime(newest)) if newest else '-',name))
rows.sort(reverse=True)
for r in rows: print('%6.2f GB (build %5.2f) %-4s mt %s cfgrefs %4d newest %s  %s'%(r[0]/1e9,r[1]/1e9,r[2],r[3],r[4],r[5],r[6]))
print('TOTAL %.1f GB'%(sum(r[0] for r in rows)/1e9))
