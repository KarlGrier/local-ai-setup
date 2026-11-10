import os, sys, collections, time
S='/home/USER/ai-speed-testing/strata-compare'
roots=[S+'/configs',S+'/work',S+'/bringup/lib',S+'/bringup/patchtest.sh','/home/USER/ai/deep-research/staging',S+'/scripts',S+'/run-strata.sh',S+'/switch-model.sh']
skipdirs={'disk-1106','__pycache__','pycache'}
toks={'nvfp4':'Maximilian228','orph-abiray':'Abiray--Qwen-Image','orph-aben':'abenzerps','tmp-r6':'tmp/r6','r12-oracle':'results/r12/oracle','tmp-r12':'tmp/r12','r9-pack':'work/r9/q4/packs','logs-old':'logs/r1','tmp-usab':'tmp/usability','r22-gap7pfy':'gap7/pfy','r22-gap9pfy':'gap9/pfy80','ud31-iq3xxs':'unsloth-v31/UD-IQ3_XXS','ud31-splice':'unsloth-v31/splice-S','ud31-mtp':'unsloth-v31/MTP','ud31-packs':'bringup/out/ud31','nllmany':'nll-many/gap','gdn':'gdn-nll/gap','hf-udq4':'38bb39ee97821de2c9009abb7e93950eec396e66','r15':'r15/splice-q5','sweep-splice':'bringup/out/sweep-splice','basalt020':'basalt-020','qimg':'Qwen-Image-2.1','comfy':'ai/ComfyUI','unsloth':'.unsloth/','oldvenv':'venv-py3.12.3','mtptensors':'strata/mtp/tensors','flashnext':'ai/flash-next','luceraw':'DSpark-draft-Q2K-Q4K.gguf','ds-after':'results/ds41/after','ds-tuning':'results/ds41/tuning','ds-hard':'results/ds41/hard','aside':'sweep-1103-aside','gateslots':'gate-slots/'}
hits=collections.defaultdict(list)
for r in roots:
    files=[r] if os.path.isfile(r) else [os.path.join(a,f) for a,ds,fs in os.walk(r) if not any(x in a.split('/') for x in skipdirs) for f in fs]
    for f in files:
        if f.endswith(('.pyc','.npy','.bin','.gguf','.log')) : continue
        try:
            if os.path.getsize(f)>20e6: continue
            t=open(f,errors='replace').read()
        except Exception: continue
        for k,v in toks.items():
            if v in t: hits[k].append(f)
for k in toks:
    fs=hits.get(k,[])
    tops=collections.Counter('/'.join(f.replace(S+'/','').replace('/home/USER/ai/deep-research/','dr/').split('/')[:2]) for f in fs)
    newest=max(fs,key=os.path.getmtime) if fs else None
    print('%-12s %4d files; newest %s %s; by dir %s'%(k,len(fs),time.strftime('%m-%d',time.localtime(os.path.getmtime(newest))) if newest else '-', (newest or '').replace(S+'/',''), dict(tops.most_common(4))))
