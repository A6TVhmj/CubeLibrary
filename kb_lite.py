import time
import math
import numpy as np

# ==============================================================
# Kociemba's Engine (Two-Phase & Optimal + Numba Accelerated)
# ==============================================================
MOVES_STR = ["U", "U2", "U'", "R", "R2", "R'", "F", "F2", "F'", "D", "D2", "D'", "L", "L2", "L'", "B", "B2", "B'"]
P2_MOVES  = [0, 1, 2, 9, 10, 11, 4, 13, 7, 16] 

CORNER_FACELETS = [(8,9,20), (6,18,38), (0,36,47), (2,45,11), (29,26,15), (27,44,24), (33,53,42), (35,17,51)]
EDGE_FACELETS   = [(5,10), (7,19), (3,37), (1,46), (32,16), (28,25), (30,43), (34,52), (23,12), (21,41), (50,39), (48,14)]
STD_CORNERS = [('U','R','F'), ('U','F','L'), ('U','L','B'), ('U','B','R'), ('D','F','R'), ('D','L','F'), ('D','B','L'), ('D','R','B')]
STD_EDGES   = [('U','R'), ('U','F'), ('U','L'), ('U','B'), ('D','R'), ('D','F'), ('D','L'), ('D','B'), ('F','R'), ('F','L'), ('B','L'), ('B','R')]

cp_U = [3, 0, 1, 2, 4, 5, 6, 7]; co_U = [0, 0, 0, 0, 0, 0, 0, 0]; ep_U = [3, 0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11]; eo_U = [0]*12
cp_R = [4, 1, 2, 0, 7, 5, 6, 3]; co_R = [2, 0, 0, 1, 1, 0, 0, 2]; ep_R = [8, 1, 2, 3, 11, 5, 6, 7, 4, 9, 10, 0]; eo_R = [0]*12
cp_F = [1, 5, 2, 3, 0, 4, 6, 7]; co_F = [1, 2, 0, 0, 2, 1, 0, 0]; ep_F = [0, 9, 2, 3, 4, 8, 6, 7, 1, 5, 10, 11]; eo_F = [0, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0]
cp_D = [0, 1, 2, 3, 5, 6, 7, 4]; co_D = [0, 0, 0, 0, 0, 0, 0, 0]; ep_D = [0, 1, 2, 3, 5, 6, 7, 4, 8, 9, 10, 11]; eo_D = [0]*12
cp_L = [0, 2, 6, 3, 4, 1, 5, 7]; co_L = [0, 1, 2, 0, 0, 2, 1, 0]; ep_L = [0, 1, 10, 3, 4, 5, 9, 7, 8, 2, 6, 11]; eo_L = [0]*12
cp_B = [0, 1, 3, 7, 4, 5, 2, 6]; co_B = [0, 0, 1, 2, 0, 0, 2, 1]; ep_B = [0, 1, 2, 11, 4, 5, 6, 10, 8, 9, 3, 7]; eo_B = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 1]
BASE_CUBIES = [(cp_U, co_U, ep_U, eo_U), (cp_R, co_R, ep_R, eo_R), (cp_F, co_F, ep_F, eo_F), (cp_D, co_D, ep_D, eo_D), (cp_L, co_L, ep_L, eo_L), (cp_B, co_B, ep_B, eo_B)]

FACT = [math.factorial(i) for i in range(13)]
CNK = np.zeros((13, 13), dtype=np.int32)
for n in range(13):
    for k in range(n + 1): CNK[n, k] = math.comb(n, k)

def multiply_cubies(c1, c2):
    return ([c1[0][c2[0][i]] for i in range(8)], [(c1[1][c2[0][i]] + c2[1][i]) % 3 for i in range(8)], [c1[2][c2[2][i]] for i in range(12)], [(c1[3][c2[2][i]] + c2[3][i]) % 2 for i in range(12)])

def get_twist(co): return sum(co[i] * (3 ** (6 - i)) for i in range(7))
def set_twist(val):
    co, p = [0]*8, 0
    for i in range(6, -1, -1): co[i] = val % 3; p += co[i]; val //= 3
    co[7] = (3 - p % 3) % 3; return co
def get_flip(eo): return sum(eo[i] * (2 ** (10 - i)) for i in range(11))
def set_flip(val):
    eo, p = [0]*12, 0
    for i in range(10, -1, -1): eo[i] = val % 2; p += eo[i]; val //= 2
    eo[11] = (2 - p % 2) % 2; return eo
def get_slice(ep):
    s, k = 0, 3
    for n in range(11, -1, -1):
        if ep[n] >= 8: k -= 1
        else: s += CNK[n, k]
        if k < 0: break
    return s
def set_slice(val):
    ep, k = [-1]*12, 3
    for n in range(11, -1, -1):
        if val < CNK[n, k]: ep[n] = 11 - k; k -= 1; 
        else: val -= CNK[n, k]
        if k < 0: break
    cur = 0
    for i in range(12):
        if ep[i] == -1: ep[i], cur = cur, cur + 1
    return ep
def get_perm(arr): return sum(sum(1 for j in range(i+1, len(arr)) if arr[j] < arr[i]) * FACT[len(arr) - 1 - i] for i in range(len(arr)))
def set_perm(val, n):
    arr, used = [0]*n, [False]*n
    for i in range(n):
        s = val // FACT[n - 1 - i]; val %= FACT[n - 1 - i]; c = 0
        for j in range(n):
            if not used[j]:
                if c == s: arr[i], used[j] = j, True; break
                c += 1
    return arr

def build_2d_pruning_table_numba(MT1, MT2, N1, N2, num_moves):
    size = N1 * N2
    prun = np.full(size, -1, dtype=np.int8)
    prun[0] = 0
    q = np.zeros(size, dtype=np.int32)
    q[0] = 0
    head = 0; tail = 1
    while head < tail:
        curr = q[head]; head += 1; d = prun[curr]
        x = curr // N2; y = curr % N2
        for m in range(num_moves):
            nidx = MT1[x, m] * N2 + MT2[y, m]
            if prun[nidx] == -1:
                prun[nidx] = d + 1
                q[tail] = nidx; tail += 1
    return prun

INITIALIZED = False
def init_engine():
    global INITIALIZED, twist_move, flip_move, slice_move, cp_move_p2, ep_move, sep_move
    global prun_p1_ts, prun_p1_fs, prun_p2_cp_sep, prun_p2_ep_sep, FULL_CUBIE_MOVES
    if INITIALIZED: return
    CUBIE_MOVES = []
    for b in BASE_CUBIES:
        m2 = multiply_cubies(b, b); m3 = multiply_cubies(m2, b)
        CUBIE_MOVES.extend([b, m2, m3])
    twist_move = np.zeros((2187, 18), dtype=np.int32)
    for i in range(2187):
        co = set_twist(i)
        for m in range(18): twist_move[i, m] = get_twist([(co[CUBIE_MOVES[m][0][j]] + CUBIE_MOVES[m][1][j]) % 3 for j in range(8)])
    flip_move = np.zeros((2048, 18), dtype=np.int32)
    for i in range(2048):
        eo = set_flip(i)
        for m in range(18): flip_move[i, m] = get_flip([(eo[CUBIE_MOVES[m][2][j]] + CUBIE_MOVES[m][3][j]) % 2 for j in range(12)])
    slice_move = np.zeros((495, 18), dtype=np.int32)
    for i in range(495):
        ep = set_slice(i)
        for m in range(18): slice_move[i, m] = get_slice([ep[CUBIE_MOVES[m][2][j]] for j in range(12)])
    cp_move = np.zeros((40320, 18), dtype=np.int32)
    for i in range(40320):
        cp = set_perm(i, 8)
        for m in range(18): cp_move[i, m] = get_perm([cp[CUBIE_MOVES[m][0][j]] for j in range(8)])
    ep_move = np.zeros((40320, 10), dtype=np.int32)
    for i in range(40320):
        ep = set_perm(i, 8) + [8,9,10,11]
        for idx, m in enumerate(P2_MOVES): ep_move[i, idx] = get_perm([ep[CUBIE_MOVES[m][2][j]] for j in range(12)][:8])
    sep_move = np.zeros((24, 10), dtype=np.int32)
    for i in range(24):
        ep = [0,1,2,3,4,5,6,7] + [x + 8 for x in set_perm(i, 4)]
        for idx, m in enumerate(P2_MOVES): sep_move[i, idx] = get_perm([x - 8 for x in [ep[CUBIE_MOVES[m][2][j]] for j in range(12)][8:12]])
            
    cp_move_p2 = cp_move[:, P2_MOVES]
    prun_p1_ts = build_2d_pruning_table_numba(twist_move, slice_move, 2187, 495, 18)
    prun_p1_fs = build_2d_pruning_table_numba(flip_move, slice_move, 2048, 495, 18)
    prun_p2_cp_sep = build_2d_pruning_table_numba(cp_move_p2, sep_move, 40320, 24, 10)
    prun_p2_ep_sep = build_2d_pruning_table_numba(ep_move, sep_move, 40320, 24, 10)
    FULL_CUBIE_MOVES = CUBIE_MOVES
    INITIALIZED = True

def parse_state(s_str):
    color_map = {s_str[4]:'U', s_str[13]:'R', s_str[22]:'F', s_str[31]:'D', s_str[40]:'L', s_str[49]:'B'}
    s = [color_map.get(c, '?') for c in s_str]
    cp, co, ep, eo = [0]*8, [0]*8, [0]*12, [0]*12
    for i in range(8):
        f = (s[CORNER_FACELETS[i][0]], s[CORNER_FACELETS[i][1]], s[CORNER_FACELETS[i][2]])
        for j in range(8):
            if set(f) == set(STD_CORNERS[j]): cp[i] = j; break
        if f[0] in ('U','D'): co[i] = 0
        elif f[1] in ('U','D'): co[i] = 1
        elif f[2] in ('U','D'): co[i] = 2
    for i in range(12):
        f = (s[EDGE_FACELETS[i][0]], s[EDGE_FACELETS[i][1]])
        for j in range(12):
            if set(f) == set(STD_EDGES[j]): ep[i] = j; break
        if f[0] in ('U','D'): eo[i] = 0
        elif f[1] in ('U','D'): eo[i] = 1
        elif f[0] in ('F','B'): eo[i] = 0
        else: eo[i] = 1
    return cp, co, ep, eo

# 🌟 新增 mode="optimal" 选项
def solve(state_string, mode="twophase", max_depth=25, stop_flag=None):
    init_engine()
    cp, co, ep, eo = parse_state(state_string)
    twist, flip, slc = get_twist(co), get_flip(eo), get_slice(ep)
    
    if twist == 0 and flip == 0 and slc == 0:
        if get_perm(cp) == 0 and get_perm(ep[:8]) == 0 and get_perm([x-8 for x in ep[8:12]]) == 0: return []

    optimal_min_len = [max_depth + 1]

    def search_p2(cp, ep, sep, g, bound, last_face, path):
        if stop_flag and stop_flag(): return
        h = prun_p2_cp_sep[cp * 24 + sep]
        h2 = prun_p2_ep_sep[ep * 24 + sep]
        h = h if h > h2 else h2
        if g + h > bound: return
        
        if h == 0 and g == bound:
            yield list(path)
            return
            
        for idx, m in enumerate(P2_MOVES):
            c_face = m // 3
            if c_face == last_face or c_face == last_face - 3: continue 
            path.append(m)
            yield from search_p2(cp_move_p2[cp, idx], ep_move[ep, idx], sep_move[sep, idx], g+1, bound, c_face, path)
            path.pop()
        
    def search_p1(tws, flp, slc, g, bound, last_face, path):
        if stop_flag and stop_flag(): return
        h = prun_p1_ts[tws * 495 + slc]
        h2 = prun_p1_fs[flp * 495 + slc]
        h = h if h > h2 else h2
        if g + h > bound: return
        
        if h == 0 and g == bound:
            c_cp, c_co, c_ep, c_eo = cp, co, ep, eo
            for m in path: c_cp, c_co, c_ep, c_eo = multiply_cubies((c_cp, c_co, c_ep, c_eo), FULL_CUBIE_MOVES[m])
            p2_cp, p2_ep, p2_sep = get_perm(c_cp), get_perm(c_ep[:8]), get_perm([x-8 for x in c_ep[8:12]])
            p2_h = max(prun_p2_cp_sep[p2_cp * 24 + p2_sep], prun_p2_ep_sep[p2_ep * 24 + p2_sep])
            
            # Optimal 模式允许 P2 探索到极限，Two-phase 模式固定 P2 最大 15步
            max_p2_depth = optimal_min_len[0] - g if mode == "optimal" else 15
            
            for p2_bound in range(p2_h, max_p2_depth + 1):
                for p2_path in search_p2(p2_cp, p2_ep, p2_sep, 0, p2_bound, path[-1]//3 if path else -1, []):
                    tot_len = g + p2_bound
                    if tot_len < optimal_min_len[0]:
                        optimal_min_len[0] = tot_len
                    yield " ".join([MOVES_STR[m] for m in path + p2_path])
                    
                    if mode == "twophase": return

        for m in range(18):
            c_face = m // 3
            if c_face == last_face or c_face == last_face - 3: continue
            path.append(m)
            yield from search_p1(twist_move[tws, m], flip_move[flp, m], slice_move[slc, m], g+1, bound, c_face, path)
            path.pop()

    # 引擎入口：返回包含所有解的 list
    all_sols = []
    for p1_bound in range(0, max_depth + 1):
        if mode == "optimal" and p1_bound >= optimal_min_len[0]:
            break  # 达到最短解的极限，立刻停止，确保全是 God's Number 长度的最优解！
            
        for sol in search_p1(int(twist), int(flip), int(slc), 0, p1_bound, -1, []):
            all_sols.append(sol)
            if mode == "twophase": return [sol] # 两阶段找到第一个就跑！
            
    # 如果是 Optimal 模式，过滤并返回所有长度等于最短长度的解
    if mode == "optimal" and all_sols:
        return [s for s in all_sols if len(s.split()) == optimal_min_len[0]]
        
    return all_sols