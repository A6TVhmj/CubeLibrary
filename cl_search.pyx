# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""
cl_search.pyx — Cython IDA* search core for Cube Library. (A 版：快解模式)
Thread-safe: 每次调用 malloc 独立的 SState，不使用全局可变状态。
Compile: python setup.py build_ext --inplace

A 版改动：
1. 新增 twist×flip 组合剪枝表 prun_tf，h = max(h_ts, h_fs, h_tf)，剪枝更强。
2. twophase 快解模式：phase-1 到达 G1 即尝试 phase-2（不再要求恰好 bound），
   phase-2 只在小窗口 [ph, ph+4] 内搜索，首个解秒级产出，gmin 逐步收紧。
3. 搜索中途周期性检查 stop 标志（每 1M 节点），停止按钮立即可用。
"""
import numpy as np
cimport numpy as cnp
from libc.stdlib cimport malloc, free
from libc.string cimport memcpy, memset
from cpython.ref cimport PyObject, Py_INCREF, Py_XDECREF
cnp.import_array()

DEF MD  = 30
DEF MS  = 256
DEF MP2 = 512

# ── 搜索状态结构体 ───────────────────────────────────────────
ctypedef struct SState:
    # move tables (只读指针，所有线程共享)
    int* twist_move
    int* flip_move
    int* slice_move
    int* cp_move_p2
    int* ep_move
    int* sep_move
    unsigned char* prun_ts
    unsigned char* prun_fs
    unsigned char* prun_tf
    unsigned char* prun_cp_sep
    unsigned char* prun_ep_sep
    int cubie[18][40]
    int face_of[18]
    int p2_moves[10]
    bint can_follow[7][6]
    # 搜索可变状态（每线程独立）
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
    # 中途中断支持
    PyObject* stop_ref
    int stop_req
    long long node_cnt

# ── 只读共享模板（load_tables 写入一次，之后只读） ───────────
ctypedef struct SharedTables:
    int* twist_move
    int* flip_move
    int* slice_move
    int* cp_move_p2
    int* ep_move
    int* sep_move
    unsigned char* prun_ts
    unsigned char* prun_fs
    unsigned char* prun_tf
    unsigned char* prun_cp_sep
    unsigned char* prun_ep_sep
    int cubie[18][40]
    int face_of[18]
    int p2_moves[10]
    bint can_follow[7][6]

cdef SharedTables _shared
_np_refs = {}           # prevent GC
_tables_loaded = False

MOVES_STR = ["U","U2","U'","R","R2","R'","F","F2","F'",
             "D","D2","D'","L","L2","L'","B","B2","B'"]

# ── helpers (nogil) ──────────────────────────────────────────

cdef inline bint can_follow_ok(int lf2, int lf, int cf) noexcept nogil:
    """面序列合法性：
    1. 禁同面连续（U U'）；
    2. 禁相对面单向相邻（U→D、R→L、F→B）——相对面转动可交换，
       两种顺序本质等价，只保留一个方向；
    3. 禁相对面交替三次（X Y X，防御，已被 2 覆盖）。
    """
    if cf == lf:
        return False
    if (lf == 0 and cf == 3) or (lf == 1 and cf == 4) or (lf == 2 and cf == 5):
        return False
    if lf2 >= 0 and cf == lf2 and (lf == cf + 3 or lf == cf - 3):
        return False
    return True

cdef inline void check_stop(SState* S) noexcept nogil:
    S.node_cnt += 1
    if (S.node_cnt & 0xFFFFF) == 0:
        with gil:
            if S.stop_ref != NULL:
                if (<object>S.stop_ref) is not None and (<object>S.stop_ref)():
                    S.stop_req = 1

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

# ── Phase 2 (nogil) ─────────────────────────────────────────

cdef void srch_p2(SState* S, int cpv, int epv, int sepv,
                  int g, int bound, int lf, int lf2) noexcept nogil:
    cdef int h1, h2, h, idx, m, cf
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
    for idx in range(10):
        m = S.p2_moves[idx]; cf = S.face_of[m]
        if not can_follow_ok(lf2, lf, cf): continue
        S.p2_path[g] = m
        srch_p2(S, S.cp_move_p2[cpv*10+idx], S.ep_move[epv*10+idx],
                S.sep_move[sepv*10+idx], g+1, bound, cf, lf)

# ── Phase 1 — twophase 快解模式 (nogil) ───────────────────────

cdef void srch_p1_tp(SState* S, int tw, int fl, int sl,
                     int g, int bound, int lf, int lf2) noexcept nogil:
    cdef int h1,h2,h3,h,m,cf,pc,pe,ps,ph1,ph2,ph,p2b,p2hi,ri,tot
    cdef int sa[4]
    check_stop(S)
    if S.stop_req: return
    h1 = <int>S.prun_ts[tw*495+sl]; h2 = <int>S.prun_fs[fl*495+sl]
    h3 = <int>S.prun_tf[tw*2048+fl]
    h = h1 if h1>h2 else h2
    if h3 > h: h = h3
    if g+h > bound: return
    if h==0:
        # 到达 G1 坐标：小窗口内尝试 phase-2，先产出快解
        pc = perm8(S.scp[g]); pe = perm8(S.sep_[g])
        sa[0]=S.sep_[g][8]-8; sa[1]=S.sep_[g][9]-8
        sa[2]=S.sep_[g][10]-8; sa[3]=S.sep_[g][11]-8
        ps = perm4(sa)
        ph1 = <int>S.prun_cp_sep[pc*24+ps]; ph2 = <int>S.prun_ep_sep[pe*24+ps]
        ph = ph1 if ph1 > ph2 else ph2
        if ph < 0:
            ph = 0
        p2hi = S.gmin - g + 2
        if p2hi > ph + 6: p2hi = ph + 6
        found_any = False
        for p2b in range(ph, p2hi):
            S.p2_cnt = 0
            srch_p2(S, pc, pe, ps, 0, p2b,
                    S.face_of[S.p1_path[g-1]] if g>0 else -1,
                    S.face_of[S.p1_path[g-2]] if g>1 else -1)
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
                found_any = True
                break
        if not found_any and S.gmin - g + 2 > p2hi:
            # 快窗口未命中：扩大窗口兜底（极深 phase-2 状态）
            for p2b in range(p2hi, S.gmin - g + 2):
                S.p2_cnt = 0
                srch_p2(S, pc, pe, ps, 0, p2b,
                        S.face_of[S.p1_path[g-1]] if g>0 else -1,
                        S.face_of[S.p1_path[g-2]] if g>1 else -1)
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
                    found_any = True
                    break
        if found_any:
            return
        # phase-2 未找到：状态可能在 G1 坐标但不在 G1 群，
        # 继续 phase-1 深入，寻找群内的坐标归零状态
    for m in range(18):
        cf = S.face_of[m]
        if not can_follow_ok(lf2, lf, cf): continue
        S.p1_path[g] = m; apply_mv(S, g, m)
        srch_p1_tp(S, S.twist_move[tw*18+m], S.flip_move[fl*18+m],
                   S.slice_move[sl*18+m], g+1, bound, cf, lf)
        if S.sol_cnt >= S.max_sol: return

# ── Phase 1 — optimal (nogil) ────────────────────────────────

cdef void srch_p1_opt(SState* S, int tw, int fl, int sl,
                      int g, int bound, int p2tl, int lf, int lf2) noexcept nogil:
    cdef int h1,h2,h3,h,m,cf,pc,pe,ps,ph1,ph2,ph,ri,tot
    cdef int sa[4]
    check_stop(S)
    if S.stop_req: return
    h1 = <int>S.prun_ts[tw*495+sl]; h2 = <int>S.prun_fs[fl*495+sl]
    h3 = <int>S.prun_tf[tw*2048+fl]
    h = h1 if h1>h2 else h2
    if h3 > h: h = h3
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
                    S.face_of[S.p1_path[g-1]] if g>0 else -1,
                    S.face_of[S.p1_path[g-2]] if g>1 else -1)
            for ri in range(S.p2_cnt):
                if S.sol_cnt >= S.max_sol: return
                tot = g + S.p2_lens[ri]
                S.sol_len[S.sol_cnt] = tot
                memcpy(&S.sol[S.sol_cnt][0], S.p1_path, g*sizeof(int))
                memcpy(&S.sol[S.sol_cnt][g], &S.p2_res[ri][0],
                       S.p2_lens[ri]*sizeof(int))
                S.sol_cnt += 1
        return
    for m in range(18):
        cf = S.face_of[m]
        if not can_follow_ok(lf2, lf, cf): continue
        S.p1_path[g] = m; apply_mv(S, g, m)
        srch_p1_opt(S, S.twist_move[tw*18+m], S.flip_move[fl*18+m],
                    S.slice_move[sl*18+m], g+1, bound, p2tl, cf, lf)
        if S.sol_cnt >= S.max_sol: return

# ── 内部工具：从 SharedTables 初始化一个 SState ──────────────

cdef SState* _new_state(list cp, list co, list ep, list eo):
    """malloc 一个 SState，复制只读表指针 + 初始化 cubie 栈。"""
    cdef SState* S = <SState*>malloc(sizeof(SState))
    if S == NULL:
        raise MemoryError("Failed to allocate SState")
    memset(S, 0, sizeof(SState))
    # 复制只读共享数据
    S.twist_move  = _shared.twist_move
    S.flip_move   = _shared.flip_move
    S.slice_move  = _shared.slice_move
    S.cp_move_p2  = _shared.cp_move_p2
    S.ep_move     = _shared.ep_move
    S.sep_move    = _shared.sep_move
    S.prun_ts     = _shared.prun_ts
    S.prun_fs     = _shared.prun_fs
    S.prun_tf     = _shared.prun_tf
    S.prun_cp_sep = _shared.prun_cp_sep
    S.prun_ep_sep = _shared.prun_ep_sep
    memcpy(S.cubie,      _shared.cubie,      sizeof(_shared.cubie))
    memcpy(S.face_of,    _shared.face_of,    sizeof(_shared.face_of))
    memcpy(S.p2_moves,   _shared.p2_moves,   sizeof(_shared.p2_moves))
    memcpy(S.can_follow, _shared.can_follow, sizeof(_shared.can_follow))
    # 初始化 cubie 栈底
    cdef int j
    for j in range(8):
        S.scp[0][j] = cp[j]; S.sco[0][j] = co[j]
    for j in range(12):
        S.sep_[0][j] = ep[j]; S.seo[0][j] = eo[j]
    S.sol_cnt = 0
    return S

cdef list _collect(SState* S):
    """从 SState 中收集解字符串列表。"""
    cdef int i, k
    result = []; seen = set()
    for i in range(S.sol_cnt):
        parts = []
        for k in range(S.sol_len[i]):
            parts.append(MOVES_STR[S.sol[i][k]])
        s = " ".join(parts)
        if s not in seen:
            seen.add(s); result.append(s)
    return result

# ── Python API（线程安全） ───────────────────────────────────

def load_tables(twist_move_np, flip_move_np, slice_move_np,
                cp_move_p2_np, ep_move_np, sep_move_np,
                prun_ts_np, prun_fs_np, prun_tf_np,
                prun_cp_sep_np, prun_ep_sep_np,
                list cubie_moves_list):
    """加载移动表到只读共享模板（只调用一次）。"""
    global _np_refs, _tables_loaded

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
    cdef cnp.ndarray ptf = np.ascontiguousarray(
        np.asarray(prun_tf_np, dtype=np.int8).view(np.uint8))
    cdef cnp.ndarray pcs = np.ascontiguousarray(
        np.asarray(prun_cp_sep_np, dtype=np.int8).view(np.uint8))
    cdef cnp.ndarray pes = np.ascontiguousarray(
        np.asarray(prun_ep_sep_np, dtype=np.int8).view(np.uint8))

    _shared.twist_move  = <int*>tw.data
    _shared.flip_move   = <int*>fl.data
    _shared.slice_move  = <int*>sl.data
    _shared.cp_move_p2  = <int*>cp.data
    _shared.ep_move     = <int*>ep.data
    _shared.sep_move    = <int*>sp.data
    _shared.prun_ts     = <unsigned char*>pts.data
    _shared.prun_fs     = <unsigned char*>pfs.data
    _shared.prun_tf     = <unsigned char*>ptf.data
    _shared.prun_cp_sep = <unsigned char*>pcs.data
    _shared.prun_ep_sep = <unsigned char*>pes.data

    _np_refs = {'tw':tw,'fl':fl,'sl':sl,
                'cp':cp,'ep':ep,'sp':sp,
                'pts':pts,'pfs':pfs,'ptf':ptf,'pcs':pcs,'pes':pes}

    cdef int i, j, a, b
    for i in range(18):
        _shared.face_of[i] = i // 3
    _shared.p2_moves[0]=0;_shared.p2_moves[1]=1;_shared.p2_moves[2]=2
    _shared.p2_moves[3]=9;_shared.p2_moves[4]=10;_shared.p2_moves[5]=11
    _shared.p2_moves[6]=4;_shared.p2_moves[7]=13
    _shared.p2_moves[8]=7;_shared.p2_moves[9]=16
    for a in range(7):
        for b in range(6):
            _shared.can_follow[a][b] = True
    for a in range(6):
        _shared.can_follow[a+1][a] = False
    _shared.can_follow[1][3]=False
    _shared.can_follow[2][4]=False
    _shared.can_follow[3][5]=False
    for i in range(18):
        cm = cubie_moves_list[i]
        for j in range(8):
            _shared.cubie[i][j]    = cm[0][j]
            _shared.cubie[i][8+j]  = cm[1][j]
        for j in range(12):
            _shared.cubie[i][16+j] = cm[2][j]
            _shared.cubie[i][28+j] = cm[3][j]

    _tables_loaded = True


def solve_twophase_gen(int twist, int flip, int slc,
                       list cp, list co, list ep, list eo,
                       int max_depth, object stop_callable=None):
    """线程安全的 Two-Phase generator（A 版快解模式）。每次调用独立分配搜索状态。"""
    if not _tables_loaded:
        raise RuntimeError("Tables not loaded. Call load_tables() first.")

    cdef SState* S = _new_state(cp, co, ep, eo)
    cdef int p1b, prev, i, k
    try:
        if stop_callable is not None:
            Py_INCREF(stop_callable)
            S.stop_ref = <PyObject*>stop_callable
        S.gmin = max_depth + 1
        seen = set()
        for p1b in range(max_depth + 1):
            if stop_callable is not None and stop_callable():
                break
            if p1b > S.gmin:
                break
            prev = S.sol_cnt
            S.max_sol = min(prev + 64, MS)
            with nogil:
                srch_p1_tp(S, twist, flip, slc, 0, p1b, -1, -1)
            for i in range(prev, S.sol_cnt):
                parts = []
                for k in range(S.sol_len[i]):
                    parts.append(MOVES_STR[S.sol[i][k]])
                s = " ".join(parts)
                if s not in seen:
                    seen.add(s)
                    yield s
    finally:
        if S.stop_ref != NULL:
            Py_XDECREF(S.stop_ref)
            S.stop_ref = NULL
        free(S)


def solve_optimal_gen(int twist, int flip, int slc,
                      list cp, list co, list ep, list eo,
                      int max_depth, object stop_callable=None):
    """线程安全的 Optimal generator。每次调用独立分配搜索状态。"""
    if not _tables_loaded:
        raise RuntimeError("Tables not loaded. Call load_tables() first.")

    cdef SState* S = _new_state(cp, co, ep, eo)
    cdef int tl, p1b, prev, i, k, abs_min = -1
    try:
        if stop_callable is not None:
            Py_INCREF(stop_callable)
            S.stop_ref = <PyObject*>stop_callable
        seen = set()
        for tl in range(max_depth + 1):
            if stop_callable is not None and stop_callable():
                break
            if abs_min >= 0 and tl > abs_min + 2:
                break
            for p1b in range(tl + 1):
                if stop_callable is not None and stop_callable():
                    break
                prev = S.sol_cnt
                S.max_sol = min(prev + 64, MS)
                with nogil:
                    srch_p1_opt(S, twist, flip, slc, 0, p1b, tl - p1b, -1, -1)
                for i in range(prev, S.sol_cnt):
                    parts = []
                    for k in range(S.sol_len[i]):
                        parts.append(MOVES_STR[S.sol[i][k]])
                    s = " ".join(parts)
                    if s not in seen:
                        seen.add(s)
                        if abs_min < 0:
                            abs_min = tl
                        yield s
    finally:
        if S.stop_ref != NULL:
            Py_XDECREF(S.stop_ref)
            S.stop_ref = NULL
        free(S)

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# ��ȱ��ȫ��������Cython ���ٰ棩
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


# ── 残缺补全生成器（Cython 快速版，迭代 DFS，线程安全） ──────


# ── 残缺补全生成器（Cython 快速版，迭代 DFS，线程安全） ──────
cdef int CC_CORNER_FACELETS[8][3]
cdef int CC_EDGE_FACELETS[12][2]
cdef int CC_STD_CORNERS[8][3]
cdef int CC_STD_EDGES[12][2]
cdef int CC_CORNER_ORI[8][3][3]
cdef int CC_EDGE_ORI[12][2][2]
cdef int CC_FACE_ASCII[6]
cdef bint CC_INITED = False

cdef void _cc_init_tables() noexcept nogil:
    global CC_INITED
    if CC_INITED:
        return
    cdef int i, j
    cdef int cf[8][3]
    cdef int ef[12][2]
    cdef int sc[8][3]
    cdef int se[12][2]
    cf[0][0]=8; cf[0][1]=9; cf[0][2]=20
    cf[1][0]=6; cf[1][1]=18; cf[1][2]=38
    cf[2][0]=0; cf[2][1]=36; cf[2][2]=47
    cf[3][0]=2; cf[3][1]=45; cf[3][2]=11
    cf[4][0]=29; cf[4][1]=26; cf[4][2]=15
    cf[5][0]=27; cf[5][1]=44; cf[5][2]=24
    cf[6][0]=33; cf[6][1]=53; cf[6][2]=42
    cf[7][0]=35; cf[7][1]=17; cf[7][2]=51
    ef[0][0]=5; ef[0][1]=10
    ef[1][0]=7; ef[1][1]=19
    ef[2][0]=3; ef[2][1]=37
    ef[3][0]=1; ef[3][1]=46
    ef[4][0]=32; ef[4][1]=16
    ef[5][0]=28; ef[5][1]=25
    ef[6][0]=30; ef[6][1]=43
    ef[7][0]=34; ef[7][1]=52
    ef[8][0]=23; ef[8][1]=12
    ef[9][0]=21; ef[9][1]=41
    ef[10][0]=50; ef[10][1]=39
    ef[11][0]=48; ef[11][1]=14
    sc[0][0]=0; sc[0][1]=1; sc[0][2]=2
    sc[1][0]=0; sc[1][1]=2; sc[1][2]=4
    sc[2][0]=0; sc[2][1]=4; sc[2][2]=5
    sc[3][0]=0; sc[3][1]=5; sc[3][2]=1
    sc[4][0]=3; sc[4][1]=2; sc[4][2]=1
    sc[5][0]=3; sc[5][1]=4; sc[5][2]=2
    sc[6][0]=3; sc[6][1]=5; sc[6][2]=4
    sc[7][0]=3; sc[7][1]=1; sc[7][2]=5
    se[0][0]=0; se[0][1]=1
    se[1][0]=0; se[1][1]=2
    se[2][0]=0; se[2][1]=4
    se[3][0]=0; se[3][1]=5
    se[4][0]=3; se[4][1]=1
    se[5][0]=3; se[5][1]=2
    se[6][0]=3; se[6][1]=4
    se[7][0]=3; se[7][1]=5
    se[8][0]=2; se[8][1]=1
    se[9][0]=2; se[9][1]=4
    se[10][0]=5; se[10][1]=4
    se[11][0]=5; se[11][1]=1
    for i in range(8):
        for j in range(3):
            CC_CORNER_FACELETS[i][j] = cf[i][j]
            CC_STD_CORNERS[i][j] = sc[i][j]
    for i in range(12):
        for j in range(2):
            CC_EDGE_FACELETS[i][j] = ef[i][j]
            CC_STD_EDGES[i][j] = se[i][j]
    for i in range(8):
        CC_CORNER_ORI[i][0][0] = CC_STD_CORNERS[i][0]
        CC_CORNER_ORI[i][0][1] = CC_STD_CORNERS[i][1]
        CC_CORNER_ORI[i][0][2] = CC_STD_CORNERS[i][2]
        CC_CORNER_ORI[i][1][0] = CC_STD_CORNERS[i][1]
        CC_CORNER_ORI[i][1][1] = CC_STD_CORNERS[i][2]
        CC_CORNER_ORI[i][1][2] = CC_STD_CORNERS[i][0]
        CC_CORNER_ORI[i][2][0] = CC_STD_CORNERS[i][2]
        CC_CORNER_ORI[i][2][1] = CC_STD_CORNERS[i][0]
        CC_CORNER_ORI[i][2][2] = CC_STD_CORNERS[i][1]
    for i in range(12):
        CC_EDGE_ORI[i][0][0] = CC_STD_EDGES[i][0]
        CC_EDGE_ORI[i][0][1] = CC_STD_EDGES[i][1]
        CC_EDGE_ORI[i][1][0] = CC_STD_EDGES[i][1]
        CC_EDGE_ORI[i][1][1] = CC_STD_EDGES[i][0]
    CC_FACE_ASCII[0]=85; CC_FACE_ASCII[1]=82; CC_FACE_ASCII[2]=70
    CC_FACE_ASCII[3]=68; CC_FACE_ASCII[4]=76; CC_FACE_ASCII[5]=66
    CC_INITED = True

cdef inline int _cc_face_code(int ch) noexcept nogil:
    """大写字母 ASCII -> 面码 0-5 (U R F D L B)。"""
    if ch == 85: return 0
    if ch == 82: return 1
    if ch == 70: return 2
    if ch == 68: return 3
    if ch == 76: return 4
    return 5

cdef inline bint _cc_match(int t, int r) noexcept nogil:
    if t == 6:
        return True
    if t >= 7:
        return (t - 7) == r
    return t == r

cdef inline bint _cc_match_slot(int* t, int n, int* rot) noexcept nogil:
    """槽级匹配：目标含小写(>=7) -> 颜色集合子集；否则逐格。与 Python 版一致。"""
    cdef int i, j, has_lower = 0, col, found
    for i in range(n):
        if t[i] >= 7:
            has_lower = 1
            break
    if has_lower:
        for i in range(n):
            if t[i] == 6:
                continue
            col = t[i] - 7 if t[i] >= 7 else t[i]
            found = 0
            for j in range(n):
                if rot[j] == col:
                    found = 1
                    break
            if not found:
                return False
        return True
    for i in range(n):
        if t[i] == 6:
            continue
        if t[i] != rot[i]:
            return False
    return True

cdef inline int _cc_parity8(int* arr) noexcept nogil:
    cdef int i, j, inv = 0
    for i in range(8):
        for j in range(i + 1, 8):
            if arr[j] < arr[i]:
                inv ^= 1
    return inv

cdef inline int _cc_parity12(int* arr) noexcept nogil:
    cdef int i, j, inv = 0
    for i in range(12):
        for j in range(i + 1, 12):
            if arr[j] < arr[i]:
                inv ^= 1
    return inv

cdef int _cc_corner_dfs(int slot, int used, int* cp, int* co,
                        int* out_cp, int* out_co, int* count,
                        int cap, int targets[8][3], bint* stop) noexcept nogil:
    cdef int i, o, k, ok
    if stop[0]:
        return 0
    if slot == 8:
        if (co[0]+co[1]+co[2]+co[3]+co[4]+co[5]+co[6]+co[7]) % 3 == 0:
            if count[0] >= cap:
                return 0
            for k in range(8):
                out_cp[count[0]*8 + k] = cp[k]
                out_co[count[0]*8 + k] = co[k]
            count[0] += 1
        return 1
    for i in range(8):
        if used & (1 << i):
            continue
        for o in range(3):
            ok = _cc_match_slot(targets[slot], 3, CC_CORNER_ORI[i][o])
            if ok:
                cp[slot] = i
                co[slot] = o
                if not _cc_corner_dfs(slot + 1, used | (1 << i), cp, co,
                                      out_cp, out_co, count, cap, targets, stop):
                    return 0
    return 1

def generate_valid_completes(str pseudo_str, object stop_callable=None):
    """残缺状态补全生成器（Cython 迭代 DFS，产出 54 字符补全字符串）。"""
    _cc_init_tables()
    cdef int targets_c[8][3]
    cdef int targets_e[12][2]
    cdef int i, j, ch, p
    cdef int cap = 1000000
    cdef int* cp_arr = NULL
    cdef int* co_arr = NULL
    cdef int* cp = NULL
    cdef int* co = NULL
    cdef int* ep = NULL
    cdef int* eo = NULL
    cdef char* buf = NULL
    cdef int count = 0
    cdef bint stop = False
    cdef int k, ci, ori, c, s, j2
    cdef int cand_ep[12][24]
    cdef int cand_eo[12][24]
    cdef int cand_cnt[12]
    cdef int stack_slot[13]
    cdef int stack_used[13]
    cdef int stack_ci[13]
    cdef int sp = 0
    cdef int used = 0
    cdef int v, eo_sum, ep_par, ci2, o, ei, ok
    for i in range(8):
        for j in range(3):
            p = CC_CORNER_FACELETS[i][j]
            ch = ord(pseudo_str[p])
            if ch == 63:
                targets_c[i][j] = 6
            elif 97 <= ch <= 122:
                targets_c[i][j] = 7 + _cc_face_code(ch - 32)
            else:
                targets_c[i][j] = _cc_face_code(ch)
    for i in range(12):
        for j in range(2):
            p = CC_EDGE_FACELETS[i][j]
            ch = ord(pseudo_str[p])
            if ch == 63:
                targets_e[i][j] = 6
            elif 97 <= ch <= 122:
                targets_e[i][j] = 7 + _cc_face_code(ch - 32)
            else:
                targets_e[i][j] = _cc_face_code(ch)
    cp_arr = <int*>malloc(cap * 16 * sizeof(int))
    if cp_arr == NULL:
        raise MemoryError('completer: alloc failed')
    co_arr = cp_arr + cap * 8
    cp = <int*>malloc(8 * sizeof(int))
    co = <int*>malloc(8 * sizeof(int))
    ep = <int*>malloc(12 * sizeof(int))
    eo = <int*>malloc(12 * sizeof(int))
    buf = <char*>malloc(54 * sizeof(char))
    try:
        _cc_corner_dfs(0, 0, cp, co, cp_arr, co_arr, &count, cap, targets_c, &stop)
        if count == 0:
            return
        if stop_callable is not None and stop_callable():
            return
        for s in range(12):
            cand_cnt[s] = 0
            for ci in range(12):
                for ori in range(2):
                    ok = _cc_match_slot(targets_e[s], 2, CC_EDGE_ORI[ci][ori])
                    if ok:
                        cand_ep[s][cand_cnt[s]] = ci
                        cand_eo[s][cand_cnt[s]] = ori
                        cand_cnt[s] += 1
        stack_slot[0] = 0
        stack_used[0] = 0
        stack_ci[0] = -1
        sp = 1
        while sp > 0:
            if stop_callable is not None and stop_callable():
                return
            s = stack_slot[sp - 1]
            used = stack_used[sp - 1]
            ci = stack_ci[sp - 1] + 1
            if ci >= cand_cnt[s]:
                sp -= 1
                continue
            stack_ci[sp - 1] = ci
            v = cand_ep[s][ci]
            if used & (1 << v):
                continue
            ep[s] = v
            eo[s] = cand_eo[s][ci]
            if s == 11:
                eo_sum = 0
                for k in range(12):
                    eo_sum += eo[k]
                if eo_sum & 1:
                    continue
                ep_par = _cc_parity12(ep)
                for c in range(count):
                    if _cc_parity8(cp_arr + c * 8) != ep_par:
                        continue
                    for k in range(6):
                        buf[k * 9 + 4] = <char>CC_FACE_ASCII[k]
                    for k in range(8):
                        ci2 = cp_arr[c * 8 + k]
                        ori = co_arr[c * 8 + k]
                        for j2 in range(3):
                            buf[CC_CORNER_FACELETS[k][j2]] = <char>CC_FACE_ASCII[CC_CORNER_ORI[ci2][ori][j2]]
                    for k in range(12):
                        ei = ep[k]
                        o = eo[k]
                        for j2 in range(2):
                            buf[CC_EDGE_FACELETS[k][j2]] = <char>CC_FACE_ASCII[CC_EDGE_ORI[ei][o][j2]]
                    yield bytes(buf[:54]).decode('ascii')
                continue
            stack_slot[sp] = s + 1
            stack_used[sp] = used | (1 << v)
            stack_ci[sp] = -1
            sp += 1
    finally:
        free(cp_arr)
        free(cp)
        free(co)
        free(ep)
        free(eo)
        free(buf)
