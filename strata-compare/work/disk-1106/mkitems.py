import json
S='$S'; HF='$HF'
orph=json.load(open('/home/USER/ai-speed-testing/strata-compare/work/disk-1106/orphans.json'))
old_wt=['r22p021','r22port','r22p021n','r22p022n','r22p022','r22p028xm','r22p028m','r22p027m','r23decode','r22p0210m','r22s0210t','v0210stock','r22p028','r22p027','r22p021mt','v021stock','v024','v026p343-iqq8k','v026iqq8k','v026p343-slotram','v026fix','v026test','v026p343','r21think']
old_eng=['r22p0210m','r23decode','r22s0210t','v0210stock','r22p028xm','r22p028m','r22p028','r22p027m','r22p027','r22p027m-g12','r22p027-g12','r22p021mt']
nm='$S/results/r23/nll-many/gap/'
I=[
 # DELETE OK now
 dict(id='nvfp4', verdict='NOW', paths=[S+'/models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata']),
 dict(id='hf-orphans', verdict='NOW', paths=[p for k,v in orph.items() for p in v]),
 dict(id='tmp-r6', verdict='NOW', paths=[S+'/tmp/r6']),
 dict(id='results-r12-oracle', verdict='NOW', paths=[S+'/results/r12/oracle']),
 dict(id='tmp-r12', verdict='NOW', paths=[S+'/tmp/r12']),
 dict(id='old-wt-builds', verdict='NOW', paths=[S+'/strata-%s/build*'%w for w in old_wt]),
 dict(id='old-engines', verdict='NOW', paths=[S+'/engine-%s'%e for e in old_eng]),
 dict(id='work-r9-q4-pack', verdict='NOW', paths=[S+'/work/r9/q4/packs']),
 dict(id='old-logs', verdict='NOW', paths=[S+'/logs/r%d'%i for i in (2,3,4,6,7,8,9,10,11,12,13,14,15,16,17,18)]),
 dict(id='tmp-usability', verdict='NOW', paths=[S+'/tmp/usability']),
 dict(id='r22-old-pfy', verdict='NOW', paths=[S+'/results/r22/gap7/pfy',S+'/results/r22/gap9/pfy80']),
 dict(id='bringup-tmp', verdict='NOW', paths=[S+'/bringup/out/tmp']),
 # AFTER v3.1 + follow-up
 dict(id='ud31-iq3xxs', verdict='AFTER', paths=[S+'/models/unsloth-v31/UD-IQ3_XXS']),
 dict(id='ud31-splice-s', verdict='AFTER', paths=[S+'/models/unsloth-v31/splice-S']),
 dict(id='ud31-mtp-bf16', verdict='AFTER', paths=[S+'/models/unsloth-v31/MTP']),
 dict(id='ud31-packs', verdict='AFTER', paths=[S+'/bringup/out/ud31']),
 dict(id='ud31-nll-dumps', verdict='AFTER', paths=[S+'/results/r23/ud31/gap/nll/P',S+'/results/r23/ud31/gap/nll/U',S+'/results/r23/ud31/gap/nll/S',S+'/results/r23/ud31/gap/nll/R']),
 dict(id='nllmany-unused-arms', verdict='AFTER', paths=[nm+a for a in ('ref','ref2','cpushare','unfused','v2','x28h-nov2','r28h')]),
 dict(id='gdn-nll-arms', verdict='AFTER', paths=['$S/results/r23/gdn-nll/gap/'+a for a in ('s210','s210cpu','s210gdn','s210unf')]),
 # ASK
 dict(id='hf-udq4kxl', verdict='ASK', paths=['$QHF/UD-Q4_K_XL','$QHF/MTP','$QHF/mmproj-F16.gguf']),
 dict(id='r15-splice', verdict='ASK', paths=[S+'/models/r15',S+'/bringup/out/sweep-splice']),
 dict(id='basalt-020', verdict='ASK', paths=['/home/USER/ai-speed-testing/basalt-020']),
 dict(id='hf-qwen-image', verdict='ASK', paths=[HF+'/models--Qwen--Qwen-Image-2.1/snapshots',HF+'/models--unsloth--Qwen-Image-2.1-FP8/snapshots',HF+'/models--unsloth--Qwen-Image-2.1-GGUF/snapshots']),
 dict(id='comfyui', verdict='ASK', paths=['/home/USER/ai/ComfyUI']),
 dict(id='unsloth-studio', verdict='ASK', paths=['/home/USER/.unsloth']),
 dict(id='dr-old-venv', verdict='ASK', paths=['/home/USER/ai/deep-research/.venv-py3.12.3']),
 dict(id='strata-mtp-tensors', verdict='ASK', paths=[S+'/strata/mtp/tensors',S+'/strata/mtp/mtp-q2_0.gguf',S+'/strata/packs']),
 dict(id='flash-next', verdict='ASK', paths=['/home/USER/ai/flash-next']),
 dict(id='lucebox-raw', verdict='ASK', paths=[S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/lucebox-dspark/DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf']),
 dict(id='ds-results-slots', verdict='ASK', paths=[S+'/results/ds41/after',S+'/results/ds41/tuning',S+'/results/ds41/hard',S+'/results/ds41/ctx128']),
 dict(id='ds-gate-slots-old', verdict='ASK', paths=[S+'/logs/ds41/gate-slots/A',S+'/logs/ds41/gate-slots/AL',S+'/logs/ds41/gate-slots/B',S+'/logs/ds41/gate-slots/BL']),
 dict(id='ds-slots-aside', verdict='ASK', paths=[S+'/logs/ds41/ds4-slots-sweep-1103-aside']),
 # KEEP (sizes for the table)
 dict(id='K-deepseek', verdict='KEEP', paths=[S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-0000*-of-00004.gguf',S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf',S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf',S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/pack-ist-das-2.00bpw*',S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/README.md',S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/tensor-allocation',S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/DeepSeek-V4.1-Flash-1017-UD-Q8_K_XL-00001-of-00009.gguf']),
 dict(id='K-lucebox-conv', verdict='KEEP', paths=[S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/lucebox-dspark/dspark-lucebox-Q2K-Q4K-converted.gguf',S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/lucebox-dspark/header.bin',S+'/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/lucebox-dspark/README.md']),
 dict(id='K-glm', verdict='KEEP', paths=[HF+'/models--unsloth--GLM-5.3-Flash-GGUF/snapshots']),
 dict(id='K-ista', verdict='KEEP', paths=[S+'/models/ISTA-GSQ-RCO']),
 dict(id='K-vision', verdict='KEEP', paths=[S+'/models/vision-r22',S+'/models/mtp-stock',S+'/models/mtp-basalt']),
 dict(id='K-trees', verdict='KEEP', paths=[S+'/strata-%s'%w for w in ('r22p028x','r22p021m','cstar18','v0115','r23p0211','v0211stock','r22p0210','r22s028t','r23basalt','v026')]+[S+'/engine-%s'%e for e in ('r22p028x','r22p021m','r22p021','cstar18','r23p0211','v0211stock','r22p0210','r22s028t','r23basalt-fix','r23basalt','v026p343-slotram-ds41','r22p021n','v024-ds41','v026-ds41','v026fix-ds41','v026test-ds41','v026iqq8k-ds41','v026p343-iqq8k-ds41','v026p343-ds41')]),
 dict(id='K-old-wt-src', verdict='KEEPSRC', paths=[S+'/strata-%s'%w for w in old_wt]),
 dict(id='K-r20a', verdict='KEEP', paths=[S+'/bringup/out/r20a',S+'/bringup/out/logs']),
 dict(id='K-refs', verdict='KEEP', paths=[S+'/results/r22/gap8',S+'/results/r22/gap16',S+'/results/r22/gap17',nm+'x28h',nm+'x28h-unfused',nm+'x28h-cpushare',S+'/results/r23/decpath']),
 dict(id='K-venvs', verdict='KEEP', paths=[S+'/.venv','/home/USER/ai/deep-research/.venv']),
 dict(id='K-dr-runs', verdict='KEEP', paths=['/home/USER/ai/deep-research/results/bench2','/home/USER/ai/deep-research/staging','/home/USER/ai/deep-research/logs']),
 dict(id='K-basalt-ab', verdict='KEEP', paths=['/home/USER/ai-speed-testing/basalt-ab']),
]
json.dump(I,open('/home/USER/ai-speed-testing/strata-compare/work/disk-1106/items.json','w'),indent=1)
print(len(I))
