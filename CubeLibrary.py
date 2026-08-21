import os
import sys
import json
import queue
import random
import threading
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs.colorchooser import ColorChooserDialog
from ttkbootstrap import ToastNotification
import cl_core
import completer
from cltimer import CLTimerTab
from cl_parser import AdvancedParser
import locales
from locales import tr

def get_base_dir():
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(get_base_dir(), "cl_config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: 
            pass
    return {"lang": "en", "theme": "cosmo"}

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f)

app_config = load_config()
locales.CURRENT_LANG = app_config.get("lang", "zh")
_TB_LOCALE = {"zh": "zh_cn", "zh_tw": "zh_tw"}
try:
    ttk.set_locale(_TB_LOCALE.get(locales.CURRENT_LANG, "en"))
except Exception:
    pass

def _theme_family_of(theme_name):
    """curated 主题名 → 家族名（-light 6 字符、-dark 5 字符）。"""
    if theme_name.endswith("-light"):
        return theme_name[:-6]
    if theme_name.endswith("-dark"):
        return theme_name[:-5]
    return theme_name

class CubeLibraryApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="bootstrap-light",
                         iconphoto=(os.path.join(get_base_dir(), "icon.ico")
                                    if sys.platform == "win32"
                                    else os.path.join(get_base_dir(), "icon.png")))
        pending = app_config.get("theme", "bootstrap-light")
        if pending not in self.style.theme_names():
            pending = "bootstrap-light"
            app_config["theme"] = pending
            save_config(app_config)
        self.style.theme_use(pending)
        self.title(tr("title"))
        w = min(1200, max(self.winfo_screenwidth() - 80, 900))
        h = min(800, max(self.winfo_screenheight() - 120, 600))
        self.geometry(f"{w}x{h}")

        self.colors = ["#FFFFFF", "#FFFF00", "#008800", "#0000FF", "#FF8800", "#FF0000"]
        self.current_color_idx = 0
        
        self.sticker_colors = ["#CCCCCC"] * 54
        self.sticker_states = [0] * 54  
        
        self.def_col = {
            'U': self.colors[0], 'D': self.colors[1],
            'F': self.colors[2], 'B': self.colors[3],
            'L': self.colors[4], 'R': self.colors[5]
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
        
        self.corner_indices = [(8, 9, 20), (6, 18, 38), (0, 36, 47), (2, 45, 11), (29, 26, 15), (27, 44, 24), (33, 53, 42), (35, 17, 51)]
        self.edge_indices = [(5, 10), (7, 19), (3, 37), (1, 46), (32, 16), (28, 25), (30, 43), (34, 52), (23, 12), (21, 41), (50, 39), (48, 14)]
        
        self._build_permutation_matrices()
        
        self.poly_ids = []
        self.overlay_ids = [None] * 54 
        self.maneuver_var = tk.StringVar()
        self.autofix_var = tk.BooleanVar(value=True)
        self.search_mode = tk.StringVar(value="twophase")
        self.infinite_mode_var = tk.BooleanVar(value=False)
        self.inverse_var = tk.BooleanVar(value=False)
        
        self._create_menu()
        self._create_layout()
        self._reset_clean()
        
        self.log_text.insert(tk.END, tr("wait_task"))
        threading.Thread(target=cl_core.init_engine, daemon=True).start()

    def _create_menu(self):
        self.menubar = ttk.Menu(self, tearoff=0)
        self.config(menu=self.menubar)
        
        self.menu_tools = ttk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=tr("menu_tools"), menu=self.menu_tools)
        self.menu_tools.add_command(label=tr("menu_wca"), command=self._generate_wca_scramble)
        
        self.menu_lang = ttk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=tr("menu_lang"), menu=self.menu_lang)
        self.menu_lang.add_command(label="English", command=lambda: self._switch_language("en"))
        self.menu_lang.add_command(label="简体中文", command=lambda: self._switch_language("zh"))
        self.menu_lang.add_command(label="繁體中文", command=lambda: self._switch_language("zh_tw"))
        self.menu_lang.add_command(label="Polski", command=lambda: self._switch_language("pl"))
        
        self.menu_theme = ttk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=tr("menu_theme"), menu=self.menu_theme)
        families = []
        for t in self.style.theme_names():
            fam = _theme_family_of(t)
            if fam not in families:
                families.append(fam)
        self._theme_family_var = tk.StringVar(value="bootstrap")
        for fam in families:
            self.menu_theme.add_radiobutton(label=fam.capitalize(), value=fam,
                                            variable=self._theme_family_var,
                                            command=lambda f=fam: self._switch_theme_family(f))
        self.menu_theme.add_separator()
        idx = self.menu_theme.index("end")
        self._toggle_theme_idx = (idx + 1) if idx is not None else 0
        self.menu_theme.add_command(label=tr("menu_toggle_theme"), command=self._toggle_theme_mode)

    def _switch_language(self, lang):
        if locales.CURRENT_LANG == lang: return
        locales.CURRENT_LANG = lang
        app_config["lang"] = lang
        save_config(app_config)
        # 同步 ttkbootstrap 内置控件（Querybox/Messagebox/颜色对话框等）
        try:
            ttk.set_locale(_TB_LOCALE.get(lang, "en"))
        except Exception:
            pass
        self._update_ui_strings()
        
    def _switch_theme_family(self, family):
        cur = self.style.theme_use()
        mode = "-dark" if cur.endswith("-dark") else "-light"
        target = family + mode
        if target not in self.style.theme_names():
            target = family + "-light"
        self._switch_theme(target)

    def _toggle_theme_mode(self):
        try:
            self.style.toggle_theme()
            app_config["theme"] = self.style.theme_use()
            save_config(app_config)
            # 展开图轮廓/标记跟随新主题
            try:
                for pid in self.poly_ids:
                    self.cube_canvas.itemconfig(pid, outline=self.style.colors.fg)
                self._sync_colors_to_canvas()
            except Exception:
                pass
        except Exception:
            pass

    def _switch_theme(self, theme_name):
        self.style.theme_use(theme_name)
        app_config["theme"] = theme_name
        save_config(app_config)
        # 同步主题菜单勾选 + 日志反馈
        try:
            self._theme_family_var.set(_theme_family_of(theme_name))
            self.log_text.insert(tk.END, f"\n>> Theme: {theme_name}\n")
            self.log_text.see(tk.END)
        except Exception:
            pass
        # 更新展开图轮廓与 overlay 标记色到新主题
        try:
            for pid in self.poly_ids:
                self.cube_canvas.itemconfig(pid, outline=self.style.colors.fg)
            self._sync_colors_to_canvas()
        except Exception:
            pass
    def _update_ui_strings(self):
        self.title(tr("title"))
        
        self.menubar.entryconfig(0, label=tr("menu_tools"))
        self.menubar.entryconfig(1, label=tr("menu_lang"))
        self.menubar.entryconfig(2, label=tr("menu_theme"))
        self.menu_tools.entryconfig(0, label=tr("menu_wca"))
        self.menu_theme.entryconfig(self._toggle_theme_idx, label=tr("menu_toggle_theme"))
        
        self.notebook.tab(self.tab_facelet, text=tr("tab_facelet"))
        self.chk_autofix.config(text=tr("autofix"))
        self.lbl_selected_color.config(text=tr("lbl_selected_color"))
        self.btn_customize.config(text=tr("btn_customize"))
        
        self.grp_solve.config(text=tr("grp_solver"))
        self.rad_twophase.config(text=tr("rad_twophase"))
        self.rad_optimal.config(text=tr("rad_optimal"))
        self.chk_infinite.config(text=tr("chk_infinite"))
        self.chk_inverse.config(text=tr("chk_inverse"))
        self.btn_solve.config(text=tr("btn_solve"))
        
        self.grp_apply.config(text=tr("grp_apply"))
        self.grp_reset.config(text=tr("grp_reset"))
        self.btn_export.config(text=tr("btn_export"))
        self.btn_import.config(text=tr("btn_import"))
        self.btn_empty.config(text=tr("btn_empty"))
        self.btn_clean.config(text=tr("btn_clean"))
        
        self.grp_maneuver.config(text=tr("grp_maneuver"))
        self.btn_apply.config(text=tr("btn_apply"))
        self.btn_clear.config(text=tr("btn_clear"))

        self.notebook.tab(self.tab_timer, text=tr("tab_timer"))
        self.tab_timer.update_strings()

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
        self.paned = ttk.Panedwindow(self, orient=HORIZONTAL, bootstyle="secondary")
        self.paned.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        self.left_frame = ttk.Frame(self.paned)
        self.paned.add(self.left_frame, weight=1)
        self.log_text = ttk.ScrolledText(self.left_frame, font=("Consolas", 11),
                                         relief=FLAT, padx=10, pady=10,
                                         auto_hide=True, width=42, height=26)
        self.log_text.pack(fill=BOTH, expand=True)
        
        self.right_frame = ttk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=4)
        self.after(500, lambda: self.paned.sashpos(0, 420))
        
        self.notebook = ttk.Notebook(self.right_frame, bootstyle=PRIMARY)
        self.notebook.pack(fill=BOTH, expand=True)
        self.tab_facelet = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_facelet, text=tr("tab_facelet"))
        self._build_facelet_editor()

        self.tab_timer = CLTimerTab(self.notebook, self, tr)
        self.notebook.add(self.tab_timer, text=tr("tab_timer"))
        
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.bind("<KeyPress-space>", self._handle_space_press)
        self.bind("<KeyRelease-space>", self._handle_space_release)
        self.is_timer_active = False

    def _build_facelet_editor(self):
        top_frame = ttk.Frame(self.tab_facelet)
        top_frame.pack(fill=BOTH, expand=True)
        
        self.cube_canvas = ttk.Canvas(top_frame, highlightthickness=0)
        self.cube_canvas.pack(fill=BOTH, expand=True) 
        
        self.cube_canvas.bind("<Button-1>", self._handle_left_click)
        self.cube_canvas.bind("<Button-3>", self._handle_right_click)
        self.cube_canvas.bind("<Button-2>", self._handle_right_click)
        
        self._init_net_geometry(self.cube_canvas, l=14, ox=50, oy=20)
        
        self.chk_autofix = ttk.Checkbutton(top_frame, text=tr("autofix"), variable=self.autofix_var, bootstyle="success-round-toggle")
        self.chk_autofix.place(x=20, y=360)
        
        self.color_box = tk.Canvas(top_frame, width=80, height=80, bg=self.colors[self.current_color_idx], relief=SOLID, borderwidth=2)
        self.color_box.place(x=520, y=160)
        self.color_box.bind("<Button-1>", lambda e: self._cycle_color())
        
        self.lbl_selected_color = ttk.Label(top_frame, text=tr("lbl_selected_color"), font=("Arial", 11, "bold"))
        self.lbl_selected_color.place(x=510, y=255)
        self.btn_customize = ttk.Button(top_frame, text=tr("btn_customize"), bootstyle=OUTLINE, command=self._customize_color)
        self.btn_customize.place(x=513, y=285)

        bot_frame = ttk.Frame(self.tab_facelet)
        bot_frame.pack(fill=X, side=BOTTOM, pady=(5,0))
        
        self.grp_solve = ttk.Labelframe(bot_frame, text=tr("grp_solver"), padding=10)
        self.grp_solve.grid(row=0, column=0, sticky=NSEW, padx=5)
        
        self.rad_twophase = ttk.Radiobutton(self.grp_solve, text=tr("rad_twophase"), variable=self.search_mode, value="twophase", bootstyle=INFO)
        self.rad_twophase.pack(anchor=W, pady=2)
        self.rad_optimal = ttk.Radiobutton(self.grp_solve, text=tr("rad_optimal"), variable=self.search_mode, value="optimal", bootstyle=INFO)
        self.rad_optimal.pack(anchor=W, pady=2)
        self.chk_infinite = ttk.Checkbutton(self.grp_solve, text=tr("chk_infinite"), variable=self.infinite_mode_var, bootstyle="warning-round-toggle")
        self.chk_infinite.pack(anchor=W, pady=4)
        self.chk_inverse = ttk.Checkbutton(self.grp_solve, text=tr("chk_inverse"), variable=self.inverse_var, bootstyle="info-round-toggle")
        self.chk_inverse.pack(anchor=W, pady=4)
        
        self.btn_solve = ttk.Button(self.grp_solve, text=tr("btn_solve"), bootstyle=SUCCESS, command=self._run_solver)
        self.btn_solve.pack(fill=X, pady=4)
        
        self.grp_apply = ttk.Labelframe(bot_frame, text=tr("grp_apply"), padding=10)
        self.grp_apply.grid(row=0, column=1, sticky=NSEW, padx=5)
        move_grid = [['R', 'U', 'F'], ['L', 'D', 'B'], ['M', 'E', 'S'], ['x', 'y', 'z']]
        for r, row_moves in enumerate(move_grid):
            for c, m in enumerate(row_moves):
                btn = ttk.Button(self.grp_apply, text=m, width=4, bootstyle=SECONDARY)
                btn.config(command=lambda move=m: self._add_and_apply_move(move))
                btn.bind("<ButtonPress-3>", lambda e, btn_ref=btn, move=m: btn_ref.configure(text=move + "'"))
                btn.bind("<ButtonPress-2>", lambda e, btn_ref=btn, move=m: btn_ref.configure(text=move + "'"))
                btn.bind("<ButtonRelease-3>", lambda e, btn_ref=btn, move=m: self._on_right_click_release(btn_ref, move))
                btn.bind("<ButtonRelease-2>", lambda e, btn_ref=btn, move=m: self._on_right_click_release(btn_ref, move))
                btn.grid(row=r, column=c, padx=3, pady=2)
                
        self.grp_reset = ttk.Labelframe(bot_frame, text=tr("grp_reset"), padding=10)
        self.grp_reset.grid(row=0, column=2, sticky=NSEW, padx=5)
        self.btn_export = ttk.Button(self.grp_reset, text=tr("btn_export"), bootstyle=PRIMARY, command=self._export_state_string)
        self.btn_export.grid(row=0, column=0, columnspan=2, sticky=EW, pady=(0, 5))
        self.btn_import = ttk.Button(self.grp_reset, text=tr("btn_import"), bootstyle=PRIMARY, command=self._import_state_dialog)
        self.btn_import.grid(row=1, column=0, columnspan=2, sticky=EW, pady=(0, 5))
        self.btn_empty = ttk.Button(self.grp_reset, text=tr("btn_empty"), bootstyle=WARNING, command=self._reset_empty)
        self.btn_empty.grid(row=2, column=0, padx=2, pady=2)
        self.btn_clean = ttk.Button(self.grp_reset, text=tr("btn_clean"), bootstyle=SUCCESS, command=self._reset_clean)
        self.btn_clean.grid(row=2, column=1, padx=2, pady=2)

        self.grp_maneuver = ttk.Labelframe(bot_frame, text=tr("grp_maneuver"), padding=10)
        self.grp_maneuver.grid(row=1, column=0, columnspan=3, sticky=EW, padx=5, pady=10)
        ttk.Entry(self.grp_maneuver, textvariable=self.maneuver_var, font=("Consolas", 12)).pack(side=LEFT, fill=X, expand=True, padx=5)
        self.btn_apply = ttk.Button(self.grp_maneuver, text=tr("btn_apply"), bootstyle=SUCCESS, width=10, command=self._apply_maneuver_string)
        self.btn_apply.pack(side=RIGHT, padx=5)
        self.btn_clear = ttk.Button(self.grp_maneuver, text=tr("btn_clear"), bootstyle=DANGER, width=8, command=lambda: self.maneuver_var.set(""))
        self.btn_clear.pack(side=RIGHT, padx=5)
    def sync_from_timer(self, scramble_str):
        self.notebook.select(self.tab_facelet)
        self._reset_clean()
        self.maneuver_var.set(scramble_str + " ")
        for m in scramble_str.split():
            self._execute_move_notation(m)
        self._sync_colors_to_canvas()
        self.log_text.insert(tk.END, f"\n[Sync] Scramble synced from Timer:\n>> {scramble_str}\n")
        self.log_text.see(tk.END)
    def _init_net_geometry(self, canvas, l, ox, oy):
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
                    pid = canvas.create_polygon(*pts, outline=self.style.colors.fg, width=1.5)
                    self.poly_ids.append(pid)
    def _on_tab_changed(self, event):
        selected_tab = event.widget.select()
        if selected_tab == str(self.tab_timer):
            self.is_timer_active = True
            self.focus_set()
        else:
            self.is_timer_active = False
    def _handle_space_press(self, event):
        if self.is_timer_active:
            self.tab_timer.on_space_press(event)
    def _handle_space_release(self, event):
        if self.is_timer_active:
            self.tab_timer.on_space_release(event)
    def _generate_wca_scramble(self):
        self.log_text.insert(tk.END, f"\n{tr('wait_scramble')}\n")
        self.log_text.see(tk.END)
        
        def _task():
            state = list("UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB")
            last_face = ''
            for _ in range(40):
                face = random.choice(['U', 'D', 'R', 'L', 'F', 'B'])
                while face == last_face: face = random.choice(['U', 'D', 'R', 'L', 'F', 'B'])
                last_face = face
                power = random.choice([1, 2, 3])
                perm = self.moves_perm[face]
                for _ in range(power):
                    state = [state[perm[i]] for i in range(54)]
            
            state_str = "".join(state)
            try:
                sol = next(cl_core.solve(state_str, mode="twophase", max_depth=24, stop_flag=lambda: False))
                inv_map = {"U":"U'", "U'":"U", "U2":"U2", "R":"R'", "R'":"R", "R2":"R2", "F":"F'", "F'":"F", "F2":"F2",
                           "D":"D'", "D'":"D", "D2":"D2", "L":"L'", "L'":"L", "L2":"L2", "B":"B'", "B'":"B", "B2":"B2"}
                moves = sol.split()
                scramble = " ".join([inv_map[m] for m in reversed(moves)]) if moves else ""
                
                self.after(0, lambda: self.log_text.insert(tk.END, f">> WCA Scramble: {scramble}\n\n"))
                self.after(0, lambda: self.log_text.see(tk.END))
            except Exception as e:
                self.after(0, lambda: self.log_text.insert(tk.END, f"[Error] {e}\n"))
                
        threading.Thread(target=_task, daemon=True).start()

    def _check_state_validity(self, state_str=None):
        """返回状态合法性检查消息：残缺可补全 / 完整可解性（朝向和、奇偶、中心格）。"""
        s = state_str if state_str is not None else self._to_state_string()
        if "?" in s:
            try:
                est, cc = completer.estimate_candidates(s)
                if cc > completer.MAX_CORNER_COMBO or est > completer.MAX_CANDIDATES:
                    return tr("check_boom").format(est)
                return tr("check_incomplete").format(cc, est)
            except Exception:
                return tr("check_unknown")
        else:
            try:
                cp, co, ep, eo = cl_core.parse_state(s)
                issues = []
                if sum(co) % 3:
                    issues.append(tr("check_co"))
                if sum(eo) % 2:
                    issues.append(tr("check_eo"))
                if cl_core.perm_parity(cp) != cl_core.perm_parity(ep):
                    issues.append(tr("check_parity"))
                if [s[i] for i in cl_core.CENTER_INDICES] != ['U', 'R', 'F', 'D', 'L', 'B']:
                    issues.append(tr("check_center"))
                return tr("check_ok") if not issues else tr("check_bad") + " " + "、".join(issues)
            except Exception:
                return tr("check_unknown")

    def _run_solver(self):
        try:
            state_str = self._to_state_string()
            mode = self.search_mode.get()
            is_incomplete = "?" in state_str
            is_infinite = self.infinite_mode_var.get()
            
            if is_infinite:
                self.log_text.insert(tk.END, f"\n[Task] Infinite Search Started ({mode.upper()})...\n")
                self.log_text.see(tk.END)
                ContinuousSearchDialog(self, state_str, mode, is_incomplete, self.inverse_var.get())
            else:
                self.log_text.insert(tk.END, f"\n[Task] Quick Search (Max 5) Started ({mode.upper()})...\n")
                self.log_text.see(tk.END)
                self.solve_stop_flag = False
                threading.Thread(target=self._solve_limited_task, args=(state_str, mode, is_incomplete), daemon=True).start()

        except Exception as e:
            self.log_text.insert(tk.END, f"\n[Error] {e}\n")
            self.log_text.see(tk.END)

    def _solve_limited_task(self, state_str, mode, is_incomplete):
        import time
        t_start = time.time()
        count = 0

        if is_incomplete:
            res_q = queue.Queue()
            worker = threading.Thread(target=completer.solve_incomplete_stream, args=(state_str, res_q, lambda: self.solve_stop_flag, mode, 0), daemon=True)
            worker.start()

            while count < 5:
                if self.solve_stop_flag: break
                try:
                    msg = res_q.get(timeout=0.1)
                    if msg[0] == "DONE": break
                    elif msg[0] == "ERROR":
                        self.after(0, lambda m=msg[1]: self.log_text.insert(tk.END, f"\n[Error] {m}\n"))
                        break
                    else:
                        sol = msg[2]
                        moves_len = msg[3]
                        if self.inverse_var.get():
                            sol = AdvancedParser.inverse(sol)
                        count += 1
                        out_msg = f"   - ({moves_len}f) {sol}\n"
                        self.after(0, lambda m=out_msg: self.log_text.insert(tk.END, m))
                        self.after(0, lambda: self.log_text.see(tk.END))
                except queue.Empty:
                    continue
            self.solve_stop_flag = True
        else:
            try:
                for sol in cl_core.solve(state_str, mode=mode, stop_flag=lambda: self.solve_stop_flag):
                    if count >= 5: break
                    count += 1
                    moves_count = len(sol.split()) if sol else 0
                    if self.inverse_var.get() and sol:
                        sol = AdvancedParser.inverse(sol)
                    out_msg = f"   - ({moves_count}f) {sol if sol else 'Already solved'}\n"
                    self.after(0, lambda m=out_msg: self.log_text.insert(tk.END, m))
                    self.after(0, lambda: self.log_text.see(tk.END))
            except Exception:
                pass
            self.solve_stop_flag = True 
            
        t_end = time.time()
        end_msg = f">> Search finished. Displaying {count} solution(s) in {t_end - t_start:.3f}s.\n"
        self.after(0, lambda: self.log_text.insert(tk.END, end_msg))
        self.after(0, lambda: self.log_text.see(tk.END))

    def _import_state_string(self, s):
        for i in range(54):
            ch = s[i]
            if ch == '?':
                self.sticker_colors[i] = "#CCCCCC"
                self.sticker_states[i] = 0
            elif ch.islower():
                self.sticker_colors[i] = self.def_col[ch.upper()]
                self.sticker_states[i] = 1
            else:
                self.sticker_colors[i] = self.def_col[ch]
                self.sticker_states[i] = 0
        self._sync_colors_to_canvas()

    def _import_state_dialog(self):
        win = ttk.Toplevel(self)
        win.title(tr("dlg_import_title"))
        win.transient(self)
        win.grab_set()
        frm = ttk.Frame(win, padding=15)
        frm.pack(fill=BOTH, expand=True)
        ttk.Label(frm, text=tr("dlg_import_str")).grid(row=0, column=0, columnspan=3, sticky=W)
        entry = ttk.Entry(frm, width=62)
        entry.grid(row=1, column=0, columnspan=3, sticky=EW, pady=(2, 8))
        color_names = {f: tr(f"dlg_color_{f}") for f in "URFDLB"}
        face_labels = [f"{f} ({color_names[f]})" for f in "URFDLB"]
        ttk.Label(frm, text=tr("dlg_import_top")).grid(row=2, column=0, sticky=W)
        top_cb = ttk.Combobox(frm, values=face_labels, width=12, state="readonly")
        top_cb.current(0)
        top_cb.grid(row=2, column=1, sticky=W, pady=2)
        ttk.Label(frm, text=tr("dlg_import_front")).grid(row=3, column=0, sticky=W)
        front_cb = ttk.Combobox(frm, values=face_labels, width=12, state="readonly")
        front_cb.current(2)
        front_cb.grid(row=3, column=1, sticky=W, pady=2)
        hint = ttk.Label(frm, text=tr("dlg_import_hint"), foreground=self.style.colors.fg, wraplength=500)
        hint.grid(row=4, column=0, columnspan=3, sticky=W, pady=(4, 8))
        def do_import():
            s = entry.get().strip()
            if len(s) != 54:
                self.log_text.insert(tk.END, f"\n[Error] {tr('dlg_import_err_len')}\n")
                return
            if any(ch not in "URFDLBurfdbl?" for ch in s):
                self.log_text.insert(tk.END, f"\n[Error] {tr('dlg_import_err_chars')}\n")
                return
            top = top_cb.get()[0]
            front = front_cb.get()[0]
            conv = cl_core.reorient_state(s, top, front)
            if conv is None:
                self.log_text.insert(tk.END, f"\n[Error] {tr('dlg_import_err_faces')}\n")
                return
            self._import_state_string(conv)
            self.log_text.insert(tk.END, f"\n>> {tr('dlg_import_done').format(top, front)}\n")
            self.log_text.insert(tk.END, f"[Check] {self._check_state_validity(conv)}\n")
            self.log_text.see(tk.END)
            win.destroy()
        btn_ok = ttk.Button(frm, text=tr("dlg_import_ok"), bootstyle=SUCCESS, command=do_import)
        btn_ok.grid(row=5, column=0, columnspan=3, pady=(6, 0))
        win.update_idletasks()
        w, h = win.winfo_reqwidth() + 30, win.winfo_reqheight() + 30
        win.geometry(f"{w}x{h}")
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _export_state_string(self):
        try:
            k_string = self._to_state_string()
            self.log_text.insert(END, f"\n--- Exported State ---\n{k_string}\n")
            self.log_text.see(END)
        except Exception as e:
            self.log_text.insert(END, f"\n[Error] {e}\n")
            self.log_text.see(END)

    def _to_state_string(self):
        color_to_face = {v: k for k, v in self.def_col.items()}
        k_string = ""
        for i in range(54):
            color, state = self.sticker_colors[i], self.sticker_states[i]            
            if color == "#CCCCCC": k_string += "?"
            else:
                face_char = color_to_face.get(color, "?")
                if state == 1 and face_char != "?": k_string += face_char.lower()
                else: k_string += face_char
        return k_string

    def _get_piece_indices(self, fc):
        for c in self.corner_indices:
            if fc in c: return c
        for e in self.edge_indices:
            if fc in e: return e
        return [fc]

    def _handle_left_click(self, event):
        items = self.cube_canvas.find_closest(event.x, event.y)
        if not items: return
        poly_id = items[0]
        if poly_id not in self.poly_ids: return
        
        idx = self.poly_ids.index(poly_id)
        
        is_shift = (event.state & 0x0001) != 0
        is_ctrl = (event.state & 0x0004) != 0
        if sys.platform == "darwin" and ((event.state & 0x0008) != 0 or (event.state & 0x0010) != 0):
            is_ctrl = True

        if idx in self.center_indices:
            picked_color = self.sticker_colors[idx]
            if picked_color in self.colors:
                self.current_color_idx = self.colors.index(picked_color)
                self.color_box.config(bg=picked_color)
            return

        piece_indices = self._get_piece_indices(idx)

        if is_ctrl:
            for i in piece_indices:
                self.sticker_colors[i] = "#CCCCCC"
                self.sticker_states[i] = 0      
        elif is_shift:
            self.sticker_colors[idx] = self.colors[self.current_color_idx]
            self.sticker_states[idx] = 1
            self._autofix(idx)
            for i in piece_indices:
                self.sticker_states[i] = 1      
        else:
            self.sticker_colors[idx] = self.colors[self.current_color_idx]
            self.sticker_states[idx] = 0
            for i in piece_indices:
                if i != idx and self.sticker_states[i] != 0:
                    self.sticker_states[i] = 0
            if self.autofix_var.get():
                self._autofix(idx)
        self._sync_colors_to_canvas()

    def _handle_right_click(self, event):
        items = self.cube_canvas.find_closest(event.x, event.y)
        if not items: return
        poly_id = items[0]
        if poly_id in self.poly_ids:
            idx = self.poly_ids.index(poly_id)
            if idx not in self.center_indices:
                self.sticker_colors[idx] = "#CCCCCC"
                self.sticker_states[idx] = 0
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

        curr_colors = [self.sticker_colors[i] for i in piece_indices]
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
            self.sticker_colors[fc] = "#CCCCCC"
        elif len(matches) == 1 and empty_count == 1:
            match = matches[0]
            for i in range(len(piece_indices)):
                if self.sticker_colors[piece_indices[i]] == "#CCCCCC":
                    self.sticker_colors[piece_indices[i]] = match[i]
                    self.sticker_states[piece_indices[i]] = 0 

    def _on_right_click_release(self, btn, base_move):
        btn.configure(text=base_move)
        self._add_and_apply_move(base_move + "'")

    def _update_standard_pieces(self):
        self.def_col = {
            'U': self.colors[0], 'D': self.colors[1],
            'F': self.colors[2], 'B': self.colors[3],
            'L': self.colors[4], 'R': self.colors[5]
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
        cd = ColorChooserDialog(initialcolor=curr_color, title=tr("btn_customize"))
        cd.show()
        colors = cd.result
        if colors:
            hex_color = colors.hex
            self.colors[self.current_color_idx] = hex_color
            self.color_box.config(bg=hex_color)
            self._update_standard_pieces()
            for i in range(54):
                if self.sticker_colors[i] == curr_color:
                    self.sticker_colors[i] = hex_color
            self._sync_colors_to_canvas()

    def _cycle_color(self):
        self.current_color_idx = (self.current_color_idx + 1) % len(self.colors)
        self.color_box.config(bg=self.colors[self.current_color_idx])

    def _apply_turn_base(self, move):
        if move not in self.moves_perm: return
        perm = self.moves_perm[move]
        temp_colors = self.sticker_colors[:]
        temp_states = self.sticker_states[:]
        new_colors = [""] * 54
        new_states = [0] * 54
        for i in range(54):
            new_colors[perm[i]] = temp_colors[i]
            new_states[perm[i]] = temp_states[i]
        self.sticker_colors = new_colors
        self.sticker_states = new_states

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
        raw_alg = self.maneuver_var.get()
        try:
            expanded_alg = AdvancedParser.parse(raw_alg)
            for m in expanded_alg.split(): 
                self._execute_move_notation(m)
            self._sync_colors_to_canvas()
            if expanded_alg != " ".join(raw_alg.split()):
                self.log_text.insert(tk.END, f"> Custom Alg: {raw_alg}\n  Expanded: {expanded_alg}\n")
            else:
                self.log_text.insert(tk.END, f"> Executed: {expanded_alg}\n")
            self.log_text.see(tk.END)
        except Exception as e:
            self.log_text.insert(tk.END, f"[Error] Parsing notation failed: {e}\n")
            self.log_text.see(tk.END)

    def _add_and_apply_move(self, move_str):
        curr = self.maneuver_var.get()
        self.maneuver_var.set(curr + move_str + " ")
        self._execute_move_notation(move_str)
        self._sync_colors_to_canvas()

    def _reset_clean(self):
        faces = ['U', 'R', 'F', 'D', 'L', 'B']
        for i in range(6):
            for j in range(9):
                self.sticker_colors[i*9 + j] = self.def_col[faces[i]]
                self.sticker_states[i*9 + j] = 0
        self.maneuver_var.set("")
        self._sync_colors_to_canvas()

    def _reset_empty(self):
        self.sticker_colors = ["#CCCCCC"] * 54
        self.sticker_states = [0] * 54
        self._sync_colors_to_canvas()

    def _sync_colors_to_canvas(self):
        for i in range(54):
            self.cube_canvas.itemconfig(self.poly_ids[i], fill=self.sticker_colors[i])
            if self.overlay_ids[i]:
                for oid in self.overlay_ids[i]:
                    self.cube_canvas.delete(oid)
                self.overlay_ids[i] = []
            else:
                self.overlay_ids[i] = []
                
            state = self.sticker_states[i]
            if state in (1, 2):
                c = self.cube_canvas.coords(self.poly_ids[i])
                if state == 1: 
                    l1 = self.cube_canvas.create_line(c[0], c[1], c[4], c[5], fill=self.style.colors.fg, width=2.5)
                    l2 = self.cube_canvas.create_line(c[2], c[3], c[6], c[7], fill=self.style.colors.fg, width=2.5)
                    self.overlay_ids[i].extend([l1, l2])
                elif state == 2: 
                    cx, cy = (c[0]+c[2]+c[4]+c[6])/4, (c[1]+c[3]+c[5]+c[7])/4
                    o = self.cube_canvas.create_oval(cx-8, cy-8, cx+8, cy+8, fill=self.style.colors.selectbg, outline=self.style.colors.border, width=2.5)
                    self.overlay_ids[i].append(o)


class ContinuousSearchDialog(ttk.Toplevel):
    def __init__(self, parent, state_str, search_mode, is_incomplete, inverse=False):
        super().__init__(parent)
        title_prefix = tr("dlg_inc") if is_incomplete else tr("dlg_com")
        self.title(tr("dlg_title").format(title_prefix, search_mode.upper()))
        self.geometry("750x450")
        
        self.state_str = state_str
        self.search_mode = search_mode
        self.is_incomplete = is_incomplete
        self.inverse = inverse
        self.stop_requested = False
        self.result_queue = queue.Queue(maxsize=20)
        self.rows = []
        self.sort_mode = tk.StringVar(value="none")
        
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill=X)
        self.lbl_status = ttk.Label(top_frame, text=tr("dlg_status_search"), font=("Arial", 11, "bold"))
        self.lbl_status.pack(side=LEFT)
        self.btn_stop = ttk.Button(top_frame, text=tr("dlg_btn_stop"), bootstyle="danger", command=self.stop_search)
        self.btn_stop.pack(side=RIGHT)
        
        sort_frame = ttk.Frame(self, padding=(10, 0))
        sort_frame.pack(fill=X)
        ttk.Label(sort_frame, text=tr("dlg_sort")).pack(side=LEFT, padx=(0, 5))
        self.sort_cb = ttk.Combobox(
            sort_frame, state="disabled", width=12, textvariable=self.sort_mode,
            values=[tr("dlg_sort_none"), tr("dlg_sort_len"), tr("dlg_sort_lex")])
        self.sort_cb.pack(side=LEFT)
        self.sort_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_sort())
        
        cols = ("ID", "Length", "Maneuver", "State") if is_incomplete else ("ID", "Length", "Maneuver")
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)
        self.tree.heading("ID", text=tr("dlg_col_id"))
        self.tree.heading("Length", text=tr("dlg_col_len"))
        self.tree.heading("Maneuver", text=tr("dlg_col_sol"))
        self.tree.column("ID", width=50, anchor=CENTER)
        self.tree.column("Length", width=50, anchor=CENTER)
        self.tree.column("Maneuver", width=350)
        
        if is_incomplete:
            self.tree.heading("State", text=tr("dlg_col_state"))
            self.tree.column("State", width=250)
        
        vbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        vbar.pack(side=RIGHT, fill=Y)
        self.tree.bind("<Control-c>", self.copy_selected)
        
        if is_incomplete:
            self.worker = threading.Thread(
                target=completer.solve_incomplete_stream,
                args=(self.state_str, self.result_queue, lambda: self.stop_requested, self.search_mode, 0)
            )
        else:
            self.worker = threading.Thread(target=self._solve_complete_stream)
            
        self.worker.daemon = True
        self.worker.start()
        self.after(50, self.process_queue)

    def _apply_sort(self):
        if not self.rows:
            return
        mode = self.sort_mode.get()
        if mode == tr("dlg_sort_len"):
            ordered = sorted(self.rows, key=lambda r: r[1])
        elif mode == tr("dlg_sort_lex"):
            ordered = sorted(self.rows, key=lambda r: r[2])
        else:
            ordered = sorted(self.rows, key=lambda r: r[0])
        self.tree.delete(*self.tree.get_children())
        for count, moves_len, sol, comp_state in ordered:
            if self.is_incomplete:
                self.tree.insert("", tk.END, values=(count, f"{moves_len}f", sol, comp_state))
            else:
                self.tree.insert("", tk.END, values=(count, f"{moves_len}f", sol))
        
    def copy_selected(self, event=None):
        sel = self.tree.selection()
        if sel:
            item = self.tree.item(sel[0])
            maneuver = item['values'][2] 
            self.clipboard_clear()
            self.clipboard_append(maneuver)
            ToastNotification(title=tr("copy_title"), message=tr("copy_msg") + f"\n{maneuver}", duration=2000).show_toast()

    def _solve_complete_stream(self):
        count = 0
        try:
            for sol in cl_core.solve(self.state_str, mode=self.search_mode, stop_flag=lambda: self.stop_requested):
                if self.stop_requested: break
                count += 1
                moves_len = len(sol.split()) if sol else 0
                while not self.stop_requested:
                    try:
                        self.result_queue.put((count, self.state_str, sol, moves_len), timeout=0.1)
                        break
                    except queue.Full:
                        continue
        except Exception as e:
            if not self.stop_requested: 
                self.result_queue.put(("ERROR", str(e)))
            
        if not self.stop_requested:
            while not self.stop_requested:
                try:
                    self.result_queue.put(("DONE", count), timeout=0.1)
                    break
                except queue.Full:
                    continue

    def stop_search(self):
        self.stop_requested = True
        self.lbl_status.config(text=tr("dlg_aborted"))
        self.btn_stop.config(text=tr("dlg_btn_close"), command=self.destroy, bootstyle="secondary", state=NORMAL)
        self.sort_cb.config(state="readonly")
        while not self.result_queue.empty():
            try: 
                self.result_queue.get_nowait()
            except queue.Empty: 
                pass

    def process_queue(self):
        while not self.result_queue.empty():
            try:
                msg = self.result_queue.get_nowait()
            except queue.Empty:
                break
                
            if msg[0] == "DONE":
                self.lbl_status.config(text=tr("dlg_finished").format(msg[1]))
                self.btn_stop.config(text=tr("dlg_btn_close"), command=self.destroy, bootstyle="secondary", state=NORMAL)
                self.sort_cb.config(state="readonly")
                return
            elif msg[0] == "ERROR":
                self.lbl_status.config(text=f"Error: {msg[1]}")
                self.sort_cb.config(state="readonly")
                return
            else:
                count, comp_state, sol, moves_len = msg
                if self.inverse and sol:
                    sol = AdvancedParser.inverse(sol)
                self.rows.append((count, moves_len, sol, comp_state))
                if self.is_incomplete:
                    self.tree.insert("", 0, values=(count, f"{moves_len}f", sol, comp_state))
                else:
                    self.tree.insert("", 0, values=(count, f"{moves_len}f", sol))
                    
                self.lbl_status.config(text=tr("dlg_found").format(count))
                
        if not self.stop_requested:
            self.after(50, self.process_queue)


if __name__ == "__main__":
    app = CubeLibraryApp()
    app.mainloop()