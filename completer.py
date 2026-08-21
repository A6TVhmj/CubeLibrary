import os
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import cl_core

try:
    from cl_search import generate_valid_completes as _cy_completer_gen
except ImportError:
    _cy_completer_gen = None


def generate_valid_completes(pseudo_str, stop_flag=lambda: False):
    """残缺状态补全生成器（Cython 实现，cl_search 扩展）。"""
    if _cy_completer_gen is None:
        raise ImportError("Cython 残缺补全不可用（需要 cl_search 扩展）")
    yield from _cy_completer_gen(pseudo_str, stop_flag)


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


MAX_CANDIDATES = 1000000000  # 完整补全组合数阈值
MAX_CORNER_COMBO = 1000000  # 角块组合数阈值


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

    # 补全组合数预算判断
    est, corner_combo = estimate_candidates(state_string)
    if corner_combo > MAX_CORNER_COMBO or est > MAX_CANDIDATES:
        queue.put(("ERROR", f"补全组合数估算约 {est:.2e}（角块组合 {corner_combo:.2e}），组合爆炸，请减少未知格子"))
        queue.put(("DONE", 0))
        return

    seen_sols = set()
    lock = threading.Lock()

    # 单个状态求解：解出一个立即上报
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
