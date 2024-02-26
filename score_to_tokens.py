from bs4 import BeautifulSoup
from bs4.element import Tag
from fractions import Fraction
from music21 import converter, harmony, stream
from pretty_midi import note_name_to_number

PITCH_ALTER_TO_SYMBOL = {'-2': 'bb', '-1': 'b', '0':'', '1': '#', '2': '##'}
SEMITONE_TO_SYMBOL = {-1: 'b', 0: '', 1: '#'}
CLEF_TRANSLATIONS = {'G': 'treble', 'F': 'bass'}
BEAM_TRANSLATIONS = {'begin': 'start', 'end': 'stop', 'forward hook': 'partial-right', 'backward hook': 'partial-left'}

def attributes_to_tokens(attributes, staff=None): # tokenize 'attributes' section in MusicXML
    tokens = []
    divisions = None

    for child in attributes.contents:
        type_ = child.name
        if type_ == 'divisions':
            divisions = int(child.text)
        elif type_ in ('clef', 'key', 'time'):
            if staff is not None:
                if 'number' in child.attrs and int(child['number']) != staff:
                    continue
            tokens.append(attribute_to_token(child))

    return tokens, divisions

def attribute_to_token(child): # clef, key signature, and time signature
    type_ = child.name
    
    if type_ == 'clef':
        return f'clef_{CLEF_TRANSLATIONS.get(child.sign.text, child.sign.text)}'
    elif type_ == 'key':
        key = int(child.fifths.text)
        if key < 0:
            return f'key_flat_{abs(key)}'
        elif key > 0:
            return f'key_sharp_{key}'
        else:
            return f'key_natural_{key}'
    elif type_ == 'time':
        times = [int(c.text) for c in child.contents if isinstance(c, Tag)] # excluding '\n'
        if times[1] == 2:
            return f'time_{times[0]*2}/{times[1]*2}'
        elif times[1] > 4:
            fraction = str(Fraction(times[0], times[1]))
            if int(fraction.split('/')[1]) == 2: # X/2
                return f"time_{int(fraction.split('/')[0])*2}/{int(fraction.split('/')[0])*2}"
            else:
                return 'time_' + fraction
        else:
            return f'time_{times[0]}/{times[1]}'

def aggregate_notes(voice_notes): # notes to chord
    for note in voice_notes[1:]:
        if note.chord is not None:
            last_note = note.find_previous('note')
            last_note.insert(0, note.pitch)
            if note.technical:
                last_note.insert(0, note.technical)
            note.decompose()
            
def pitch_to_note_number(pitch):
    note_number = note_name_to_number(pitch.step.text + pitch.octave.text) # 'C4' -> 60
    if pitch.alter:
        note_number += int(pitch.alter.text)
    return note_number

def note_to_tokens(note, divisions=8, note_name=False): # notes and rests
    if note.duration is None: # gracenote
        return []

    duration_in_fraction = str(Fraction(int(note.duration.text), divisions))

    if note.rest:
        return ['rest', f'len_{duration_in_fraction}'] # for rests

    tokens = []

    sorted_pitches = sorted(note.find_all('pitch'), key=lambda x:pitch_to_note_number(x))
    for pitch in sorted_pitches:
        if note_name:
            if pitch.alter:
                tokens.append(f'note_{pitch.step.text}{PITCH_ALTER_TO_SYMBOL[pitch.alter.text]}{pitch.octave.text}')
            else:
                tokens.append(f'note_{pitch.step.text}{pitch.octave.text}')
        else:
            tokens.append(f'note_{pitch_to_note_number(pitch)}')

    # len
    tokens.append(f'len_{duration_in_fraction}')

    if note.stem and note.stem.text != 'none':
        tokens.append(f'stem_{note.stem.text}')

    if note.beam:
        beams = note.find_all('beam')
        tokens.append('beam_' + '_'.join([BEAM_TRANSLATIONS[b.text] if b.text in BEAM_TRANSLATIONS else b.text for b in beams]))

    if note.tied:
        tokens.append('tie_' + note.tied.attrs['type'])

    # articulations
    if note.notations:
        if note.staccato:
            tokens.append('staccato')
        if note.accent:
            tokens.append('accent')
        if note.tenuto:
            tokens.append('tenuto')

    # slur
    if note.slur:
        if note.slur.attrs['type'] == 'start':
            tokens.append('slur_start')
        if note.slur.attrs['type'] == 'stop':
            tokens.append('slur_stop')

    return tokens

def element_segmentation(measure, soup, staff=None): # divide elements into three sections
    voice_starts, voice_ends = {}, {}
    position = 0
    last_voice = None
    for element in measure.contents:
        if element.name == 'note':
            if element.duration is None: # gracenote
                continue
                
            if element.voice:
                voice = element.voice.text
                last_voice = voice
            elif element.chord:
                voice = last_voice
                
            duration = int(element.duration.text)
            if element.chord: # rewind for concurrent notes
                position -= last_duration

            if not element.staff or int(element.staff.text) == staff:
                voice_starts[voice] = min(voice_starts[voice], position) if voice in voice_starts else position
                start_tag = soup.new_tag('start')
                start_tag.string = str(position)
                element.append(start_tag)

            position += duration

            if not element.staff or int(element.staff.text) == staff:
                voice_ends[voice] = max(voice_ends[voice], position) if voice in voice_ends else position
                end_tag = soup.new_tag('end')
                end_tag.string = str(position)
                element.append(end_tag)

            last_duration = duration
        elif element.name == 'backup':
            position -= int(element.duration.text)
        elif element.name == 'forward':
            position += int(element.duration.text)
        else: # other types
            start_tag = soup.new_tag('start')
            end_tag = soup.new_tag('end')

            start_tag.string = str(position)
            end_tag.string = str(position)

            element.append(start_tag)
            element.append(end_tag)

    # voice section
    voice_start = sorted(voice_starts.values())[1] if voice_starts else 0
    voice_end = sorted(voice_ends.values(), reverse=True)[1] if voice_ends else 0

    pre_voice_elements, post_voice_elements, voice_elements = [], [], []
    for element in measure.contents:
        if element.name in ('backup', 'forward'):
            continue
        if element.name == 'note' and element.duration is None: # gracenote
            continue
        if staff is not None:
            if element.staff and int(element.staff.text) != staff:
                continue

        if voice_starts or voice_ends:
            if int(element.end.text) <= voice_start:
                pre_voice_elements.append(element)
            elif voice_end <= int(element.start.text):
                post_voice_elements.append(element)
            else:
                voice_elements.append(element)
        else:
            pre_voice_elements.append(element)

    return pre_voice_elements, voice_elements, post_voice_elements

def measures_to_tokens(measures, soup, staff=None, note_name=False):
    tokens = []
    for measure in measures:
        tokens += ['bar'] + measure_to_tokens(measure, soup, staff, note_name)
        
    return tokens

def measure_to_tokens(measure, soup, staff=None, note_name=False):
    divisions = int(soup.divisions.text)
    tokens = []

    if staff is not None:
        notes = [n for n in measure.find_all('note') if n.staff and int(n.staff.text) == staff]
    else:
        notes = measure.find_all('note')

    # add voice to unvoiced notes (of a chord)
    last_voice = None
    for note in notes:
        if note.voice:
            last_voice = note.voice.text
        elif note.chord:                
            voice_tag = soup.new_tag('voice')
            voice_tag.string = str(last_voice)
            note.append(voice_tag)

    voices = list(set([n.voice.text for n in notes if n.voice]))
    for voice in voices:
        voice_notes = [n for n in notes if n.voice and n.voice.text == voice]
        aggregate_notes(voice_notes)

    if len(voices) > 1:
        pre_voice_elements, voice_elements, post_voice_elements = element_segmentation(measure, soup, staff)

        for element in pre_voice_elements:
            if element.name == 'attributes':
                attr_tokens, div = attributes_to_tokens(element, staff)
                tokens += attr_tokens
                divisions = div or divisions
            elif element.name == 'note':
                tokens += note_to_tokens(element, divisions, note_name)

        if voice_elements:
            for voice in voices:
                tokens.append('<voice>')
                for element in voice_elements:
                    if (element.voice and element.voice.text == voice) or (not element.voice and voice == '1'):
                        if element.name == 'attributes':
                            attr_tokens, div = attributes_to_tokens(element, staff)
                            tokens += attr_tokens
                            divisions = div or divisions
                        elif element.name == 'note':
                            tokens += note_to_tokens(element, divisions, note_name)
                tokens.append('</voice>')

        for element in post_voice_elements:
            if element.name == 'attributes':
                attr_tokens, div = attributes_to_tokens(element, staff)
                tokens += attr_tokens
                divisions = div or divisions
            elif element.name == 'note':
                tokens += note_to_tokens(element, divisions, note_name)
    else:
        for element in measure.contents:
            if staff is not None:
                if element.name in ('attributes', 'note') and \
                   element.staff and int(element.staff.text) != staff:
                    continue
            if element.name == 'attributes':
                attr_tokens, div = attributes_to_tokens(element, staff)
                tokens += attr_tokens
                divisions = div or divisions
            elif element.name == 'note':
                tokens += note_to_tokens(element, divisions, note_name)

    return tokens

def common(tokens, common_types=['time', 'key']):
    return [t for t in tokens if t.split('_')[0] in common_types]

def others(tokens, common_types=['time', 'key']):
    return [t for t in tokens if t.split('_')[0] not in common_types]

## for chord symbols
def ChordSymbol_to_tokens(c):
    if isinstance(c, harmony.NoChord):
        return []

    root = c.root().name.replace('-', 'b')
    bass = c.bass().name.replace('-', 'b')
    mods = ''.join([mod_to_str(mod) for mod in c.chordStepModifications])

    if not c.chordKindStr and ' ' in c.figure:
        kind = c.figure.split()[0][len(c.root().name):]
    else:
        kind = c.chordKindStr

    if kind or mods:
        type_ = kind + mods if mods else kind
        tokens = [f'chord_{root}{type_}']
    else:
        tokens = [f'chord_{root}']

    if bass != root:
        tokens += [f'bass_{bass}']

    return tokens

def mod_to_str(mod):
    if mod.modType in ('alter', 'add'):
        mod_str = f'{SEMITONE_TO_SYMBOL[mod.interval.semitones]}{mod.degree}'
    else:
        mod_str = ''

    if mod.degree == 5:
        return mod_str
    else:
        return f'({mod_str})'

def get_chord_tokens(s):
    if not s.recurse().getElementsByClass('ChordSymbol'):
        return []
    
    measures = sorted(set([
        (m.offset, m.offset + m.duration.quarterLength)
        for m in s.recurse().getElementsByClass(stream.Measure)
    ]))

    chords = []
    for c in s.recurse().getElementsByClass('ChordSymbol'):
        measure_offset = list(c.contextSites(priorityTarget=stream.Measure))[0].site.offset
        time = measure_offset + c.beat - 1
        if measures[0][0] <= time < measures[-1][1]:
            chords.append((time, ChordSymbol_to_tokens(c)))
    
    # add chords to the top of each measure
    additional_chords = [
        (t, [chord for time, chord in chords if time < t][-1]) # last chord
        for t in set([start for start, end in measures]) - set([time for time, _ in chords])
        if measures[0][0] < t and any(time < t for time, _ in chords)
    ]

    # arrange all elements in time order
    ordered_elements = sorted(
        [(t, ['bar']) for t, _ in measures] + chords + additional_chords + [(measures[-1][1], 'EOS')],
        key=lambda x: x[0]
    )

    last_time = ordered_elements[0][0]
    all_tokens, tokens = [], None

    for time, element in ordered_elements:
        time_diff = time - last_time
        if time_diff:
            if time_diff.is_integer():
                tokens.append(f'len_{int(time_diff)}')
            else:
                tokens.append(f'len_{str(Fraction(time_diff).limit_denominator(6))}')

        if element == 'EOS':
            break
        elif element == ['bar']:
            if tokens is not None:
                all_tokens.append(tokens)
            tokens = []
        else:
            tokens += element

        last_time = time

    return all_tokens


def load_MusicXML(mxml_path): 
    soup = BeautifulSoup(open(mxml_path, encoding='utf-8'), 'lxml-xml', from_encoding='utf-8')
    
    # eliminate line breaks
    for tag in soup(string='\n'):
        tag.extract()

    return [part.find_all('measure') for part in soup.find_all('part')], soup

def MusicXML_to_tokens(mxml_path, bar_major=True, note_name=True, tokenize_chord_symbols=True):
    parts, soup = load_MusicXML(mxml_path)
    assert len(parts) in (1, 2)
    
    if len(parts) == 1:
        R_part, L_part = parts[0], parts[0]
        R_staff, L_staff = 1, 2
    elif len(parts) == 2:
        R_part, L_part = parts[0], parts[1]
        R_staff, L_staff = None, None
        assert len(parts[0]) == len(parts[1])
    
    if tokenize_chord_symbols:
        chords = get_chord_tokens(converter.parse(mxml_path))
        
    tokens = []
    if bar_major:
        if tokenize_chord_symbols and chords:
            for R_measure, L_measure, C in zip(R_part, L_part, chords):
                R = measure_to_tokens(R_measure, soup, R_staff, note_name)
                L = measure_to_tokens(L_measure, soup, L_staff, note_name)
                tokens += ['bar'] + common(R) + C + ['R'] + others(R) + ['L'] + others(L)
        else:
            for R_measure, L_measure in zip(R_part, L_part):
                R = measure_to_tokens(R_measure, soup, R_staff, note_name)
                L = measure_to_tokens(L_measure, soup, L_staff, note_name)
                tokens += ['bar'] + common(R) + ['R'] + others(R) + ['L'] + others(L)
    else:
        if tokenize_chord_symbols and chords:
            tokens += ['C'] + sum([['bar'] + C for C in chords], [])
        tokens += ['R'] + measures_to_tokens(R_part, soup, R_staff, note_name)
        tokens += ['L'] + measures_to_tokens(L_part, soup, L_staff, note_name)

    return tokens
