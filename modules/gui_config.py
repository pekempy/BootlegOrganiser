import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import os
from modules.config import config

# --- Dark Palette ---
BG_COLOUR = "#1c1c1e"
CARD_COLOUR = "#2c2c2e"
ACCENT_BLUE = "#0a84ff"
TEXT_COLOUR = "#f5f5f7"
MUTED_TEXT = "#8e8e93"
BORDER_COLOUR = "#3a3a3c"
TAG_BG = "#0a84ff"
PART_TEXT_BG = "#2c2c2e"

class FormatPart:
    def __init__(self, parent, part_type, value, on_change_callback, on_delete_callback, on_focus_callback):
        self.parent = parent
        self.part_type = part_type
        self.value = value
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        self.on_focus = on_focus_callback
        
        self.frame = tk.Frame(parent, bg=CARD_COLOUR)
        self.render()
        
    def render(self):
        for widget in self.frame.winfo_children():
            widget.destroy()
            
        if self.part_type == 'tag':
            tag_frame = tk.Frame(self.frame, bg=TAG_BG)
            tag_frame.pack(side=tk.LEFT, padx=2)
            
            content = self.value.strip('{}').replace('_', ' ').title().replace(' Id', ' ID')
            label = tk.Label(tag_frame, text=content, bg=TAG_BG, fg="white", 
                            font=("Segoe UI", 9, "bold"), pady=4)
            label.pack(side=tk.LEFT, padx=8)
            
            del_btn = tk.Label(tag_frame, text="×", bg=TAG_BG, fg="white", 
                              font=("Segoe UI", 9, "bold"), cursor="hand2", padx=4)
            del_btn.pack(side=tk.LEFT)
            del_btn.bind("<Button-1>", lambda e: self.on_delete(self))
            del_btn.bind("<Enter>", lambda e: del_btn.config(fg="#ff453a")) # Red hover
            del_btn.bind("<Leave>", lambda e: del_btn.config(fg="white"))
        else:
            self.entry_var = tk.StringVar(value=self.value)
            self.entry_var.trace_add("write", lambda *args: self.update_value())
            width = max(2, len(self.value)) if self.value else 2
            self.entry = tk.Entry(self.frame, textvariable=self.entry_var, width=width,
                                font=("Segoe UI", 10), bg=CARD_COLOUR, fg=TEXT_COLOUR,
                                relief="flat", highlightthickness=0, insertbackground=TEXT_COLOUR)
            self.entry.pack(side=tk.LEFT, padx=2, pady=2)
            self.frame.bind("<Button-1>", lambda e: self.entry.focus_set())
            
            self.entry.bind("<FocusIn>", lambda e: [self.entry.config(bg="#3a3a3c"), self.on_focus(self, self.entry)])
            self.entry.bind("<FocusOut>", lambda e: self.entry.config(bg=CARD_COLOUR))
            self.entry_var.trace_add("write", lambda *args: self.entry.configure(width=max(2, len(self.entry_var.get()))))

    def update_value(self):
        # Collapse multiple spaces
        val = self.entry_var.get()
        self.value = re.sub(r' +', ' ', val)
        self.on_change()

class FormatBuilder(tk.Frame):
    def __init__(self, parent, on_change_callback):
        super().__init__(parent, bg=CARD_COLOUR, highlightthickness=1, highlightbackground=BORDER_COLOUR)
        self.on_change = on_change_callback
        self.parts = []
        self.part_widgets = []
        self.container = tk.Frame(self, bg=CARD_COLOUR)
        self.container.pack(fill=tk.X, expand=True, padx=5, pady=2)
        self.active_entry_part = None
        self.active_entry = None

    def set_format(self, fmt):
        self.parts = []
        if fmt:
            pattern = r'(\{.*?\})'
            tokens = re.split(pattern, fmt)
            for token in tokens:
                if not token: continue
                if token.startswith('{') and token.endswith('}'):
                    self.parts.append({'type': 'tag', 'value': token})
                else:
                    self.parts.append({'type': 'text', 'value': token})
        self._ensure_wrapping_text()
        self.render_parts()
    def _ensure_wrapping_text(self):
        self.update_state()
        
        # 1. Merge adjacent text parts and remove empty ones between text
        merged_parts = []
        for p in self.parts:
            if not merged_parts:
                merged_parts.append(p)
            else:
                last = merged_parts[-1]
                if last['type'] == 'text' and p['type'] == 'text':
                    last['value'] += p['value']
                else:
                    merged_parts.append(p)
        
        # 2. Enforce space between tags and ensure text wrappers
        final = []
        if not merged_parts or merged_parts[0]['type'] == 'tag':
            final.append({'type': 'text', 'value': ''})
            
        for i, p in enumerate(merged_parts):
            final.append(p)
            if p['type'] == 'tag':
                # Check if next is a tag or the end
                if i == len(merged_parts) - 1:
                    final.append({'type': 'text', 'value': ''})
                elif merged_parts[i+1]['type'] == 'tag':
                    # Forced space between tags
                    final.append({'type': 'text', 'value': ' '})
                elif merged_parts[i+1]['type'] == 'text':
                    # If it's a text part, ensure it has content or it's forced to a space if between tags
                    text_val = merged_parts[i+1]['value']
                    if not text_val and i+1 < len(merged_parts)-1 and merged_parts[i+2]['type'] == 'tag':
                         merged_parts[i+1]['value'] = ' '
        
        self.parts = final


    def render_parts(self):
        for widget in self.container.winfo_children():
            widget.destroy()
        self.part_widgets = []
        
        for part in self.parts:
            pw = FormatPart(self.container, part['type'], part['value'], 
                           self.on_part_change, self.on_part_delete, self.on_part_focus)
            pw.frame.pack(side=tk.LEFT)
            self.part_widgets.append(pw)

    def on_part_focus(self, part_widget, entry_widget):
        self.active_idx = self.part_widgets.index(part_widget)
        self.active_entry = entry_widget

    def add_tag(self, tag):
        self.update_state()
        idx = getattr(self, 'active_idx', -1)
        
        if idx != -1 and idx < len(self.part_widgets):
            entry = self.part_widgets[idx].entry
            cursor_pos = entry.index(tk.INSERT)
            val = self.parts[idx]['value']
            left = val[:cursor_pos]
            right = val[cursor_pos:]
            
            # Replace text part with: [left, tag, right]
            self.parts[idx:idx+1] = [
                {'type': 'text', 'value': left},
                {'type': 'tag', 'value': f"{{{tag}}}"},
                {'type': 'text', 'value': right}
            ]
        else:
            self.parts.append({'type': 'tag', 'value': f"{{{tag}}}"})
            
        self._ensure_wrapping_text()
        self.render_parts()
        
        if idx != -1:
            for i in range(idx + 1, len(self.part_widgets)):
                if self.part_widgets[i].part_type == 'text':
                    self.part_widgets[i].entry.focus_set()
                    self.part_widgets[i].entry.icursor(0)
                    break
        self.on_change()
        
    def on_part_change(self):
        self.update_state()
        self.on_change()

    def on_part_delete(self, p_widget):
        idx = self.part_widgets.index(p_widget)
        self.update_state()
        self.parts.pop(idx)
        self.part_widgets.pop(idx) # Match lengths to avoid IndexError
        self._ensure_wrapping_text()
        self.render_parts()
        
        if idx != -1:
            for i in range(idx + 1, len(self.part_widgets)):
                if self.part_widgets[i].part_type == 'text':
                    self.part_widgets[i].entry.focus_set()
                    self.part_widgets[i].entry.icursor(0)
                    break
                    
        self.on_change()
    def update_state(self):
        for i, pw in enumerate(self.part_widgets):
            self.parts[i]['value'] = pw.value

    def get_format(self, escape_braces=False):
        res = ""
        for p in self.parts:
            val = p['value']
            if escape_braces and p['type'] == 'text':
                val = val.replace('{', '{{').replace('}', '}}')
            res += val
        # Final safety cleanup to prevent multiple spaces in the pattern
        return re.sub(r' +', ' ', res)

class ConfigGUI:
    def __init__(self, root, on_run_callback):
        self.root = root
        self.root.title("Bootleg Organiser")
        self.root.geometry("900x850")
        self.root.minsize(850, 800)
        self.root.configure(bg=BG_COLOUR)
        self.on_run_callback = on_run_callback
        
        self.setup_ui()
        self.load_config()
    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground=BG_COLOUR, background=BG_COLOUR, foreground=TEXT_COLOUR, arrowcolor=TEXT_COLOUR)
        style.map('TCombobox', 
                  fieldbackground=[('readonly', BG_COLOUR), ('focus', BG_COLOUR)], 
                  background=[('readonly', BG_COLOUR)],
                  selectbackground=[('readonly', BG_COLOUR)], 
                  selectforeground=[('readonly', TEXT_COLOUR)])
        
        # Dark Notebook Styling
        style.configure("TNotebook", background=BG_COLOUR, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD_COLOUR, foreground=TEXT_COLOUR, padding=[15, 5])
        style.map("TNotebook.Tab", background=[("selected", ACCENT_BLUE)], foreground=[("selected", "white")])

        # Fix for dropdown background
        self.root.option_add("*TCombobox*Listbox.background", BG_COLOUR)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT_COLOUR)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_BLUE)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")

        content = tk.Frame(self.root, bg=BG_COLOUR, padx=15, pady=5)
        content.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(content, bg=BG_COLOUR)
        header.pack(fill=tk.X, pady=(5, 10))
        tk.Label(header, text="Organiser Setup", font=("Segoe UI", 16, "bold"), bg=BG_COLOUR, fg=TEXT_COLOUR).pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tabs
        tab_api = tk.Frame(self.notebook, bg=BG_COLOUR, padx=15, pady=15)
        tab_dir = tk.Frame(self.notebook, bg=BG_COLOUR, padx=15, pady=15)
        tab_excl = tk.Frame(self.notebook, bg=BG_COLOUR, padx=15, pady=15)

        self.notebook.add(tab_api, text="API & Options")
        self.notebook.add(tab_dir, text="Directory Settings")
        self.notebook.add(tab_excl, text="Exclusion Rules")

        self.tab_dir = tab_dir
        self.tab_excl = tab_excl

        # --- Tab 1: API & Options ---
        api_card = tk.Frame(tab_api, bg=CARD_COLOUR, padx=15, pady=15, highlightthickness=1, highlightbackground=BORDER_COLOUR)
        api_card.pack(fill=tk.X)
        self.create_label(api_card, "Authentication", ("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 15))
        
        row_key = tk.Frame(api_card, bg=CARD_COLOUR)
        row_key.pack(fill=tk.X)
        self.create_label(row_key, "Encora API Key", bg=CARD_COLOUR).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar()
        tk.Entry(row_key, textvariable=self.api_key_var, font=("Segoe UI", 10), relief="flat", 
                 bg=BG_COLOUR, fg=TEXT_COLOUR, insertbackground=TEXT_COLOUR,
                 highlightthickness=1, highlightbackground=BORDER_COLOUR).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        opt_frame = tk.Frame(tab_api, bg=CARD_COLOUR, padx=15, pady=15, highlightthickness=1, highlightbackground=BORDER_COLOUR)
        opt_frame.pack(fill=tk.X, pady=15)
        self.create_label(opt_frame, "General Options", ("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        self.cast_files_var = tk.BooleanVar()
        self.encora_id_files_var = tk.BooleanVar()
        self.redownload_subs_var = tk.BooleanVar()
        
        for text, var in [("Generate Cast Files", self.cast_files_var), 
                         ("Generate ID Files", self.encora_id_files_var),
                         ("Always Redownload Subtitles", self.redownload_subs_var)]:
            tk.Checkbutton(opt_frame, text=text, variable=var, bg=CARD_COLOUR, fg=TEXT_COLOUR, 
                          selectcolor=ACCENT_BLUE, activebackground=CARD_COLOUR, activeforeground=TEXT_COLOUR,
                          font=("Segoe UI", 9)).pack(anchor=tk.W, pady=2)
        # --- Tab 2: Directory Settings ---
        self.create_label(tab_dir, "Main Directory", ("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))
        row_dir = tk.Frame(tab_dir, bg=BG_COLOUR)
        row_dir.pack(fill=tk.X, pady=(0, 20))
        self.main_dir_var = tk.StringVar()
        self.main_dir_var.trace_add("write", lambda *args: self.update_previews())
        tk.Entry(row_dir, textvariable=self.main_dir_var, font=("Segoe UI", 10), relief="flat", 
                 bg=CARD_COLOUR, fg=TEXT_COLOUR, insertbackground=TEXT_COLOUR,
                 highlightthickness=1, highlightbackground=BORDER_COLOUR).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        tk.Button(row_dir, text="Browse", command=self.browse_directory, bg="#48484a", fg="white", relief="flat", padx=10, pady=4).pack(side=tk.RIGHT)

        format_card = tk.Frame(tab_dir, bg=CARD_COLOUR, padx=15, pady=15, highlightthickness=1, highlightbackground=BORDER_COLOUR)
        format_card.pack(fill=tk.BOTH, expand=True)
        self.create_label(format_card, "Naming & Path Structure", ("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))

        # Containers row
        cont_frame = tk.Frame(format_card, bg=CARD_COLOUR)
        cont_frame.pack(fill=tk.X, pady=5)
        containers_list = ["None", "Brackets []", "Parenthesis ()", "Curly Brackets {}"]
        self.date_cont_var = tk.StringVar()
        self.nft_cont_var = tk.StringVar()
        self.matinee_cont_var = tk.StringVar()
        self.amount_cont_var = tk.StringVar()
        self.id_cont_var = tk.StringVar()
        self.date_replace_char_var = tk.StringVar(value="0")
        self.date_replace_char_var.trace_add("write", lambda *args: self.update_previews())

        def add_cont_cb(parent, lbl, var):
            f = tk.Frame(parent, bg=CARD_COLOUR)
            f.pack(side=tk.LEFT, padx=5)
            tk.Label(f, text=lbl, bg=CARD_COLOUR, font=("Segoe UI", 8, "bold"), fg=MUTED_TEXT).pack(anchor=tk.W)
            cb = ttk.Combobox(f, textvariable=var, values=containers_list, width=12, state="readonly")
            cb.pack()
            cb.bind("<<ComboboxSelected>>", lambda e: self.update_previews())

        for l, v in [("Date", self.date_cont_var), ("NFT", self.nft_cont_var), ("Matinee", self.matinee_cont_var), 
                    ("Amount", self.amount_cont_var), ("ID", self.id_cont_var)]:
            add_cont_cb(cont_frame, l, v)

        # Date Placeholder Char
        dp_frame = tk.Frame(format_card, bg=CARD_COLOUR)
        dp_frame.pack(fill=tk.X, pady=(5, 10))
        self.create_label(dp_frame, "Date Unknown Placeholder:", bg=CARD_COLOUR, font=("Segoe UI", 8, "bold"), fg=MUTED_TEXT).pack(side=tk.LEFT)
        tk.Entry(dp_frame, textvariable=self.date_replace_char_var, width=3, font=("Consolas", 9),
                 bg=BG_COLOUR, fg=TEXT_COLOUR, relief="flat", insertbackground=TEXT_COLOUR,
                 highlightthickness=1, highlightbackground=BORDER_COLOUR).pack(side=tk.LEFT, padx=10)

        # Builders
        def create_builder_section(parent, title, preview_attr_name):
            self.create_label(parent, title, bg=CARD_COLOUR, font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(10, 5))
            builder = FormatBuilder(parent, self.update_previews)
            
            # Tray
            t = tk.Frame(parent, bg=CARD_COLOUR)
            t.pack(fill=tk.X, pady=2)
            tags = [("Show", "show_name"), ("Tour", "tour"), ("Date", "date"), 
                    ("Matinee", "matinee"), ("HL", "highlights"), ("NFT", "nft"),
                    ("ID", "encora_id"), ("Type", "type"), ("S-Type", "short_type"), ("Master", "master")]
            if title == "Structure Pattern":
                tags.append(("Folder", "folder"))
            for lbl, tag_val in tags:
                def make_cmd(b=builder, tv=tag_val): return lambda: b.add_tag(tv)
                tk.Button(t, text=lbl, bg=BG_COLOUR, fg=TEXT_COLOUR, relief="flat", padx=6, pady=2, 
                         font=("Segoe UI", 8), cursor="hand2", command=make_cmd(),
                         highlightthickness=0, activebackground=BORDER_COLOUR, activeforeground=TEXT_COLOUR).pack(side=tk.LEFT, padx=1)
            
            builder.pack(fill=tk.X, pady=5)
            builder.bind("<FocusIn>", lambda e: self.set_active_builder(builder))
            
            p_lbl = tk.Label(parent, text="", bg=CARD_COLOUR, fg=MUTED_TEXT, font=("Consolas", 9), anchor=tk.W)
            p_lbl.pack(fill=tk.X, pady=(0, 10))
            setattr(self, preview_attr_name, p_lbl)
            return builder

        self.folder_builder = create_builder_section(format_card, "Folder Pattern", "folder_preview")
        self.dir_builder = create_builder_section(format_card, "Structure Pattern", "dir_preview")

        # --- Final Path Preview ---
        final_frame = tk.Frame(tab_dir, bg=BG_COLOUR, pady=10)
        final_frame.pack(fill=tk.X)
        self.create_label(final_frame, "FINAL OUTPUT PATH", bg=BG_COLOUR, font=("Segoe UI", 9, "bold"), fg=MUTED_TEXT).pack(anchor=tk.W)
        self.final_preview = tk.Label(final_frame, text="", bg=BG_COLOUR, fg=ACCENT_BLUE, font=("Consolas", 10, "bold"), anchor=tk.W, justify=tk.LEFT)
        self.final_preview.pack(fill=tk.X, pady=5)
        
        # Add dynamic wrapping
        def _on_wrap_resize(event):
            self.final_preview.config(wraplength=event.width - 20)
        final_frame.bind("<Configure>", _on_wrap_resize)

        # --- Tab 3: Exclusions ---
        excl_card = tk.Frame(tab_excl, bg=CARD_COLOUR, padx=15, pady=15, highlightthickness=1, highlightbackground=BORDER_COLOUR)
        excl_card.pack(fill=tk.X)
        self.create_label(excl_card, "Exclusion Rules", ("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 15))
        
        self.create_label(excl_card, "Excluded IDs (comma separated)", bg=CARD_COLOUR).pack(anchor=tk.W)
        self.excluded_ids_var = tk.StringVar()
        tk.Entry(excl_card, textvariable=self.excluded_ids_var, font=("Segoe UI", 10), relief="flat", 
                 bg=BG_COLOUR, fg=TEXT_COLOUR, insertbackground=TEXT_COLOUR,
                 highlightthickness=1, highlightbackground=BORDER_COLOUR).pack(fill=tk.X, pady=10)

        excl_opt = tk.Frame(excl_card, bg=CARD_COLOUR)
        excl_opt.pack(fill=tk.X, pady=10)
        self.excl_format_var = tk.BooleanVar()
        self.excl_cast_var = tk.BooleanVar()
        tk.Checkbutton(excl_opt, text="Skip Format Update", variable=self.excl_format_var, bg=CARD_COLOUR, fg=TEXT_COLOUR,
                       selectcolor=ACCENT_BLUE, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 15))
        tk.Checkbutton(excl_opt, text="Skip Cast.txt", variable=self.excl_cast_var, bg=CARD_COLOUR, fg=TEXT_COLOUR,
                       selectcolor=ACCENT_BLUE, font=("Segoe UI", 9)).pack(side=tk.LEFT)

        # --- Footer ---
        footer = tk.Frame(content, bg=BG_COLOUR)
        footer.pack(fill=tk.X, pady=15)
        
        tk.Button(footer, text="Run Organiser", bg=ACCENT_BLUE, fg="white", relief="flat", 
                  padx=20, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2", command=self.run_now,
                  highlightthickness=0, activebackground="#0071e3", activeforeground="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(footer, text="Save Settings", bg="#48484a", fg="white", relief="flat", 
                  padx=15, pady=8, font=("Segoe UI", 10), cursor="hand2", command=self.save_config,
                  highlightthickness=0, activebackground="#5a5a5c", activeforeground="white").pack(side=tk.RIGHT)

    def create_label(self, parent, text, font=("Segoe UI", 10), bg=None, fg=None):
        return tk.Label(parent, text=text, font=font, bg=bg or parent.cget('bg'), fg=fg or TEXT_COLOUR)

    def set_active_builder(self, builder):
        self.active_builder = builder
        if hasattr(self, 'folder_builder'):
            self.folder_builder.config(highlightbackground=BORDER_COLOUR, highlightthickness=1)
        if hasattr(self, 'dir_builder'):
            self.dir_builder.config(highlightbackground=BORDER_COLOUR, highlightthickness=1)
        builder.config(highlightbackground=ACCENT_BLUE, highlightthickness=2)

    def add_tag_to_active(self, tag):
        self.active_builder.add_tag(tag)

    def update_previews(self):
        def wrap(val, container):
            if not val or container == 'None': return val
            if container == 'Brackets []': return f"[{val}]"
            if container == 'Parenthesis ()': return f"({val})"
            if container == 'Curly Brackets {}': return f"{{{val}}}"
            return val

        # Use the replacement char in the dummy date
        char = self.date_replace_char_var.get() or "0"
        dummy_date = f"2016-12-{char}{char} (4)"
        
        dummy = {
            'show_name': 'Murder Ballad',
            'tour': 'West End',
            'date': wrap(dummy_date, self.date_cont_var.get()),
            'highlights': wrap('hl', self.amount_cont_var.get()),
            'matinee': wrap('m', self.matinee_cont_var.get()),
            'nft': wrap('NFT-2026-09-24', self.nft_cont_var.get()),
            'master': 'TroubledMind',
            'encora_id': wrap('e-123456', self.id_cont_var.get()),
            'type': 'Video',
            'short_type': 'V'
        }
        
        def fmt(f_str):
            try:
                # Use escaped format to allow literal braces
                r = f_str.format(**dummy)
                # Only clean up empty groupings, don't be too aggressive with strip()
                r = r.replace('[]', '').replace('()', '').replace('{}', '')
                return re.sub(r' +', ' ', r).strip()
            except Exception as e:
                return "..."

        f_res = fmt(self.folder_builder.get_format(escape_braces=True))
        d_raw = self.dir_builder.get_format(escape_braces=True)
        
        # If {folder} is in structure, replace it. Otherwise, append folder to path.
        if '{folder}' in d_raw:
            d_res = fmt(d_raw.replace('{folder}', f_res))
            full_path = os.path.join(self.main_dir_var.get(), d_res)
        else:
            d_res = fmt(d_raw)
            full_path = os.path.join(self.main_dir_var.get(), d_res, f_res)
        
        self.folder_preview.config(text=f"Result: {f_res}")
        self.dir_preview.config(text=f"Path: {fmt(d_raw).replace('{folder}', '[Folder]')}")
        
        self.final_preview.config(text=full_path)

    def browse_directory(self):
        d = filedialog.askdirectory()
        if d: self.main_dir_var.set(d)

    def load_config(self):
        self.api_key_var.set(config.api_key or "")
        self.main_dir_var.set(config.main_directory or "")
        self.cast_files_var.set(config.generate_cast_files)
        self.encora_id_files_var.set(config.generate_encoraid_files)
        self.redownload_subs_var.set(config.redownload_subtitles)
        self.folder_builder.set_format(config.show_folder_format)
        self.dir_builder.set_format(config.show_directory_format)
        self.excluded_ids_var.set(", ".join(config.excluded_ids))
        self.excl_format_var.set(config.exclude_format_update)
        self.excl_cast_var.set(config.exclude_cast_files)
        
        self.date_cont_var.set(config.date_container)
        self.nft_cont_var.set(config.nft_container)
        self.matinee_cont_var.set(config.matinee_container)
        self.amount_cont_var.set(config.amount_container)
        self.id_cont_var.set(config.encora_id_container)
        self.date_replace_char_var.set(config.date_replace_char)
        
        self.update_previews()

    def save_config(self, msg=True):
        config.set('ENCORA_API_KEY', self.api_key_var.get())
        config.set('BOOTLEG_MAIN_DIRECTORY', self.main_dir_var.get())
        config.set('GENERATE_CAST_FILES', str(self.cast_files_var.get()).lower())
        config.set('GENERATE_ENCORAID_FILES', str(self.encora_id_files_var.get()).lower())
        config.set('REDOWNLOAD_SUBTITLES', str(self.redownload_subs_var.get()).lower())
        config.set('SHOW_FOLDER_FORMAT', self.folder_builder.get_format())
        config.set('SHOW_DIRECTORY_FORMAT', self.dir_builder.get_format())
        config.set('EXCLUDED_IDS', self.excluded_ids_var.get())
        config.set('EXCLUDE_FORMAT_UPDATE', str(self.excl_format_var.get()).lower())
        config.set('EXCLUDE_CAST_FILES', str(self.excl_cast_var.get()).lower())
        
        config.set('DATE_CONTAINER', self.date_cont_var.get())
        config.set('NFT_CONTAINER', self.nft_cont_var.get())
        config.set('MATINEE_CONTAINER', self.matinee_cont_var.get())
        config.set('AMOUNT_CONTAINER', self.amount_cont_var.get())
        config.set('ENCORA_ID_CONTAINER', self.id_cont_var.get())
        config.set('DATE_REPLACE_CHAR', self.date_replace_char_var.get())
        if msg: messagebox.showinfo("Saved", "Settings updated!")
        return True

    def run_now(self):
        if self.save_config(False):
            self.root.destroy()
            self.on_run_callback()

def start_gui(on_run_callback):
    root = tk.Tk()
    ConfigGUI(root, on_run_callback)
    root.mainloop()
