# -*- coding: utf-8 -*-
"""「천국 가는 버스」 — 독거아조씨 음역(말소리 F0 중앙값 ≈ A2)에 맞춘 작곡.
멜로디 음역 D3~D4 (베이스-바리톤 편안한 구간). G장조, 76bpm.
python compose.py  →  song_full.musicxml / song_guide.mid / song_backing.musicxml
"""
from music21 import stream, note, chord, tempo, meter, key, instrument, metadata, expressions, dynamics, bar
from music21 import harmony, clef

TITLE = "천국 가는 버스"
BPM = 76
# (가사줄, [(음, 길이)...])  길이: q=1 e=0.5 h=2 w=4
VERSE_RHY = [1,1,1,1,1,1,2]            # 7음절
CHORUS_RHY = [1,1,.5,.5,1,1,1,2]       # 8음절
OUTRO_RHY = [1,1,1,1,2,2]              # 6음절

SECTIONS = [
 ("verse1", [
   ("혼자 먹는 저녁 밥",  ["G3","A3","B3","A3","G3","E3","D3"], VERSE_RHY, ["G","G","Em","Em"]),
   ("티브이는 켜둔 채",   ["D3","E3","G3","G3","A3","B3","A3"], VERSE_RHY, None),
   ("곁에 작은 숨소리",   ["B3","B3","A3","G3","A3","G3","E3"], VERSE_RHY, ["C","C","D","D"]),
   ("그거면 됐다 했지",   ["E3","G3","A3","G3","E3","D3","G3"], VERSE_RHY, None),
 ]),
 ("chorus", [
   ("가자 우리 천국 버스", ["D4","B3","D4","D4","B3","A3","G3","A3"], CHORUS_RHY, ["C","G","D","Em"]),
   ("지붕 위엔 빨래 펄럭", ["B3","B3","C4","C4","B3","A3","B3","G3"], CHORUS_RHY, None),
   ("못 가 본 바다까지도", ["D4","D4","D4","C4","B3","A3","B3","D4"], CHORUS_RHY, ["C","G","D","G"]),
   ("너와 함께 가는 이 길", ["B3","A3","G3","A3","B3","A3","G3","G3"], CHORUS_RHY, None),
 ]),
 ("verse2", [
   ("아픈 날은 두고 가",   ["G3","A3","B3","A3","G3","E3","D3"], VERSE_RHY, ["G","G","Em","Em"]),
   ("창밖엔 벚꽃이 져",    ["D3","E3","G3","G3","A3","B3","A3"], VERSE_RHY, None),
   ("눈 감고도 웃는 너",   ["B3","B3","A3","G3","A3","G3","E3"], VERSE_RHY, ["C","C","D","D"]),
   ("바다 냄새가 난다",    ["E3","G3","A3","G3","E3","D3","G3"], VERSE_RHY, None),
 ]),
 ("chorus2", [
   ("가자 우리 천국 버스", ["D4","B3","D4","D4","B3","A3","G3","A3"], CHORUS_RHY, ["C","G","D","Em"]),
   ("지붕 위엔 빨래 펄럭", ["B3","B3","C4","C4","B3","A3","B3","G3"], CHORUS_RHY, None),
   ("못 가 본 바다까지도", ["D4","D4","D4","C4","B3","A3","B3","D4"], CHORUS_RHY, ["C","G","D","G"]),
   ("너와 함께 가는 이 길", ["B3","A3","G3","A3","B3","A3","G3","G3"], CHORUS_RHY, None),
 ]),
 ("outro", [
   ("이렇게 살아도",       ["D3","E3","G3","A3","B3","A3"], OUTRO_RHY, ["C","D","G","G"]),
   ("우린 잘 삽니다",      ["G3","A3","G3","E3","D3","D3"], OUTRO_RHY, None),
 ]),
]
CHORD_NOTES = {"G":["G2","B2","D3","G3"], "Em":["E2","G2","B2","E3"], "C":["C3","E3","G3","C4"], "D":["D3","F#3","A3","D4"]}

def syllables(line): return [c for c in line if c.strip()]

def build(with_melody=True, with_backing=True):
    sc = stream.Score(); sc.metadata = metadata.Metadata(title=TITLE, composer="독거아조씨 × Claude")
    mel = stream.Part(); mel.id="Vocal"; mel.insert(0, instrument.Vocalist() if with_melody else instrument.Piano())
    acc = stream.Part(); acc.id="Piano"; acc.insert(0, instrument.Piano())
    acc.append(clef.BassClef())
    for p in (mel, acc):
        p.append(tempo.MetronomeMark(number=BPM)); p.append(meter.TimeSignature('4/4')); p.append(key.Key('G'))
    chords_seq = []
    for sec, lines in SECTIONS:
        for text, pitches, rhy, ch in lines:
            syl = syllables(text); assert len(syl)==len(pitches)==len(rhy), (text,len(syl),len(pitches),len(rhy))
            if ch: chords_seq += ch
            for s,p,d in zip(syl,pitches,rhy):
                n = note.Note(p, quarterLength=d)
                if with_melody: n.addLyric(s)
                else: n = note.Rest(quarterLength=d)
                mel.append(n)
        if sec in ("chorus","chorus2") and with_melody: mel[-1].expressions.append(expressions.Fermata()) if sec=="chorus2" else None
    for i, cname in enumerate(chords_seq):
        pat = CHORD_NOTES[cname]
        if with_backing:
            # 왼손 베이스(2분) + 오른손 3화음 분산(8분) — 어쿠스틱 발라드 느낌
            m = stream.Measure(number=i+1)
            m.insert(0, note.Note(pat[0], quarterLength=2)); m.insert(2, note.Note(pat[0], quarterLength=2))
            for k,off in enumerate([0,.5,1,1.5,2,2.5,3,3.5]):
                m.insert(off, note.Note(pat[1+(k%3)], quarterLength=0.5))
            m.insert(0, harmony.ChordSymbol(cname))
            acc.append(m)
        else:
            acc.append(note.Rest(quarterLength=4))
    mel = mel.makeMeasures(inPlace=False); mel.id='Vocal'
    if not with_backing: acc = acc.makeMeasures(inPlace=False); acc.id='Piano'
    sc.insert(0, mel); sc.insert(0, acc)
    return sc

full = build(True, True);  full.write('musicxml', fp='song_full.musicxml'); full.write('midi', fp='song_full.mid')
guide = build(True, False); guide.write('midi', fp='song_guide_melody.mid')
back = build(False, True);  back.write('musicxml', fp='song_backing.musicxml')
bars = sum(len(l[3]) for _,ls in SECTIONS for l in ls if l[3])
print(f"bars={bars} approx {bars*4*60/BPM:.0f}s  range D3-D4")
