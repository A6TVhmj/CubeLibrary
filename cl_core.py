import os, math, threading
import numpy as np

try:
    import cl_search as _cy
    _HAS_CYTHON = True
except ImportError:
    _cy = None
    _HAS_CYTHON = False

_INIT_LOCK = threading.Lock()
MOVES_STR = ["U","U2","U'","R","R2","R'","F","F2","F'",
             "D","D2","D'","L","L2","L'","B","B2","B'"]
P2_MOVES = [0,1,2,9,10,11,4,13,7,16]

CORNER_FACELETS = ((8,9,20),(6,18,38),(0,36,47),(2,45,11),
                   (29,26,15),(27,44,24),(33,53,42),(35,17,51))
EDGE_FACELETS   = ((5,10),(7,19),(3,37),(1,46),(32,16),(28,25),
                   (30,43),(34,52),(23,12),(21,41),(50,39),(48,14))
STD_CORNERS = (('U','R','F'),('U','F','L'),('U','L','B'),('U','B','R'),
               ('D','F','R'),('D','L','F'),('D','B','L'),('D','R','B'))
STD_EDGES   = (('U','R'),('U','F'),('U','L'),('U','B'),
               ('D','R'),('D','F'),('D','L'),('D','B'),
               ('F','R'),('F','L'),('B','L'),('B','R'))

FACT = [math.factorial(i) for i in range(13)]
CNK  = [[0]*13 for _ in range(13)]
for _n in range(13):
    for _k in range(_n+1): CNK[_n][_k] = math.comb(_n, _k)

FACE_OF    = [m//3 for m in range(18)]
CAN_FOLLOW = [[True]*6 for _ in range(7)]
for _lf in range(6):
    CAN_FOLLOW[_lf+1][_lf] = False
    for _cf in (3,4,5):
        if _lf == _cf-3: CAN_FOLLOW[_lf+1][_cf] = False

cp_U=[3,0,1,2,4,5,6,7];co_U=[0]*8;ep_U=[3,0,1,2,4,5,6,7,8,9,10,11];eo_U=[0]*12
cp_R=[4,1,2,0,7,5,6,3];co_R=[2,0,0,1,1,0,0,2];ep_R=[8,1,2,3,11,5,6,7,4,9,10,0];eo_R=[0]*12
cp_F=[1,5,2,3,0,4,6,7];co_F=[1,2,0,0,2,1,0,0];ep_F=[0,9,2,3,4,8,6,7,1,5,10,11];eo_F=[0,1,0,0,0,1,0,0,1,1,0,0]
cp_D=[0,1,2,3,5,6,7,4];co_D=[0]*8;ep_D=[0,1,2,3,5,6,7,4,8,9,10,11];eo_D=[0]*12
cp_L=[0,2,6,3,4,1,5,7];co_L=[0,1,2,0,0,2,1,0];ep_L=[0,1,10,3,4,5,9,7,8,2,6,11];eo_L=[0]*12
cp_B=[0,1,3,7,4,5,2,6];co_B=[0,0,1,2,0,0,2,1];ep_B=[0,1,2,11,4,5,6,10,8,9,3,7];eo_B=[0,0,0,1,0,0,0,1,0,0,1,1]
BASE_CUBIES = [(cp_U,co_U,ep_U,eo_U),(cp_R,co_R,ep_R,eo_R),(cp_F,co_F,ep_F,eo_F),
               (cp_D,co_D,ep_D,eo_D),(cp_L,co_L,ep_L,eo_L),(cp_B,co_B,ep_B,eo_B)]

def multiply_cubies(c1, c2):
    c1_0,c1_1,c1_2,c1_3 = c1; c2_0,c2_1,c2_2,c2_3 = c2
    return (
        [c1_0[c2_0[0]],c1_0[c2_0[1]],c1_0[c2_0[2]],c1_0[c2_0[3]],
         c1_0[c2_0[4]],c1_0[c2_0[5]],c1_0[c2_0[6]],c1_0[c2_0[7]]],
        [(c1_1[c2_0[0]]+c2_1[0])%3,(c1_1[c2_0[1]]+c2_1[1])%3,
         (c1_1[c2_0[2]]+c2_1[2])%3,(c1_1[c2_0[3]]+c2_1[3])%3,
         (c1_1[c2_0[4]]+c2_1[4])%3,(c1_1[c2_0[5]]+c2_1[5])%3,
         (c1_1[c2_0[6]]+c2_1[6])%3,(c1_1[c2_0[7]]+c2_1[7])%3],
        [c1_2[c2_2[0]],c1_2[c2_2[1]],c1_2[c2_2[2]],c1_2[c2_2[3]],
         c1_2[c2_2[4]],c1_2[c2_2[5]],c1_2[c2_2[6]],c1_2[c2_2[7]],
         c1_2[c2_2[8]],c1_2[c2_2[9]],c1_2[c2_2[10]],c1_2[c2_2[11]]],
        [(c1_3[c2_2[0]]+c2_3[0])&1,(c1_3[c2_2[1]]+c2_3[1])&1,
         (c1_3[c2_2[2]]+c2_3[2])&1,(c1_3[c2_2[3]]+c2_3[3])&1,
         (c1_3[c2_2[4]]+c2_3[4])&1,(c1_3[c2_2[5]]+c2_3[5])&1,
         (c1_3[c2_2[6]]+c2_3[6])&1,(c1_3[c2_2[7]]+c2_3[7])&1,
         (c1_3[c2_2[8]]+c2_3[8])&1,(c1_3[c2_2[9]]+c2_3[9])&1,
         (c1_3[c2_2[10]]+c2_3[10])&1,(c1_3[c2_2[11]]+c2_3[11])&1])

def get_twist(co):
    return co[0]*729+co[1]*243+co[2]*81+co[3]*27+co[4]*9+co[5]*3+co[6]
def set_twist(val):
    co,p=[0]*8,0
    for i in range(6,-1,-1): co[i]=val%3; p+=co[i]; val//=3
    co[7]=(3-p%3)%3; return co
def get_flip(eo):
    return (eo[0]<<10)|(eo[1]<<9)|(eo[2]<<8)|(eo[3]<<7)|(eo[4]<<6)|(eo[5]<<5)|(eo[6]<<4)|(eo[7]<<3)|(eo[8]<<2)|(eo[9]<<1)|eo[10]
def set_flip(val):
    eo,p=[0]*12,0
    for i in range(10,-1,-1): eo[i]=val&1; p+=eo[i]; val>>=1
    eo[11]=(2-p%2)%2; return eo
def get_slice(ep):
    s,k=0,3
    for n in range(11,-1,-1):
        if ep[n]>=8: k-=1;
        else: s+=CNK[n][k]
        if k<0: break
    return s
def set_slice(val):
    ep,k=[-1]*12,3
    for n in range(11,-1,-1):
        if val<CNK[n][k]: ep[n]=11-k; k-=1
        else: val-=CNK[n][k]
        if k<0: break
    cur=0
    for i in range(12):
        if ep[i]==-1: ep[i]=cur; cur+=1
    return ep
def get_perm8(arr):
    a0,a1,a2,a3,a4,a5,a6,a7=arr[0],arr[1],arr[2],arr[3],arr[4],arr[5],arr[6],arr[7]
    return (((a1<a0)+(a2<a0)+(a3<a0)+(a4<a0)+(a5<a0)+(a6<a0)+(a7<a0))*5040+
            ((a2<a1)+(a3<a1)+(a4<a1)+(a5<a1)+(a6<a1)+(a7<a1))*720+
            ((a3<a2)+(a4<a2)+(a5<a2)+(a6<a2)+(a7<a2))*120+
            ((a4<a3)+(a5<a3)+(a6<a3)+(a7<a3))*24+
            ((a5<a4)+(a6<a4)+(a7<a4))*6+((a6<a5)+(a7<a5))*2+(a7<a6))
def get_perm4(arr):
    a0,a1,a2,a3=arr[0],arr[1],arr[2],arr[3]
    return ((a1<a0)+(a2<a0)+(a3<a0))*6+((a2<a1)+(a3<a1))*2+(a3<a2)
def set_perm(val,n):
    arr=[0]*n; avail=list(range(n))
    for i in range(n):
        f=FACT[n-1-i]; idx=val//f; val%=f
        arr[i]=avail[idx]; del avail[idx]
    return arr
def perm_parity(arr):
    """排列奇偶性（逆序对数 % 2）。注意 get_perm(x) % 2 不等于排列奇偶性。"""
    inv = 0
    for i in range(len(arr)):
        ai = arr[i]
        for j in range(i + 1, len(arr)):
            if arr[j] < ai:
                inv ^= 1
    return inv

def build_2d_pruning_table(MT1,MT2,N1,N2,num_moves):
    total=N1*N2; prun=np.full(total,-1,dtype=np.int8); prun[0]=0
    front=np.array([0],dtype=np.int32); depth=0; filled=1
    while front.size>0 and filled<total:
        x=front//N2; y=front%N2; nexts=[]
        for m in range(num_moves):
            nidx=MT1[x,m].astype(np.int64)*N2+MT2[y,m]
            mask=prun[nidx]==-1; cand=nidx[mask]
            if cand.size==0: continue
            valid=np.unique(cand); valid=valid[prun[valid]==-1]
            if valid.size>0: prun[valid]=depth+1; filled+=valid.size; nexts.append(valid)
        if not nexts: break
        front=np.unique(np.concatenate(nexts)); depth+=1
    return prun

def build_tf_pruning_table(tw, fl, N1=2187, N2=2048, num_moves=18):
    """twist×flip 组合剪枝表（分块 BFS，控制峰值内存）。"""
    total=N1*N2; prun=np.full(total,-1,dtype=np.int8); prun[0]=0
    front=np.array([0],dtype=np.int32); depth=0; filled=1
    CHUNK=150000
    while front.size>0 and filled<total:
        fw=front//N2; ff=front%N2; nexts=[]
        for s in range(0,fw.size,CHUNK):
            e=min(s+CHUNK,fw.size)
            cand=(tw[fw[s:e]]*N2+fl[ff[s:e]]).ravel()
            cand=np.unique(cand)
            valid=cand[prun[cand]==-1]
            if valid.size>0:
                prun[valid]=depth+1; nexts.append(valid)
        if not nexts: break
        front=np.unique(np.concatenate(nexts)); filled+=front.size; depth+=1
    return prun

def parse_state(s_str):
    """解析状态字符串。

    字符串语义：每格字母 = 该格颜色所属的标准面（'U' 表示 U 面颜色）。
    中心格同样按颜色语义（M/E/S 等中层转动后中心格颜色会移动，
    不能用"中心格所在位置"推断颜色→面映射）。
    eo 采用与引擎配套的"颜色序列"语义。
    """
    s = list(s_str)
    cp,co,ep,eo=[0]*8,[0]*8,[0]*12,[0]*12
    for i in range(8):
        f=(s[CORNER_FACELETS[i][0]],s[CORNER_FACELETS[i][1]],s[CORNER_FACELETS[i][2]]); fs=set(f)
        for j in range(8):
            if fs==set(STD_CORNERS[j]): cp[i]=j; break
        if   f[0] in ('U','D'): co[i]=0
        elif f[1] in ('U','D'): co[i]=1
        else:                    co[i]=2
    for i in range(12):
        f=(s[EDGE_FACELETS[i][0]],s[EDGE_FACELETS[i][1]]); fs=set(f)
        for j in range(12):
            if fs==set(STD_EDGES[j]): ep[i]=j; break
        if   f[0] in ('U','D'): eo[i]=0
        elif f[1] in ('U','D'): eo[i]=1
        elif f[0] in ('F','B'): eo[i]=0
        else:                    eo[i]=1
    return cp,co,ep,eo

INITIALIZED = False
FULL_CUBIE_MOVES = None

def init_engine():
    global INITIALIZED, FULL_CUBIE_MOVES
    if INITIALIZED: return
    with _INIT_LOCK:
        if INITIALIZED: return
        CUBIE_MOVES = []
        for b in BASE_CUBIES:
            m2=multiply_cubies(b,b); m3=multiply_cubies(m2,b)
            CUBIE_MOVES.extend([b,m2,m3])
        FULL_CUBIE_MOVES = CUBIE_MOVES
        fp = os.path.join(os.path.dirname(os.path.abspath(__file__)),"cl_tables_cache.npz")
        if os.path.exists(fp):
            with np.load(fp) as d:
                tables = {k: d[k] for k in d.files}
        else:
            twist_move=np.zeros((2187,18),dtype=np.int32)
            for i in range(2187):
                co=set_twist(i)
                for m in range(18): cm=CUBIE_MOVES[m]; twist_move[i,m]=get_twist([(co[cm[0][j]]+cm[1][j])%3 for j in range(8)])
            flip_move=np.zeros((2048,18),dtype=np.int32)
            for i in range(2048):
                eo=set_flip(i)
                for m in range(18): cm=CUBIE_MOVES[m]; flip_move[i,m]=get_flip([(eo[cm[2][j]]+cm[3][j])%2 for j in range(12)])
            slice_move=np.zeros((495,18),dtype=np.int32)
            for i in range(495):
                ep=set_slice(i)
                for m in range(18): cm=CUBIE_MOVES[m]; slice_move[i,m]=get_slice([ep[cm[2][j]] for j in range(12)])
            cp_move=np.zeros((40320,18),dtype=np.int32)
            for i in range(40320):
                cp_=set_perm(i,8)
                for m in range(18): cm=CUBIE_MOVES[m]; cp_move[i,m]=get_perm8([cp_[cm[0][j]] for j in range(8)])
            ep_move=np.zeros((40320,10),dtype=np.int32)
            for i in range(40320):
                ep_=set_perm(i,8)+[8,9,10,11]
                for idx,m in enumerate(P2_MOVES): cm=CUBIE_MOVES[m]; ep_move[i,idx]=get_perm8([ep_[cm[2][j]] for j in range(12)][:8])
            sep_move=np.zeros((24,10),dtype=np.int32)
            for i in range(24):
                ep_=[0,1,2,3,4,5,6,7]+[x+8 for x in set_perm(i,4)]
                for idx,m in enumerate(P2_MOVES): cm=CUBIE_MOVES[m]; sep_move[i,idx]=get_perm4([x-8 for x in [ep_[cm[2][j]] for j in range(12)][8:12]])
            cp_move_p2=cp_move[:,P2_MOVES]
            prun_p1_ts=build_2d_pruning_table(twist_move,slice_move,2187,495,18)
            prun_p1_fs=build_2d_pruning_table(flip_move,slice_move,2048,495,18)
            prun_p1_tf=build_tf_pruning_table(twist_move,flip_move)
            prun_p2_cp_sep=build_2d_pruning_table(cp_move_p2,sep_move,40320,24,10)
            prun_p2_ep_sep=build_2d_pruning_table(ep_move,sep_move,40320,24,10)
            tables = dict(twist_move=twist_move,flip_move=flip_move,slice_move=slice_move,
                          cp_move_p2=cp_move_p2,ep_move=ep_move,sep_move=sep_move,
                          prun_p1_ts=prun_p1_ts,prun_p1_fs=prun_p1_fs,prun_p1_tf=prun_p1_tf,
                          prun_p2_cp_sep=prun_p2_cp_sep,prun_p2_ep_sep=prun_p2_ep_sep)
            np.savez_compressed(fp, **tables)
        if _HAS_CYTHON:
            _cy.load_tables(tables['twist_move'],tables['flip_move'],tables['slice_move'],
                            tables['cp_move_p2'],tables['ep_move'],tables['sep_move'],
                            tables['prun_p1_ts'],tables['prun_p1_fs'],tables['prun_p1_tf'],
                            tables['prun_p2_cp_sep'],tables['prun_p2_ep_sep'],
                            CUBIE_MOVES)
        else:
            _setup_py_globals(tables)
        INITIALIZED = True

def _setup_py_globals(t):
    global twist_move_l,flip_move_l,slice_move_l,cp_move_p2_l,ep_move_l,sep_move_l
    global prun_p1_ts_b,prun_p1_fs_b,prun_p1_tf_b,prun_p2_cp_sep_b,prun_p2_ep_sep_b
    twist_move_l=t['twist_move'].tolist(); flip_move_l=t['flip_move'].tolist()
    slice_move_l=t['slice_move'].tolist(); cp_move_p2_l=t['cp_move_p2'].tolist()
    ep_move_l=t['ep_move'].tolist(); sep_move_l=t['sep_move'].tolist()
    prun_p1_ts_b=t['prun_p1_ts'].tobytes(); prun_p1_fs_b=t['prun_p1_fs'].tobytes()
    prun_p1_tf_b=t['prun_p1_tf'].tobytes()
    prun_p2_cp_sep_b=t['prun_p2_cp_sep'].tobytes(); prun_p2_ep_sep_b=t['prun_p2_ep_sep'].tobytes()

_faces_idx = {'U': 0, 'R': 1, 'F': 2, 'D': 3, 'L': 4, 'B': 5}
CENTER_INDICES = [4, 13, 22, 31, 40, 49]
_ROT_RAW = {
    'x': 'B9,B8,B7,B6,B5,B4,B3,B2,B1,R3,R6,R9,R2,R5,R8,R1,R4,R7,U1,U2,U3,U4,U5,U6,U7,U8,U9,F1,F2,F3,F4,F5,F6,F7,F8,F9,L7,L4,L1,L8,L5,L2,L9,L6,L3,D9,D8,D7,D6,D5,D4,D3,D2,D1',
    'y': 'U3,U6,U9,U2,U5,U8,U1,U4,U7,F1,F2,F3,F4,F5,F6,F7,F8,F9,L1,L2,L3,L4,L5,L6,L7,L8,L9,D7,D4,D1,D8,D5,D2,D9,D6,D3,B1,B2,B3,B4,B5,B6,B7,B8,B9,R1,R2,R3,R4,R5,R6,R7,R8,R9',
    'z': 'R3,R6,R9,R2,R5,R8,R1,R4,R7,D3,D6,D9,D2,D5,D8,D1,D4,D7,F3,F6,F9,F2,F5,F8,F1,F4,F7,L3,L6,L9,L2,L5,L8,L1,L4,L7,U3,U6,U9,U2,U5,U8,U1,U4,U7,B7,B4,B1,B8,B5,B2,B9,B6,B3',
}
ROTATION_TABLES = {}
for _name, _s in _ROT_RAW.items():
    _arr = []
    for _item in _s.split(','):
        _arr.append(_faces_idx[_item[0]] * 9 + int(_item[1]) - 1)
    ROTATION_TABLES[_name] = _arr

def _apply_rotation(state_str, perm):
    """应用 54 格置换（位置 i 的内容去 perm[i]）。"""
    out = [''] * 54
    for i in range(54):
        out[perm[i]] = state_str[i]
    return ''.join(out)

def _rot_face_map(perm):
    """转体的面映射：{U,R,F,D,L,B} → 面。面 f 的中心格经转体后位于哪个面。"""
    m = {}
    for f, idx in zip('URFDLB', CENTER_INDICES):
        m[f] = _pos_face_idx(perm[idx])
    return m

def _pos_face_idx(pos):
    if pos < 9: return 'U'
    if pos < 18: return 'R'
    if pos < 27: return 'F'
    if pos < 36: return 'D'
    if pos < 45: return 'L'
    return 'B'

def _all_rotations():
    """24 个整体转动（x/y/z 幂组合去重），返回 (置换, 面映射) 列表。"""
    seen = {}
    for i in range(4):
        px = ROTATION_TABLES['x']
        for _ in range(i): px = _compose_perm(px, ROTATION_TABLES['x'])
        for j in range(4):
            py = px
            for _ in range(j): py = _compose_perm(py, ROTATION_TABLES['y'])
            for k in range(4):
                pz = py
                for _ in range(k): pz = _compose_perm(pz, ROTATION_TABLES['z'])
                key = tuple(pz)
                if key not in seen:
                    seen[key] = _rot_face_map(pz)
    return [(list(k), v) for k, v in seen.items()]

def _compose_perm(a, b):
    """置换复合：先 a 后 b（b∘a）。"""
    return [b[a[i]] for i in range(54)]

ROTATIONS = _all_rotations()

def _remap_solution(sol, face_map):
    """把解按转体面映射换字母（保持 2 与 ' 后缀）。"""
    out = []
    for m in sol.split():
        base = m[0]
        nb = face_map.get(base, base)
        out.append(nb + m[1:])
    return ' '.join(out)

def reorient_state(state_string, top, front):
    """按顶面/正面把观察参考系的状态转成标准参考系。

    top/front：观察时顶面/正面在标准参考系中对应的面字母（如顶面是 B 色、正面是 R 色）。
    返回转换后的 54 字符状态；若 top/front 非法（相同或相对面）返回 None。
    """
    if top == front or (top, front) in (('U', 'D'), ('D', 'U'), ('R', 'L'), ('L', 'R'), ('F', 'B'), ('B', 'F')):
        return None
    for perm, face_map in ROTATIONS:
        if face_map['U'] == top and face_map['F'] == front:
            return _apply_rotation(state_string, perm)
    return None



def solve(state_string, mode="twophase", max_depth=22, stop_flag=None):
    init_engine()
    cp,co,ep,eo = parse_state(state_string)
    twist,flip,slc = get_twist(co),get_flip(eo),get_slice(ep)
    if twist==0 and flip==0 and slc==0 and get_perm8(cp)==0 and get_perm8(ep[:8])==0 and get_perm4([x-8 for x in ep[8:12]])==0:
        yield ""; return
    centers = [state_string[i] for i in CENTER_INDICES]
    if centers != ['U', 'R', 'F', 'D', 'L', 'B']:
        # 中心格错位：可能是整体转动（x/y/z）——先逆转体规范化再求解，解按转体换字母
        for perm, face_map in ROTATIONS:
            s2 = _apply_rotation(state_string, perm)
            if [s2[i] for i in CENTER_INDICES] == ['U', 'R', 'F', 'D', 'L', 'B']:
                cp2, co2, ep2, eo2 = parse_state(s2)
                if perm_parity(cp2) == perm_parity(ep2):
                    twist2, flip2, slc2 = get_twist(co2), get_flip(eo2), get_slice(ep2)
                    inv_map = {v: k for k, v in face_map.items()}
                    if _HAS_CYTHON:
                        gen = (_cy.solve_optimal_gen if mode == "optimal" else _cy.solve_twophase_gen)
                        seen_rot = set()
                        for sol in gen(int(twist2), int(flip2), int(slc2), cp2, co2, ep2, eo2, max_depth, stop_flag):
                            remapped = _remap_solution(sol, inv_map)
                            if remapped not in seen_rot:
                                seen_rot.add(remapped)
                                yield remapped
                    else:
                        seen_rot = set()
                        for sol in _solve_python(cp2, co2, ep2, eo2, int(twist2), int(flip2), int(slc2), mode, max_depth, stop_flag):
                            remapped = _remap_solution(sol, inv_map)
                            if remapped not in seen_rot:
                                seen_rot.add(remapped)
                                yield remapped
                    return
        raise ValueError("状态不可解：中心块颜色错位（可能包含中层转动 M/E/S，当前求解器仅支持标准六面转动）")
    if perm_parity(cp) != perm_parity(ep):
        raise ValueError("状态不可解：角块与棱块的置换奇偶性不匹配（可能包含中层转动 M/E/S，当前求解器仅支持标准六面转动）")
    if _HAS_CYTHON:
        gen = (_cy.solve_optimal_gen if mode=="optimal" else _cy.solve_twophase_gen)
        yield from gen(int(twist),int(flip),int(slc),cp,co,ep,eo,max_depth,stop_flag)
    else:
        yield from _solve_python(cp,co,ep,eo,int(twist),int(flip),int(slc),mode,max_depth,stop_flag)

def _solve_python(cp,co,ep,eo,twist,flip,slc,mode,max_depth,stop_flag):
    found_sols=set(); gmin=[max_depth+1]
    _tw=twist_move_l;_fl=flip_move_l;_sl=slice_move_l;_cp=cp_move_p2_l;_ep=ep_move_l;_sp=sep_move_l
    _pts=prun_p1_ts_b;_pfs=prun_p1_fs_b;_ptf=prun_p1_tf_b
    _pcs=prun_p2_cp_sep_b;_pes=prun_p2_ep_sep_b
    _cm=FULL_CUBIE_MOVES;_p2=P2_MOVES;_fo=FACE_OF;_cf=CAN_FOLLOW;_ms=MOVES_STR;_mc=multiply_cubies
    _nc=[0]; _sf=stop_flag
    class Stop(Exception): pass
    def _ck():
        _nc[0]+=1
        if _nc[0]&0xFF==0 and _sf and _sf(): raise Stop()
    def _follow_ok(lf2, lf, cf):
        if cf == lf: return False
        if (lf == 0 and cf == 3) or (lf == 1 and cf == 4) or (lf == 2 and cf == 5):
            return False
        if lf2 >= 0 and cf == lf2 and (lf == cf + 3 or lf == cf - 3):
            return False
        return True
    def sp2(cv,ev,sv,g,bd,lf,lf2,pa):
        _ck(); h=max(_pcs[cv*24+sv],_pes[ev*24+sv])
        if g+h>bd: return
        if h==0 and g==bd: yield list(pa); return
        for idx,m in enumerate(_p2):
            cf=_fo[m]
            if not _follow_ok(lf2,lf,cf): continue
            pa.append(m); yield from sp2(_cp[cv][idx],_ep[ev][idx],_sp[sv][idx],g+1,bd,cf,lf,pa); pa.pop()
    def sp1(tw,fl,sl,g,bd,p2tl,lf,lf2,pa):
        _ck(); h=max(_pts[tw*495+sl],_pfs[fl*495+sl],_ptf[tw*2048+fl])
        if g+h>bd: return
        if h==0 and g==bd:
            c=cp,co,ep,eo
            for m in pa: c=_mc(c,_cm[m])
            pc,pe,ps=get_perm8(c[0]),get_perm8(c[2][:8]),get_perm4([x-8 for x in c[2][8:12]])
            ph=max(_pcs[pc*24+ps],_pes[pe*24+ps])
            pbs=[p2tl] if p2tl is not None and p2tl>=ph else ([] if p2tl is not None else range(ph,gmin[0]-g))
            for pb in pbs:
                found=False
                for p2p in sp2(pc,pe,ps,0,pb,pa[-1]//3 if pa else -1,pa[-2]//3 if len(pa)>1 else -1,[]):
                    ss=" ".join([_ms[m] for m in pa+p2p])
                    if ss not in found_sols:
                        found_sols.add(ss)
                        if p2tl is None and g+pb<gmin[0]: gmin[0]=g+pb
                        yield ss; found=True
                if p2tl is None and found: break
        for m in range(18):
            cf=_fo[m]
            if not _follow_ok(lf2,lf,cf): continue
            pa.append(m); yield from sp1(_tw[tw][m],_fl[fl][m],_sl[sl][m],g+1,bd,p2tl,cf,lf,pa); pa.pop()
    try:
        if mode=="optimal":
            am=None
            for tl in range(max_depth+1):
                if _sf and _sf(): break
                if am is not None and tl>am+2: break
                for p1b in range(tl+1):
                    if _sf and _sf(): break
                    for sol in sp1(twist,flip,slc,0,p1b,tl-p1b,-1,-1,[]):
                        if am is None: am=tl
                        yield sol
        else:
            for p1b in range(max_depth+1):
                if _sf and _sf(): break
                if p1b>=gmin[0]: break
                yield from sp1(twist,flip,slc,0,p1b,None,-1,-1,[])
    except Stop: pass
