# Bare-VM driver for EXPLORE: real [PREF]/[EXPLORE] code from main.splash + expected-value checks.
import json, re, sys
src = open(sys.argv[1], encoding='utf-8').read(); exp = json.load(open(sys.argv[2], encoding='utf-8'))
lines = src.split('\n')
def block(pat):
    i = next(n for n, l in enumerate(lines) if re.match(pat, l)); depth, out = 0, []
    for l in lines[i:]:
        out.append(l); depth += l.count('{') + l.count('[') - l.count('}') - l.count(']')
        if depth <= 0 and ('{' in ''.join(out) or '[' in ''.join(out)): break
    return '\n'.join(out)
parts = [block(r'^let SEED = \['), block(r'^let ACTS = \['), block(r'^fn key_of'), block(r'^fn act_by_id'), block(r'^fn rec_member')]
for l in lines:
    if re.match(r'^let (PREF_\w+|X_\w+|EXPLORE_ON|TOPK) =', l): parts.append(l)
for f in ['pref_hash', 'x_floor64', 'x_uniforms', 'x_beta', 'x_cap', 'x_counts', 'x_why', 'explore_pick', 'x_fmt3']:
    parts.append(block(r'^fn %s\(' % f))
pre = re.sub(r'(?<![\w.])(floor|exp|sqrt|clamp)\(', r'mod.math.\1(', '\n'.join(parts))
def lit(v):
    if v is None: return 'nil'
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list): return '[' + ' '.join(lit(x) for x in v) + ']'
    if isinstance(v, dict): return '{' + ' '.join('%s: %s' % (k, lit(x)) for k, x in v.items()) + '}'
    return repr(v)
x2 = exp['x2_demo']; x3 = exp['x3_counts']
keys5 = list(exp['x1_uniforms']['1'].keys())
drv = '''
let songs = []
for s in SEED { songs.push({t: s.t a: s.a}) }
let song_keys = []
for s in songs { song_keys.push(key_of(s)) }
fn idx(k){
    let r = -1
    for j key in song_keys { if key == k { r = j } }
    r
}
let playlist_x = nil
let x_rows = []
let x_none = ""
let o = ""
for seed in [1 17] {
    for k in %s { let u = x_uniforms(seed, k, 3) o = o + "U#" + seed + "#" + k + "#" + u[0] + "," + u[1] + "," + u[2] + "\\n" }
    for k in song_keys { o = o + "T#" + seed + "#" + k + "#" + x_beta(seed, k, 1, 1) + "\\n" }
}
for j c in %s { o = o + "AB#" + j + "#" + x_beta(c.seed, c.k, c.a, c.b) + "\\n" }
for c in %s { let u = x_cap(c.c1, c.c0) o = o + "CAP#" + c.c1 + "," + c.c0 + "#" + u.u1 + "," + u.u0 + "\\n" }
let rec_pref_rows = []
for j k in %s { rec_pref_rows.push({i: idx(k) k: k rank: j + 1}) }
let picks = []
for k in %s { picks.push({i: idx(k) why: ""}) }
fn dump(tag, p){
    let t = tag + "#"
    if p == nil { t = t + "nil#" + x_none }
    else { t = t + song_keys[p.i] + "#" + p.rank + "#" + p.c1 + "#" + p.c0 + "#" + p.a + "#" + p.b + "#" + p.xt + "#" + p.why }
    for r in x_rows { t = t + "#" + song_keys[r.i] + "=" + r.c1 + "," + r.c0 + "," + r.th }
    t + "\\n"
}
let pref_votes = %s
o = o + dump("X2", explore_pick(picks, "commute", 1001))
pref_votes = %s
o = o + dump("X3", explore_pick(picks, "commute", 1002))
o = o + dump("N0", explore_pick(picks, "", 1001))
o = o + dump("N1", explore_pick(picks, "party", 1001))
o = o + "F#" + x_fmt3(0.8789) + "#" + x_fmt3(0.0004) + "#" + x_fmt3(0.9996) + "#" + x_fmt3(0.05) + "\\n"
o
''' % (lit(keys5), lit(exp['x1_theta_ab']), lit([{"c1": c[0], "c0": c[1]} for c in exp["x1_cap"]]), lit(x2['top12']), lit(x2['six']),
       lit([dict(r, x=0) for r in exp['x3_counts']['votes'][:2]]), lit([dict(r, x=0) for r in x3['votes']]))
open(sys.argv[3], 'w', encoding='utf-8').write(pre + '\n' + drv)
