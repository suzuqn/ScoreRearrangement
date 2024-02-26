from music21 import articulations, bar, chord, clef, key, layout, meter, note, pitch, spanner, stream, tie

# dictionary to change note names
sharp_to_flat = {'C#': 'D-', 'D#': 'E-', 'F#': 'G-', 'G#': 'A-', 'A#': 'B-'}
flat_to_sharp = {v:k for k, v in sharp_to_flat.items()}

# translate note numbers into note names considering key signature
def pitch_to_name(pitch_, key=key.KeySignature(0)):
    if pitch_.isdecimal():
        name = str(pitch.Pitch(int(pitch_)))
        if key.sharps < 0:
            for k, v in sharp_to_flat.items():
                name = name.replace(k, v)
        elif key.sharps > 0:
            for k, v in flat_to_sharp.items():
                name = name.replace(k, v)
        return name
    else:
        return pitch_.replace('b', '-')

# group note(rest)-related tokens
def group_related_tokens(tokens):
    notes, others, out = [], [], []
    note_flag, len_flag = False, False

    for t in tokens:
        parts = t.split('_')
        if parts[0] in ('note', 'rest'):
            if note_flag and len_flag and len(notes):
                out.append(' '.join(notes))
                notes = []
            note_flag = True
            len_flag = False
            notes.append(t)
        elif parts[0] == 'len':
            len_flag = True
            notes.append(t)
        elif parts[0] in ('stem', 'beam', 'tie', 'staccato', 'accent', 'tenuto'):
            notes.append(t)
        elif t == 'slur_start':
            out.append(t)
        else: # other than note-related
            if len(notes):
                out.append(' '.join(notes))
                notes = []
            out.append(t)

    # buffer flush
    if len(notes):
        out.append(' '.join(notes))

    return out

# translate clef or signature token into music21 object
def single_token_to_obj(token):
    parts = token.split('_')
    if parts[0] == 'clef':
        if parts[1] == 'treble':
            return clef.TrebleClef()
        elif parts[1] == 'bass':
            return clef.BassClef()
    elif parts[0] == 'key':
        if parts[1] == 'sharp':
            return key.KeySignature(int(parts[2]))
        elif parts[1] == 'flat':
            return key.KeySignature(-1 * int(parts[2]))
        elif parts[1] == 'natural':
            return key.KeySignature(0)
    elif parts[0] == 'time':
        if '/' in parts[1]:
            return meter.TimeSignature(parts[1])
        else:
            return meter.TimeSignature(parts[1]+'/4' if int(parts[1]) < 6 else parts[1]+'/8')

# translate note(rest)-related tokens into music21 object
def note_token_to_obj(tokens, key):
    if tokens[0] == 'rest': # for rests
        length = str_to_float(tokens[1])
        return note.Rest(quarterLength=length)

    # for notes
    note_names = [pitch_to_name(t.split('_')[1], key) for t in tokens if t.split('_')[0] == 'note']
    lengths = [str_to_float(t) for t in tokens if t.split('_')[0] == 'len']
    direction = [t.split('_')[1] for t in tokens if t.split('_')[0] in ('stem', 'dir')] + [t.split('_')[2] for t in tokens if t.split('_')[0] == 'len' and len(t.split('_')) >= 3]
    beams = [t.split('_')[1:] for t in tokens if t.split('_')[0] == 'beam'] + [t.split('_')[3:] for t in tokens if t.split('_')[0] == 'len' and len(t.split('_')) >= 4]
    tie_ = [t.split('_')[1] for t in tokens if t.split('_')[0] == 'tie']
    articulations_ = [t for t in tokens if t in ('staccato', 'accent', 'tenuto')]

    if len(note_names) > 1: # chord
        if len(lengths) > 1:
            chords = []
            for i, l in enumerate(lengths):
                chord_ = chord.Chord(note_names, quarterLength=l)
                if len(direction):
                    chord_.stemDirection = direction[0]

                if len(beams):
                    append_beams(chord_, beams)

                if len(tie_):
                    chord_.tie = tie.Tie('continue')
                elif i == 0:
                    chord_.tie = tie.Tie('start')
                elif i == len(lengths) - 1:
                    chord_.tie = tie.Tie('stop')
                else:
                    chord_.tie = tie.Tie('continue')

                if articulations_:
                    chord_.articulations = [translate_articulation(t) for t in articulations_]

                chords.append(chord_)

            return chords
        else:
            chord_ = chord.Chord(note_names, quarterLength=lengths[0])
            if len(direction):
                chord_.stemDirection = direction[0]
            if len(beams):
                append_beams(chord_, beams)
            if len(tie_):
                chord_.tie = tie.Tie(tie_[0])
            if articulations_:
                chord_.articulations = [translate_articulation(t) for t in articulations_]
            return chord_
    else: # note
        if len(lengths) > 1:
            notes = []
            for i, l in enumerate(lengths):
                note_ = note.Note(note_names[0], quarterLength=l)
                if len(direction):
                    note_.stemDirection = direction[0]

                if len(beams):
                    append_beams(note_, beams)

                if len(tie_):
                    note_.tie = tie.Tie('continue')
                elif i == 0:
                    note_.tie = tie.Tie('start')
                elif i == len(lengths) - 1:
                    note_.tie = tie.Tie('stop')
                else:
                    note_.tie = tie.Tie('continue')

                if articulations_:
                    note_.articulations = [translate_articulation(t) for t in articulations_]

                notes.append(note_)

            return notes
        else:
            note_ = note.Note(note_names[0], quarterLength=lengths[0])
            if len(direction):
                note_.stemDirection = direction[0]
            if len(beams):
                append_beams(note_, beams)
            if len(tie_):
                note_.tie = tie.Tie(tie_[0])
            if articulations_:
                note_.articulations = [translate_articulation(t) for t in articulations_]
            return note_

# [aux func] translate note length into float number
def str_to_float(t):
    length = t.split('_')[1] if 'len' in t else t
    if '/' in length:
        numerator, denominator = length.split('/')
        return int(numerator) / int(denominator)
    else:
        return float(length)

# [aux func] append beams property to music21 Note or Chord object
def append_beams(obj, beams):
    for b in beams[0]:
        if '-' in b:
            former, latter = b.split('-')
            obj.beams.append(former, latter)
        else:
            obj.beams.append(b)

def translate_articulation(token):
    if token == 'staccato':
        return articulations.Staccato()
    elif token == 'accent':
        return articulations.Accent()
    elif token == 'tenuto':
        return articulations.Tenuto()

def tokens_to_PartStaff(tokens, key_=0, start_voice=1, slur_number=1):
    tokens = concatenated_to_regular(tokens)

    p = stream.PartStaff()
    k = key.KeySignature(key_)

    voice_id = start_voice
    voice_flag = False
    after_voice = False
    voice_start = None

    ottava_flag = False
    ottava_elements = []

    slur_flag = False
    slur_elements = []

    tokens = group_related_tokens(tokens)

    for i, t in enumerate(tokens):
        if t == 'bar':
            if i != 0:
                p.append(m)
            m = stream.Measure()
            voice_id = start_voice
            voice_start = None
            voice_flag = False
            after_voice = False
        elif t == '<voice>':
            v = stream.Voice(id=voice_id)
            voice_flag = True
            if voice_start is None:
                voice_start = m.duration.quarterLength # record the start point of voice
        elif t == '</voice>':
            if voice_flag:
                v.makeAccidentals(useKeySignature=k)
                for element in v:
                    element.offset += voice_start
                m.append(v)
                voice_id += 1
                voice_flag = False
                after_voice = True
        elif t == 'slur_start':
            slur = spanner.Slur()
            slur.idLocal = slur_number
            slur_flag = True
        elif t == 'slur_stop':
            if slur_flag:
                slur.addSpannedElements(slur_elements)
                m.append(slur)
                slur_flag = False
                slur_elements = []
        elif t.split('_')[0] in ('clef', 'key', 'time'):
            if t[:11] == 'key_natural' and i+1 < len(tokens) and tokens[i+1].split('_')[0] == 'key':
                continue # workaround for MuseScore (which ignores consecutive key signtures): if key signatures appear in succession, skip the one with natural
            o = single_token_to_obj(t)
            if voice_flag:
                v.append(o)
            else:
                m.append(o)
            if slur_flag:
                slur_elements.append(o)
            if t.split('_')[0] == 'key': # generate another key signature object to use makeAccidentals and to translate note number to name
                k = o
        elif t[:4] in ('note', 'rest'):
            n = note_token_to_obj(t.split(), k)
            if ottava_flag:
                ottava_elements.append(n)
            if slur_flag:
                slur_elements.append(n)

            if voice_flag:
                v.append(n)
            else:
                m.append(n)

            if after_voice:
                n.offset -= v.quarterLength * (voice_id - 1)
    # last measure
    p.append(m)

    # adjust offsets for notes in voices
    for m in p:
        voices = m.getElementsByClass(stream.Voice)
        for v in voices[1:]:
            v.offset = voices[0].offset
        
        for v in voices:
            for element in v:
                element.offset += v.offset

    p.makeAccidentals(cautionaryNotImmediateRepeat=False, overrideStatus=True, inPlace=True)
    return p

def concatenated_to_regular(tokens):
    regular_tokens = []
    for t in tokens:
        if t.startswith('len') or t.startswith('attr'):
            attrs = t.split('_')
            if len(attrs) == 2:
                regular_tokens.append(f'len_{attrs[1]}')
            elif len(attrs) == 3:
                regular_tokens += [f'len_{attrs[1]}', f'stem_{attrs[2]}']
            else:
                regular_tokens += [f'len_{attrs[1]}', f'stem_{attrs[2]}', f'beam_{"_".join(attrs[3:])}']
        else:
            regular_tokens.append(t)
    return regular_tokens

def split_header_R_L(string):
    tokens = string.split()
    if 'L' in tokens:
        h = ' '.join(tokens[:tokens.index('R')])
        R = ' '.join(tokens[tokens.index('R')+1:tokens.index('L')])
        L = ' '.join(tokens[tokens.index('L')+1:])
    else:
        h = ' '.join(tokens[:tokens.index('R')])
        R = ' '.join(tokens[tokens.index('R')+1:])
        L = ''
    return h, R, L

# ST+ to ST
def normalize(seq):
    return ' '.join(seq.split())

def common(seq):
    return ' '.join([t for t in seq.split() if t.split('_')[0] in ('time', 'key')])

def insert_attrs(seq, common_attrs):
    if common_attrs:
        tokens = seq.split()
        if seq.startswith('clef'):
            tokens[1:1] += common_attrs.split()
        else:
            tokens[0:0] += common_attrs.split()
        return ' '.join(tokens)
    else:
        return seq
    
def to_ST(seq):
    R_bars, L_bars = [], []
    
    bars = seq.split('bar')
    for bar in bars[1:]:
        header, R, L = split_header_R_L(bar)
        attrs = common(header)
        R_bars += ['bar', insert_attrs(R, attrs)]
        L_bars += ['bar', insert_attrs(L, attrs)]
            
    return normalize(f"{bars[0]} R {' '.join(R_bars)} L {' '.join(L_bars)}")

# build music21 Score object from a token sequence (string or list)
def tokens_to_score(string_or_list, voice_numbering=False):
    if type(string_or_list) is not str:
        string = ' '.join(string_or_list)
    else:
        string = string_or_list

    if string.index('bar') < string.index('R'): # ST+
        string = to_ST(string)
    
    _, R_str, L_str = split_header_R_L(string)
    R_tokens = R_str.split()
    L_tokens = L_str.split()
    
    if voice_numbering:
        r = tokens_to_PartStaff(R_tokens, slur_number=1)
        r_voices = max([len(m.voices) if m.hasVoices() else 1 for m in r])
        l = tokens_to_PartStaff(L_tokens, start_voice=r_voices+1, slur_number=2)
    else:
        r = tokens_to_PartStaff(R_tokens, start_voice=0, slur_number=1)
        l = tokens_to_PartStaff(L_tokens, start_voice=0, slur_number=2)

    # add last barline
    r.elements[-1].rightBarline = bar.Barline('regular')
    l.elements[-1].rightBarline = bar.Barline('regular')

    s = stream.Score()
    g = layout.StaffGroup([r, l], symbol='brace', barTogether=True)
    s.append([g, r, l])
    return s
