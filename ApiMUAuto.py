import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pyautogui
import time
import json
import threading
import os
import glob
import sys 
import keyboard

CONFIDENCE = 0.8

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
IMAGE_DIR = os.path.join(BASE_DIR, "images")

# ==========================================
# 1. VISION MODULE
# ==========================================
class GameVision:
    def __init__(self, folder=IMAGE_DIR):
        self.folder = folder

    def get_pos(self, img_name):
        try:
            full_path = os.path.join(self.folder, img_name)
            pos = pyautogui.locateCenterOnScreen(full_path, confidence=CONFIDENCE)
            if pos: return pos.x, pos.y
        except: pass
        return None

    def get_pos_absolute(self, img_path):
        try:
            pos = pyautogui.locateCenterOnScreen(img_path, confidence=CONFIDENCE)
            if pos: return pos.x, pos.y
        except: pass
        return None

    def check_state(self):
        if self.get_pos("btn_confirm.png"): return "DISCONNECT"
        if self.get_pos("btn_spell_card.png"): return "IN_BATTLE"
        if self.get_pos("btn_redraw.png") or self.get_pos("btn_redraw_dark.png"): return "BUFF_SELECT"
        if self.get_pos("btn_set_party.png") or self.get_pos("btn_challenge.png"): return "PREPARE"
        return "UNKNOWN"


# ==========================================
# 2. UI & ENGINE MODULE
# ==========================================
class DynamicGroupBot:
    def __init__(self, root):
        self.root = root
        self.root.title("Api Moriya Unmapped Auto")
        self.root.geometry("1000x950")
        
        icon_path = os.path.join(BASE_DIR, "icon.ico")
        if os.path.exists(icon_path):
            try: self.root.iconbitmap(icon_path)
            except: pass
        
        self.vision = GameVision()
        self.is_running = False
        self.current_area = 1
        self.completed_loops = 0
        
        self.char_notes = {"1": "", "2": "", "3": ""}
        self.char_note_vars = {}
        self.clipboard = []
        
        # --- COORDINATE KEYS ---
        self.common_keys = [
            "Open/Close Skill", "Open Spell", "Boost", "Spread Shot", "Focus Shot",
            "Random Buff", "Skip Corner" 
        ]
        self.party_keys = [
            "Main Stage", "Party Button", "Party Back",
            "Battle", "Challenge"
        ]
        self.spell_keys = []
        for i in range(1, 5): self.spell_keys.append(f"Spell {i}")
        self.spell_keys.append("LastWord")
        
        self.all_possible_keys = []
        self.all_possible_keys.extend(self.common_keys)
        self.all_possible_keys.extend(self.party_keys)
        self.all_possible_keys.extend(self.spell_keys)
        self.all_possible_keys.extend(["Open Skill", "Close Skill"])
        
        for i in range(1, 4): 
             self.all_possible_keys.append(f"Slot {i} Open List")
             self.all_possible_keys.append(f"Slot {i} Selected Grid Pos")
             for j in range(1, 4): self.all_possible_keys.append(f"Char {i} Skill {j}")

        self.coords = {key: {"x": 0, "y": 0} for key in self.all_possible_keys}
        self.displayed_keys = []
        self.main_script = [] 
        self.current_hotkey = None
        self.current_stop_hotkey = None

        self.build_ui()

    # ================= UI BUILDER =================
    def build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # ================= TAB 1: ASSIGN COORDINATES =================
        tab_coord = ttk.Frame(notebook)
        notebook.add(tab_coord, text="1. Assign Coordinates")
        
        ctrl_frame = ttk.LabelFrame(tab_coord, text="Display Settings")
        ctrl_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(ctrl_frame, text="Number of Characters:").pack(side="left", padx=5)
        self.num_chars_var = tk.IntVar(value=2)
        cbo_chars = ttk.Combobox(ctrl_frame, textvariable=self.num_chars_var, values=[1, 2, 3], state="readonly", width=5)
        cbo_chars.pack(side="left", padx=5)
        cbo_chars.bind("<<ComboboxSelected>>", self.render_coord_ui)
        
        canvas = tk.Canvas(tab_coord)
        scrollbar = ttk.Scrollbar(tab_coord, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)
        self.scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # ================= TAB 2: SCRIPT EDITOR =================
        tab_script = ttk.Frame(notebook)
        notebook.add(tab_script, text="2. Script Editor")
        
        
        frame_input = ttk.LabelFrame(tab_script, text="Action Toolset")
        frame_input.pack(fill="x", padx=5, pady=5, ipady=5)
        
        ttk.Label(frame_input, text="Category:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.categories = ["⚔️ Combat", "🛡️ Party Preparation", "🎁 Buff & Area Transition", "⚙️ System Commands"]
        self.cbo_category = ttk.Combobox(frame_input, values=self.categories, state="readonly", width=25)
        self.cbo_category.current(0)
        self.cbo_category.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.cbo_category.bind("<<ComboboxSelected>>", self.update_action_combobox)
        
        ttk.Label(frame_input, text="Action:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.cbo_action = ttk.Combobox(frame_input, state="readonly", width=25)
        self.cbo_action.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.cbo_action.bind("<<ComboboxSelected>>", self.update_target_combobox)
        
        ttk.Label(frame_input, text="Target:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.cbo_target = ttk.Combobox(frame_input, width=30) 
        self.cbo_target.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        self.cbo_target.config(postcommand=lambda: self.update_target_combobox(None))
        
        frame_btns = ttk.Frame(frame_input)
        frame_btns.grid(row=2, column=0, columnspan=4, pady=10)
        ttk.Button(frame_btns, text="➕ Add to Bottom", width=20, command=self.add_action).pack(side="left", padx=5)
        ttk.Button(frame_btns, text="📥 Insert Above", width=20, command=self.insert_action).pack(side="left", padx=5)
        ttk.Button(frame_btns, text="📝 Update Selected", width=25, command=self.update_action).pack(side="left", padx=5)
        
        self.listbox = tk.Listbox(tab_script, height=13, font=("Consolas", 11), selectmode=tk.EXTENDED, exportselection=False)
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.listbox.bind('<ButtonRelease-1>', self.load_selected_to_inputs)
        
        frame_edit = ttk.Frame(tab_script)
        frame_edit.pack(fill="x", pady=5)
        ttk.Button(frame_edit, text="⬆ Up", command=lambda: self.move_item(-1)).pack(side="left", padx=2)
        ttk.Button(frame_edit, text="⬇ Down", command=lambda: self.move_item(1)).pack(side="left", padx=2)
        ttk.Button(frame_edit, text="📋 Copy", command=self.copy_action).pack(side="left", padx=10)
        ttk.Button(frame_edit, text="📋 Paste", command=self.paste_action).pack(side="left", padx=2)
        ttk.Button(frame_edit, text="❌ Delete", command=self.delete_action).pack(side="left", padx=20)
        ttk.Button(frame_edit, text="🧹 Clear All", command=lambda: self.listbox.delete(0, tk.END)).pack(side="right", padx=5)

        # --- Structured Search & Replace ---
        frame_sr = ttk.LabelFrame(tab_script, text="Search & Replace")
        frame_sr.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(frame_sr, text="Find Action:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.cbo_search_act = ttk.Combobox(frame_sr, width=20)
        self.cbo_search_act.config(postcommand=self.update_sr_dropdowns)
        self.cbo_search_act.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(frame_sr, text="Find Target:").grid(row=0, column=2, padx=5, pady=2, sticky="e")
        self.cbo_search_tgt = ttk.Combobox(frame_sr, width=35)
        self.cbo_search_tgt.config(postcommand=self.update_sr_dropdowns)
        self.cbo_search_tgt.grid(row=0, column=3, padx=5, pady=2, sticky="w")

        ttk.Label(frame_sr, text="Replace Action:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.cbo_replace_act = ttk.Combobox(frame_sr, width=20)
        self.cbo_replace_act.config(postcommand=self.update_sr_dropdowns)
        self.cbo_replace_act.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(frame_sr, text="Replace Target:").grid(row=1, column=2, padx=5, pady=2, sticky="e")
        self.cbo_replace_tgt = ttk.Combobox(frame_sr, width=35)
        self.cbo_replace_tgt.config(postcommand=self.update_sr_dropdowns)
        self.cbo_replace_tgt.grid(row=1, column=3, padx=5, pady=2, sticky="w")
        
        frame_sr_btns = ttk.Frame(frame_sr)
        frame_sr_btns.grid(row=2, column=0, columnspan=4, pady=5)
        ttk.Button(frame_sr_btns, text="🔍 Search", width=15, command=self.perform_search).pack(side="left", padx=10)
        ttk.Button(frame_sr_btns, text="🔄 Replace All", width=15, command=self.replace_all).pack(side="left", padx=10)
        ttk.Button(frame_sr_btns, text="🧹 Clear Search", width=15, command=self.clear_search).pack(side="left", padx=10)

        # ================= TAB 3: AUTO RUNNER =================
        tab_run = ttk.Frame(notebook)
        notebook.add(tab_run, text="3. Auto Runner")
        
        frame_settings = ttk.LabelFrame(tab_run, text="Farming Settings (Chế độ chạy)")
        frame_settings.pack(fill="x", padx=10, pady=10)
        
        self.run_mode = tk.StringVar(value="loop")
        
        ttk.Radiobutton(frame_settings, text="Run by Loops:", variable=self.run_mode, value="loop", command=self.update_run_mode).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.loop_var = tk.IntVar(value=1)
        self.entry_loop = ttk.Entry(frame_settings, textvariable=self.loop_var, width=10)
        self.entry_loop.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Radiobutton(frame_settings, text="Run by Time:", variable=self.run_mode, value="time", command=self.update_run_mode).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        frame_time = ttk.Frame(frame_settings)
        frame_time.grid(row=1, column=1, sticky="w")
        self.hour_var = tk.IntVar(value=0)
        self.min_var = tk.IntVar(value=30)
        
        self.entry_h = ttk.Entry(frame_time, textvariable=self.hour_var, width=5)
        self.entry_h.pack(side="left")
        ttk.Label(frame_time, text="h").pack(side="left", padx=2)
        self.entry_m = ttk.Entry(frame_time, textvariable=self.min_var, width=5)
        self.entry_m.pack(side="left", padx=2)
        ttk.Label(frame_time, text="m").pack(side="left")
        
        ttk.Radiobutton(frame_settings, text="Run Infinitely", variable=self.run_mode, value="infinite", command=self.update_run_mode).grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        self.update_run_mode()
        
        self.lbl_status = ttk.Label(tab_run, text="Status: STOPPED", foreground="red", font=("Arial", 14, "bold"))
        self.lbl_status.pack(pady=15)
        self.lbl_info = ttk.Label(tab_run, text="Ready", font=("Arial", 11))
        self.lbl_info.pack(pady=5)

        # === BẮT ĐẦU ĐOẠN CODE HOTKEY MỚI ===
        frame_hotkey = ttk.LabelFrame(tab_run, text="Cài đặt Phím tắt (Hotkeys)")
        frame_hotkey.pack(fill="x", padx=10, pady=5)
        
        # --- Dòng 1: Phím Bắt đầu / Bật tắt (Start/Toggle) ---
        frame_hk_start = ttk.Frame(frame_hotkey)
        frame_hk_start.pack(fill="x", padx=5, pady=2)
        ttk.Label(frame_hk_start, text="Start/Toggle: Modifier:").pack(side="left", padx=2)
        self.cbo_modifier = ttk.Combobox(frame_hk_start, values=["None", "ctrl", "alt", "shift"], state="readonly", width=6)
        self.cbo_modifier.current(0)
        self.cbo_modifier.pack(side="left", padx=2)
        self.cbo_modifier.bind("<<ComboboxSelected>>", self.update_hotkey)
        
        ttk.Label(frame_hk_start, text="Key:").pack(side="left", padx=2)
        self.cbo_key = ttk.Combobox(frame_hk_start, values=["f6", "f7", "f8", "f9", "f10", "f11", "f12"], state="readonly", width=6)
        self.cbo_key.current(0) # Mặc định F6
        self.cbo_key.pack(side="left", padx=2)
        self.cbo_key.bind("<<ComboboxSelected>>", self.update_hotkey)
        
        self.lbl_current_hotkey = ttk.Label(frame_hk_start, text="[F6]", foreground="blue", font=("Arial", 10, "bold"))
        self.lbl_current_hotkey.pack(side="left", padx=10)

        # --- Dòng 2: Phím Dừng hẳn (Force Stop) ---
        frame_hk_stop = ttk.Frame(frame_hotkey)
        frame_hk_stop.pack(fill="x", padx=5, pady=2)
        ttk.Label(frame_hk_stop, text="Force Stop:   Modifier:").pack(side="left", padx=2)
        self.cbo_stop_modifier = ttk.Combobox(frame_hk_stop, values=["None", "ctrl", "alt", "shift"], state="readonly", width=6)
        self.cbo_stop_modifier.current(0)
        self.cbo_stop_modifier.pack(side="left", padx=2)
        self.cbo_stop_modifier.bind("<<ComboboxSelected>>", self.update_stop_hotkey)
        
        ttk.Label(frame_hk_stop, text="Key:").pack(side="left", padx=2)
        self.cbo_stop_key = ttk.Combobox(frame_hk_stop, values=["f6", "f7", "f8", "f9", "f10", "f11", "f12"], state="readonly", width=6)
        self.cbo_stop_key.current(1) # Mặc định F7
        self.cbo_stop_key.pack(side="left", padx=2)
        self.cbo_stop_key.bind("<<ComboboxSelected>>", self.update_stop_hotkey)
        
        self.lbl_current_stop_hotkey = ttk.Label(frame_hk_stop, text="[F7]", foreground="red", font=("Arial", 10, "bold"))
        self.lbl_current_stop_hotkey.pack(side="left", padx=10)
        # === KẾT THÚC ĐOẠN CODE HOTKEY MỚI ===
        
        
        
        ttk.Button(tab_run, text="▶ START / ⏹ STOP", command=self.toggle_bot).pack(ipady=15, fill="x", padx=50, pady=10)
        
        frame_file = ttk.Frame(tab_run)
        frame_file.pack(pady=20)
        ttk.Button(frame_file, text="💾 Save Profile", command=self.save_profile).pack(side="left", expand=True, padx=5)
        ttk.Button(frame_file, text="📂 Load Profile", command=self.load_profile).pack(side="left", expand=True, padx=5)

        self.render_coord_ui()
        self.update_action_combobox(None) 
        self.update_hotkey()
        self.update_stop_hotkey()
        self.root.after(100, self.check_hotkeys_loop)

    # ================= UI LOGIC =================
    
    def update_sr_dropdowns(self):
        all_actions = ["CLICK", "BOOST", "WAIT", "WAIT_FOR_SCREEN", "CHOOSE_DIFFICULTY", "CONFIRM", "CONFIRM_PARTY_SLOT", "CLICK_SKIP_CORNER", "SELECT_BUFF", "START_AREA", "END_AREA", "SEPARATOR"]
        all_targets = ["None"]
        
        # Nạp target từ script hiện tại
        for i in range(self.listbox.size()):
            text = self.listbox.get(i)
            if "] -> " in text:
                all_targets.append(text.split("] -> ")[1].strip())
                
        # Nạp target từ hệ thống
        all_t = list(self.coords.keys()) + ["btn_normal.png", "btn_hard.png", "btn_lunatic.png", "btn_boss_lunatic.png", "Strict Tier 1", "Any Tier", "BATTLE_SCREEN", "PREPARE_SCREEN", "BUFF_SCREEN", "SELECT_PARTY_SCREEN", "END_BATTLE_SCREEN"]
        for i in range(1, 4):
            c_name = self.char_note_vars[str(i)].get().strip() if str(i) in self.char_note_vars else ""
            if c_name:
                for j in range(1, 4): all_t.append(f"{c_name} Skill {j}")
                all_t.append(f"{c_name} Spread Shot")
                all_t.append(f"{c_name} Focus Shot")
                for j in range(1, 5): all_t.append(f"{c_name} Spell {j}")
                all_t.append(f"{c_name} LastWord")
                
        all_targets.extend(all_t)
        unique_targets = sorted(list(set(all_targets)))
        
        self.cbo_search_act.config(values=all_actions)
        self.cbo_replace_act.config(values=all_actions)
        self.cbo_search_tgt.config(values=unique_targets)
        self.cbo_replace_tgt.config(values=unique_targets)

    def clear_search(self):
        self.cbo_search_act.set("")
        self.cbo_search_tgt.set("")
        self.cbo_replace_act.set("")
        self.cbo_replace_tgt.set("")
        self.apply_listbox_colors()

    def check_hotkeys_loop(self):
        try:
            # Quét phím Bật/Tắt
            if self.current_hotkey and keyboard.is_pressed(self.current_hotkey):
                now = time.time()
                if now - getattr(self, 'last_toggle_time', 0) > 0.5: # Chống dội phím 0.5s
                    self.last_toggle_time = now
                    self.toggle_bot()
                    
            # Quét phím Dừng hẳn
            if self.current_stop_hotkey and keyboard.is_pressed(self.current_stop_hotkey):
                now = time.time()
                if now - getattr(self, 'last_stop_time', 0) > 0.5:
                    self.last_stop_time = now
                    self.force_stop()
        except Exception:
            pass # Bỏ qua lỗi nếu mất quyền admin đột ngột
        finally:
            # Lặp lại sau mỗi 100ms (0.1 giây)
            self.root.after(100, self.check_hotkeys_loop)

    def update_hotkey(self, event=None):
        mod = self.cbo_modifier.get()
        key = self.cbo_key.get()
        self.current_hotkey = key if mod == "None" else f"{mod}+{key}"
        self.lbl_current_hotkey.config(text=f"[{self.current_hotkey.upper()}]")

    def update_stop_hotkey(self, event=None):
        mod = self.cbo_stop_modifier.get()
        key = self.cbo_stop_key.get()
        self.current_stop_hotkey = key if mod == "None" else f"{mod}+{key}"
        self.lbl_current_stop_hotkey.config(text=f"[{self.current_stop_hotkey.upper()}]")

    
    def force_stop(self):
        if self.is_running:
            self.is_running = False
            self.lbl_status.config(text="Status: STOPPED", foreground="red")
            self.root.deiconify() 

    def perform_search(self):
        s_act = self.cbo_search_act.get().strip().lower()
        s_tgt = self.cbo_search_tgt.get().strip().lower()
        self.apply_listbox_colors() 
        
        if not s_act and not s_tgt:
            return messagebox.showwarning("Warning", "Please enter Find Action or Find Target to search!")
            
        found_count = 0
        first_idx = -1
        
        for i in range(self.listbox.size()):
            text = self.listbox.get(i)
            if "] -> " not in text: continue
            
            parts = text.split("] -> ")
            act = parts[0].replace("[", "").lower()
            tgt = parts[1].lower()
            
            # Logic: Bỏ trống ô nào thì ô đó auto = True
            match_act = True if not s_act else (s_act in act)
            match_tgt = True if not s_tgt else (s_tgt in tgt)
            
            if match_act and match_tgt:
                self.listbox.itemconfig(i, bg="#fff566", fg="black") # Vàng highlight
                if first_idx == -1: first_idx = i
                found_count += 1
                
        if found_count > 0:
            self.listbox.see(first_idx) 
            messagebox.showinfo("Search", f"Found {found_count} matches. Highlighted in yellow.")
        else:
            messagebox.showinfo("Search", "No matches found!")
            
    def replace_all(self):
        s_act = self.cbo_search_act.get().strip()
        s_tgt = self.cbo_search_tgt.get().strip()
        r_act = self.cbo_replace_act.get().strip()
        r_tgt = self.cbo_replace_tgt.get().strip()
        
        if not s_act and not s_tgt:
            return messagebox.showwarning("Warning", "Please define what to Find before replacing!")
        if not r_act and not r_tgt:
            return messagebox.showwarning("Warning", "Please define what to Replace with!")
            
        count = 0
        for i in range(self.listbox.size()):
            text = self.listbox.get(i)
            if "] -> " not in text: continue
            
            parts = text.split("] -> ")
            act = parts[0].replace("[", "")
            tgt = parts[1]
            
            match_act = True if not s_act else (s_act.lower() in act.lower())
            match_tgt = True if not s_tgt else (s_tgt.lower() in tgt.lower())
            
            if match_act and match_tgt:
                # Nếu replace ô nào rỗng, giữ nguyên giá trị cũ
                new_act = r_act if r_act else act
                new_tgt = r_tgt if r_tgt else tgt
                
                new_text = f"[{new_act}] -> {new_tgt}"
                
                if text != new_text:
                    was_selected = self.listbox.selection_includes(i)
                    self.listbox.delete(i)
                    self.listbox.insert(i, new_text)
                    if was_selected: self.listbox.selection_set(i)
                    count += 1
                    
        if count > 0:
            self.auto_format_list()
            messagebox.showinfo("Replace", f"Replaced {count} occurrences successfully!")
        else:
            messagebox.showinfo("Replace", "No matching lines found to replace!")
    # ---------------------------------------------------------

    def update_run_mode(self):
        mode = self.run_mode.get()
        if mode == "loop":
            self.entry_loop.config(state="normal")
            self.entry_h.config(state="disabled")
            self.entry_m.config(state="disabled")
        elif mode == "time":
            self.entry_loop.config(state="disabled")
            self.entry_h.config(state="normal")
            self.entry_m.config(state="normal")
        else:
            self.entry_loop.config(state="disabled")
            self.entry_h.config(state="disabled")
            self.entry_m.config(state="disabled")

    def render_coord_ui(self, *args):
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        self.lbl_coords = {}
        row = 0
        
        group_frames = [
            ("Core Controls", [k for k in self.common_keys if k not in ["Open Skill", "Close Skill"]]),
            ("Party & Prepare", self.party_keys),
            ("Spells & LastWord", self.spell_keys)
        ]

        self.displayed_keys = []
        for g_name, g_keys in group_frames:
            self.create_group_frame(g_name, g_keys, row)
            row += 1
            self.displayed_keys.extend(g_keys)

        ttk.Label(self.scroll_frame, text="="*60, foreground="gray").grid(row=row, column=0, columnspan=2, pady=10)
        row += 1
        
        chars = self.num_chars_var.get()
        for i in range(1, chars + 1):
            char_keys = [
                f"Slot {i} Open List", f"Slot {i} Selected Grid Pos",
                f"Char {i} Skill {1}", f"Char {i} Skill {2}", f"Char {i} Skill {3}"
            ]
            c_name = self.char_notes.get(str(i), "").strip()
            title = f"Character {i}" + (f" ({c_name})" if c_name else "")
            
            frame = ttk.LabelFrame(self.scroll_frame, text=title)
            frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10) 
            
            note_frame = ttk.Frame(frame)
            note_frame.grid(row=0, column=0, columnspan=6, sticky="w", padx=5, pady=5)
            ttk.Label(note_frame, text="📝 Note (Name):").pack(side="left")
            
            if str(i) not in self.char_note_vars:
                self.char_note_vars[str(i)] = tk.StringVar(value=self.char_notes.get(str(i), ""))
            
            ttk.Entry(note_frame, textvariable=self.char_note_vars[str(i)], width=25, foreground="blue").pack(side="left", padx=5)
            
            self.render_keys_in_frame(frame, char_keys, start_row=1)
            self.displayed_keys.extend(char_keys)
            row += 1

        self.update_target_combobox(None)

    def create_group_frame(self, group_name, keys, main_row):
        frame = ttk.LabelFrame(self.scroll_frame, text=group_name)
        frame.grid(row=main_row, column=0, columnspan=2, sticky="ew", padx=10, pady=5) 
        self.render_keys_in_frame(frame, keys)

    def render_keys_in_frame(self, frame, keys, start_row=0):
        r, c = start_row, 0
        for key in keys:
            ttk.Label(frame, text=f"{key}:").grid(row=r, column=c, sticky="w", padx=5, pady=5)
            val = self.coords.get(key, {"x": 0, "y": 0})
            lbl = ttk.Label(frame, text=f"[{val['x']}, {val['y']}]", foreground="blue", width=12)
            lbl.grid(row=r, column=c+1, sticky="w", padx=5, pady=5)
            self.lbl_coords[key] = lbl
            
            btn = ttk.Button(frame, text="🎯 Get", width=6, command=lambda k=key: self.start_capture_mode(k))
            btn.grid(row=r, column=c+2, padx=5, pady=5)
            
            c += 3
            if c > 3: 
                c = 0
                r += 1

    def start_capture_mode(self, key):
        self.root.iconify() 
        time.sleep(0.3) 
        self.capture_win = tk.Toplevel(self.root)
        self.capture_win.attributes('-fullscreen', True)
        self.capture_win.attributes('-alpha', 0.1)
        self.capture_win.config(cursor="crosshair", bg="gray")
        self.capture_win.attributes("-topmost", True)
        
        lbl = tk.Label(self.capture_win, text=f"Click on the position for: {key}", font=("Arial", 24, "bold"), fg="red", bg="white")
        lbl.pack(pady=100)
        self.capture_win.bind("<Button-1>", lambda e, k=key: self.end_capture_mode(e, k))

    def end_capture_mode(self, event, key):
        x, y = event.x_root, event.y_root
        self.coords[key] = {"x": x, "y": y}
        if key in self.lbl_coords:
            self.lbl_coords[key].config(text=f"[{x}, {y}]")
            
        if key == "Open/Close Skill":
            self.coords["Open Skill"] = {"x": x, "y": y}
            self.coords["Close Skill"] = {"x": x, "y": y}
            
        self.capture_win.destroy()
        self.root.deiconify()
        self.root.lift()

    def get_real_key(self, display_target):
        shared_combat_btns = ["Spread Shot", "Focus Shot", "Spell 1", "Spell 2", "Spell 3", "Spell 4", "LastWord"]
        for i in range(1, 4):
            c_name = self.char_note_vars[str(i)].get().strip() if str(i) in self.char_note_vars else ""
            prefix = c_name if c_name else f"Char {i}"
            if display_target.startswith(f"{prefix} Skill"):
                return display_target.replace(f"{prefix} Skill", f"Char {i} Skill")
            if display_target.startswith(f"{prefix} Open List"):
                return display_target.replace(f"{prefix} Open List", f"Slot {i} Open List")
            if display_target.startswith(f"{prefix} Selected Grid Pos"):
                return display_target.replace(f"{prefix} Selected Grid Pos", f"Slot {i} Selected Grid Pos")
            for btn in shared_combat_btns:
                if display_target == f"{prefix} {btn}":
                    return btn 
        return display_target

    def update_action_combobox(self, event):
        cat = self.cbo_category.get()
        if "Combat" in cat:
            self.cbo_action.config(values=["CLICK", "BOOST", "WAIT_FOR_SCREEN"])
        elif "Party" in cat:
            self.cbo_action.config(values=["CLICK", "CHOOSE_DIFFICULTY", "CONFIRM_PARTY_SLOT", "WAIT_FOR_SCREEN"])
        elif "Buff" in cat:
            self.cbo_action.config(values=["SELECT_BUFF", "CLICK_SKIP_CORNER", "START_AREA", "END_AREA", "WAIT_FOR_SCREEN"])
        elif "System" in cat:
            self.cbo_action.config(values=["WAIT", "SEPARATOR", "CONFIRM"])
            
        self.cbo_action.current(0)
        self.update_target_combobox(None)

    def update_target_combobox(self, event):
        cat = self.cbo_category.get()
        action = self.cbo_action.get()
        
        if action == "CLICK":
            if "Combat" in cat:
                targets = ["Open/Close Skill", "Open Spell"]
                for i in range(1, self.num_chars_var.get() + 1):
                    c_name = self.char_note_vars[str(i)].get().strip() or f"Char {i}"
                    for j in range(1, 4): targets.append(f"{c_name} Skill {j}")
                    targets.append(f"{c_name} Spread Shot")
                    targets.append(f"{c_name} Focus Shot")
                    for j in range(1, 5): targets.append(f"{c_name} Spell {j}")
                    targets.append(f"{c_name} LastWord")
                self.cbo_target.config(values=targets)
                
            elif "Party" in cat:
                targets = ["Main Stage", "Party Button", "Party Back", "Battle", "Challenge"]
                for i in range(1, self.num_chars_var.get() + 1):
                    c_name = self.char_note_vars[str(i)].get().strip() or f"Slot {i}"
                    targets.append(f"{c_name} Open List")
                    targets.append(f"{c_name} Selected Grid Pos")
                self.cbo_target.config(values=targets)
                
            if self.cbo_target['values']: self.cbo_target.current(0)
            
        elif action == "CHOOSE_DIFFICULTY": 
            self.cbo_target.config(values=["btn_normal.png", "btn_hard.png", "btn_lunatic.png", "btn_boss_lunatic.png"])
            self.cbo_target.set("btn_hard.png") 
        elif action in ["CONFIRM", "CONFIRM_PARTY_SLOT", "END_AREA", "SEPARATOR"]: 
            self.cbo_target.config(values=["None"])
            self.cbo_target.current(0)
        elif action == "BOOST":
            self.cbo_target.config(values=["1", "2", "3"])
            self.cbo_target.current(2)
        elif action == "WAIT":
            self.cbo_target.config(values=["0.5", "1", "1.5", "2", "3", "5", "8", "10", "15"])
            self.cbo_target.current(3)
        elif action == "WAIT_FOR_SCREEN":
            if "Combat" in cat: self.cbo_target.config(values=["BATTLE_SCREEN", "END_BATTLE_SCREEN"])
            elif "Buff" in cat: self.cbo_target.config(values=["BUFF_SCREEN"])
            elif "Party" in cat: self.cbo_target.config(values=["PREPARE_SCREEN", "SELECT_PARTY_SCREEN"])
            else: self.cbo_target.config(values=["BATTLE_SCREEN", "BUFF_SCREEN", "PREPARE_SCREEN", "SELECT_PARTY_SCREEN", "END_BATTLE_SCREEN"])
            self.cbo_target.current(0)
        elif action == "CLICK_SKIP_CORNER":
            self.cbo_target.config(values=["1", "2", "3", "4", "5", "6", "7", "8"])
            self.cbo_target.current(4)
        elif action == "SELECT_BUFF":
            self.cbo_target.config(values=["Strict Tier 1", "Any Tier"])
            self.cbo_target.current(0)
        elif action == "START_AREA":
            self.cbo_target.config(values=["1", "2", "3", "4", "5", "6", "7"])
            self.cbo_target.current(0)

    def apply_listbox_colors(self):
        for i in range(self.listbox.size()):
            text = self.listbox.get(i)
            if "[START_AREA]" in text:
                self.listbox.itemconfig(i, bg="#d9f7be", fg="black") 
            elif "[END_AREA]" in text:
                self.listbox.itemconfig(i, bg="#ffd6e7", fg="black") 
            elif "[SEPARATOR]" in text:
                self.listbox.itemconfig(i, bg="#f0f0f0", fg="#888888") 
            else:
                self.listbox.itemconfig(i, bg="white", fg="black") 

    def auto_format_list(self):
        count = 0
        for i in range(self.listbox.size()):
            text = self.listbox.get(i)
            if any(x in text for x in ["Open Skill", "Close Skill", "Open/Close Skill"]):
                parts = text.split("] -> ")
                if len(parts) == 2 and parts[0] == "[CLICK":
                    new_target = "Open Skill" if count % 2 == 0 else "Close Skill"
                    new_text = f"[CLICK] -> {new_target}"
                    if text != new_text:
                        was_selected = self.listbox.selection_includes(i)
                        self.listbox.delete(i)
                        self.listbox.insert(i, new_text)
                        if was_selected: self.listbox.selection_set(i)
                    count += 1
        self.apply_listbox_colors()

    def add_action(self):
        action = self.cbo_action.get()
        if action == "SEPARATOR":
            self.listbox.insert(tk.END, "[SEPARATOR] -> =============================")
        else:
            self.listbox.insert(tk.END, f"[{action}] -> {self.cbo_target.get()}")
            if action == "END_AREA":
                self.listbox.insert(tk.END, "[SEPARATOR] -> ========== END OF AREA ==========")
        self.auto_format_list()

    def insert_action(self):
        selected = self.listbox.curselection()
        action = self.cbo_action.get()
        idx = selected[0] if selected else tk.END
        
        if action == "SEPARATOR":
            self.listbox.insert(idx, "[SEPARATOR] -> ========== END OF AREA ==========")
        else:
            self.listbox.insert(idx, f"[{action}] -> {self.cbo_target.get()}")
            if action == "END_AREA":
                insert_pos = idx + 1 if idx != tk.END else tk.END
                self.listbox.insert(insert_pos, "[SEPARATOR] -> ========== END OF AREA ==========")
                
        if selected: self.listbox.selection_set(idx)
        self.auto_format_list()

    def update_action(self):
        selected = self.listbox.curselection()
        if not selected: return messagebox.showwarning("Warning", "Please select a line to update!")
        if len(selected) > 1: return messagebox.showwarning("Warning", "You can only update 1 line at a time!")
            
        idx = selected[0]
        action = self.cbo_action.get()
        self.listbox.delete(idx)
        
        if action == "SEPARATOR":
            self.listbox.insert(idx, "[SEPARATOR] -> ========== END OF AREA ==========")
        else:
            self.listbox.insert(idx, f"[{action}] -> {self.cbo_target.get()}")
            
        self.listbox.selection_set(idx)
        self.auto_format_list()

    def copy_action(self):
        selected = self.listbox.curselection()
        if not selected: return
        self.clipboard = [self.listbox.get(i) for i in selected]
        self.root.title(f"Api Moriya Unmapped Auto - V38 (Copied {len(self.clipboard)} lines!)")
        self.root.after(2000, lambda: self.root.title("Api Moriya Unmapped Auto"))

    def paste_action(self):
        if not self.clipboard: 
            return messagebox.showinfo("Paste", "Clipboard is empty! Copy something first.")
            
        selected = self.listbox.curselection()
        insert_idx = selected[-1] + 1 if selected else self.listbox.size()
        
        self.listbox.selection_clear(0, tk.END)
        for text in self.clipboard:
            self.listbox.insert(insert_idx, text)
            self.listbox.selection_set(insert_idx)
            insert_idx += 1
            
        self.auto_format_list()

    def load_selected_to_inputs(self, event):
        selected = self.listbox.curselection()
        if not selected: return
        text = self.listbox.get(selected[0])
        parts = text.split("] -> ")
        if len(parts) != 2: return
        
        act = parts[0].replace("[", "")
        tgt = parts[1]
        
        if tgt in ["Open Skill", "Close Skill"]: tgt = "Open/Close Skill"
        
        cat_index = 0
        if act in ["WAIT", "SEPARATOR", "CONFIRM"]: cat_index = 3
        elif act in ["SELECT_BUFF", "START_AREA", "END_AREA", "CLICK_SKIP_CORNER"]: cat_index = 2
        elif act in ["CHOOSE_DIFFICULTY", "CONFIRM_PARTY_SLOT"]: cat_index = 1
        elif act in ["BOOST"]: cat_index = 0
        elif act == "WAIT_FOR_SCREEN":
            if tgt in ["BATTLE_SCREEN", "END_BATTLE_SCREEN"]: cat_index = 0
            elif tgt in ["PREPARE_SCREEN", "SELECT_PARTY_SCREEN"]: cat_index = 1
            elif tgt == "BUFF_SCREEN": cat_index = 2
        elif act == "CLICK":
            prepare_targets = ["Main Stage", "Party", "Battle", "Challenge", "Slot", "Open List", "Grid Pos"]
            if any(p in tgt for p in prepare_targets): cat_index = 1
            else: cat_index = 0

        self.cbo_category.current(cat_index)
        self.update_action_combobox(None)
        self.cbo_action.set(act)
        self.update_target_combobox(None)
        
        if tgt in self.cbo_target['values'] or act == "SEPARATOR":
            self.cbo_target.set(tgt)

    def delete_action(self):
        selected = self.listbox.curselection()
        if not selected: return
        for i in reversed(selected):
            self.listbox.delete(i)
        self.auto_format_list()

    def move_item(self, direction):
        selected = list(self.listbox.curselection())
        if not selected: return
        
        if direction == -1: 
            if selected[0] == 0: return 
            for i in selected:
                text = self.listbox.get(i)
                self.listbox.delete(i)
                self.listbox.insert(i - 1, text)
                self.listbox.selection_set(i - 1)
        
        elif direction == 1: 
            if selected[-1] == self.listbox.size() - 1: return 
            for i in reversed(selected):
                text = self.listbox.get(i)
                self.listbox.delete(i)
                self.listbox.insert(i + 1, text)
                self.listbox.selection_set(i + 1)
        self.auto_format_list()

    def save_profile(self):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            script_data = [self.listbox.get(i) for i in range(self.listbox.size())]
            for i in range(1, 4):
                if str(i) in self.char_note_vars:
                    self.char_notes[str(i)] = self.char_note_vars[str(i)].get()
                    
            with open(path, 'w', encoding='utf-8') as f: 
                json.dump({
                    "coords": self.coords, 
                    "script": script_data,
                    "char_notes": self.char_notes
                }, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Success", "Profile saved successfully!")

    def load_profile(self):
        path = filedialog.askopenfilename()
        if path:
            with open(path, 'r', encoding='utf-8') as f: 
                data = json.load(f)
                self.coords = data.get("coords", self.coords)
                    
                if "Open/Close Skill" in self.coords:
                    self.coords["Open Skill"] = self.coords["Open/Close Skill"]
                    self.coords["Close Skill"] = self.coords["Open/Close Skill"]
                elif "Open Skill" in self.coords: 
                    self.coords["Open/Close Skill"] = self.coords["Open Skill"]
                    self.coords["Close Skill"] = self.coords["Open Skill"]
                    
                self.char_notes = data.get("char_notes", {"1": "", "2": "", "3": ""})
                for i in range(1, 4):
                    if str(i) in self.char_note_vars:
                        self.char_note_vars[str(i)].set(self.char_notes.get(str(i), ""))
                        
                script_data = data.get("script", [])
                
            self.render_coord_ui() 
            self.listbox.delete(0, tk.END)
            for act in script_data:
                act = act.replace("[CLICK_IMAGE]", "[CHOOSE_DIFFICULTY]")
                act = act.replace("[SKIP_ANIM]", "[CLICK_SKIP_CORNER]")
                self.listbox.insert(tk.END, act)
            self.auto_format_list()

    # ================= AUTO RUN ENGINE =================
    def toggle_bot(self):
        self.is_running = not self.is_running
        if self.is_running:
            self.lbl_status.config(text="Status: RUNNING", foreground="green")
            self.root.iconify()
            self.root.update() 
            
            self.completed_loops = 0
            self.current_area = 1
            self.update_info_label(f"Starting loop: 1")
            
            self.main_script = []
            for i in range(self.listbox.size()):
                parts = self.listbox.get(i).split("] -> ")
                self.main_script.append({"action": parts[0].replace("[", ""), "target": parts[1] if len(parts)>1 else "None"})
                
            threading.Thread(target=self.bot_loop, daemon=True).start()
        else:
            self.lbl_status.config(text="Status: STOPPED", foreground="red")
            self.root.deiconify()
            self.root.state('normal')
            self.root.update()

    def force_stop(self):
        if self.is_running:
            self.is_running = False
            self.lbl_status.config(text="Status: STOPPED", foreground="red")
            self.root.deiconify()
            self.root.state('normal')
            self.root.update() 

    def update_info_label(self, msg):
        self.lbl_info.config(text=msg)

    def click_coord(self, key_name, delay=0.4):
        coord = self.coords.get(key_name)
        if coord and coord["x"] > 0:
            pyautogui.click(x=coord["x"], y=coord["y"])
            time.sleep(delay)
        else:
            print(f"[-] Warning: Coordinates for {key_name} not set or found!")

    def handle_disconnect(self):
        print("[!] Network Error Detected! Reconnecting...")
        self.update_info_label("Network Error! Reconnecting...")
        
        pos = self.vision.get_pos("btn_confirm.png")
        if pos: pyautogui.click(x=pos[0], y=pos[1])
        else: pyautogui.click(x=600, y=450)
        time.sleep(5)

    def wait_for_screen(self, target_screen):
        self.update_info_label(f"Waiting for: {target_screen}...")
        while self.is_running:
            if self.vision.get_pos("btn_confirm.png"): 
                self.handle_disconnect()
                continue
                
            if target_screen == "SELECT_PARTY_SCREEN":
                pos = self.vision.get_pos("btn_cancel.png")
                if pos:
                    print("[+] Party Selection screen detected (Remove button found)!")
                    time.sleep(0.5)
                    return
            
            elif target_screen == "END_BATTLE_SCREEN":
                pos = self.vision.get_pos("btn_next.png")
                if pos:
                    print("[+] Battle End screen detected (Next button found)!")
                    pyautogui.click(x=pos[0], y=pos[1])
                    time.sleep(1.0)
                    
                    
                    for _ in range(3):
                        self.click_coord("Skip Corner", 1.0)
                    return
            else:
                state_map = {"BATTLE_SCREEN": "IN_BATTLE", "BUFF_SCREEN": "BUFF_SELECT", "PREPARE_SCREEN": "PREPARE"}
                mapped_target = state_map.get(target_screen, "UNKNOWN")
                if self.vision.check_state() == mapped_target: 
                    time.sleep(0.5)
                    return
                
            time.sleep(1)

    def click_auto_confirm(self, max_wait=5, target_img="btn_confirm.png"):
        print(f"[*] Looking for {target_img}...")
        start_time = time.time()
        img_path = os.path.join(IMAGE_DIR, target_img)

        while time.time() - start_time < max_wait:
            if not self.is_running: return False
            
            pos = self.vision.get_pos_absolute(img_path)
            if pos:
                pyautogui.click(x=pos[0], y=pos[1])
                print(f"[+] Clicked Confirm: {target_img}")
                time.sleep(1) 
                return True
            time.sleep(0.5)
        print(f"[-] {target_img} not found!")
        return False

    def execute_buff_selection(self, mode="Strict Tier 1"):
        self.update_info_label(f"Scanning Buff (Area {self.current_area})...")
        folder = os.path.join(IMAGE_DIR, f"area_{self.current_area}")
        
        tier1_images = sorted(glob.glob(os.path.join(folder, "tier1", "*.png")))
        all_tier_images = []
        for t in range(1, 6): 
            all_tier_images.extend(sorted(glob.glob(os.path.join(folder, f"tier{t}", "*.png"))))
            
        for attempt in range(4): 
            if not self.is_running: return
            
            if attempt == 3:
                buff_clicked = False
                for img_path in all_tier_images:
                    pos = self.vision.get_pos_absolute(img_path)
                    if pos: 
                        pyautogui.click(x=pos[0], y=pos[1])
                        time.sleep(0.3)
                        buff_clicked = True
                        break 
                
                if not buff_clicked: self.click_coord("Random Buff", 1)
                
                if self.click_auto_confirm(max_wait=3, target_img="btn_confirm.png"):
                    time.sleep(1) 
                return

            buff_clicked = False
            images_to_scan = tier1_images if mode == "Strict Tier 1" else all_tier_images
            
            for img_path in images_to_scan:
                pos = self.vision.get_pos_absolute(img_path)
                if pos: 
                    pyautogui.click(x=pos[0], y=pos[1])
                    time.sleep(0.3) 
                    buff_clicked = True
                    break 
            
            if buff_clicked:
                if self.click_auto_confirm(max_wait=3, target_img="btn_confirm.png"):
                    time.sleep(1) 
                return
            else:
                redraw_pos = self.vision.get_pos("btn_redraw.png")
                if not redraw_pos: redraw_pos = self.vision.get_pos("btn_redraw_dark.png")
                if redraw_pos: pyautogui.click(x=redraw_pos[0], y=redraw_pos[1])
                time.sleep(3)

    def bot_loop(self):
        start_time_limit = time.time()
        max_duration = self.hour_var.get() * 3600 + self.min_var.get() * 60

        while self.is_running:
            run_mode = self.run_mode.get()
            
            if run_mode == "loop" and self.completed_loops >= self.loop_var.get():
                break
            if run_mode == "time" and (time.time() - start_time_limit) >= max_duration:
                break
            
            for act in self.main_script:
                if not self.is_running: break
                
                if self.vision.get_pos("btn_confirm.png"): self.handle_disconnect()
                
                cmd, target = act["action"], act["target"]
                
                if cmd == "SEPARATOR": continue
                
                print(f"Executing: {cmd} -> {target}")
                
                if cmd == "WAIT": time.sleep(float(target))
                
                elif cmd == "CLICK": 
                    mapped_target = "Open Skill" if target in ["Close Skill", "Open/Close Skill"] else target
                    real_target = self.get_real_key(mapped_target)
                    self.click_coord(real_target)
                    
                    if real_target.startswith("Char ") and "Skill" in real_target:
                        print(f"[*] Auto Confirm after using: {target}")
                        time.sleep(1.0) 
                        self.click_auto_confirm(max_wait=4, target_img="btn_confirm.png")
                        
                elif cmd == "CHOOSE_DIFFICULTY": 
                    for _ in range(5): 
                        if not self.is_running: break
                        pos = self.vision.get_pos(target)
                        if pos:
                            pyautogui.click(x=pos[0], y=pos[1])
                            time.sleep(1)
                            break
                        time.sleep(1)
                        
                elif cmd == "CONFIRM":
                    self.click_auto_confirm(target_img="btn_confirm.png") 
                    
                elif cmd == "CONFIRM_PARTY_SLOT":
                    self.click_auto_confirm(target_img="btn_confirm_party.png")
                    
                elif cmd == "BOOST":
                    for _ in range(int(target)): self.click_coord("Boost", 0.2)
                    
                elif cmd == "WAIT_FOR_SCREEN": 
                    self.wait_for_screen(target)
                
                elif cmd == "CLICK_SKIP_CORNER": 
                    for _ in range(int(target)): self.click_coord("Skip Corner", 1)
                    
                elif cmd == "SELECT_BUFF": 
                    self.execute_buff_selection(target)
                    
                elif cmd == "START_AREA":
                    self.current_area = int(target)
                    self.update_info_label(f"Updated to Area {self.current_area}")
                    
                elif cmd == "END_AREA": 
                    self.current_area += 1
                    self.update_info_label(f"Advancing to Area {self.current_area}...")
                    print(f"[*] END_AREA reached. Automatically setting script to Next Area: {self.current_area}")
                    # Lệnh clear rương đã được loại bỏ

            if self.is_running:
                self.completed_loops += 1
                
                if run_mode == "time":
                    elapsed = int(time.time() - start_time_limit)
                    rem = max(0, max_duration - elapsed)
                    m, s = divmod(rem, 60)
                    h, m = divmod(m, 60)
                    self.update_info_label(f"Completed loop: {self.completed_loops} | Time left: {h}h {m}m {s}s")
                elif run_mode == "loop":
                    self.update_info_label(f"Completed loop: {self.completed_loops}/{self.loop_var.get()}")
                else:
                    self.update_info_label(f"Completed loop: {self.completed_loops} (Infinite)")
                
        if self.is_running:
            print("\n[+] Farming Complete!")
            self.toggle_bot()

if __name__ == "__main__":
    if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR, exist_ok=True)
    for i in range(1, 8):
        for t in range(1, 4): 
            folder = os.path.join(IMAGE_DIR, f"area_{i}", f"tier{t}")
            os.makedirs(folder, exist_ok=True)
        
    root = tk.Tk()
    app = DynamicGroupBot(root)
    root.mainloop()