import sys, os, glob, json
import jiwer, numpy as np
from whisper_normalizer.english import EnglishTextNormalizer
en=EnglishTextNormalizer()
data_root,res_dir=sys.argv[1:3]; models=["nemotron","zip0626","zip0621"]
raw={m:json.load(open(f"{res_dir}/raw_{m}.json")) for m in models}
out={}
for js in sorted(glob.glob(f"{data_root}/clips/*.json")):
    set_=os.path.basename(js)[:-5]; rows=json.load(open(js))
    refs=[en(r["ref"].lower()) for r in rows]; keep=[i for i,r in enumerate(refs) if r.strip()]
    for cond in ("clean","babble5dB"):
        k=f"{set_}/{cond}"
        if k not in raw["nemotron"]: continue
        h={m:[en(t.lower()) for t in raw[m][k]["hyps"]] for m in models}
        audio=raw["nemotron"][k]["audio_s"]
        wer={m:round(jiwer.wer([refs[i] for i in keep],[h[m][i] for i in keep])*100,2) for m in models}
        pc={m:np.array([jiwer.wer(refs[i],h[m][i]) if h[m][i] else 1.0 for i in keep]) for m in models}
        paired={f"{z}_vs_nemotron":{"better":int((pc[z]<pc["nemotron"]).sum()),"worse":int((pc[z]>pc["nemotron"]).sum())} for z in ("zip0626","zip0621")}
        out[k]={"n":len(keep),"audio_s":round(audio,1),"wer_pct":wer,
                "rtfx":{m:round(raw[m][k]["audio_s"]/raw[m][k]["decode_s"],1) for m in models},"paired_per_clip":paired}
        print(k,out[k])
json.dump(out,open(f"{res_dir}/bench_out.json","w"),indent=1)
