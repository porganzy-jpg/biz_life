# -*- coding: utf-8 -*-
"""쇼츠 BGM 2곡 — music21 → MuseScore. heaven_lofi(72bpm 따뜻함) / hell_pulse(128bpm 긴장)."""
from music21 import stream, note, chord, tempo, meter, key, instrument
def heaven():
    s = stream.Score(); p = stream.Part(); p.insert(0, instrument.ElectricPiano())
    p.append(tempo.MetronomeMark(number=72)); p.append(meter.TimeSignature('4/4')); p.append(key.Key('C'))
    prog = [["C3","E3","G3","B3"],["A2","C3","E3","G3"],["F2","A2","C3","E3"],["G2","B2","D3","F3"]]*2
    for pat in prog:
        m = stream.Measure()
        m.insert(0, chord.Chord(pat[:2], quarterLength=4))
        for k,off in enumerate([0,.75,1.5,2,2.75,3.5]):   # 스윙 느낌 분산화음
            m.insert(off, note.Note(pat[1+(k%3)], quarterLength=0.5))
        p.append(m)
    s.insert(0,p); return s
def hell():
    s = stream.Score(); bass = stream.Part(); bass.insert(0, instrument.ElectricBass()); lead = stream.Part(); lead.insert(0, instrument.Piano())
    for p in (bass, lead): p.append(tempo.MetronomeMark(number=128)); p.append(meter.TimeSignature('4/4')); p.append(key.Key('E','minor'))
    prog = ["E2","C2","D2","B1"]*2
    for r in prog:
        m = stream.Measure(); m2 = stream.Measure()
        for off in [0,.5,1,1.5,2,2.5,3,3.5]: m.insert(off, note.Note(r, quarterLength=0.25))
        n = note.Note(r, quarterLength=0.5); n.octave += 2
        m2.insert(0, chord.Chord([n.nameWithOctave, note.Note(r).transpose(15).nameWithOctave], quarterLength=1))
        m2.insert(2.5, chord.Chord([n.nameWithOctave, note.Note(r).transpose(19).nameWithOctave], quarterLength=0.5))
        bass.append(m); lead.append(m2)
    s.insert(0,bass); s.insert(0,lead); return s
heaven().write('musicxml', fp='bgm/heaven_lofi.musicxml'); hell().write('musicxml', fp='bgm/hell_pulse.musicxml'); print("ok")
