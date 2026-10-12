import json, sys
exp = json.load(open(sys.argv[1], encoding='utf-8')); out = open(sys.argv[2], encoding='utf-8').read().strip().split('\n')
worst = 0.0; bad = []
for line in out:
    if line.startswith('X|'):
        k, *xs = line[2:].split(','); xs = [float(x) for x in xs]
        e = exp['features'][k]
        d = max(abs(a - b) for a, b in zip(xs, e)); worst = max(worst, d)
        if d > 1e-9: bad.append(('feat', k, d))
    else:
        tag, *ms = line.split('|'); want = exp['fixture_%s' % tag]['model']
        got = {}
        for m in ms:
            a, rest = m.split(':', 1); n, rest = rest.split(':', 1); beta, *v = rest.split(',')
            got[a] = (int(float(n)), float(beta), [float(x) for x in v])
        if set(got) != set(want): bad.append((tag, 'acts', sorted(got), sorted(want)))
        for a in want:
            w = want[a]; wv = w['v'] if isinstance(w, dict) else w
            g = got.get(a)
            if g is None: continue
            d = max(abs(x - y) for x, y in zip(g[2], wv))
            if isinstance(w, dict):
                d = max(d, abs(g[1] - w['beta'])); 
                if g[0] != w['n']: bad.append((tag, a, 'n', g[0], w['n']))
            worst = max(worst, d); print(tag, a, 'n=%d' % g[0], 'max|Δ|=%.3g' % d)
            if d > 1e-9: bad.append((tag, a, d))
print('worst', worst); print('FAIL' if bad else 'PASS', bad[:5])
