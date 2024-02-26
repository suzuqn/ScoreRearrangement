# Piano Score Rearrangement

This is the official repository for "[Piano score rearrangement](https://link.springer.com/article/10.1186/s13636-023-00321-7)" paper,  providing the tools for **ST+**, an **updated version** of [score token](https://github.com/suzuqn/ScoreTransformer/) representaion. 

[Paper](https://link.springer.com/article/10.1186/s13636-023-00321-7) | [Project page](https://score-rearrangement.github.io/)

## Usage

### Tokenization

```python
from score_to_tokens import MusicXML_to_tokens

tokens = MusicXML_to_tokens('input_score.musicxml', bar_major=True, tokenize_chord_symbols=True)
```

available options
- **bar_major**: tokenize in a bar-major style (True) or staff-major style (False)
- **note_name**: tokenize pitches as note names (True) or note numbers (False)
- **tokenize_chord_symbols**: tokenize chord symbols (True) or not (False)

### Detokenization

```Python
from tokens_to_score import tokens_to_score

s = tokens_to_score(tokens)
s.write('musicxml', 'output_score')
```

## Dependencies
- music21
- BeautifulSoup4

## Citation
If you find this repository helpful, please consider citing our paper:
```
@inproceedings{suzuki2023,
 author = {Suzuki, Masahiro},
 title = {Piano score rearrangement into multiple difficulty levels via notation-to-notation approach},
 booktitle = {EURASIP Journal on Audio, Speech, and Music Processing},
 volume = {2023},
 number = {52},
 year = {2023},
 doi = {10.1186/s13636-023-00321-7}
}
