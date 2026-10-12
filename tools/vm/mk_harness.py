# Build a bare-VM script: real PREF code from main.splash + fixture driver. Usage: mk_harness.py main.splash expected.json out.splash
import json, re, sys
src = open(sys.argv[1], encoding='utf-8').read()
exp = json.load(open(sys.argv[2], encoding='utf-8'))
lines = src.split('\n')
def block(start_pat):
    i = next(n for n, l in enumerate(lines) if re.match(start_pat, l))
    depth, out = 0, []
    for l in lines[i:]:
        out.append(l); depth += l.count('{') + l.count('[') - l.count('}') - l.count(']')
        if depth <= 0 and len(out) > 0 and ('{' in ''.join(out) or '[' in ''.join(out)): break
    return '\n'.join(out)
parts = [block(r'^let SEED = \['), block(r'^let ACTS = \['), block(r'^fn key_of'), block(r'^fn act_by_id')]
for l in lines:
    if re.match(r'^let (PREF_\w+|SEED_BPM) =', l): parts.append(l)
for f in ['pref_exp64', 'pref_sqrt64', 'pref_x', 'pref_update', 'pref_replay']:
    parts.append(block(r'^fn %s\(' % f))
pre = '\n'.join(parts)
pre = re.sub(r'(?<![\w.])(floor|exp|sqrt|clamp)\(', r'mod.math.\1(', pre)
def lit(v):
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list): return '[' + ' '.join(lit(x) for x in v) + ']'
    if isinstance(v, dict): return '{' + ' '.join('%s: %s' % (k, lit(x)) for k, x in v.items()) + '}'
    return repr(v)
drv = '''
let pref_model = nil
let songs = []
for s in SEED { songs.push({t: s.t a: s.a en: s.en vo: s.vo md: s.md lg: s.lg pc: s.pc}) }
let song_keys = []
for s in songs { song_keys.push(key_of(s)) }
let out = ""
fn dump(tag){
    let t = tag
    for a in ACTS {
        if pref_model != nil {
            let m = pref_model[a.id]
            if m != nil {
                t = t + "|" + a.id + ":" + m.n + ":" + m.beta
                for j in 12 { t = t + "," + m.v[j] }
            }
        }
    }
    t + "\\n"
}
// fixture_A: votes in order via incremental update
let pref_votes = %s
pref_model = nil
for r in pref_votes { pref_update(r) }
out = out + dump("A")
// fixture_B: replay of final table
pref_votes = %s
pref_replay()
out = out + dump("B")
// features of all songs
for s in songs {
    let x = pref_x(s)
    let t = "X|" + key_of(s)
    for j in 12 { t = t + "," + x[j] }
    out = out + t + "\\n"
}
out
''' % (lit(exp['fixture_A']['votes']), lit(exp['fixture_B']['final_table']))
open(sys.argv[3], 'w', encoding='utf-8').write(pre + '\n' + drv)
