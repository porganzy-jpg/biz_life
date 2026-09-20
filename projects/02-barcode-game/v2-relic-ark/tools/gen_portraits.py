# -*- coding: utf-8 -*-
"""역할별 전신 일러스트(명단·카드용) 생성. 큰 해상도에서 500이 나면 작은 해상도·turbo로 폴백."""
import urllib.parse, urllib.request, time, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "art_raw" / "portraits"; OUT.mkdir(parents=True, exist_ok=True)
ROLES = {"scout": "a young Korean woman scout with a khaki hooded jacket, backpack and binoculars around her neck",
         "cook": "a cheerful middle-aged Korean man cook with a white apron, headscarf and a dented pot",
         "medic": "a calm Korean woman medic with a white coat, red cross armband and a green first aid bag",
         "engineer": "a Korean man engineer with goggles on his forehead, tool belt and a wrench, oil-stained gloves",
         "farmer": "an elderly Korean farmer with a straw hat, rolled sleeves and a green watering can",
         "scholar": "a Korean woman scholar with round glasses, cardigan, hugging a thick old book and blueprints",
         "trader": "a smiling Korean man trader with a long coat, wide hat, red scarf and a bag of bartered goods",
         "kid": "a small Korean child in an oversized yellow raincoat and rubber boots holding a plush toy"}
STYLE = (", full body standing, front three-quarter view, post-apocalyptic survivor, worn but colorful clothes, "
         "anime game character design illustration, clean line art, soft cel shading, warm lantern light, "
         "plain light beige background, no text, no watermark, highly detailed")
ATTEMPTS = [(768, 1024, "flux"), (512, 704, "flux"), (512, 704, "turbo"), (384, 512, "turbo")]
for i, (k, d) in enumerate(ROLES.items()):
    out = OUT / f"{k}.jpg"
    if out.exists() and out.stat().st_size > 15000: print("skip", k); continue
    for (w, h, model) in ATTEMPTS:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote("character design of " + d + STYLE) + f"?width={w}&height={h}&seed={7000+i}&nologo=true&model={model}"
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=200).read()
            if len(b) < 12000: raise RuntimeError(f"small {len(b)}")
            out.write_bytes(b); print("ok", k, w, h, model, len(b) // 1024, "KB", flush=True); break
        except Exception as e:
            print("retry", k, w, h, model, str(e)[:60], flush=True); time.sleep(6)
    time.sleep(3)
print("PORTRAITS DONE", flush=True)
