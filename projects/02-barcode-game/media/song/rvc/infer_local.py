# -*- coding: utf-8 -*-
"""로컬 CPU에서 RVC 추론. 사용: python infer_local.py <vocal.wav> [pitch]
사전: pip install rvc-python  /  models/ajossi.pth, models/added_*.index 필요"""
import sys, glob, os
from rvc_python.infer import RVCInference
src = sys.argv[1]; pitch = int(sys.argv[2]) if len(sys.argv) > 2 else 0
idx = (glob.glob("models/added_*.index") or [None])[0]
rvc = RVCInference(device="cpu")
rvc.load_model("models/ajossi.pth", index_path=idx)
rvc.set_params(f0method="rmvpe", f0up_key=pitch, index_rate=0.6, protect=0.33)
out = os.path.splitext(src)[0] + "_ajossi.wav"
rvc.infer_file(src, out); print("saved", out)
