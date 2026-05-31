import os
import math
import threading
import numpy as np

# ==============================================================
# CubeLibrary Core Engine (Pure Python + Native Types Optimization)
# ==============================================================
_INIT_LOCK = threading.Lock()
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

def build_2d_pruning_table(MT1, MT2, N1, N2, num_moves):
    prun = np.full(N1 * N2, -1, dtype=np.int8)
    prun[0] = 0
    front = np.array([0], dtype=np.int32)
    depth = 0
    while front.size > 0:
        x, y = front // N2, front % N2
        next_fronts = []
        for m in range(num_moves):
            nidx = MT1[x, m] * N2 + MT2[y, m]
            valid = np.unique(nidx[prun[nidx] == -1])
            valid = valid[prun[valid] == -1]
            prun[valid] = depth + 1
            next_fronts.append(valid)
        if not next_fronts: break
        front = np.concatenate(next_fronts)
        depth += 1
    return prun

INITIALIZED = False

def _setup_fast_globals(twist_move, flip_move, slice_move, cp_move_p2, ep_move, sep_move, prun_p1_ts, prun_p1_fs, prun_p2_cp_sep, prun_p2_ep_sep):
    """提取为独立函数，将 NumPy 数据转为 Python 原生高效格式"""
    global twist_move_l, flip_move_l, slice_move_l, cp_move_p2_l, ep_move_l, sep_move_l
    global prun_p1_ts_b, prun_p1_fs_b, prun_p2_cp_sep_b, prun_p2_ep_sep_b
    
    # 2D 矩阵转为 Python 嵌套 List（纯 Python 中 list[x][y] 读取比 NumPy 快得多）
    twist_move_l = twist_move.tolist()
    flip_move_l = flip_move.tolist()
    slice_move_l = slice_move.tolist()
    cp_move_p2_l = cp_move_p2.tolist()
    ep_move_l = ep_move.tolist()
    sep_move_l = sep_move.tolist()
    
    # 1D 修剪表直接转换为 C 级原生 bytes（无敌提速，-1 溢出为 255 完美促成自然剪枝）
    prun_p1_ts_b = prun_p1_ts.tobytes()
    prun_p1_fs_b = prun_p1_fs.tobytes()
    prun_p2_cp_sep_b = prun_p2_cp_sep.tobytes()
    prun_p2_ep_sep_b = prun_p2_ep_sep.tobytes()

def init_engine():
    global INITIALIZED, FULL_CUBIE_MOVES
    if INITIALIZED: return
    with _INIT_LOCK:
        if INITIALIZED: return  # 双重检查锁定
    
    CUBIE_MOVES = []
    for b in BASE_CUBIES:
        m2 = multiply_cubies(b, b); m3 = multiply_cubies(m2, b)
        CUBIE_MOVES.extend([b, m2, m3])
    FULL_CUBIE_MOVES = CUBIE_MOVES
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CACHE_FILE = os.path.join(BASE_DIR, "cl_tables_cache.npz")
    
    if os.path.exists(CACHE_FILE):
        with np.load(CACHE_FILE) as data:
            _setup_fast_globals(
                data['twist_move'], data['flip_move'], data['slice_move'], 
                data['cp_move_p2'], data['ep_move'], data['sep_move'],
                data['prun_p1_ts'], data['prun_p1_fs'], data['prun_p2_cp_sep'], data['prun_p2_ep_sep']
            )
        INITIALIZED = True
        return

    # 生成表 (耗时操作，仅在无缓存时执行)
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
    prun_p1_ts = build_2d_pruning_table(twist_move, slice_move, 2187, 495, 18)
    prun_p1_fs = build_2d_pruning_table(flip_move, slice_move, 2048, 495, 18)
    prun_p2_cp_sep = build_2d_pruning_table(cp_move_p2, sep_move, 40320, 24, 10)
    prun_p2_ep_sep = build_2d_pruning_table(ep_move, sep_move, 40320, 24, 10)
    
    np.savez_compressed(CACHE_FILE, twist_move=twist_move, flip_move=flip_move, slice_move=slice_move,
                        cp_move_p2=cp_move_p2, ep_move=ep_move, sep_move=sep_move,
                        prun_p1_ts=prun_p1_ts, prun_p1_fs=prun_p1_fs, 
                        prun_p2_cp_sep=prun_p2_cp_sep, prun_p2_ep_sep=prun_p2_ep_sep)
    
    _setup_fast_globals(twist_move, flip_move, slice_move, cp_move_p2, ep_move, sep_move, 
                        prun_p1_ts, prun_p1_fs, prun_p2_cp_sep, prun_p2_ep_sep)
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

def solve(state_string, mode="twophase", max_depth=22, stop_flag=None):
    init_engine()
    cp, co, ep, eo = parse_state(state_string)
    twist, flip, slc = get_twist(co), get_flip(eo), get_slice(ep)
    
    if twist == 0 and flip == 0 and slc == 0:
        if get_perm(cp) == 0 and get_perm(ep[:8]) == 0 and get_perm([x-8 for x in ep[8:12]]) == 0: 
            yield ""
            return

    found_solutions = set()
    global_min = [max_depth + 1]
    
    class StopSearchException(Exception): pass

    def search_p2(cp, ep, sep, g, bound, last_face, path):
        if stop_flag and stop_flag(): raise StopSearchException()
        
        # 🌟 黑科技：用 bytes 原生读取替代 Numpy，避免装箱开销，无需 min/max 函数！
        h1 = prun_p2_cp_sep_b[cp * 24 + sep]
        h2 = prun_p2_ep_sep_b[ep * 24 + sep]
        h = h1 if h1 > h2 else h2
        
        if g + h > bound: return
        
        if h == 0 and g == bound:
            yield list(path)
            return
            
        for idx, m in enumerate(P2_MOVES):
            c_face = m // 3
            if c_face == last_face: continue 
            if c_face in (3, 4, 5) and last_face == c_face - 3: continue 
            
            path.append(m)
            # 🌟 使用预处理的 Python List 替代 Numpy 切片访问
            yield from search_p2(cp_move_p2_l[cp][idx], ep_move_l[ep][idx], sep_move_l[sep][idx], g+1, bound, c_face, path)
            path.pop()
        
    def search_p1(tws, flp, slc, g, bound, p2_target_len, last_face, path):
        if stop_flag and stop_flag(): raise StopSearchException()
        
        # 🌟 同理，bytes 原生读取
        h1 = prun_p1_ts_b[tws * 495 + slc]
        h2 = prun_p1_fs_b[flp * 495 + slc]
        h = h1 if h1 > h2 else h2
        
        if g + h > bound: return
        
        if h == 0 and g == bound:
            c_cp, c_co, c_ep, c_eo = cp, co, ep, eo
            for m in path: c_cp, c_co, c_ep, c_eo = multiply_cubies((c_cp, c_co, c_ep, c_eo), FULL_CUBIE_MOVES[m])
            p2_cp, p2_ep, p2_sep = get_perm(c_cp), get_perm(c_ep[:8]), get_perm([x-8 for x in c_ep[8:12]])
            
            ph1 = prun_p2_cp_sep_b[p2_cp * 24 + p2_sep]
            ph2 = prun_p2_ep_sep_b[p2_ep * 24 + p2_sep]
            p2_h = ph1 if ph1 > ph2 else ph2
            
            if p2_target_len is not None:
                p2_bounds = [p2_target_len] if p2_target_len >= p2_h else []
            else:
                max_p2 = global_min[0] - g - 1
                p2_bounds = range(p2_h, max_p2 + 1)

            for p2_bound in p2_bounds:
                found_in_this_p1 = False
                for p2_path in search_p2(p2_cp, p2_ep, p2_sep, 0, p2_bound, path[-1]//3 if path else -1, []):
                    sol_str = " ".join([MOVES_STR[m] for m in path + p2_path])
                    if sol_str not in found_solutions:
                        found_solutions.add(sol_str)
                        if p2_target_len is None:
                            tot_len = g + p2_bound
                            if tot_len < global_min[0]:
                                global_min[0] = tot_len
                        yield sol_str
                        found_in_this_p1 = True
                        
                if p2_target_len is None and found_in_this_p1:
                    break

        for m in range(18):
            c_face = m // 3
            if c_face == last_face: continue
            if c_face in (3, 4, 5) and last_face == c_face - 3: continue
            
            path.append(m)
            # 🌟 List 提速读取
            yield from search_p1(twist_move_l[tws][m], flip_move_l[flp][m], slice_move_l[slc][m], g+1, bound, p2_target_len, c_face, path)
            path.pop()

    try:
        if mode == "optimal":
            absolute_min = None
            margin = 2  
            
            for target_len in range(0, max_depth + 1):
                if stop_flag and stop_flag(): break
                if absolute_min is not None and target_len > absolute_min + margin:
                    break
                
                for p1_bound in range(0, target_len + 1):
                    if stop_flag and stop_flag(): break
                    p2_target = target_len - p1_bound
                    for sol in search_p1(int(twist), int(flip), int(slc), 0, p1_bound, p2_target, -1, []):
                        if absolute_min is None:
                            absolute_min = target_len  
                        yield sol
        else:
            for p1_bound in range(0, max_depth + 1):
                if stop_flag and stop_flag(): break
                if p1_bound >= global_min[0]: 
                    break 
                yield from search_p1(int(twist), int(flip), int(slc), 0, p1_bound, None, -1, [])
                
    except StopSearchException:
        pass