import time
import random
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Querybox
from ttkbootstrap.toast import ToastNotification

class CLTimerTab(ttk.Frame):
    def __init__(self, master, app_instance, tr_func):
        super().__init__(master, padding=10)
        self.app = app_instance
        self.tr = tr_func  
        
        self.state = 0 
        self.start_time = 0.0
        self.elapsed = 0.0
        
        self.history = []
        self.current_scramble = ""
        self.viewing_idx = -1
        
        self.ready_job = None 
        self.update_job = None 
        self._release_debounce_job = None 
        
        self._create_ui()
        self._generate_new_scramble()
        
    def _create_ui(self):
        self.left_frame = ttk.Frame(self, width=200)
        self.left_frame.pack(side=LEFT, fill=Y, padx=(0, 10))
        
        self.right_frame = ttk.Frame(self)
        self.right_frame.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_hist = ttk.Label(self.left_frame, text=self.tr("timer_history"), font=("Arial", 10, "bold"))
        self.lbl_hist.pack(anchor=W, pady=(0, 5))
        
        self.tree = ttk.Treeview(self.left_frame, columns=("ID", "Time"), show="headings", selectmode="browse")
        self.tree.heading("ID", text=self.tr("timer_col_id"))
        self.tree.heading("Time", text=self.tr("timer_col_time"))
        self.tree.column("ID", width=40, anchor=CENTER)
        self.tree.column("Time", width=100, anchor=CENTER)
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        top_bar = ttk.Frame(self.right_frame)
        top_bar.pack(fill=X, pady=(10, 20))
        
        self.lbl_scramble = ttk.Label(
            top_bar, text="", font=("Consolas", 18, "bold"), 
            wraplength=600, justify=CENTER
        )
        self.lbl_scramble.pack(side=LEFT, expand=True, fill=X)
        self.lbl_scramble.bind("<Enter>", self._on_scramble_hover)
        self.lbl_scramble.bind("<Leave>", self._on_scramble_leave)
        self.lbl_scramble.bind("<Button-1>", self._copy_scramble)
        
        # === 新增的同步按钮 ===
        self.btn_sync = ttk.Button(top_bar, text=self.tr("timer_btn_sync"), bootstyle="info-outline", command=self._sync_to_editor)
        self.btn_sync.pack(side=RIGHT, padx=5)

        self.btn_custom = ttk.Button(top_bar, text=self.tr("timer_btn_custom"), bootstyle="outline", command=self._input_custom_scramble)
        self.btn_custom.pack(side=RIGHT, padx=5)
        
        self.lbl_time = ttk.Label(self.right_frame, text="0.00", font=("Arial", 120, "bold"), bootstyle=DEFAULT)
        self.lbl_time.pack(expand=True)
        
        bot_frame = ttk.Frame(self.right_frame)
        bot_frame.pack(fill=X, side=BOTTOM, pady=20)
        
        self.lbl_stats = ttk.Label(bot_frame, text="", font=("Arial", 14))
        self.lbl_stats.pack(side=LEFT, padx=10)
        
        self.btn_next = ttk.Button(bot_frame, text=self.tr("timer_btn_next"), bootstyle=PRIMARY, command=self._generate_new_scramble)
        self.btn_next.pack(side=RIGHT, padx=5)

        self.btn_del = ttk.Button(bot_frame, text=self.tr("timer_btn_delete"), bootstyle="danger-outline", command=self._delete_record)
        self.btn_del.pack(side=RIGHT, padx=(20, 5))
        
        self.btn_dnf = ttk.Button(bot_frame, text="DNF", bootstyle="warning-outline", command=lambda: self._toggle_penalty("DNF"))
        self.btn_dnf.pack(side=RIGHT, padx=5)

        self.btn_plus2 = ttk.Button(bot_frame, text="+2", bootstyle="warning-outline", command=lambda: self._toggle_penalty("+2"))
        self.btn_plus2.pack(side=RIGHT, padx=5)
        
        self.update_stats()

    def update_strings(self):
        self.lbl_hist.configure(text=self.tr("timer_history"))
        self.tree.heading("ID", text=self.tr("timer_col_id"))
        self.tree.heading("Time", text=self.tr("timer_col_time"))
        self.btn_custom.configure(text=self.tr("timer_btn_custom"))
        self.btn_sync.configure(text=self.tr("timer_btn_sync"))
        self.btn_next.configure(text=self.tr("timer_btn_next"))
        self.btn_del.configure(text=self.tr("timer_btn_delete"))
        self.update_stats()

    def _on_scramble_hover(self, event):
        self.lbl_scramble.configure(cursor="hand2")
        self.lbl_scramble.configure(foreground=ttk.Style().colors.primary)

    def _on_scramble_leave(self, event):
        self.lbl_scramble.configure(cursor="")
        # 【修复 BUG】：改为 fg
        self.lbl_scramble.configure(foreground=ttk.Style().colors.fg)

    def _copy_scramble(self, event):
        scramble_text = self.lbl_scramble.cget("text")
        if scramble_text:
            self.clipboard_clear()
            self.clipboard_append(scramble_text)
            ToastNotification(title=self.tr("timer_copy_title"), message=self.tr("timer_copy_msg"), duration=1500).show_toast()

    def _input_custom_scramble(self):
        res = Querybox.get_string(self.tr("timer_custom_prompt"), self.tr("timer_custom_title"))
        if res and res.strip():
            self.current_scramble = res.strip()
            self._exit_review_mode()

    # === [新增：同步给主程序] ===
    def _sync_to_editor(self):
        if hasattr(self.app, "sync_from_timer"):
            # 获取当前屏幕上正在显示的公式（支持历史回顾态）
            target_scramble = self.lbl_scramble.cget("text")
            self.app.sync_from_timer(target_scramble)

    def _generate_new_scramble(self):
        moves = ["U", "D", "R", "L", "F", "B"]
        mods = ["", "'", "2"]
        scramble = []
        last = ""
        for _ in range(21):
            m = random.choice(moves)
            while m == last: m = random.choice(moves)
            last = m
            scramble.append(m + random.choice(mods))
        self.current_scramble = " ".join(scramble)
        self._exit_review_mode()

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        idx = int(self.tree.item(sel[0])['values'][0]) - 1
        self.viewing_idx = idx
        record = self.history[idx]
        
        self.lbl_scramble.configure(text=record["scramble"])
        self.lbl_time.configure(text=self.format_record(record), bootstyle=INFO)

    def _exit_review_mode(self):
        self.viewing_idx = -1
        for item in self.tree.selection():
            self.tree.selection_remove(item)
            
        self.lbl_scramble.configure(text=self.current_scramble)
        if self.history:
            self.lbl_time.configure(text=self.format_record(self.history[-1]), bootstyle=DEFAULT)
        else:
            self.lbl_time.configure(text="0.00", bootstyle=DEFAULT)

    def _refresh_treeview(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, record in enumerate(self.history):
            t_str = self.format_record(record)
            self.tree.insert("", "end", values=(i + 1, t_str))
        if self.tree.get_children():
            self.tree.yview_moveto(1)

    def raw_format(self, seconds):
        if seconds == float('inf'): return "DNF"
        if seconds < 60: return f"{seconds:.2f}"
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}:{secs:05.2f}"

    def get_effective_time(self, record):
        if record["penalty"] == "DNF": return float('inf')
        elif record["penalty"] == "+2": return record["base"] + 2.0
        return record["base"]

    def format_record(self, record):
        if record["penalty"] == "DNF": return "DNF"
        elif record["penalty"] == "+2": return self.raw_format(record["base"] + 2.0) + "+"
        return self.raw_format(record["base"])

    def calculate_wca_average(self, n):
        if len(self.history) < n: return "--"
        effective_times = [self.get_effective_time(r) for r in self.history[-n:]]
        effective_times.sort()
        trimmed = effective_times[1:-1]
        if float('inf') in trimmed: return "DNF"
        return self.raw_format(sum(trimmed) / len(trimmed))

    def update_stats(self):
        ao5 = self.calculate_wca_average(5)
        ao12 = self.calculate_wca_average(12)
        stats_text = self.tr("timer_stats")
        if stats_text == "timer_stats": 
            stats_text = "Solves: {0} | Ao5: {1} | Ao12: {2}"
        self.lbl_stats.configure(text=stats_text.format(len(self.history), ao5, ao12))

    def _get_target_idx(self):
        if not self.history: return -1
        return self.viewing_idx if self.viewing_idx != -1 else len(self.history) - 1

    def _delete_record(self):
        idx = self._get_target_idx()
        if idx == -1: return
        self.history.pop(idx)
        self.update_stats()
        self._refresh_treeview()
        self._exit_review_mode() 

    def _toggle_penalty(self, p_type):
        idx = self._get_target_idx()
        if idx == -1: return
        
        record = self.history[idx]
        record["penalty"] = "" if record["penalty"] == p_type else p_type
            
        style = INFO if self.viewing_idx != -1 else DEFAULT
        self.lbl_time.configure(text=self.format_record(record), bootstyle=style)
        
        self.update_stats()
        self._refresh_treeview()
        
        if self.viewing_idx != -1:
            items = self.tree.get_children()
            if items and idx < len(items):
                self.tree.selection_set(items[idx])

    def on_space_press(self, event):
        if self._release_debounce_job is not None:
            self.after_cancel(self._release_debounce_job)
            self._release_debounce_job = None
            return  

        if self.viewing_idx != -1:
            self._exit_review_mode()
            
        if self.state == 0: 
            self.state = 1
            self.lbl_time.configure(bootstyle=DANGER) 
            if self.ready_job is not None: self.after_cancel(self.ready_job)
            self.ready_job = self.after(300, self._set_ready)
            
        elif self.state == 3: 
            self.state = 0
            self.elapsed = time.time() - self.start_time
            if self.update_job is not None: self.after_cancel(self.update_job)
            
            new_record = {"base": self.elapsed, "penalty": "", "scramble": self.current_scramble}
            self.history.append(new_record)
            
            self.lbl_time.configure(text=self.format_record(new_record))
            self.update_stats()
            self._refresh_treeview()
            self._generate_new_scramble()

    def _set_ready(self):
        if self.state == 1: 
            self.state = 2
            self.lbl_time.configure(bootstyle=SUCCESS) 
            self.lbl_time.configure(text="0.00")

    def on_space_release(self, event):
        if self._release_debounce_job is not None:
            self.after_cancel(self._release_debounce_job)
        self._release_debounce_job = self.after(10, self._actual_space_release)

    def _actual_space_release(self):
        self._release_debounce_job = None
        
        if self.state == 1: 
            self.state = 0
            if self.history:
                self.lbl_time.configure(text=self.format_record(self.history[-1]), bootstyle=DEFAULT)
            else:
                self.lbl_time.configure(text="0.00", bootstyle=DEFAULT)
                
            if self.ready_job is not None: self.after_cancel(self.ready_job)
                
        elif self.state == 2:
            self.state = 3
            self.lbl_time.configure(bootstyle=DEFAULT)
            self.start_time = time.time()
            self._update_timer()

    def _update_timer(self):
        if self.state == 3:
            current = time.time() - self.start_time
            self.lbl_time.configure(text=self.raw_format(current))
            self.update_job = self.after(30, self._update_timer)