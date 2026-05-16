import time
import cl_core

CORNER_FACELETS = cl_core.CORNER_FACELETS
EDGE_FACELETS = cl_core.EDGE_FACELETS
STD_CORNERS = cl_core.STD_CORNERS
STD_EDGES = cl_core.STD_EDGES

def _match_piece(target, piece):
    for t, p in zip(target, piece):
        if t != '?' and t != p: return False
    return True

def _get_corner_rotations(c): return [c, (c[1], c[2], c[0]), (c[2], c[0], c[1])]
def _get_edge_rotations(e): return [e, (e[1], e[0])]

def generate_valid_completes(pseudo_str, stop_flag):
    c_targets = [tuple(pseudo_str[i] for i in idx) for idx in CORNER_FACELETS]
    e_targets = [tuple(pseudo_str[i] for i in idx) for idx in EDGE_FACELETS]
    valid_corners = []
    
    def dfs_corners(slot, used_mask, curr_cp, curr_co):
        if stop_flag(): return
        if slot == 8:
            if sum(curr_co) % 3 == 0: valid_corners.append((list(curr_cp), list(curr_co)))
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
                        curr_ep.append(i); curr_eo.append(ori)
                        yield from dfs_edges(slot + 1, used_mask | (1 << i), curr_ep, curr_eo)
                        curr_eo.pop(); curr_ep.pop()

    yield from dfs_edges(0, 0, [], [])

def build_full_string(cp, co, ep, eo):
    facelets = ['?'] * 54
    for i, c in enumerate([4, 13, 22, 31, 40, 49]): facelets[c] = ['U', 'R', 'F', 'D', 'L', 'B'][i]
    for i in range(8):
        for j, color in enumerate(_get_corner_rotations(STD_CORNERS[cp[i]])[co[i]]): facelets[CORNER_FACELETS[i][j]] = color
    for i in range(12):
        for j, color in enumerate(_get_edge_rotations(STD_EDGES[ep[i]])[eo[i]]): facelets[EDGE_FACELETS[i][j]] = color
    return "".join(facelets)

def solve_incomplete_stream(state_string, queue, stop_flag, search_mode):
    cl_core.init_engine()
    generator = generate_valid_completes(state_string, stop_flag)
    count = 0
    seen_sols = set()
    
    try:
        for comp_state in generator:
            if stop_flag(): break
            for sol in cl_core.solve(comp_state, mode=search_mode, max_depth=20, stop_flag=stop_flag):
                if stop_flag(): break
                if sol not in seen_sols and sol != "":
                    seen_sols.add(sol)
                    count += 1
                    queue.put((count, comp_state, sol, len(sol.split())))
            
    except Exception as e:
        queue.put(("ERROR", str(e)))
        
    queue.put(("DONE", count))
