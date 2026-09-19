# -*- coding: utf-8 -*-
"""몬스터 몸체 10종 다크판타지 컨셉아트 (Pollinations). 클라이언트는 body_elem.png가 없으면 body_concept.png로 폴백한다.
python tools/gen_body_concepts.py"""
import urllib.parse, urllib.request, time, os
from PIL import Image
STYLE = "dark fantasy game creature concept art, dramatic rim lighting, rich saturated colors, painterly, highly detailed, Hades and Pokemon inspired, centered full body, dark cavern background, no text, "
BODIES = {
 "dragon": "a young dragon monster with molten cracks along its scales, wings folded, glowing eyes",
 "slime": "a translucent slime monster with a glowing core and mischievous face, dripping",
 "goblin": "a goblin monster warrior with oversized ears, patchwork armor, cunning grin",
 "fairy": "a dark fairy monster with luminous moth wings and tiny horns, floating",
 "golem": "a stone golem monster with runes glowing on its chest, moss and cracks",
 "unicorn": "a shadow unicorn monster with a crystal horn and starry mane",
 "phoenix": "a phoenix monster of violet and orange flame, wings spread",
 "sprite": "a small elemental sprite monster made of swirling wind and leaves, glowing eyes",
 "wisp": "a will-o-wisp monster, a ghostly floating flame with a mask-like face",
 "chimera": "a chimera monster with lion body and serpent tail, mane of fire",
}
os.makedirs("artwork/monsters", exist_ok=True)
for body, desc in BODIES.items():
    out = f"artwork/monsters/{body}_concept.png"
    if os.path.exists(out): print("skip", body); continue
    url = "https://image.pollinations.ai/prompt/"+urllib.parse.quote(STYLE+desc)+f"?width=768&height=768&seed={4300+len(body)*7}&nologo=true"
    for a in range(3):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=180).read()
            if len(data) < 20000: raise RuntimeError("small")
            tmp = out+".jpg"; open(tmp,"wb").write(data)
            im = Image.open(tmp).convert("RGB"); w,h = im.size; im = im.crop((0,0,w,int(h*0.955))).resize((512,512), Image.LANCZOS); im.save(out); os.remove(tmp)
            print("ok", body, flush=True); break
        except Exception as e: print("retry", body, e, flush=True); time.sleep(8)
    time.sleep(3)
print("ALL DONE")
