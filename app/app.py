from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

from agilize_batch import AgilizeSession
from batch import GrupoLancamento, agrupar_documentos
from browsers import labels_para_combo, label_para_preferencia
from config import APP_HOME, LOG_DIR
from credentials import carregar_credenciais, remover_credenciais, salvar_credenciais, salvar_navegador
from resources import apply_window_icon
from updater import (
    STATE_CHECK_FAILED,
    STATE_OFFLINE,
    STATE_NO_RELEASE,
    STATE_RATE_LIMITED,
    STATE_RELEASE_PENDING,
    STATE_REPOSITORY_UNAVAILABLE,
    STATE_UPDATED,
    STATE_UPDATE_AVAILABLE,
    aguardar_instalador,
    baixar_instalador,
    iniciar_instalador,
    verificar_atualizacao,
)
from tipos_agilize import TIPOS, label_tipo
from version import GITHUB_URL, __version__


class SlimScrollbar(tk.Canvas):
    """Scrollbar vertical minimalista, sem setas e com thumb fino."""

    def __init__(self, master, command, *, width=8, bg="#F5F7FA", thumb="#B8C4CF", active="#8796A5"):
        super().__init__(master, width=width, highlightthickness=0, bd=0, bg=bg, cursor="arrow")
        self.command = command
        self.thumb_color = thumb
        self.active_color = active
        self.first = 0.0
        self.last = 1.0
        self._drag_y = 0
        self._drag_first = 0.0
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Enter>", lambda _e: self._draw(active=True))
        self.bind("<Leave>", lambda _e: self._draw(active=False))

    def set(self, first, last):
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        self._draw()

    def _thumb_bounds(self):
        h = max(1, self.winfo_height())
        if self.first <= 0 and self.last >= 1:
            return 0, 0
        top = int(self.first * h)
        bottom = int(self.last * h)
        min_size = 30
        if bottom - top < min_size:
            bottom = min(h, top + min_size)
            top = max(0, bottom - min_size)
        return top, bottom

    def _draw(self, active=False):
        self.delete("all")
        top, bottom = self._thumb_bounds()
        if bottom <= top:
            return
        w = self.winfo_width()
        color = self.active_color if active else self.thumb_color
        self.create_rectangle(2, top + 2, max(3, w - 2), bottom - 2, fill=color, outline="")

    def _press(self, event):
        top, bottom = self._thumb_bounds()
        if top <= event.y <= bottom:
            self._drag_y = event.y
            self._drag_first = self.first
        else:
            h = max(1, self.winfo_height())
            fraction = max(0.0, min(1.0, event.y / h - (self.last - self.first) / 2))
            self.command("moveto", fraction)
            self._drag_y = event.y
            self._drag_first = fraction

    def _drag(self, event):
        h = max(1, self.winfo_height())
        delta = (event.y - self._drag_y) / h
        max_first = max(0.0, 1.0 - (self.last - self.first))
        target = max(0.0, min(max_first, self._drag_first + delta))
        self.command("moveto", target)


class App(TkinterDnD.Tk):
    BG = "#F3F6F9"
    SURFACE = "#FFFFFF"
    SURFACE_ALT = "#F8FAFC"
    NAVY = "#123247"
    NAVY_2 = "#173F57"
    TEXT = "#172433"
    MUTED = "#6C7A89"
    BORDER = "#DEE6EC"
    PRIMARY = "#14805F"
    PRIMARY_DARK = "#0E664B"
    PRIMARY_SOFT = "#EAF7F2"
    SUCCESS = "#14805F"
    WARNING = "#A66A13"
    DANGER = "#B44242"
    DROP_BG = "#F1FAF6"
    DROP_BORDER = "#8BCDB2"

    def __init__(self):
        super().__init__()
        self.title("Automação Agilize")
        apply_window_icon(self)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        largura = min(1080, max(900, screen_w - 100))
        altura = min(760, max(620, screen_h - 105))
        x = max(0, (screen_w - largura) // 2)
        y = max(0, (screen_h - altura) // 2 - 8)
        self.geometry(f"{largura}x{altura}+{x}+{y}")
        self.minsize(860, 600)
        self.configure(bg=self.BG)

        self.pdfs: list[Path] = []
        self.grupos: list[GrupoLancamento] = []
        self.grupos_by_key: dict[str, GrupoLancamento] = {}
        self.tipo_preferido_var = tk.StringVar(value="auto")
        self.tipo_buttons: dict[str, tk.Button] = {}
        self._browser_jobs: queue.Queue = queue.Queue()
        self._browser_thread = threading.Thread(target=self._browser_loop, daemon=True)
        self._browser_thread.start()
        self.details_visible = False
        self.current_page = "lancamento"
        self.update_info = None
        self._startup_update_prompted = False

        creds = carregar_credenciais()
        self.email_var = tk.StringVar(value=creds.email)
        self.senha_var = tk.StringVar(value=creds.senha)
        self.login_auto_var = tk.BooleanVar(value=creds.login_automatico)
        self.browser_labels, self.browser_map = labels_para_combo()
        self.browser_var = tk.StringVar(value=label_para_preferencia(creds.navegador))
        if self.browser_var.get() not in self.browser_labels:
            self.browser_var.set(self.browser_labels[0])

        self.status_docs = tk.StringVar(value="Arraste os PDFs aqui")
        self.status_execucao = tk.StringVar(value="Aguardando documentos")
        self.anexo_status_var = tk.StringVar(value="Os PDFs serão agrupados automaticamente pela referência do documento")
        self.queue_summary_var = tk.StringVar(value="Nenhum lançamento identificado")
        self.update_status_var = tk.StringVar(
            value=f"Versão instalada: v{__version__} · atualização ainda não verificada."
        )
        self.update_detail_var = tk.StringVar(
            value="A verificação automática acontece alguns segundos após abrir o aplicativo."
        )
        self.update_latest_var = tk.StringVar(value=f"v{__version__}")

        self._configure_style()
        self._build()
        self._sync_document_state()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(1800, lambda: self._verificar_atualizacao(silencioso=True))

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(20, 11), borderwidth=0)
        style.map(
            "Accent.TButton",
            background=[("active", self.PRIMARY_DARK), ("disabled", "#ADC9BE"), ("!disabled", self.PRIMARY)],
            foreground=[("disabled", "#F7F9F8"), ("!disabled", "#FFFFFF")],
        )
        style.configure("Secondary.TButton", font=("Segoe UI Semibold", 9), padding=(13, 8))
        style.configure("Ghost.TButton", font=("Segoe UI", 9), padding=(6, 4), borderwidth=0)
        style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor="#E6EDF2",
            background=self.PRIMARY,
            bordercolor="#E6EDF2",
            lightcolor=self.PRIMARY,
            darkcolor=self.PRIMARY,
            thickness=6,
        )
        style.configure("TEntry", padding=8, fieldbackground="#FBFCFD")
        style.configure("TCombobox", padding=7, fieldbackground="#FBFCFD")
        style.configure("TCheckbutton", background=self.SURFACE, foreground=self.TEXT, font=("Segoe UI", 9))

    def _build(self):
        self._build_header()
        self._build_navigation()

        content = tk.Frame(self, bg=self.BG)
        content.pack(fill="both", expand=True, padx=20, pady=(12, 14))

        self.page_lancamento = tk.Frame(content, bg=self.BG)
        self.page_config = tk.Frame(content, bg=self.BG)
        self.page_updates = tk.Frame(content, bg=self.BG)
        for frame in (self.page_lancamento, self.page_config, self.page_updates):
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_lancamento(self._scrollable_page(self.page_lancamento))
        self._build_configuracoes(self._scrollable_page(self.page_config))
        self._build_atualizacoes(self._scrollable_page(self.page_updates))
        self._show_page("lancamento")

    def _build_header(self):
        header = tk.Frame(self, bg=self.NAVY, height=68)
        header.pack(fill="x")
        header.pack_propagate(False)
        inner = tk.Frame(header, bg=self.NAVY)
        inner.pack(fill="both", expand=True, padx=22, pady=10)

        logo = tk.Frame(inner, bg=self.PRIMARY, width=42, height=42)
        logo.pack(side="left", padx=(0, 12))
        logo.pack_propagate(False)
        tk.Label(logo, text="A", bg=self.PRIMARY, fg="white", font=("Segoe UI Semibold", 18)).pack(expand=True)

        brand = tk.Frame(inner, bg=self.NAVY)
        brand.pack(side="left", fill="y")
        tk.Label(brand, text="Automação Agilize", bg=self.NAVY, fg="white", font=("Segoe UI Semibold", 18)).pack(anchor="w")
        tk.Label(brand, text="Preenchimento assistido de notas no Agilize", bg=self.NAVY, fg="#BFD0DB", font=("Segoe UI", 8)).pack(anchor="w")

        badge = tk.Label(inner, text="ENVIO SEMPRE MANUAL", bg=self.NAVY_2, fg="#D1EEE2", font=("Segoe UI Semibold", 8), padx=12, pady=6)
        badge.pack(side="right", anchor="center")

    def _build_navigation(self):
        nav = tk.Frame(self, bg=self.SURFACE, height=46, highlightthickness=1, highlightbackground=self.BORDER)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        inner = tk.Frame(nav, bg=self.SURFACE)
        inner.pack(fill="both", expand=True, padx=20, pady=6)

        self.nav_lancamento = self._nav_button(inner, "Lançamento", lambda: self._show_page("lancamento"))
        self.nav_config = self._nav_button(inner, "Configurações", lambda: self._show_page("configuracoes"))
        self.nav_updates = self._nav_button(inner, "Atualizações", lambda: self._show_page("atualizacoes"))
        for idx, btn in enumerate((self.nav_lancamento, self.nav_config, self.nav_updates)):
            btn.pack(side="left", padx=(0 if idx == 0 else 6, 0))

    def _nav_button(self, parent, text, command):
        return tk.Button(
            parent, text=text, command=command, relief="flat", bd=0,
            bg=self.SURFACE, activebackground=self.PRIMARY_SOFT,
            fg=self.MUTED, activeforeground=self.PRIMARY_DARK,
            font=("Segoe UI Semibold", 9), padx=16, pady=7, cursor="hand2",
        )

    def _show_page(self, page: str):
        self.current_page = page
        pages = {
            "lancamento": (self.page_lancamento, self.nav_lancamento),
            "configuracoes": (self.page_config, self.nav_config),
            "atualizacoes": (self.page_updates, self.nav_updates),
        }
        frame, active = pages.get(page, pages["lancamento"])
        frame.lift()
        for btn in (self.nav_lancamento, self.nav_config, self.nav_updates):
            btn.configure(bg=self.PRIMARY_SOFT if btn is active else self.SURFACE, fg=self.PRIMARY_DARK if btn is active else self.MUTED)

    def _card(self, parent, padx=20, pady=17):
        frame = tk.Frame(parent, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER)
        inner = tk.Frame(frame, bg=self.SURFACE)
        inner.pack(fill="both", expand=True, padx=padx, pady=pady)
        return frame, inner

    def _scrollable_page(self, parent):
        outer = tk.Frame(parent, bg=self.BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=self.BG, highlightthickness=0, bd=0)
        scroll = SlimScrollbar(outer, canvas.yview, width=8, bg=self.BG)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y", padx=(4, 0))

        inner = tk.Frame(canvas, bg=self.BG)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))

        def wheel(event):
            if getattr(event, "delta", 0):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        return inner

    def _build_lancamento(self, parent):
        parent.grid_columnconfigure(0, weight=1)

        intro = tk.Frame(parent, bg=self.BG)
        intro.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tk.Label(intro, text="Fila de lançamentos", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 17)).pack(anchor="w")
        tk.Label(
            intro,
            text="Adicione quantos PDFs precisar. A automação relaciona nota e boleto pela referência do documento e prepara cada lançamento separadamente.",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9), wraplength=900, justify="left"
        ).pack(anchor="w", pady=(2, 0))

        self.update_banner = tk.Frame(parent, bg="#FFF7E8", highlightthickness=1, highlightbackground="#EBCB8C")
        self.update_banner.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.update_banner.grid_columnconfigure(0, weight=1)
        self.update_banner_text = tk.Label(
            self.update_banner, text="", bg="#FFF7E8", fg="#7A4B05",
            font=("Segoe UI Semibold", 9), anchor="w", justify="left"
        )
        self.update_banner_text.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=9)
        ttk.Button(
            self.update_banner, text="Ver atualização", style="Secondary.TButton",
            command=lambda: self._show_page("atualizacoes")
        ).grid(row=0, column=1, padx=(0, 10), pady=6)
        self.update_banner.grid_remove()

        # Mesmos módulos exibidos no menu do Agilize. A seleção define onde o sistema
        # procura a referência primeiro; se não encontrar, pesquisa automaticamente nos demais.
        ref_card, ref_body = self._card(parent, padx=16, pady=12)
        ref_card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        tk.Label(ref_body, text="Pesquisa de histórico", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI Semibold", 10)).pack(anchor="w")
        tk.Label(
            ref_body,
            text="Escolha onde procurar primeiro pelo CNPJ. Se não houver registro, a busca continua nas outras áreas do Agilize.",
            bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 8), wraplength=900, justify="left"
        ).pack(anchor="w", pady=(2, 8))
        tipos_line = tk.Frame(ref_body, bg=self.SURFACE)
        tipos_line.pack(fill="x")
        opcoes = [
            ("auto", "Automático"),
            ("nfse", "Notas NFS-E"),
            ("documentos", "Doc. - Contas a pagar"),
        ]
        for idx, (key, label) in enumerate(opcoes):
            btn = tk.Button(
                tipos_line, text=label, relief="flat", bd=0, cursor="hand2",
                font=("Segoe UI Semibold", 8), padx=11, pady=8,
                command=lambda k=key: self._set_tipo_preferido(k)
            )
            btn.pack(side="left", padx=(0 if idx == 0 else 5, 0))
            self.tipo_buttons[key] = btn
        self._refresh_tipo_buttons()

        card, body = self._card(parent, padx=20, pady=15)
        card.grid(row=3, column=0, sticky="ew")
        body.grid_columnconfigure(0, weight=1)

        title_line = tk.Frame(body, bg=self.SURFACE)
        title_line.grid(row=0, column=0, sticky="ew")
        tk.Label(title_line, text="Documentos", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI Semibold", 13)).pack(side="left")
        tk.Label(title_line, text="1 OU MAIS PDFs", bg=self.PRIMARY_SOFT, fg=self.PRIMARY_DARK, font=("Segoe UI Semibold", 8), padx=9, pady=4).pack(side="right")

        self.drop_frame = tk.Frame(body, bg=self.DROP_BG, height=96, highlightthickness=1, highlightbackground=self.DROP_BORDER, cursor="hand2")
        self.drop_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.drop_frame.grid_propagate(False)
        self.drop_frame.grid_columnconfigure(0, weight=1)
        drop_icon = tk.Label(self.drop_frame, text="↓", bg=self.DROP_BG, fg=self.PRIMARY, font=("Segoe UI Semibold", 18))
        drop_icon.grid(row=0, column=0, pady=(8, 0))
        drop_title = tk.Label(self.drop_frame, textvariable=self.status_docs, bg=self.DROP_BG, fg=self.NAVY, font=("Segoe UI Semibold", 12))
        drop_title.grid(row=1, column=0)
        drop_hint = tk.Label(self.drop_frame, text="A ordem não importa. Nota, boleto e documentos soltos serão relacionados por Nº NFS-e, fatura ou Nº do documento.", bg=self.DROP_BG, fg=self.MUTED, font=("Segoe UI", 8))
        drop_hint.grid(row=2, column=0, pady=(1, 0))
        for widget in (self.drop_frame, drop_icon, drop_title, drop_hint):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            widget.bind("<Button-1>", lambda _event: self._selecionar_pdfs())

        queue_top = tk.Frame(body, bg=self.SURFACE)
        queue_top.grid(row=2, column=0, sticky="ew", pady=(12, 6))
        tk.Label(queue_top, text="Lançamentos identificados", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI Semibold", 10)).pack(side="left")
        tk.Label(queue_top, textvariable=self.queue_summary_var, bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 8)).pack(side="right")

        tree_wrap = tk.Frame(body, bg=self.SURFACE_ALT, highlightthickness=1, highlightbackground=self.BORDER)
        tree_wrap.grid(row=3, column=0, sticky="ew")
        tree_wrap.grid_columnconfigure(0, weight=1)
        style = ttk.Style(self)
        style.configure("Queue.Treeview", rowheight=31, font=("Segoe UI", 8), background=self.SURFACE_ALT, fieldbackground=self.SURFACE_ALT, borderwidth=0)
        style.configure("Queue.Treeview.Heading", font=("Segoe UI Semibold", 8), background="#EEF3F6", foreground=self.TEXT, relief="flat")
        self.queue_tree = ttk.Treeview(
            tree_wrap, columns=("numero", "empresa", "docs", "tipo", "status"), show="headings",
            height=7, style="Queue.Treeview", selectmode="extended"
        )
        for key, text, width, anchor in (
            ("numero", "Nº / Referência", 110, "center"),
            ("empresa", "Empresa", 300, "w"),
            ("docs", "Arquivos", 80, "center"),
            ("tipo", "Referência", 190, "w"),
            ("status", "Situação", 170, "w"),
        ):
            self.queue_tree.heading(key, text=text)
            self.queue_tree.column(key, width=width, minwidth=65, anchor=anchor, stretch=(key in ("empresa", "tipo", "status")))
        queue_scroll = SlimScrollbar(tree_wrap, self.queue_tree.yview, width=6, bg=self.SURFACE_ALT)
        self.queue_tree.configure(yscrollcommand=queue_scroll.set)
        self.queue_tree.grid(row=0, column=0, sticky="ew")
        queue_scroll.grid(row=0, column=1, sticky="ns", padx=(3, 2), pady=2)

        actions = tk.Frame(body, bg=self.SURFACE)
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="Limpar fila", style="Secondary.TButton", command=self._limpar_documentos).pack(side="left")
        self.btn_selected = ttk.Button(actions, text="PREPARAR SELECIONADO", style="Secondary.TButton", command=self._preparar_selecionado)
        self.btn_selected.pack(side="right", padx=(8, 0))
        self.btn_processar = ttk.Button(actions, text="PREPARAR TODOS NO AGILIZE", style="Accent.TButton", command=self.processar_e_abrir)
        self.btn_processar.pack(side="right")
        self.btn_processar.configure(state="disabled")
        self.btn_selected.configure(state="disabled")

        note = tk.Frame(body, bg="#F7FAFC")
        note.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        tk.Label(
            note,
            text="Cada lançamento é independente. Depois que um formulário for preparado, você já pode abrir o próximo sem precisar enviar o anterior.",
            bg="#F7FAFC", fg="#516576", font=("Segoe UI", 8), anchor="w", justify="left", wraplength=890, padx=10, pady=7
        ).pack(fill="x")

        status_card = tk.Frame(parent, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER)
        status_card.grid(row=4, column=0, sticky="ew", pady=(10, 14))
        status_top = tk.Frame(status_card, bg=self.SURFACE)
        status_top.pack(fill="x", padx=16, pady=(10, 6))
        tk.Label(status_top, text="STATUS", bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI Semibold", 8)).pack(side="left")
        tk.Label(status_top, textvariable=self.status_execucao, bg=self.SURFACE, fg=self.PRIMARY, font=("Segoe UI Semibold", 9)).pack(side="left", padx=(8, 0))
        tk.Label(status_top, textvariable=self.anexo_status_var, bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 8)).pack(side="right")
        self.progress = ttk.Progressbar(status_card, mode="determinate", maximum=100, style="Modern.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=16)

        detail_line = tk.Frame(status_card, bg=self.SURFACE)
        detail_line.pack(fill="x", padx=16, pady=(5, 8))
        self.btn_detalhes = ttk.Button(detail_line, text="Ver detalhes", style="Ghost.TButton", command=self._toggle_detalhes)
        self.btn_detalhes.pack(side="left")
        tk.Label(detail_line, text="O envio final permanece manual em cada aba.", bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 8)).pack(side="right")

        self.log_frame = tk.Frame(status_card, bg=self.SURFACE)
        self.log = tk.Text(self.log_frame, height=6, state="disabled", wrap="word", bd=0, bg=self.SURFACE_ALT, fg="#405467", font=("Consolas", 9), padx=10, pady=8)
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _set_tipo_preferido(self, key: str):
        self.tipo_preferido_var.set(key)
        self._refresh_tipo_buttons()
        self.log_msg(f"Pesquisa de histórico: {label_tipo(key)} primeiro; fallback automático nas demais áreas.")

    def _refresh_tipo_buttons(self):
        current = self.tipo_preferido_var.get()
        for key, btn in self.tipo_buttons.items():
            active = key == current
            btn.configure(
                bg=self.PRIMARY if active else "#EEF3F6",
                fg="white" if active else self.TEXT,
                activebackground=self.PRIMARY_DARK if active else "#E3EBF0",
                activeforeground="white" if active else self.TEXT,
            )

    def _step(self, parent, column, number, title, subtitle, active=False):
        box = tk.Frame(parent, bg=self.BG)
        box.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 5, 0 if column == 2 else 5))
        bubble = tk.Label(box, text=number, bg=self.PRIMARY if active else "#DDE5EB", fg="white" if active else self.MUTED, font=("Segoe UI Semibold", 8), width=3, pady=3)
        bubble.pack(side="left")
        txt = tk.Frame(box, bg=self.BG)
        txt.pack(side="left", padx=(7, 0))
        tk.Label(txt, text=title, bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 9)).pack(anchor="w")
        tk.Label(txt, text=subtitle, bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8)).pack(anchor="w")

    def _build_configuracoes(self, parent):
        tk.Label(parent, text="Configurações", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 17)).pack(anchor="w")
        tk.Label(parent, text="Salve seu acesso uma vez e escolha o navegador usado na automação.", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 10))

        card, body = self._card(parent, padx=22, pady=19)
        card.pack(fill="x")
        body.grid_columnconfigure(1, weight=1)
        tk.Label(body, text="Acesso ao Agilize", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI Semibold", 13)).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        tk.Label(body, text="E-mail", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI Semibold", 9)).grid(row=1, column=0, sticky="w", padx=(0, 15), pady=6)
        ttk.Entry(body, textvariable=self.email_var).grid(row=1, column=1, sticky="ew", pady=6)
        tk.Label(body, text="Senha", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI Semibold", 9)).grid(row=2, column=0, sticky="w", padx=(0, 15), pady=6)
        self.senha_entry = ttk.Entry(body, textvariable=self.senha_var, show="*")
        self.senha_entry.grid(row=2, column=1, sticky="ew", pady=6)

        mostrar_var = tk.BooleanVar(value=False)
        def toggle_senha():
            self.senha_entry.configure(show="" if mostrar_var.get() else "*")
        opts = tk.Frame(body, bg=self.SURFACE)
        opts.grid(row=3, column=1, sticky="w", pady=(2, 12))
        ttk.Checkbutton(opts, text="Mostrar senha", variable=mostrar_var, command=toggle_senha).pack(side="left")
        ttk.Checkbutton(opts, text="Login automático", variable=self.login_auto_var).pack(side="left", padx=(18, 0))

        tk.Frame(body, bg=self.BORDER, height=1).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(1, 13))
        tk.Label(body, text="Navegador", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI Semibold", 9)).grid(row=5, column=0, sticky="w", padx=(0, 15), pady=6)
        browser_line = tk.Frame(body, bg=self.SURFACE)
        browser_line.grid(row=5, column=1, sticky="ew", pady=6)
        browser_line.grid_columnconfigure(0, weight=1)
        self.browser_combo = ttk.Combobox(browser_line, textvariable=self.browser_var, values=self.browser_labels, state="readonly")
        self.browser_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(browser_line, text="Atualizar lista", style="Secondary.TButton", command=self._atualizar_navegadores).grid(row=0, column=1, padx=(8, 0))

        actions = tk.Frame(parent, bg=self.BG)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Abrir dados e logs", style="Secondary.TButton", command=self._abrir_dados_logs).pack(side="left")
        ttk.Button(actions, text="Remover credenciais", style="Secondary.TButton", command=self._remover_credenciais).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Salvar configurações", style="Accent.TButton", command=self._salvar_configuracoes).pack(side="right")

    def _build_atualizacoes(self, parent):
        tk.Label(parent, text="Atualizações", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 17)).pack(anchor="w")
        tk.Label(
            parent,
            text="A Automação Agilize verifica a última Release publicada no GitHub e só oferece atualização quando o instalador estiver pronto.",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9), wraplength=820, justify="left"
        ).pack(anchor="w", pady=(2, 10))

        card, body = self._card(parent, padx=22, pady=18)
        card.pack(fill="x")
        body.grid_columnconfigure(0, weight=1)

        top = tk.Frame(body, bg=self.SURFACE)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        tk.Label(
            top, text="Atualização do sistema", bg=self.SURFACE, fg=self.TEXT,
            font=("Segoe UI Semibold", 12)
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            top, text=f"v{__version__}", bg=self.PRIMARY_SOFT, fg=self.PRIMARY_DARK,
            font=("Segoe UI Semibold", 9), padx=10, pady=4
        ).grid(row=0, column=1, sticky="e")

        self.update_status_box = tk.Frame(
            body, bg=self.SURFACE_ALT, highlightthickness=1, highlightbackground=self.BORDER
        )
        self.update_status_box.grid(row=1, column=0, sticky="ew", pady=(12, 8))
        self.update_status_box.grid_columnconfigure(1, weight=1)
        self.update_dot = tk.Label(
            self.update_status_box, text="●", bg=self.SURFACE_ALT, fg=self.MUTED,
            font=("Segoe UI Semibold", 12)
        )
        self.update_dot.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=11, sticky="n")
        self.update_status_label = tk.Label(
            self.update_status_box, textvariable=self.update_status_var, bg=self.SURFACE_ALT,
            fg=self.TEXT, font=("Segoe UI Semibold", 9), anchor="w", justify="left",
            wraplength=720
        )
        self.update_status_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(9, 2))
        self.update_detail_label = tk.Label(
            self.update_status_box, textvariable=self.update_detail_var, bg=self.SURFACE_ALT,
            fg=self.MUTED, font=("Segoe UI", 8), anchor="w", justify="left", wraplength=720
        )
        self.update_detail_label.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 9))

        self.update_progress = ttk.Progressbar(
            body, mode="determinate", maximum=100, style="Modern.Horizontal.TProgressbar"
        )
        self.update_progress.grid(row=2, column=0, sticky="ew", pady=(2, 12))

        actions = tk.Frame(body, bg=self.SURFACE)
        actions.grid(row=3, column=0, sticky="ew")
        ttk.Button(
            actions, text="Abrir GitHub", style="Secondary.TButton",
            command=lambda: webbrowser.open(GITHUB_URL)
        ).pack(side="left")
        self.btn_check_update = ttk.Button(
            actions, text="Verificar atualização", style="Secondary.TButton",
            command=lambda: self._verificar_atualizacao(False)
        )
        self.btn_check_update.pack(side="right")
        self.btn_install_update = ttk.Button(
            actions, text="Atualizar agora", style="Accent.TButton",
            command=self._baixar_e_instalar_update
        )
        self.btn_install_update.pack(side="right", padx=(0, 8))
        self.btn_install_update.configure(state="disabled")

        info_card, info_body = self._card(parent, padx=18, pady=14)
        info_card.pack(fill="x", pady=(10, 14))
        tk.Label(
            info_body, text="Como funciona", bg=self.SURFACE, fg=self.TEXT,
            font=("Segoe UI Semibold", 10)
        ).pack(anchor="w")
        tk.Label(
            info_body,
            text=(
                "O sistema compara a versão do código com a última Release. Quando uma versão acabou de ser "
                "publicada e o GitHub Actions ainda está gerando o instalador, o botão muda para 'Aguardar "
                "instalador'. A Automação Agilize acompanha a publicação e inicia a atualização assim que o "
                "Setup.exe + SHA-256 estiverem prontos."
            ),
            bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 8), wraplength=820, justify="left"
        ).pack(anchor="w", pady=(4, 0))

    def _compact_name(self, name: str, max_len: int = 78) -> str:
        if len(name) <= max_len:
            return name
        keep_left = max_len // 2
        keep_right = max_len - keep_left - 3
        return f"{name[:keep_left]}...{name[-keep_right:]}"

    def _selecionar_pdfs(self):
        paths = filedialog.askopenfilenames(title="Selecione os PDFs", filetypes=[("Arquivos PDF", "*.pdf")])
        if paths:
            self._registrar_documentos(list(paths), append=True)

    def _on_drop(self, event):
        try:
            self._registrar_documentos(list(self.tk.splitlist(event.data)), append=True)
        except Exception as exc:
            messagebox.showerror("Arquivos", str(exc))

    def _registrar_documentos(self, paths: list[str], append: bool = True):
        novos: list[Path] = []
        for raw in paths:
            path = Path(raw.strip("{}\"")).resolve()
            if path.suffix.lower() == ".pdf" and path.exists() and path not in novos:
                novos.append(path)
        if not novos:
            messagebox.showwarning("Documentos", "Nenhum PDF válido foi encontrado.")
            return

        combinados = list(self.pdfs) if append else []
        for path in novos:
            if path not in combinados:
                combinados.append(path)
        if len(combinados) > 100:
            messagebox.showwarning("Documentos", "Para evitar uma seleção acidental, processe no máximo 100 PDFs por fila.")
            return

        self.pdfs = combinados
        self.progress["value"] = 0
        self.status_docs.set(f"{len(self.pdfs)} PDF(s) carregado(s) · analisando...")
        self.status_execucao.set("Agrupando documentos")
        self._limpar_log()
        self.log_msg(f"{len(self.pdfs)} PDF(s) recebido(s). Identificando Nº NFS-e, fatura ou Nº do documento e relacionando arquivos...")
        self._analisar_fila()

    def _analisar_fila(self):
        self.btn_processar.configure(state="disabled")
        self.btn_selected.configure(state="disabled")
        old_status = {g.key: g.status for g in self.grupos}

        def worker():
            try:
                grupos = agrupar_documentos(self.pdfs)
                for g in grupos:
                    if g.key in old_status and old_status[g.key] in ("Aberto para conferência", "Na fila", "Preparando"):
                        g.status = old_status[g.key]
                self.grupos = grupos
                self.grupos_by_key = {g.key: g for g in grupos}
                self.after(0, self._refresh_queue_tree)
            except Exception as exc:
                self.log_msg(f"ERRO ao analisar PDFs: {exc}")
                self.after(0, lambda: messagebox.showerror("Documentos", str(exc)))
                self.after(0, self._sync_document_state)
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_queue_tree(self):
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        single_count = 0
        warning_count = 0
        for grupo in self.grupos:
            if len(grupo.documentos) == 1:
                single_count += 1
            warning_count += len(grupo.avisos)
            tipo = label_tipo(grupo.tipo_sugerido)
            numero = grupo.numero or "Sem número"
            status = grupo.status
            if len(grupo.documentos) == 1 and status == "Pronto":
                status = "Pronto · 1 PDF"
            self.queue_tree.insert(
                "", "end", iid=grupo.key,
                values=(numero, grupo.empresa, grupo.resumo_documentos, tipo, status),
            )
        qtd = len(self.grupos)
        self.status_docs.set(f"{len(self.pdfs)} PDF(s) · {qtd} lançamento(s)")
        extras = []
        if single_count:
            extras.append(f"{single_count} com documento único")
        if warning_count:
            extras.append(f"{warning_count} aviso(s)")
        self.queue_summary_var.set(f"{qtd} lançamento(s)" + (" · " + " · ".join(extras) if extras else ""))
        self.anexo_status_var.set(f"{len(self.pdfs)} PDF(s) em {qtd} lançamento(s)")
        self.status_execucao.set("Fila pronta" if qtd else "Aguardando documentos")
        self._sync_document_state()

    def _sync_document_state(self):
        ready = len(self.grupos) > 0
        if hasattr(self, "btn_processar"):
            self.btn_processar.configure(state="normal" if ready else "disabled")
        if hasattr(self, "btn_selected"):
            self.btn_selected.configure(state="normal" if ready else "disabled")
        if not self.pdfs:
            self.status_docs.set("Arraste os PDFs aqui")
            self.queue_summary_var.set("Nenhum lançamento identificado")
            self.anexo_status_var.set("Os PDFs serão agrupados automaticamente pela referência do documento")
            self.status_execucao.set("Aguardando documentos")

    def _limpar_documentos(self):
        ativos = any(g.status in ("Na fila", "Preparando") for g in self.grupos)
        if ativos and not messagebox.askyesno("Limpar fila", "Há lançamentos sendo preparados. Deseja limpar a lista visual mesmo assim?"):
            return
        self.pdfs.clear()
        self.grupos.clear()
        self.grupos_by_key.clear()
        if hasattr(self, "queue_tree"):
            for item in self.queue_tree.get_children():
                self.queue_tree.delete(item)
        self.progress["value"] = 0
        self._limpar_log()
        self._sync_document_state()

    def _atualizar_navegadores(self):
        atual_key = self.browser_map.get(self.browser_var.get(), "auto")
        self.browser_labels, self.browser_map = labels_para_combo()
        self.browser_combo.configure(values=self.browser_labels)
        label = label_para_preferencia(atual_key)
        self.browser_var.set(label if label in self.browser_labels else self.browser_labels[0])

    def _salvar_configuracoes(self):
        browser_key = self.browser_map.get(self.browser_var.get(), "auto")
        try:
            email = self.email_var.get().strip()
            senha = self.senha_var.get()
            if email and senha:
                salvar_credenciais(email, senha, self.login_auto_var.get(), browser_key)
                msg = "Configurações salvas."
            else:
                salvar_navegador(browser_key)
                msg = "Navegador salvo. Preencha e-mail e senha para ativar o login automático."
            messagebox.showinfo("Configurações", msg)
        except Exception as exc:
            messagebox.showerror("Configurações", f"Não foi possível salvar: {exc}")

    def _remover_credenciais(self):
        remover_credenciais()
        self.email_var.set("")
        self.senha_var.set("")
        self.login_auto_var.set(True)
        messagebox.showinfo("Credenciais", "Credenciais removidas.")

    def _abrir_dados_logs(self):
        try:
            APP_HOME.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(APP_HOME))
            else:
                webbrowser.open(APP_HOME.as_uri())
        except Exception as exc:
            messagebox.showerror("Pasta de dados", str(exc))

    def _toggle_detalhes(self):
        self.details_visible = not self.details_visible
        if self.details_visible:
            self.log_frame.pack(fill="x")
            self.btn_detalhes.configure(text="Ocultar detalhes")
        else:
            self.log_frame.pack_forget()
            self.btn_detalhes.configure(text="Ver detalhes")

    def _limpar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def log_msg(self, msg: str):
        def update():
            self.log.configure(state="normal")
            self.log.insert("end", msg + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.after(0, update)

    def set_progress(self, value: int, status: str = ""):
        def update():
            self.progress["value"] = value
            if status:
                self.status_execucao.set(status)
        self.after(0, update)

    def _refresh_update_banner(self, info):
        # O banner principal so aparece quando existe um Setup.exe realmente
        # instalavel. Estados como repositorio nao publicado, offline ou Release
        # em preparacao ficam apenas na aba Atualizacoes e nao parecem erro.
        if info and info.state == STATE_UPDATE_AVAILABLE and info.can_install:
            self.update_banner_text.configure(
                text=f"Nova versão v{info.latest_version} disponível. Atualização pronta para instalar."
            )
            self.update_banner.grid()
            self.nav_updates.configure(
                text=f"Atualizações  •  v{info.latest_version}",
                bg="#FFF7E8", fg=self.WARNING, activebackground="#FFF1D6", activeforeground="#7A4B05"
            )
        else:
            self.update_banner.grid_remove()
            self.nav_updates.configure(
                text="Atualizações", bg=self.SURFACE, fg=self.MUTED,
                activebackground=self.PRIMARY_SOFT, activeforeground=self.PRIMARY_DARK
            )

    def _prompt_startup_update(self):
        info = self.update_info
        if (
            self._startup_update_prompted
            or not info
            or info.state != STATE_UPDATE_AVAILABLE
            or not info.available
            or not info.can_install
        ):
            return
        self._startup_update_prompted = True
        if messagebox.askyesno(
            "Atualização disponível",
            f"Uma nova versão da Automação Agilize está disponível: v{info.latest_version}.\n\n"
            f"Versão instalada: v{__version__}.\n\n"
            "Deseja atualizar agora? O aplicativo será reaberto automaticamente ao concluir.",
        ):
            self._show_page("atualizacoes")
            self._baixar_e_instalar_update()

    def _verificar_atualizacao(self, silencioso: bool = False):
        if hasattr(self, "btn_check_update"):
            self.btn_check_update.configure(state="disabled")
        if hasattr(self, "update_progress"):
            self.update_progress.configure(value=0)
        self.update_status_var.set(f"Versão instalada: v{__version__} · verificando atualização...")
        self.update_detail_var.set("Consultando a última Release publicada no GitHub.")
        if hasattr(self, "update_dot"):
            self.update_dot.configure(fg=self.MUTED)

        def worker():
            info = verificar_atualizacao()
            self.update_info = info

            def done():
                if hasattr(self, "btn_check_update"):
                    self.btn_check_update.configure(state="normal")
                if hasattr(self, "update_progress"):
                    self.update_progress.configure(value=100 if info.state in {STATE_UPDATED, STATE_UPDATE_AVAILABLE, STATE_RELEASE_PENDING, STATE_NO_RELEASE} else 0)
                self.update_latest_var.set(
                    f"v{info.latest_version}" if info.latest_version else f"v{__version__}"
                )

                self.update_status_var.set(info.message or "Verificação concluída.")
                self.update_detail_var.set(info.detail or "")
                if info.state == STATE_UPDATE_AVAILABLE and info.can_install:
                    self.btn_install_update.configure(text="Atualizar agora", state="normal")
                elif info.state == STATE_RELEASE_PENDING and info.available:
                    self.btn_install_update.configure(text="Aguardar instalador", state="normal")
                else:
                    self.btn_install_update.configure(text="Atualizar agora", state="disabled")

                # Cores: verde = atualizado; amarelo = atualização/publish pendente;
                # azul/cinza = canal indisponível/offline; vermelho apenas para uma
                # falha inesperada de software.
                if hasattr(self, "update_dot"):
                    if info.state == STATE_UPDATED:
                        self.update_dot.configure(fg=self.SUCCESS)
                    elif info.state in {STATE_UPDATE_AVAILABLE, STATE_RELEASE_PENDING}:
                        self.update_dot.configure(fg=self.WARNING)
                    elif info.state in {STATE_NO_RELEASE, STATE_REPOSITORY_UNAVAILABLE, STATE_OFFLINE, STATE_RATE_LIMITED}:
                        self.update_dot.configure(fg=self.MUTED)
                    elif info.state == STATE_CHECK_FAILED:
                        self.update_dot.configure(fg=self.DANGER)
                    else:
                        self.update_dot.configure(fg=self.MUTED)

                self._refresh_update_banner(info)

                # Nunca exibe popup de erro para estados esperados do GitHub.
                # A checagem manual informa tudo dentro da propria aba.
                if not silencioso and info.state == STATE_CHECK_FAILED and info.error:
                    messagebox.showwarning(
                        "Atualizações",
                        info.error + "\n\nConsulte Ver detalhes ou o arquivo update.log para diagnóstico."
                    )

                if silencioso and info.state == STATE_UPDATE_AVAILABLE and info.can_install:
                    self.after(350, self._prompt_startup_update)

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _baixar_e_instalar_update(self):
        info = self.update_info
        if not info or not info.available:
            messagebox.showinfo("Atualizações", "Nenhuma atualização está disponível.")
            return

        # A versão já chegou ao repositório, mas o GitHub Actions ainda está
        # construindo/publicando o Setup. O usuário não precisa sair da tela nem
        # ficar clicando em verificar: aguardamos a Release oficial por até 10 min.
        precisa_aguardar = not info.can_install or not info.download_url
        if precisa_aguardar:
            if not messagebox.askyesno(
                "Aguardar instalador",
                f"A versão v{info.latest_version} já foi detectada, mas o instalador ainda está sendo gerado pelo GitHub.\n\n"
                "Deseja aguardar por aqui? A Automação Agilize verificará automaticamente até o instalador ficar pronto.",
            ):
                return
        else:
            if not messagebox.askyesno(
                "Atualizar Automação Agilize",
                f"Baixar e instalar a versão v{info.latest_version}?\n\nO aplicativo será fechado para concluir a atualização.",
            ):
                return

        self.btn_install_update.configure(state="disabled")
        if hasattr(self, "btn_check_update"):
            self.btn_check_update.configure(state="disabled")

        def ui_progress(pct: int, text: str):
            self.after(0, lambda: self.update_progress.configure(value=pct))
            self.after(0, lambda: self.update_status_var.set(text))

        def worker():
            try:
                ready = info
                if precisa_aguardar:
                    self.after(0, lambda: self.update_detail_var.set(
                        "O GitHub Actions está preparando o instalador. Esta tela pode permanecer aberta."
                    ))

                    def wait_progress(pct: int, text: str):
                        # Reserva os primeiros 35% da barra para a publicação.
                        ui_progress(min(35, max(1, int(pct * 0.35))), text)

                    ready = aguardar_instalador(
                        info.latest_version,
                        timeout_seconds=600,
                        interval_seconds=12,
                        progress=wait_progress,
                    )
                    self.update_info = ready
                    self.after(0, lambda: self.update_detail_var.set(
                        "Instalador publicado. Iniciando download e validação SHA-256."
                    ))

                def download_progress(pct: int, text: str):
                    mapped = 35 + int(max(0, min(100, pct)) * 0.55)
                    ui_progress(mapped, text)

                instalador = baixar_instalador(ready, progress=download_progress)
                ui_progress(95, "Instalador validado. Preparando atualização...")
                self.after(0, lambda: self.update_detail_var.set(
                    "A Automação Agilize será fechada e reaberta automaticamente."
                ))
                iniciar_instalador(instalador)
                self.after(800, self.destroy)
            except Exception as exc:
                self.after(0, lambda: self.update_status_var.set(f"Não foi possível concluir a atualização: {exc}"))
                self.after(0, lambda: self.update_detail_var.set(
                    "A versão continua disponível. Verifique a Release/Actions do GitHub e tente novamente."
                ))
                self.after(0, lambda: self.btn_check_update.configure(state="normal"))
                self.after(0, lambda: self.btn_install_update.configure(
                    text="Aguardar instalador" if info.state == STATE_RELEASE_PENDING else "Atualizar agora",
                    state="normal",
                ))
                self.after(0, lambda: messagebox.showerror("Atualizações", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _preparar_selecionado(self):
        selecionados = list(self.queue_tree.selection())
        if not selecionados:
            messagebox.showinfo("Fila", "Selecione pelo menos um lançamento na lista.")
            return
        grupos = [self.grupos_by_key[key] for key in selecionados if key in self.grupos_by_key]
        self._enfileirar_grupos(grupos)

    def processar_e_abrir(self):
        if not self.grupos:
            messagebox.showwarning("Fila", "Adicione pelo menos um PDF.")
            return
        self._enfileirar_grupos(self.grupos)

    def _enfileirar_grupos(self, grupos: list[GrupoLancamento]):
        creds = carregar_credenciais()
        browser_key = self.browser_map.get(self.browser_var.get(), creds.navegador or "auto")
        preferido = self.tipo_preferido_var.get()
        enviados = 0
        for grupo in grupos:
            if grupo.status in ("Na fila", "Preparando"):
                continue
            if not grupo.dados:
                grupo.status = "Erro de leitura"
                continue
            # Mantém o fluxo permissivo para documento único ou parcial, mas bloqueia
            # somente quando não há dados mínimos para identificar o lançamento.
            if not grupo.dados.provider_cnpj or not grupo.dados.company_id:
                grupo.status = "Revisar dados"
                self.log_msg(f"Grupo {grupo.numero or grupo.key}: faltou CNPJ fornecedor ou empresa; não enviado à fila do navegador.")
                continue
            grupo.status = "Na fila"
            self._browser_jobs.put({
                "grupo": grupo,
                "browser": browser_key,
                "email": creds.email if creds.login_automatico else "",
                "senha": creds.senha if creds.login_automatico else "",
                "preferido": preferido,
            })
            enviados += 1
        self._refresh_queue_tree()
        if enviados:
            self.status_execucao.set(f"{enviados} lançamento(s) na fila do navegador")
            self.log_msg(f"{enviados} lançamento(s) adicionados à fila. Não é necessário enviar um para preparar o próximo.")
        else:
            messagebox.showinfo("Fila", "Nenhum lançamento novo foi adicionado. Verifique os status da lista.")

    def _set_group_status(self, key: str, status: str):
        grupo = self.grupos_by_key.get(key)
        if grupo:
            grupo.status = status
        if hasattr(self, "queue_tree") and self.queue_tree.exists(key):
            vals = list(self.queue_tree.item(key, "values"))
            if len(vals) >= 5:
                vals[4] = status
                self.queue_tree.item(key, values=vals)

    def _browser_loop(self):
        session = None
        session_config = None
        while True:
            job = self._browser_jobs.get()
            if job is None:
                break
            grupo: GrupoLancamento = job["grupo"]
            config = (job["browser"], job["email"], job["senha"])
            try:
                if session is None or config != session_config:
                    if session is not None:
                        session.close()
                    session = AgilizeSession(
                        navegador=job["browser"], email=job["email"], senha=job["senha"], logger=self.log_msg
                    )
                    session_config = config
                self.after(0, lambda k=grupo.key: self._set_group_status(k, "Preparando"))
                self.log_msg(f"Preparando lançamento {grupo.numero or '(sem referência)'}...")
                anexos = [str(p) for p in grupo.paths]
                conferencia = str(grupo.conferencia_pdf or grupo.paths[0])
                session.preparar_lancamento(
                    grupo.dados,
                    anexos_pdf=anexos,
                    conferencia_pdf=conferencia,
                    tipo_preferido=job["preferido"],
                    tipo_sugerido=grupo.tipo_sugerido,
                )
                self.after(0, lambda k=grupo.key: self._set_group_status(k, "Aberto para conferência"))
                self.after(0, lambda: self.status_execucao.set("Formulário aberto · fila continua disponível"))
            except Exception as exc:
                self.log_msg(f"ERRO no grupo {grupo.numero or grupo.key}: {exc}")
                self.after(0, lambda k=grupo.key: self._set_group_status(k, "Erro"))
            finally:
                self._browser_jobs.task_done()
        if session is not None:
            try:
                session.close()
            except Exception:
                pass

    def _on_close(self):
        try:
            self._browser_jobs.put_nowait(None)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
