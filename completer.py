import os
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import cl_core

_USE_CYTHON_COMPLETER = False
try:
    from cl_search import generate_valid_completes as _cy_completer_gen
    _USE_CYTHON_COMPLETER = True
except Exception:
    _USE_CYTHON_COMPLETER = False

CORNER_FACELETS = [(8,9,20), (6,18,38), (0,36,47), (2,45,11), (29,26,15), (27,44,24), (33,53,42), (35,17,51)]
EDGE_FACELETS   = [(5,10), (7,19), (3,37), (1,46), (32,16), (28,25), (30,43), (34,52), (23,12), (21,41), (50,39), (48,14)]
STD_CORNERS = [('U','R','F'), ('U','F','L'), ('U','L','B'), ('U','B','R'), ('D','F','R'), ('D','L','F'), ('D','B','L'), ('D','R','B')]
STD_EDGES   = [('U','R'), ('U','F'), ('U','L'), ('U','B'), ('D','R'), ('D','F'), ('D','L'), ('D','B'), ('F','R'), ('F','L'), ('B','L'), ('B','R')]

def _get_corner_rotations(c):
    return [c, (c[1], c[2], c[0]), (c[2], c[0], c[1])]

def _get_edge_rotations(e):
    return [e, (e[1], e[0])]

def _match_piece(target, piece):
    is_ignore_ori = any(t.islower() for t in target if t != '?')
    if is_ignore_ori:
        target_colors = set(t.upper() for t in target if t != '?')
        piece_colors = set(piece)
        return target_colors.issubset(piece_colors)
    else:
        for t, p in zip(target, piece):
            if t != '?' and t != p: return False
        return True

def generate_valid_completes(pseudo_str, stop_flag=lambda: False):
    """残缺状态补全生成器（优先 Cython 快速版，Python 兜底）。"""
    if _USE_CYTHON_COMPLETER:
        yield from _cy_completer_gen(pseudo_str, stop_flag)
        return
    c_targets = [tuple(pseudo_str[i] for i in idx) for idx in CORNER_FACELETS]
    e_targets = [tuple(pseudo_str[i] for i in idx) for idx in EDGE_FACELETS]
    valid_corners = []

    def dfs_corners(slot, used_mask, curr_cp, curr_co):
        if stop_flag(): return
        if slot == 8:
            if sum(curr_co) % 3 == 0: 
                valid_corners.append((list(curr_cp), list(curr_co)))
            return
        target = c_targets[slot]
        for i, std_c in enumerate(STD_CORNERS):
            if not (used_mask & (1 << i)):
                for ori, rot_c in enumerate(_get_corner_rotations(std_c)):
                    if _match_piece(target, rot_c):
                        curr_cp.append(i); curr_co.append(ori)
                        dfs_corners(slot + 1, used_mask | (1 << i), curr_cp, curr_co)
                        curr_co.pop(); curr_cp.pop()

    dfs_corners(0, 0, [], [])
    if not valid_corners or stop_flag(): return

    def dfs_edges(slot, used_mask, curr_ep, curr_eo):
        if stop_flag(): return
        if slot == 12:
            if sum(curr_eo) % 2 == 0:
                ep_parity = cl_core.perm_parity(curr_ep)
                for cp, co in valid_corners:
                    if stop_flag(): return
                    if cl_core.perm_parity(cp) == ep_parity:
                        yield build_full_string(cp, co, curr_ep, curr_eo)
            return
        target = e_targets[slot]
        for i, std_e in enumerate(STD_EDGES):
            if not (used_mask & (1 << i)):
                for ori, rot_e in enumerate(_get_edge_rotations(std_e)):
                    if _match_piece(target, rot_e):
                        curr_ep.append(i); curr_eo.append(ori)
                        yield from dfs_edges(slot + 1, used_mask | (1 << i), curr_ep, curr_eo)
                        curr_eo.pop(); curr_ep.pop()
    yield from dfs_edges(0, 0, [], [])

def build_full_string(cp, co, ep, eo):
    facelets = ['?'] * 54
    for i, c in enumerate([4, 13, 22, 31, 40, 49]):
        facelets[c] = ['U', 'R', 'F', 'D', 'L', 'B'][i]
    for i in range(8):
        for j, color in enumerate(_get_corner_rotations(STD_CORNERS[cp[i]])[co[i]]):
            facelets[CORNER_FACELETS[i][j]] = color
    for i in range(12):
        for j, color in enumerate(_get_edge_rotations(STD_EDGES[ep[i]])[eo[i]]):
            facelets[EDGE_FACELETS[i][j]] = color
    return "".join(facelets)


def _slot_matches(target, rot):
    for tk, rk in zip(target, rot):
        if tk == '?':
            continue
        if tk.islower():
            if tk.upper() != rk:
                return False
        elif tk != rk:
            return False
    return True

def estimate_candidates(state_string):
    """估算补全组合数（排列感知，接近真实值）。

    返回 (total, corner_combo)：
    - corner_combo：角块合法组合数（预收集阶段的内存/时间瓶颈）
    - total：完整补全组合数（≈ corner_combo × 棱块组合 / 2 奇偶）
    """
    s = state_string
    c_vals = []
    for i in range(8):
        t = tuple(s[j] for j in cl_core.CORNER_FACELETS[i])
        n = 0
        for std in cl_core.STD_CORNERS:
            for rot in (std, (std[1], std[2], std[0]), (std[2], std[0], std[1])):
                if _slot_matches(t, rot):
                    n += 1
        c_vals.append(max(n, 1))
    c_vals.sort(reverse=True)
    c_prod = 1
    for i, n in enumerate(c_vals):
        c_prod *= max(n - 3 * i, 1)

    e_vals = []
    for i in range(12):
        t = tuple(s[j] for j in cl_core.EDGE_FACELETS[i])
        n = 0
        for std in cl_core.STD_EDGES:
            for rot in (std, (std[1], std[0])):
                if _slot_matches(t, rot):
                    n += 1
        e_vals.append(max(n, 1))
    e_vals.sort(reverse=True)
    e_prod = 1
    for i, n in enumerate(e_vals):
        e_prod *= max(n - 2 * i, 1)

    corner_combo = c_prod / 3.0          # 角朝向和约束
    edge_combo = e_prod / 2.0            # 棱朝向和约束
    return corner_combo * edge_combo / 2.0, corner_combo  # 奇偶匹配 /2

MAX_CANDIDATES = 1000000000  # 完整补全组合数阈值（流式+提交上限兜底，基本不限制）
MAX_CORNER_COMBO = 1000000  # 角块组合数阈值（预收集阶段瓶颈）


def solve_incomplete_stream(state_string, queue, stop_flag, search_mode, max_workers=0):
    """
    并行残缺求解：补全按批提交线程池，解出一个立即上报一个。
    若输入中心格错位（整体/中层转动后的残缺状态），先转体规范化
    再生成补全，输出解换字母回用户参考系。
    """
    cl_core.init_engine()

    if max_workers <= 0:
        max_workers = os.cpu_count() or 4

    rot_inv = None
    rot_inv_perm = None
    centers = [state_string[i] for i in cl_core.CENTER_INDICES]
    if centers != ['U', 'R', 'F', 'D', 'L', 'B']:
        for perm, face_map in cl_core.ROTATIONS:
            s2 = cl_core._apply_rotation(state_string, perm)
            if [s2[i] for i in cl_core.CENTER_INDICES] == ['U', 'R', 'F', 'D', 'L', 'B']:
                state_string = s2
                rot_inv = {v: k for k, v in face_map.items()}
                inv_perm = [0] * 54
                for i, p in enumerate(perm):
                    inv_perm[p] = i
                rot_inv_perm = inv_perm
                break

    # 补全组合数预算判断（排列感知估算）
    est, corner_combo = estimate_candidates(state_string)
    if corner_combo > MAX_CORNER_COMBO or est > MAX_CANDIDATES:
        queue.put(("ERROR", f"补全组合数估算约 {est:.2e}（角块组合 {corner_combo:.2e}），组合爆炸，请减少未知格子"))
        queue.put(("DONE", 0))
        return

    seen_sols = set()
    lock = threading.Lock()

    # 单个状态求解：解出一个立即上报（不等待），继续找下一个解直到停止/耗尽
    def solve_single(state):
        if stop_flag():
            return
        try:
            for sol in cl_core.solve(state, mode=search_mode,
                                     max_depth=20, stop_flag=stop_flag):
                if stop_flag():
                    break
                if sol != "":
                    if rot_inv:
                        sol = cl_core._remap_solution(sol, rot_inv)
                    with lock:
                        if sol in seen_sols:
                            continue
                        seen_sols.add(sol)
                        n = len(seen_sols)
                    state_out = (cl_core._apply_rotation(state, rot_inv_perm)
                                 if rot_inv_perm is not None else state)
                    queue.put((n, state_out, sol, len(sol.split())))
        except Exception:
            pass

    gen = generate_valid_completes(state_string, stop_flag)
    BATCH = max(2, max_workers * 2)
    MAX_STATES = 256  # 补全提交上限，防止全未知状态无限生成

    def submit_more(n):
        nonlocal submitted_total
        submitted = 0
        while submitted < n and submitted_total < MAX_STATES:
            try:
                st = next(gen)
            except StopIteration:
                break
            futures.add(executor.submit(solve_single, st))
            submitted += 1
            submitted_total += 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = set()
        submitted_total = 0
        submit_more(BATCH)
        while futures:
            if stop_flag():
                for f in futures:
                    f.cancel()
                break
            done, futures = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    future.result()
                except Exception as e:
                    queue.put(("ERROR", str(e)))
            submit_more(len(done))

    queue.put(("DONE", len(seen_sols)))