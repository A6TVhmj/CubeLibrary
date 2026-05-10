import sys
import time
import queue
import threading
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs.colorchooser import ColorChooserDialog
import kb_lite
import cube_completer

class CubeExplorerClone(ttk.Window):
    def __init__(self):
        # 使用 cosmo 主题
        super().__init__(themename="cosmo")
        
        self.title("Cube Explorer 5.15 (Modern ttkbootstrap Edition)")
        self.geometry("1080x800")
        
        self.colors = ["#FFFFFF", "#FFFF00", "#FF0000", "#FF8800", "#0000FF", "#008800"]
        self.current_color_idx = 1
        
        self.facelet_colors = ["#CCCCCC"] * 54
        self.facelet_states = [0] * 54  
        
        self.def_col = {
            'U': self.colors[0], 'R': self.colors[4], 'F': self.colors[2], 
            'D': self.colors[1], 'L': self.colors[5], 'B': self.colors[3]
        }
        self.center_indices = [4, 13, 22, 31, 40, 49]
        
        C = self.def_col
        self.std_corners = [
            (C['U'], C['R'], C['F']), (C['U'], C['F'], C['L']), (C['U'], C['L'], C['B']), (C['U'], C['B'], C['R']),
            (C['D'], C['F'], C['R']), (C['D'], C['L'], C['F']), (C['D'], C['B'], C['L']), (C['D'], C['R'], C['B'])
        ]
        self.std_edges = [
            (C['U'], C['R']), (C['U'], C['F']), (C['U'], C['L']), (C['U'], C['B']),
            (C['D'], C['R']), (C['D'], C['F']), (C['D'], C['L']), (C['D'], C['B']),
            (C['F'], C['R']), (C['F'], C['L']), (C['B'], C['L']), (C['B'], C['R'])
        ]
        
        self.corner_indices = [
            (8, 9, 20), (6, 18, 38), (0, 36, 47), (2, 45, 11),
            (29, 26, 15), (27, 44, 24), (33, 53, 42), (35, 17, 51)
        ]
        self.edge_indices = [
            (5, 10), (7, 19), (3, 37), (1, 46),
            (32, 16), (28, 25), (30, 43), (34, 52),
            (23, 12), (21, 41), (50, 39), (48, 14)
        ]
        
        self._build_permutation_matrices()
        
        self.poly_ids = []
        self.overlay_ids = [None] * 54 
        self.maneuver_var = tk.StringVar()
        self.autofix_var = tk.BooleanVar(value=True)
        self.search_mode = tk.StringVar(value="twophase")
        
        self._create_layout()
        self._reset_clean()
        
        self.log_text.insert(tk.END, ">> Preloading Kociemba Pruning Tables in background...\n")
        threading.Thread(target=kb_lite.init_engine, daemon=True).start()

    def _build_permutation_matrices(self):
        raw_perms = {
            'U': 'U3,U6,U9,U2,U5,U8,U1,U4,U7,F1,F2,F3,R4,R5,R6,R7,R8,R9,L1,L2,L3,F4,F5,F6,F7,F8,F9,D1,D2,D3,D4,D5,D6,D7,D8,D9,B1,B2,B3,L4,L5,L6,L7,L8,L9,R1,R2,R3,B4,B5,B6,B7,B8,B9',
            'R': 'U1,U2,B7,U4,U5,B4,U7,U8,B1,R3,R6,R9,R2,R5,R8,R1,R4,R7,F1,F2,U3,F4,F5,U6,F7,F8,U9,D1,D2,F3,D4,D5,F6,D7,D8,F9,L1,L2,L3,L4,L5,L6,L7,L8,L9,D9,B2,B3,D6,B5,B6,D3,B8,B9',
            'F': 'U1,U2,U3,U4,U5,U6,R1,R4,R7,D3,R2,R3,D2,R5,R6,D1,R8,R9,F3,F6,F9,F2,F5,F8,F1,F4,F7,L3,L6,L9,D4,D5,D6,D7,D8,D9,L1,L2,U9,L4,L5,U8,L7,L8,U7,B1,B2,B3,B4,B5,B6,B7,B8,B9',
            'D': 'U1,U2,U3,U4,U5,U6,U7,U8,U9,R1,R2,R3,R4,R5,R6,B7,B8,B9,F1,F2,F3,F4,F5,F6,R7,R8,R9,D3,D6,D9,D2,D5,D8,D1,D4,D7,L1,L2,L3,L4,L5,L6,F7,F8,F9,B1,B2,B3,B4,B5,B6,L7,L8,L9',
            'L': 'F1,U2,U3,F4,U5,U6,F7,U8,U9,R1,R2,R3,R4,R5,R6,R7,R8,R9,D1,F2,F3,D4,F5,F6,D7,F8,F9,B9,D2,D3,B6,D5,D6,B3,D8,D9,L3,L6,L9,L2,L5,L8,L1,L4,L7,B1,B2,U7,B4,B5,U4,B7,B8,U1',
            'B': 'L7,L4,L1,U4,U5,U6,U7,U8,U9,R1,R2,U1,R4,R5,U2,R7,R8,U3,F1,F2,F3,F4,F5,F6,F7,F8,F9,D1,D2,D3,D4,D5,D6,R9,R6,R3,D7,L2,L3,D8,L5,L6,D9,L8,L9,B3,B6,B9,B2,B5,B8,B1,B4,B7',
            'x': 'B9,B8,B7,B6,B5,B4,B3,B2,B1,R3,R6,R9,R2,R5,R8,R1,R4,R7,U1,U2,U3,U4,U5,U6,U7,U8,U9,F1,F2,F3,F4,F5,F6,F7,F8,F9,L7,L4,L1,L8,L5,L2,L9,L6,L3,D9,D8,D7,D6,D5,D4,D3,D2,D1',
            'y': 'U3,U6,U9,U2,U5,U8,U1,U4,U7,F1,F2,F3,F4,F5,F6,F7,F8,F9,L1,L2,L3,L4,L5,L6,L7,L8,L9,D7,D4,D1,D8,D5,D2,D9,D6,D3,B1,B2,B3,B4,B5,B6,B7,B8,B9,R1,R2,R3,R4,R5,R6,R7,R8,R9',
            'z': 'R3,R6,R9,R2,R5,R8,R1,R4,R7,D3,D6,D9,D2,D5,D8,D1,D4,D7,F3,F6,F9,F2,F5,F8,F1,F4,F7,L3,L6,L9,L2,L5,L8,L1,L4,L7,U3,U6,U9,U2,U5,U8,U1,U4,U7,B7,B4,B1,B8,B5,B2,B9,B6,B3',
            'E': 'U1,U2,U3,U4,U5,U6,U7,U8,U9,R1,R2,R3,B4,B5,B6,R7,R8,R9,F1,F2,F3,R4,R5,R6,F7,F8,F9,D1,D2,D3,D4,D5,D6,D7,D8,D9,L1,L2,L3,F4,F5,F6,L7,L8,L9,B1,B2,B3,L4,L5,L6,B7,B8,B9',
            'M': 'U1,F2,U3,U4,F5,U6,U7,F8,U9,R1,R2,R3,R4,R5,R6,R7,R8,R9,F1,D2,F3,F4,D5,F6,F7,D8,F9,D1,B8,D3,D4,B5,D6,D7,B2,D9,L1,L2,L3,L4,L5,L6,L7,L8,L9,B1,U8,B3,B4,U5,B6,B7,U2,B9',
            'S': 'U1,U2,U3,R2,R5,R8,U7,U8,U9,R1,D6,R3,R4,D5,R6,R7,D4,R9,F1,F2,F3,F4,F5,F6,F7,F8,F9,D1,D2,D3,L2,L5,L8,D7,D8,D9,L1,U6,L3,L4,U5,L6,L7,U4,L9,B1,B2,B3,B4,B5,B6,B7,B8,B9'
        }
        self.moves_perm = {}
        faces = ['U', 'R', 'F', 'D', 'L', 'B']
        for move_name, str_arr in raw_perms.items():
            arr = []
            for item in str_arr.split(','):
                arr.append(faces.index(item[0]) * 9 + int(item[1]) - 1)
            self.moves_perm[move_name] = arr

    def _create_layout(self):
        # 修正: Panedwindow
        self.paned = ttk.Panedwindow(self, orient=HORIZONTAL)
        self.paned.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        # 修正: 让 left_frame 更窄，right_frame 更宽
        self.left_frame = ttk.Frame(self.paned)
        self.paned.add(self.left_frame, weight=1)
        self.log_text = tk.Text(self.left_frame, font=("Consolas", 11), bg="#1E1E1E", fg="#4AF626", insertbackground="white", relief=FLAT, padx=10, pady=10)
        self.log_text.pack(fill=BOTH, expand=True)
        self.log_text.insert(END, "Cube Explorer Modern Engine initialized.\nWaiting for tasks...\n")
        
        self.right_frame = ttk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=0) # 分配更多空间
        self.paned.sashpos(0,0)
        
        self.notebook = ttk.Notebook(self.right_frame, bootstyle=PRIMARY)
        self.notebook.pack(fill=BOTH, expand=True)
        self.tab_facelet = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_facelet, text="Facelet Editor")
        
        self._build_facelet_editor()

    def _build_facelet_editor(self):
        top_frame = ttk.Frame(self.tab_facelet)
        top_frame.pack(fill=BOTH, expand=True)
        
        # 3D 画布区域 
        self.cube_canvas = tk.Canvas(top_frame, bg="#E8E8E8", highlightthickness=0)
        self.cube_canvas.pack(fill=BOTH, expand=True) # 使用 pack 而不是 place 适应大小变化
        
        self.cube_canvas.bind("<Button-1>", self._handle_left_click)
        self.cube_canvas.bind("<Button-3>", self._handle_right_click)
        self.cube_canvas.bind("<Button-2>", self._handle_right_click)
        
        # 修正: 画布缩小且原点上移，保证不被遮挡 (l=14, ox=50, oy=20)
        self._init_exact_delphi_geometry(self.cube_canvas, l=14, ox=50, oy=20)
        
        ttk.Checkbutton(top_frame, text="AutoFix Colors", variable=self.autofix_var, bootstyle="success-round-toggle").place(x=20, y=360)
        
        self.color_box = tk.Canvas(top_frame, width=80, height=80, bg=self.colors[self.current_color_idx], relief=SOLID, borderwidth=2)
        self.color_box.place(x=520, y=160)
        self.color_box.bind("<Button-1>", lambda e: self._cycle_color())
        
        ttk.Label(top_frame, text="Selected Color", font=("Arial", 11, "bold")).place(x=510, y=255)
        ttk.Button(top_frame, text="Customize", bootstyle=OUTLINE, command=self._customize_color).place(x=513, y=285)

        # 底部控制台布局
        bot_frame = ttk.Frame(self.tab_facelet)
        bot_frame.pack(fill=X, side=BOTTOM, pady=(5,0))
        
        # --- Solver 区 ---
        grp_solve = ttk.Labelframe(bot_frame, text="Kociemba Solver", padding=10)
        grp_solve.grid(row=0, column=0, sticky=NSEW, padx=5)
        ttk.Radiobutton(grp_solve, text="Two-Phase (Fast)", variable=self.search_mode, value="twophase", bootstyle=INFO).pack(anchor=W, pady=2)
        ttk.Radiobutton(grp_solve, text="Optimal (Slow)", variable=self.search_mode, value="optimal", bootstyle=INFO).pack(anchor=W, pady=2)
        ttk.Button(grp_solve, text="SOLVE CUBE", bootstyle=SUCCESS, command=self._run_solver).pack(fill=X, pady=8)
        
        # --- Apply Move 区 ---
        grp_apply = ttk.Labelframe(bot_frame, text="Apply Move (L-Click: 90°, R-Click: -90°)", padding=10)
        grp_apply.grid(row=0, column=1, sticky=NSEW, padx=5)
        move_grid = [['R', 'U', 'F'], ['L', 'D', 'B'], ['M', 'E', 'S'], ['x', 'y', 'z']]
        for r, row_moves in enumerate(move_grid):
            for c, m in enumerate(row_moves):
                btn = ttk.Button(grp_apply, text=m, width=4, bootstyle=SECONDARY)
                btn.config(command=lambda move=m: self._add_and_apply_move(move))
                btn.bind("<ButtonPress-3>", lambda e, btn_ref=btn, move=m: btn_ref.configure(text=move + "'"))
                btn.bind("<ButtonPress-2>", lambda e, btn_ref=btn, move=m: btn_ref.configure(text=move + "'"))
                btn.bind("<ButtonRelease-3>", lambda e, btn_ref=btn, move=m: self._on_right_click_release(btn_ref, move))
                btn.bind("<ButtonRelease-2>", lambda e, btn_ref=btn, move=m: self._on_right_click_release(btn_ref, move))
                btn.grid(row=r, column=c, padx=3, pady=2)
                
        # --- Reset 区 ---
        grp_reset = ttk.Labelframe(bot_frame, text="Reset & Export", padding=10)
        grp_reset.grid(row=0, column=2, sticky=NSEW, padx=5)
        # 修正: 取消 fill=X，改为 sticky=EW
        ttk.Button(grp_reset, text="Export String", bootstyle=PRIMARY, command=self._export_kociemba_string).grid(row=0, column=0, columnspan=2, sticky=EW, pady=(0, 5))
        ttk.Button(grp_reset, text="Empty Cube", bootstyle=WARNING, command=self._reset_empty).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(grp_reset, text="Clean Cube", bootstyle=SUCCESS, command=self._reset_clean).grid(row=1, column=1, padx=2, pady=2)

        # --- 公式执行框 ---
        row_maneuver = ttk.Labelframe(bot_frame, text="Enter Maneuver", padding=10)
        row_maneuver.grid(row=1, column=0, columnspan=3, sticky=EW, padx=5, pady=10)
        ttk.Entry(row_maneuver, textvariable=self.maneuver_var, font=("Consolas", 12)).pack(side=LEFT, fill=X, expand=True, padx=5)
        ttk.Button(row_maneuver, text="Apply", bootstyle=SUCCESS, width=10, command=self._apply_maneuver_string).pack(side=RIGHT, padx=5)
        ttk.Button(row_maneuver, text="Clear", bootstyle=DANGER, width=8, command=lambda: self.maneuver_var.set("")).pack(side=RIGHT, padx=5)

    def _init_exact_delphi_geometry(self, canvas, l, ox, oy):
        self.poly_ids = []
        for face in range(6):
            for b in range(3):
                for a in range(3):
                    if face == 0:
                        x = ox + l*(3*a - 2*b + 15); y = oy + l*(2*b)
                        pts = [x, y, x+3*l, y, x+l, y+2*l, x-2*l, y+2*l]
                    elif face == 1:
                        x = ox + l*(2*a + 18); y = oy + l*(-2*a + 3*b + 6)
                        pts = [x, y, x+2*l, y-2*l, x+2*l, y+l, x, y+3*l]
                    elif face == 2:
                        x = ox + l*(3*a + 9); y = oy + l*(3*b + 6)
                        pts = [x, y, x+3*l, y, x+3*l, y+3*l, x, y+3*l]
                    elif face == 3:
                        x = ox + l*(3*a + 9); y = oy + l*(3*b + 15)
                        pts = [x, y, x+3*l, y, x+3*l, y+3*l, x, y+3*l]
                    elif face == 4:
                        x = ox + l*(3*a); y = oy + l*(3*b + 6)
                        pts = [x, y, x+3*l, y, x+3*l, y+3*l, x, y+3*l]
                    elif face == 5:
                        x = ox + l*(3*a + 24); y = oy + l*(3*b)
                        pts = [x, y, x+3*l, y, x+3*l, y+3*l, x, y+3*l]
                    pid = canvas.create_polygon(*pts, outline="#333333", width=1.5)
                    self.poly_ids.append(pid)

    # ================== Solver 与 算法接口 ==================
    def _run_solver(self):
        try:
            state_str = self._extract_state_string()
            mode = self.search_mode.get()
            
            if "?" in state_str:
                self.log_text.insert(tk.END, f"\n[Task] Incomplete Cube Search Started ({mode.upper()})...\n")
                self.log_text.see(tk.END)
                IncompleteSearchDialog(self, state_str, mode)
                return

            self.log_text.insert(tk.END, f"\n[Task] Target State:\n{state_str}\n")
            self.log_text.insert(tk.END, f"> Searching for solution ({mode.upper()}) please wait...\n")
            self.log_text.see(tk.END)
            self.update()
            
            
            def solve_task():
                t_start = time.time()
                # 丢入后台计算
                sols = kb_lite.solve(state_str, mode=mode, max_depth=22)
                t_end = time.time()
                
                # 计算完毕后，通过 after 让主线程安全地更新文本框
                self.after(0, lambda: self._on_solve_finished(sols, t_end - t_start))

            threading.Thread(target=solve_task, daemon=True).start()

        except Exception as e:
            self.log_text.insert(tk.END, f"\n[Error] {e}\n")
            self.log_text.see(tk.END)

    def _on_solve_finished(self, sols, time_taken):
        """异步求解完成后的回调函数，用于刷新 UI"""
        if not sols:
            self.log_text.insert(tk.END, f">> No solution found within limits.\n")
        elif sols[0] == "":
            self.log_text.insert(tk.END, f">> Cube is already solved.\n")
        else:
            self.log_text.insert(tk.END, f">> Found {len(sols)} optimal solution(s) in {time_taken:.3f}s:\n")
            for sol in sols:
                moves_count = len(sol.split())
                self.log_text.insert(tk.END, f"   - ({moves_count}f) {sol}\n")
                
        self.log_text.see(tk.END)
    def _export_kociemba_string(self):
        try:
            k_string = self._extract_state_string()
            self.log_text.insert(END, f"\n--- Exported State ---\n{k_string}\n")
            self.log_text.see(END)
        except Exception as e:
            self.log_text.insert(END, f"\n[Error] {e}\n")
            self.log_text.see(END)

    def _extract_state_string(self):
        color_to_face = {}
        for face, idx in zip(['U', 'R', 'F', 'D', 'L', 'B'], self.center_indices):
            color_to_face[self.facelet_colors[idx]] = face
        k_string = ""
        for i in range(54):
            color = self.facelet_colors[i]
            if color == "#CCCCCC" and self.facelet_states[i] == 0:
                raise ValueError("Cube is incomplete! Paint all grey spots.")
            k_string += color_to_face.get(color, "?")
        return k_string

    # ================== 物理联动与 UI 逻辑 ==================
    def _apply_cubie_linkage(self, fc):
        piece_indices = None
        for c in self.corner_indices:
            if fc in c: piece_indices = c; break
        if not piece_indices:
            for e in self.edge_indices:
                if fc in e: piece_indices = e; break
        if not piece_indices: return 

        fc_state = self.facelet_states[fc]
        if fc_state == 1: 
            for i in piece_indices:
                if i != fc and self.facelet_colors[i] != "#CCCCCC" and self.facelet_states[i] == 0:
                    self.facelet_states[i] = 1
        elif fc_state == 2: 
            for i in piece_indices:
                if i != fc and self.facelet_colors[i] != "#CCCCCC":
                    self.facelet_colors[i] = "#CCCCCC"
                    self.facelet_states[i] = 0
        elif fc_state == 0: 
            for i in piece_indices:
                if i != fc and self.facelet_states[i] == 1:
                    self.facelet_states[i] = 0 

    def _handle_left_click(self, event):
        items = self.cube_canvas.find_closest(event.x, event.y)
        if not items: return
        poly_id = items[0]
        if poly_id not in self.poly_ids: return
        
        is_shift = (event.state & 0x0001) != 0
        is_ctrl = (event.state & 0x0004) != 0
        if sys.platform == "darwin" and ((event.state & 0x0008) != 0 or (event.state & 0x0010) != 0):
            is_ctrl = True

        state_mode = 0
        if is_ctrl: state_mode = 2
        elif is_shift: state_mode = 1

        idx = self.poly_ids.index(poly_id)
        if idx in self.center_indices:
            if state_mode == 0:
                picked_color = self.facelet_colors[idx]
                if picked_color in self.colors:
                    self.current_color_idx = self.colors.index(picked_color)
                    self.color_box.config(bg=picked_color)
        else:
            if state_mode == 2:
                self.facelet_colors[idx] = "#CCCCCC"
            else:
                self.facelet_colors[idx] = self.colors[self.current_color_idx]
                
            self.facelet_states[idx] = state_mode
            self._apply_cubie_linkage(idx)
            
            if self.autofix_var.get() and state_mode == 0:
                self._autofix(idx)
                
            self._sync_colors_to_canvas()

    def _handle_right_click(self, event):
        items = self.cube_canvas.find_closest(event.x, event.y)
        if not items: return
        poly_id = items[0]
        if poly_id in self.poly_ids:
            idx = self.poly_ids.index(poly_id)
            if idx not in self.center_indices:
                self.facelet_colors[idx] = "#CCCCCC"
                self.facelet_states[idx] = 0
                self._sync_colors_to_canvas()

    def _autofix(self, fc):
        piece_indices = None
        is_corner = False
        for c in self.corner_indices:
            if fc in c: piece_indices = c; is_corner = True; break
        if not piece_indices:
            for e in self.edge_indices:
                if fc in e: piece_indices = e; break
        if not piece_indices: return

        curr_colors = [self.facelet_colors[i] for i in piece_indices]
        empty_count = curr_colors.count("#CCCCCC")
        valid_pieces = self.std_corners if is_corner else self.std_edges
        matches = []
        for vp in valid_pieces:
            n = len(vp)
            for shift in range(n):
                shifted_vp = vp[shift:] + vp[:shift]
                compatible = True
                for i in range(n):
                    if curr_colors[i] != "#CCCCCC" and curr_colors[i] != shifted_vp[i]:
                        compatible = False; break
                if compatible: matches.append(shifted_vp)

        if len(matches) == 0:
            self.facelet_colors[fc] = "#CCCCCC"
        elif len(matches) == 1 and empty_count == 1:
            match = matches[0]
            for i in range(len(piece_indices)):
                if self.facelet_colors[piece_indices[i]] == "#CCCCCC":
                    self.facelet_colors[piece_indices[i]] = match[i]
                    self.facelet_states[piece_indices[i]] = 0 

    def _on_right_click_release(self, btn, base_move):
        btn.configure(text=base_move) # ttk.Button 使用 configure 修改 text
        self._add_and_apply_move(base_move + "'")
    def _update_standard_pieces(self):
        self.def_col = {
            'U': self.colors[0], 'R': self.colors[4], 'F': self.colors[2], 
            'D': self.colors[1], 'L': self.colors[5], 'B': self.colors[3]
        }
        C = self.def_col
        self.std_corners = [
            (C['U'], C['R'], C['F']), (C['U'], C['F'], C['L']), (C['U'], C['L'], C['B']), (C['U'], C['B'], C['R']),
            (C['D'], C['F'], C['R']), (C['D'], C['L'], C['F']), (C['D'], C['B'], C['L']), (C['D'], C['R'], C['B'])
        ]
        self.std_edges = [
            (C['U'], C['R']), (C['U'], C['F']), (C['U'], C['L']), (C['U'], C['B']),
            (C['D'], C['R']), (C['D'], C['F']), (C['D'], C['L']), (C['D'], C['B']),
            (C['F'], C['R']), (C['F'], C['L']), (C['B'], C['L']), (C['B'], C['R'])
        ]
    def _customize_color(self):
        curr_color = self.colors[self.current_color_idx]
        cd = ColorChooserDialog(initialcolor=curr_color, title="Customize Selected Color")
        cd.show()
        colors = cd.result
        if colors:
            hex_color = colors.hex
            self.colors[self.current_color_idx] = hex_color
            self.color_box.config(bg=hex_color)
            
            self._update_standard_pieces()
            
            # 刷新画布上已有的该颜色块
            for i in range(54):
                if self.facelet_colors[i] == curr_color:
                    self.facelet_colors[i] = hex_color
            self._sync_colors_to_canvas()

    def _cycle_color(self):
        self.current_color_idx = (self.current_color_idx + 1) % len(self.colors)
        self.color_box.config(bg=self.colors[self.current_color_idx])

    # ================== 置换与渲染引擎 ==================
    def _apply_turn_base(self, move):
        if move not in self.moves_perm: return
        perm = self.moves_perm[move]
        temp_colors = self.facelet_colors[:]
        temp_states = self.facelet_states[:]
        new_colors = [""] * 54
        new_states = [0] * 54
        for i in range(54):
            new_colors[perm[i]] = temp_colors[i]
            new_states[perm[i]] = temp_states[i]
        self.facelet_colors = new_colors
        self.facelet_states = new_states

    def _execute_move_notation(self, move_str):
        move_str = move_str.strip()
        if not move_str: return
        base_move = move_str[0] 
        if base_move not in self.moves_perm: return
        
        if len(move_str) == 1: self._apply_turn_base(base_move)
        elif len(move_str) >= 2 and move_str[1] == '2':
            self._apply_turn_base(base_move); self._apply_turn_base(base_move)
        elif len(move_str) >= 2 and move_str[1] == "'":
            self._apply_turn_base(base_move); self._apply_turn_base(base_move); self._apply_turn_base(base_move)

    def _apply_maneuver_string(self):
        alg = self.maneuver_var.get()
        for m in alg.split(): self._execute_move_notation(m)
        self._sync_colors_to_canvas()
        self.log_text.insert(END, f"> Executed: {alg}\n")
        self.log_text.see(END)

    def _add_and_apply_move(self, move_str):
        curr = self.maneuver_var.get()
        self.maneuver_var.set(curr + move_str + " ")
        self._execute_move_notation(move_str)
        self._sync_colors_to_canvas()

    def _reset_clean(self):
        faces = ['U', 'R', 'F', 'D', 'L', 'B']
        for i in range(6):
            for j in range(9):
                self.facelet_colors[i*9 + j] = self.def_col[faces[i]]
                self.facelet_states[i*9 + j] = 0
        self.maneuver_var.set("")
        self._sync_colors_to_canvas()

    def _reset_empty(self):
        self.facelet_colors = ["#CCCCCC"] * 54
        self.facelet_states = [0] * 54
        self._sync_colors_to_canvas()

    def _sync_colors_to_canvas(self):
        for i in range(54):
            self.cube_canvas.itemconfig(self.poly_ids[i], fill=self.facelet_colors[i])
            if self.overlay_ids[i]:
                for oid in self.overlay_ids[i]:
                    self.cube_canvas.delete(oid)
                self.overlay_ids[i] = []
            else:
                self.overlay_ids[i] = []
                
            state = self.facelet_states[i]
            if state in (1, 2):
                c = self.cube_canvas.coords(self.poly_ids[i])
                if state == 1: 
                    l1 = self.cube_canvas.create_line(c[0], c[1], c[4], c[5], fill="#222222", width=2.5)
                    l2 = self.cube_canvas.create_line(c[2], c[3], c[6], c[7], fill="#222222", width=2.5)
                    self.overlay_ids[i].extend([l1, l2])
                elif state == 2: 
                    cx, cy = (c[0]+c[2]+c[4]+c[6])/4, (c[1]+c[3]+c[5]+c[7])/4
                    o = self.cube_canvas.create_oval(cx-8, cy-8, cx+8, cy+8, fill="white", outline="#222222", width=2.5)
                    self.overlay_ids[i].append(o)
class IncompleteSearchDialog(ttk.Toplevel):
    def __init__(self, parent, state_str):
        super().__init__(parent)
        self.title("Pattern Search (Incomplete Cube)")
        self.geometry("600x400")
        self.state_str = state_str
        self.stop_requested = False
        
        # 结果队列
        self.result_queue = queue.Queue()
        
        # UI 布局
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill=X)
        self.lbl_status = ttk.Label(top_frame, text="Searching valid patterns...", font=("Arial", 11, "bold"))
        self.lbl_status.pack(side=LEFT)
        self.btn_stop = ttk.Button(top_frame, text="Stop Search", bootstyle="danger", command=self.stop_search)
        self.btn_stop.pack(side=RIGHT)
        
        # 表格显示解法
        cols = ("ID", "Length", "Maneuver")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        self.tree.heading("ID", text="#")
        self.tree.heading("Length", text="Len")
        self.tree.heading("Maneuver", text="Solution")
        self.tree.column("ID", width=50, anchor=CENTER)
        self.tree.column("Length", width=50, anchor=CENTER)
        self.tree.column("Maneuver", width=450)
        self.tree.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # 启动后台线程
        self.worker = threading.Thread(
            target=cube_completer.solve_incomplete_stream,
            args=(self.state_str, self.result_queue, lambda: self.stop_requested, mode)
        )
        self.worker.daemon = True
        self.worker.start()
        
        # 定时器拉取队列
        self.after(100, self.process_queue)
        
    def stop_search(self):
        self.stop_requested = True
        self.lbl_status.config(text="Stopping... Please wait.")
        self.btn_stop.config(state=DISABLED)
        
    def process_queue(self):
        while not self.result_queue.empty():
            msg = self.result_queue.get()
            if msg[0] == "DONE":
                self.lbl_status.config(text=f"Search Finished! Found {msg[1]} valid configurations.")
                self.btn_stop.config(text="Close", command=self.destroy, bootstyle="secondary", state=NORMAL)
                return
            elif msg[0] == "ERROR":
                self.lbl_status.config(text=f"Error: {msg[1]}")
                return
            else:
                # 收到正常的解法
                count, comp_state, sol, moves_len = msg
                # 插入表格，最新找出的在最上面
                self.tree.insert("", 0, values=(count, f"{moves_len}f", sol))
                self.lbl_status.config(text=f"Searching... Found {count} configurations so far.")
                
        # 继续循环监听
        self.after(100, self.process_queue)

if __name__ == "__main__":
    app = CubeExplorerClone()
    app.mainloop()