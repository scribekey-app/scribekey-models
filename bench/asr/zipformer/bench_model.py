# Streaming decode of every clip/condition for ONE model; mixture generation mirrors
# /home/user/scribekey-models/bench/asr/bench.py exactly (rng seed 1, same set order, 3 others at -5 dB).
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, soundfile as sf
from common import mk, decode
name,models_root,data_root,out=sys.argv[1:5]
# Optional supplementary mode: PEAK_NORM=0.9 scales every final (post-mix) clip to that peak; ONLY_SET limits sets
# (rng is still consumed for skipped sets so mixtures stay identical to the main run).
PEAK=float(os.environ.get("PEAK_NORM","0")); ONLY=os.environ.get("ONLY_SET","")
rc=mk(name,models_root); rng=np.random.default_rng(1)
def load(p):
    x,sr=sf.read(p,dtype="float32"); assert sr==16000,sr; return x
res={}
for js in sorted(glob.glob(f"{data_root}/clips/*.json")):
    set_=os.path.basename(js)[:-5]; rows=json.load(open(js)); pool=[load(r["wav"]) for r in rows]
    for cond in ("clean","babble5dB"):
        hyps=[];secs=[];tm=0.
        for i,r in enumerate(rows):
            x=pool[i]
            if cond!="clean":
                b=np.zeros_like(x)
                for j in rng.choice(len(pool),3,replace=False):
                    y=pool[j]; y=np.resize(y,len(x)); b+=y
                g=np.sqrt(np.mean(x**2)/(np.mean(b**2)+1e-9)/10**(5/10)); x=(x+g*b).astype(np.float32)
            if ONLY and set_!=ONLY: continue
            if PEAK: x=(x*(PEAK/max(np.abs(x).max(),1e-9))).astype(np.float32)
            txt,dt=decode(rc,x); tm+=dt; hyps.append(txt); secs.append(len(x)/16000)
        if ONLY and set_!=ONLY: continue
        res[f"{set_}/{cond}"]={"hyps":hyps,"audio_s":sum(secs),"decode_s":tm}
        print(name,set_,cond,"audio",round(sum(secs)),"rtfx",round(sum(secs)/tm,1),flush=True)
json.dump(res,open(out,"w"))
