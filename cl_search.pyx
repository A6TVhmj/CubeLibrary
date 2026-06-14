# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""
cl_search.pyx — Cython IDA* search core for Cube Library.
Compile: python setup.py build_ext --inplace
"""
import numpy as np
cimport numpy as cnp
from libc.string cimport memcpy
cnp.import_array()

DEF MD  = 30
DEF MS  = 256
DEF MP2 = 512

ctypedef struct SState:
    int* twist_move
    int* flip_move
    int* slice_move
    int* cp_move_p2
    int* ep_move
    int* sep_move
    unsigned char* prun_ts
    unsigned char* prun_fs
    unsigned char* prun_cp_sep
    unsigned char* prun_ep_sep
    int cubie[18][40]
    int face_of[18]
    int p2_moves[10]
    bint can_follow[7][6]
    int scp[32][8]
    int sco[32][8]
    int sep_[32][12]
    int seo[32][12]
    int p1_path[MD]
    int p2_path[MD]
    int p2_res[MP2][MD]
    int p2_lens[MP2]
    int p2_cnt
    int sol[MS][MD]
    int sol_len[MS]
    int sol_cnt
    int gmin
    int max_sol

cdef SState _S
_np_refs = {}

MOVES_STR = ["U","U2","U'","R","R2","R'","F","F2","F'",
             "D","D2","D'","L","L2","L'","B","B2","B'"]

# ── helpers ──────────────────────────────────────────────────

cdef inline int perm8(int* a) noexcept nogil:
    cdef int a0=a[0],a1=a[1],a2=a[2],a3=a[3],a4=a[4],a5=a[5],a6=a[6],a7=a[7]
    return (((a1<a0)+(a2<a0)+(a3<a0)+(a4<a0)+(a5<a0)+(a6<a0)+(a7<a0))*5040+
            ((a2<a1)+(a3<a1)+(a4<a1)+(a5<a1)+(a6<a1)+(a7<a1))*720+
            ((a3<a2)+(a4<a2)+(a5<a2)+(a6<a2)+(a7<a2))*120+
            ((a4<a3)+(a5<a3)+(a6<a3)+(a7<a3))*24+
            ((a5<a4)+(a6<a4)+(a7<a4))*6+
            ((a6<a5)+(a7<a5))*2+(a7<a6))

cdef inline int perm4(int* a) noexcept nogil:
    return ((a[1]<a[0])+(a[2]<a[0])+(a[3]<a[0]))*6+((a[2]<a[1])+(a[3]<a[1]))*2+(a[3]<a[2])

cdef inline void apply_mv(SState* S, int g, int mv) noexcept nogil:
    cdef int j, idx
    cdef int* cm = S.cubie[mv]
    for j in range(8):
        idx = cm[j]
        S.scp[g+1][j] = S.scp[g][idx]
        S.sco[g+1][j] = (S.sco[g][idx] + cm[8+j]) % 3
    for j in range(12):
        idx = cm[16+j]
        S.sep_[g+1][j] = S.sep_[g][idx]
        S.seo[g+1][j] = (S.seo[g][idx] + cm[28+j]) & 1

# ── Phase 2 ──────────────────────────────────────────────────

cdef void srch_p2(SState* S, int cpv, int epv, int sepv,
                  int g, int bound, int lf) noexcept nogil:
    cdef int h1, h2, h, idx, m, cf, lf1
    h1 = <int>S.prun_cp_sep[cpv*24+sepv]
    h2 = <int>S.prun_ep_sep[epv*24+sepv]
    h = h1 if h1>h2 else h2
    if g+h > bound: return
    if h==0 and g==bound:
        if S.p2_cnt < MP2:
            S.p2_lens[S.p2_cnt] = g
            memcpy(&S.p2_res[S.p2_cnt][0], S.p2_path, g*sizeof(int))
            S.p2_cnt += 1
        return
    lf1 = lf+1
    for idx in range(10):
        m = S.p2_moves[idx]; cf = S.face_of[m]
        if not S.can_follow[lf1][cf]: continue
        S.p2_path[g] = m
        srch_p2(S, S.cp_move_p2[cpv*10+idx], S.ep_move[epv*10+idx],
                S.sep_move[sepv*10+idx], g+1, bound, cf)

# ── Phase 1 — twophase ───────────────────────────────────────

cdef void srch_p1_tp(SState* S, int tw, int fl, int sl,
                     int g, int bound, int lf) noexcept nogil:
    cdef int h1,h2,h,m,cf,lf1,pc,pe,ps,ph1,ph2,ph,p2b,ri,tot
    cdef int sa[4]
    h1 = <int>S.prun_ts[tw*495+sl]; h2 = <int>S.prun_fs[fl*495+sl]
    h = h1 if h1>h2 else h2
    if g+h > bound: return
    if h==0 and g==bound:
        pc = perm8(S.scp[g]); pe = perm8(S.sep_[g])
        sa[0]=S.sep_[g][8]-8; sa[1]=S.sep_[g][9]-8
        sa[2]=S.sep_[g][10]-8; sa[3]=S.sep_[g][11]-8
        ps = perm4(sa)
        ph1 = <int>S.prun_cp_sep[pc*24+ps]; ph2 = <int>S.prun_ep_sep[pe*24+ps]
        ph = ph1 if ph1>ph2 else ph2
        for p2b in range(ph, S.gmin-g):
            S.p2_cnt = 0
            srch_p2(S, pc, pe, ps, 0, p2b,
                    S.face_of[S.p1_path[g-1]] if g>0 else -1)
            if S.p2_cnt > 0:
                for ri in range(S.p2_cnt):
                    if S.sol_cnt >= S.max_sol: return
                    tot = g + S.p2_lens[ri]
                    if tot < S.gmin: S.gmin = tot
                    S.sol_len[S.sol_cnt] = tot
                    memcpy(&S.sol[S.sol_cnt][0], S.p1_path, g*sizeof(int))
                    memcpy(&S.sol[S.sol_cnt][g], &S.p2_res[ri][0],
                           S.p2_lens[ri]*sizeof(int))
                    S.sol_cnt += 1
                break
        return
    lf1 = lf+1
    for m in range(18):
        cf = S.face_of[m]
        if not S.can_follow[lf1][cf]: continue
        S.p1_path[g] = m; apply_mv(S, g, m)
        srch_p1_tp(S, S.twist_move[tw*18+m], S.flip_move[fl*18+m],
                   S.slice_move[sl*18+m], g+1, bound, cf)
        if S.sol_cnt >= S.max_sol: return

# ── Phase 1 — optimal ────────────────────────────────────────

cdef void srch_p1_opt(SState* S, int tw, int fl, int sl,
                      int g, int bound, int p2tl, int lf) noexcept nogil:
    cdef int h1,h2,h,m,cf,lf1,pc,pe,ps,ph1,ph2,ph,ri,tot
    cdef int sa[4]
    h1 = <int>S.prun_ts[tw*495+sl]; h2 = <int>S.prun_fs[fl*495+sl]
    h = h1 if h1>h2 else h2
    if g+h > bound: return
    if h==0 and g==bound:
        pc = perm8(S.scp[g]); pe = perm8(S.sep_[g])
        sa[0]=S.sep_[g][8]-8; sa[1]=S.sep_[g][9]-8
        sa[2]=S.sep_[g][10]-8; sa[3]=S.sep_[g][11]-8
        ps = perm4(sa)
        ph1 = <int>S.prun_cp_sep[pc*24+ps]; ph2 = <int>S.prun_ep_sep[pe*24+ps]
        ph = ph1 if ph1>ph2 else ph2
        if p2tl >= ph:
            S.p2_cnt = 0
            srch_p2(S, pc, pe, ps, 0, p2tl,
                    S.face_of[S.p1_path[g-1]] if g>0 else -1)
            for ri in range(S.p2_cnt):
                if S.sol_cnt >= S.max_sol: return
                tot = g + S.p2_lens[ri]
                S.sol_len[S.sol_cnt] = tot
                memcpy(&S.sol[S.sol_cnt][0], S.p1_path, g*sizeof(int))
                memcpy(&S.sol[S.sol_cnt][g], &S.p2_res[ri][0],
                       S.p2_lens[ri]*sizeof(int))
                S.sol_cnt += 1
        return
    lf1 = lf+1
    for m in range(18):
        cf = S.face_of[m]
        if not S.can_follow[lf1][cf]: continue
        S.p1_path[g] = m; apply_mv(S, g, m)
        srch_p1_opt(S, S.twist_move[tw*18+m], S.flip_move[fl*18+m],
                    S.slice_move[sl*18+m], g+1, bound, p2tl, cf)
        if S.sol_cnt >= S.max_sol: return

# ── Python API ───────────────────────────────────────────────

def load_tables(twist_move_np, flip_move_np, slice_move_np,
                cp_move_p2_np, ep_move_np, sep_move_np,
                prun_ts_np, prun_fs_np, prun_cp_sep_np, prun_ep_sep_np,
                list cubie_moves_list):
    global _np_refs
    cdef cnp.ndarray tw = np.ascontiguousarray(twist_move_np, dtype=np.intc)
    cdef cnp.ndarray fl = np.ascontiguousarray(flip_move_np, dtype=np.intc)
    cdef cnp.ndarray sl = np.ascontiguousarray(slice_move_np, dtype=np.intc)
    cdef cnp.ndarray cp = np.ascontiguousarray(cp_move_p2_np, dtype=np.intc)
    cdef cnp.ndarray ep = np.ascontiguousarray(ep_move_np, dtype=np.intc)
    cdef cnp.ndarray sp = np.ascontiguousarray(sep_move_np, dtype=np.intc)
    cdef cnp.ndarray pts = np.ascontiguousarray(
        np.asarray(prun_ts_np, dtype=np.int8).view(np.uint8))
    cdef cnp.ndarray pfs = np.ascontiguousarray(
        np.asarray(prun_fs_np, dtype=np.int8).view(np.uint8))
    cdef cnp.ndarray pcs = np.ascontiguousarray(
        np.asarray(prun_cp_sep_np, dtype=np.int8).view(np.uint8))
    cdef cnp.ndarray pes = np.ascontiguousarray(
        np.asarray(prun_ep_sep_np, dtype=np.int8).view(np.uint8))

    _S.twist_move=<int*>tw.data; _S.flip_move=<int*>fl.data
    _S.slice_move=<int*>sl.data; _S.cp_move_p2=<int*>cp.data
    _S.ep_move=<int*>ep.data;    _S.sep_move=<int*>sp.data
    _S.prun_ts=<unsigned char*>pts.data; _S.prun_fs=<unsigned char*>pfs.data
    _S.prun_cp_sep=<unsigned char*>pcs.data; _S.prun_ep_sep=<unsigned char*>pes.data
    _np_refs = {'tw':tw,'fl':fl,'sl':sl,'cp':cp,'ep':ep,'sp':sp,
                'pts':pts,'pfs':pfs,'pcs':pcs,'pes':pes}
    cdef int i, j, a, b
    for i in range(18): _S.face_of[i] = i // 3
    _S.p2_moves[0]=0;_S.p2_moves[1]=1;_S.p2_moves[2]=2;_S.p2_moves[3]=9
    _S.p2_moves[4]=10;_S.p2_moves[5]=11;_S.p2_moves[6]=4;_S.p2_moves[7]=13
    _S.p2_moves[8]=7;_S.p2_moves[9]=16
    for a in range(7):
        for b in range(6): _S.can_follow[a][b] = True
    for a in range(6): _S.can_follow[a+1][a] = False
    _S.can_follow[1][3]=False; _S.can_follow[2][4]=False; _S.can_follow[3][5]=False
    for i in range(18):
        cm = cubie_moves_list[i]
        for j in range(8):
            _S.cubie[i][j] = cm[0][j]; _S.cubie[i][8+j] = cm[1][j]
        for j in range(12):
            _S.cubie[i][16+j] = cm[2][j]; _S.cubie[i][28+j] = cm[3][j]

cdef void _init_stack(list cp, list co, list ep, list eo):
    cdef int j
    for j in range(8):  _S.scp[0][j]=cp[j]; _S.sco[0][j]=co[j]
    for j in range(12): _S.sep_[0][j]=ep[j]; _S.seo[0][j]=eo[j]

cdef list _collect():
    cdef int i, k
    result = []; seen = set()
    for i in range(_S.sol_cnt):
        parts = []
        for k in range(_S.sol_len[i]): parts.append(MOVES_STR[_S.sol[i][k]])
        s = " ".join(parts)
        if s not in seen: seen.add(s); result.append(s)
    return result

def solve_twophase_gen(int twist, int flip, int slc,
                       list cp, list co, list ep, list eo,
                       int max_depth, object stop_callable=None):
    _init_stack(cp, co, ep, eo)
    _S.gmin = max_depth + 1; _S.sol_cnt = 0
    seen = set()
    cdef int p1b, prev, i, k
    for p1b in range(max_depth + 1):
        if stop_callable is not None and stop_callable(): break
        if p1b >= _S.gmin: break
        prev = _S.sol_cnt; _S.max_sol = prev + 1
        with nogil: srch_p1_tp(&_S, twist, flip, slc, 0, p1b, -1)
        for i in range(prev, _S.sol_cnt):
            parts = []
            for k in range(_S.sol_len[i]): parts.append(MOVES_STR[_S.sol[i][k]])
            s = " ".join(parts)
            if s not in seen: seen.add(s); yield s

def solve_optimal_gen(int twist, int flip, int slc,
                      list cp, list co, list ep, list eo,
                      int max_depth, object stop_callable=None):
    _init_stack(cp, co, ep, eo)
    _S.sol_cnt = 0; seen = set()
    cdef int tl, p1b, prev, i, k, abs_min = -1
    for tl in range(max_depth + 1):
        if stop_callable is not None and stop_callable(): break
        if abs_min >= 0 and tl > abs_min + 2: break
        for p1b in range(tl + 1):
            if stop_callable is not None and stop_callable(): break
            prev = _S.sol_cnt; _S.max_sol = prev + 1
            with nogil: srch_p1_opt(&_S, twist, flip, slc, 0, p1b, tl-p1b, -1)
            for i in range(prev, _S.sol_cnt):
                parts = []
                for k in range(_S.sol_len[i]): parts.append(MOVES_STR[_S.sol[i][k]])
                s = " ".join(parts)
                if s not in seen:
                    seen.add(s)
                    if abs_min < 0: abs_min = tl
                    yield s
