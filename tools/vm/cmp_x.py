import json, sys
exp = json.load(open(sys.argv[1], encoding='utf-8')); out = open(sys.argv[2], encoding='utf-8').read().strip().split('\n')
ok = {}; bad = []
def chk(name, cond, info=''):
    ok.setdefault(name, [0, 0]); ok[name][0 if cond else 1] += 1
    if not cond: bad.append((name, info))
x2, x3 = exp['x2_demo'], exp['x3_counts']
for l in out:
    f = l.split('#')
    if f[0] == 'U':
        got = [float(v) for v in f[3].split(',')]; chk('V2 uniforms', got == exp['x1_uniforms'][f[1]][f[2]], l)
    elif f[0] == 'T': chk('V2 theta_11', float(f[3]) == exp['x1_theta_11'][f[1]][f[2]], l)
    elif f[0] == 'AB': chk('V2 theta_ab', float(f[2]) == exp['x1_theta_ab'][int(f[1])]['theta'], l)
    elif f[0] == 'CAP':
        c = [int(v) for v in f[1].split(',')]; u = [int(float(v)) for v in f[2].split(',')]
        want = next(r[2:] for r in exp['x1_cap'] if r[:2] == c); chk('V2 cap', u == want, l)
    elif f[0] in ('X2', 'X3'):
        want = x2['pick'] if f[0] == 'X2' else x3['pick']
        k, rank, c1, c0, a, b, xt, why = f[1:9]
        got = {'k': k, 'rank': int(float(rank)), 'c1': int(float(c1)), 'c0': int(float(c0)), 'a': int(float(a)), 'b': int(float(b)), 'xt': int(float(xt)), 'why': why}
        for key in got: chk(f[0] + ' pick.' + key, got[key] == want[key], (key, got[key], want[key]))
        rows = [r.split('=') for r in f[9:]]
        if f[0] == 'X3':
            det = {d['k']: d for d in x3['detail']}
            chk('V4 candidates', [r[0] for r in rows] == [d['k'] for d in x3['detail']], rows)
            for k, v in rows:
                c1, c0, th = v.split(','); d = det[k]
                chk('V4 detail', (int(float(c1)), int(float(c0)), float(th)) == (d['c1'], d['c0'], d['theta']), (k, v))
        else:
            chk('X2 candidates', [r[0] for r in rows] == x2['candidates'], rows)
    elif f[0] in ('N0', 'N1'): chk('X4 none', f[1] == 'nil', l)
    elif f[0] == 'F': chk('fmt3', f[1:] == ['0.879', '0.000', '1.000', '0.050'], l)
for k, (p, n) in ok.items(): print(('PASS' if n == 0 else 'FAIL'), k, '%d/%d' % (p, p + n))
need = {'V2 uniforms','V2 theta_11','V2 theta_ab','V2 cap','X2 pick.k','X2 candidates','X3 pick.k','V4 detail','V4 candidates','X4 none','fmt3'}
miss = need - set(ok)
print('ALL PASS' if not bad and not miss else ('MISSING %s' % sorted(miss) if miss else bad[:6]))
