import os, time, numpy as np, sherpa_onnx
SR=16000; CHUNK=int(0.1*SR); TAIL=np.zeros(int(0.66*SR),dtype=np.float32)
MODELS={
 "nemotron":dict(prefix="",suffix=".int8.onnx",feature_dim=128,model_type=os.environ.get("NEMOTRON_MODEL_TYPE","")),
 "zip0626":dict(prefix="",suffix="-epoch-99-avg-1-chunk-16-left-128.int8.onnx",feature_dim=80,model_type=""),
 "zip0621":dict(prefix="",suffix="-epoch-99-avg-1.int8.onnx",feature_dim=80,model_type=""),
}
def mk(name,models_root):
    c=MODELS[name]; d=f"{models_root}/{name}"
    return sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=f"{d}/tokens.txt",encoder=f"{d}/encoder{c['suffix']}",decoder=f"{d}/decoder{c['suffix']}",
        joiner=f"{d}/joiner{c['suffix']}",num_threads=2,sample_rate=SR,feature_dim=c["feature_dim"],
        decoding_method="greedy_search",enable_endpoint_detection=False,model_type=c["model_type"])
def decode(rc,x):
    """Streaming decode; returns (text, seconds spent in accept/decode)."""
    t=time.perf_counter(); s=rc.create_stream()
    for i in range(0,len(x),CHUNK):
        s.accept_waveform(SR,x[i:i+CHUNK])
        while rc.is_ready(s): rc.decode_stream(s)
    s.accept_waveform(SR,TAIL); s.input_finished()
    while rc.is_ready(s): rc.decode_stream(s)
    txt=rc.get_result(s); return (txt if isinstance(txt,str) else txt.text), time.perf_counter()-t
