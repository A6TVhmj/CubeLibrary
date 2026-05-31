import cl_core

CORNER_FACELETS = [(8,9,20), (6,18,38), (0,36,47), (2,45,11), (29,26,15), (27,44,24), (33,53,42), (35,17,51)]
EDGE_FACELETS   = [(5,10), (7,19), (3,37), (1,46), (32,16), (28,25), (30,43), (34,52), (23,12), (21,41), (50,39), (48,14)]
STD_CORNERS = [('U','R','F'), ('U','F','L'), ('U','L','B'), ('U','B','R'), ('D','F','R'), ('D','L','F'), ('D','B','L'), ('D','R','B')]
STD_EDGES   = [('U','R'), ('U','F'), ('U','L'), ('U','B'), ('D','R'), ('D','F'), ('D','L'), ('D','B'), ('F','R'), ('F','L'), ('B','L'), ('B','R')]

def _get_corner_rotations(c):
    """返回角块的 3 种朝向"""
    return [c, (c[1], c[2], c[0]), (c[2], c[0], c[1])]

def _get_edge_rotations(e):
    """返回棱块的 2 种朝向"""
    return [e, (e[1], e[0])]

def _match_piece(target, piece):
    """
    匹配逻辑升级版：
    - target 可能是: ('U', '?', '?'), ('u', 'r', 'f'), ('U', 'R', 'F')
    - piece 是物理标准块的某种朝向: ('U', 'R', 'F')
    """
    is_ignore_ori = any(t.islower() for t in target if t != '?')
    
    if is_ignore_ori:
        target_colors = set(t.upper() for t in target if t != '?')
        piece_colors = set(piece)
        return target_colors.issubset(piece_colors)
    else:
        for t, p in zip(target, piece):
            if t != '?' and t != p: return False
        return True

def generate_valid_completes(pseudo_str, stop_flag):
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
                        curr_cp.append(i)
                        curr_co.append(ori)
                        dfs_corners(slot + 1, used_mask | (1 << i), curr_cp, curr_co)
                        curr_co.pop()
                        curr_cp.pop()

    # 1. 优先暴力猜解角块
    dfs_corners(0, 0, [], [])
    if not valid_corners or stop_flag(): return

    def dfs_edges(slot, used_mask, curr_ep, curr_eo):
        if stop_flag(): return
        if slot == 12:
            if sum(curr_eo) % 2 == 0:
                ep_parity = cl_core.get_perm(curr_ep) % 2
                for cp, co in valid_corners:
                    if stop_flag(): return
                    if cl_core.get_perm(cp) % 2 == ep_parity:
                        yield build_full_string(cp, co, curr_ep, curr_eo)
            return
            
        target = e_targets[slot]
        for i, std_e in enumerate(STD_EDGES):
            if not (used_mask & (1 << i)):
                for ori, rot_e in enumerate(_get_edge_rotations(std_e)):
                    if _match_piece(target, rot_e):
                        curr_ep.append(i)
                        curr_eo.append(ori)
                        yield from dfs_edges(slot + 1, used_mask | (1 << i), curr_ep, curr_eo)
                        curr_eo.pop()
                        curr_ep.pop()
    yield from dfs_edges(0, 0, [], [])

def build_full_string(cp, co, ep, eo):
    """将内部数组转化为 Kociemba 字符串，大写标准输出"""
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

def solve_incomplete_stream(state_string, queue, stop_flag, search_mode):
    """供主程序调用的多线程入口函数"""
    cl_core.init_engine()
    generator = generate_valid_completes(state_string, stop_flag)
    count = 0
    seen_sols = set()
    
    try:
        for comp_state in generator:
            if stop_flag(): break
            
            # 使用引擎寻找这一种可能的解
            for sol in cl_core.solve(comp_state, mode=search_mode, max_depth=20, stop_flag=stop_flag):
                if stop_flag(): break
                if sol not in seen_sols and sol != "":
                    seen_sols.add(sol)
                    count += 1
                    queue.put((count, comp_state, sol, len(sol.split())))
                    
    except Exception as e:
        queue.put(("ERROR", str(e)))
        
    queue.put(("DONE", count))