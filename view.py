import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
import json
from models import MindMapModel, Node
from graphics import GraphicsEngine

class MindMapView:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("pymind - Python Mind Map Tool")
        
        # メインフレーム（CanvasとScrollbarを配置）
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # スクロールバー
        self.v_scroll = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll = tk.Scrollbar(self.main_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.canvas = tk.Canvas(self.main_frame, bg="#fafafa", highlightthickness=0,
                                xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        self.model = MindMapModel()
        self.graphics = GraphicsEngine(self.canvas)
        self.selected_node: Node = self.model.root
        self.editing_entry = None # インライン編集用のウィジェット
        
        # メニューバーの作成
        self._create_menu()
        
        # イベントバインド
        # イベントバインド (bind_allではなくroot.bindを使用し、breakが機能するようにする)
        def bind_key(key, handler):
            self.root.bind(key, self._wrap_handler(handler))

        bind_key("<Tab>", self.on_add_child)
        bind_key("<Return>", self.on_add_sibling)
        bind_key("<F2>", self.on_edit_node)
        bind_key("<Delete>", self.on_delete_node)
        bind_key("<Control-s>", self.on_save)
        bind_key("<Control-o>", self.on_open)
        bind_key("<Up>", lambda e: self.navigate("up"))
        bind_key("<Down>", lambda e: self.navigate("down"))
        bind_key("<Left>", lambda e: self.navigate("left"))
        bind_key("<Right>", lambda e: self.navigate("right"))
        
        # マウスホイール
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_mouse_wheel_x)
        
        self.first_render = True
        self.render()

    def on_mouse_wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_mouse_wheel_x(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")

    def _on_canvas_click(self, event):
        if not self.editing_entry:
            self.canvas.focus_set()

    def _wrap_handler(self, func):
        """編集中は入力を無視し、かつイベントが他へ伝播しないようにする"""
        def wrapper(event):
            if self.editing_entry:
                return "break"
            res = func(event)
            return "break" # 基本的にマインドマップの操作はここで完結させる
        return wrapper

    def calculate_subtree_height(self, node: Node):
        """そのノードを含むサブツリー全体の必要高さを計算・更新する"""
        # draw_nodeを呼ばなくてもサイズが必要なため、一度計算しておく
        font = self.graphics.root_font if node.parent is None else self.graphics.font
        node.width, node.height = self.graphics.get_text_size(node.text, font)
        
        if not node.children:
            node.subtree_height = node.height
            return node.height
            
        spacing = 20
        total_height = sum(self.calculate_subtree_height(c) for c in node.children)
        total_height += spacing * (len(node.children) - 1)
        node.subtree_height = max(node.height, total_height)
        return node.subtree_height

    def layout(self, center_x, center_y):
        """左右対称レイアウトの実行"""
        root = self.model.root
        self.calculate_subtree_height(root)
        
        root.x = center_x
        root.y = center_y
        
        # ルートの子ノードを左右に分ける
        right_children = [c for c in root.children if c.direction != 'left']
        left_children = [c for c in root.children if c.direction == 'left']
        
        self._layout_branch(right_children, center_x + 200, center_y, 'right')
        self._layout_branch(left_children, center_x - 200, center_y, 'left')

    def _layout_branch(self, nodes, start_x, start_y, direction):
        if not nodes:
            return
            
        spacing = 20
        total_height = sum(n.subtree_height for n in nodes) + spacing * (len(nodes) - 1)
        current_y = start_y - total_height / 2
        
        for node in nodes:
            node.x = start_x
            node.y = current_y + node.subtree_height / 2
            
            # 孫以降の配置
            next_x = start_x + 200 if direction == 'right' else start_x - 200
            self._layout_branch(node.children, next_x, node.y, direction)
            
            current_y += node.subtree_height + spacing

    def render(self):
        self.graphics.clear()
        
        # キャンバスの現在のサイズを正確に取得
        self.root.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # fallback
        if w < 100: w = 1000
        if h < 100: h = 800
        
        # レイアウト計算 (キャンバスの中央を基準にする)
        self.layout(w / 2, h / 2)
        
        # 全ノード描画
        self._draw_subtree(self.model.root)
        
        # スクロール範囲の設定を動的に行う
        bbox = self.canvas.bbox("all")
        if bbox:
            # コンテンツの周囲に適切な余白（500px程度）を設ける
            margin = 500
            new_sr = (bbox[0] - margin, bbox[1] - margin, bbox[2] + margin, bbox[3] + margin)
            self.canvas.config(scrollregion=new_sr)
            
            sr_w = new_sr[2] - new_sr[0]
            sr_h = new_sr[3] - new_sr[1]

            # 初回起動時のみ中央に移動
            if self.first_render:
                # rootを画面中央に持ってくるための比率を計算
                # (root.x - sr_x1) が 0〜sr_w の間のどこにあるか
                fraction_x = (self.model.root.x - new_sr[0] - w/2) / sr_w
                fraction_y = (self.model.root.y - new_sr[1] - h/2) / sr_h
                
                self.canvas.xview_moveto(max(0, fraction_x))
                self.canvas.yview_moveto(max(0, fraction_y))
                self.first_render = False
            
            # 選択中のノードを画面内に収める
            self.ensure_node_visible(self.selected_node)

    def ensure_node_visible(self, node: Node):
        """指定したノードが画面外にある場合、見える位置までスクロールする"""
        if not node or not self.canvas.cget("scrollregion"): return
        
        # キャンバス上の現在の表示領域を取得 (比率 0.0 to 1.0)
        vx1, vx2 = self.canvas.xview()
        vy1, vy2 = self.canvas.yview()
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # scrollregionを取得
        sr = [float(c) for c in self.canvas.cget("scrollregion").split()]
        sr_w = sr[2] - sr[0]
        sr_h = sr[3] - sr[1]
        
        # ノードの現在位置（比率）
        node_rel_x = (node.x - sr[0]) / sr_w
        node_rel_y = (node.y - sr[1]) / sr_h
        
        # 画面の幅の比率
        view_w_ratio = w / sr_w
        view_h_ratio = h / sr_h
        
        margin = 0.05
        # 画面外（または端に近い）なら移動
        if node_rel_x < vx1 + margin or node_rel_x > vx2 - margin:
            self.canvas.xview_moveto(max(0, node_rel_x - view_w_ratio / 2))
            
        if node_rel_y < vy1 + margin or node_rel_y > vy2 - margin:
            self.canvas.yview_moveto(max(0, node_rel_y - view_h_ratio / 2))

    def _draw_subtree(self, node: Node):
        self.graphics.draw_node(node, is_selected=(node == self.selected_node))
        for child in node.children:
            self._draw_subtree(child)

    def on_add_child(self, event):
        if self.editing_entry: return
        
        # 方向の決定
        if self.selected_node == self.model.root:
            direction = self._get_balanced_direction()
        else:
            # 親の方向を継承（孫以降も左側・右側の概念を保持するため）
            direction = self.selected_node.direction
        
        new_node = self.selected_node.add_child("新規トピック", direction)
        self.selected_node = new_node
        self.render()
        self.on_edit_node(None)

    def _get_balanced_direction(self):
        """ルートの子ノードの左右バランスを計算して次の方向を返す"""
        right_count = len([c for c in self.model.root.children if c.direction != 'left'])
        left_count = len([c for c in self.model.root.children if c.direction == 'left'])
        return 'right' if right_count <= left_count else 'left'

    def on_add_sibling(self, event):
        if self.editing_entry: return
        if self.selected_node.parent:
            direction = None
            if self.selected_node.parent == self.model.root:
                direction = self._get_balanced_direction()
            else:
                direction = self.selected_node.direction
            
            new_node = self.selected_node.parent.add_child("新規トピック", direction)
            self.selected_node = new_node
            self.render()
            self.on_edit_node(None)

    def on_edit_node(self, event):
        print(f"DEBUG: on_edit_node triggered by {event}")
        if self.editing_entry:
            return
            
        node = self.selected_node
        # Entryウィジェットの作成（枠線と背景色を明示して視認性を向上）
        entry = tk.Entry(self.canvas, justify="center", font=self.graphics.font, 
                         bg="white", fg="black", insertbackground="black",
                         relief="flat", highlightbackground="#0078d7", highlightthickness=2)
        entry.insert(0, node.text)
        entry.select_range(0, tk.END)
        
        # キャンバスに配置 (最前面に配置されるよう、タグを使用して管理も検討できるが通常は最前面)
        window_id = self.canvas.create_window(node.x, node.y, window=entry, width=max(120, node.width + 20), anchor="center")
        self.editing_entry = entry
        
        # 確実にフォーカスを当てる
        def set_focus():
            if self.editing_entry == entry:
                entry.focus_set()
                print("DEBUG: Entry focused")
        self.root.after(100, set_focus)
        
        self.finishing = False # 再入防止フラグ
        
        def finish_edit(event=None):
            if self.finishing or not self.editing_entry:
                return "break"
            self.finishing = True
            print("DEBUG: finish_edit started")
            
            new_text = entry.get()
            if new_text:
                node.text = new_text
            
            self.editing_entry = None
            self.canvas.delete(window_id)
            self.render()
            self.canvas.focus_set() # キャンバスにフォーカスを戻す
            return "break"
            
        def cancel_edit(event=None):
            if self.finishing or not self.editing_entry:
                return "break"
            self.finishing = True
            print("DEBUG: cancel_edit started")
            
            self.editing_entry = None
            self.canvas.delete(window_id)
            self.render()
            self.canvas.focus_set()
            return "break"

        entry.bind("<Return>", finish_edit)
        entry.bind("<Escape>", cancel_edit)
        # FocusOutはタイミングによって危ないが、一旦副作用を抑えて利用
        entry.bind("<FocusOut>", lambda e: finish_edit())
        
        # Entry内でのキー入力を他のハンドラに渡さないためのガード
        entry.bind("<Tab>", lambda e: "break")
        
        return "break" # on_edit_node自体の伝播も止める

    def on_delete_node(self, event):
        if self.editing_entry: return
        if self.selected_node.parent:
            parent = self.selected_node.parent
            parent.remove_child(self.selected_node)
            self.selected_node = parent
            self.render()

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="開く (Ctrl+O)", command=self.on_open)
        filemenu.add_command(label="保存 (Ctrl+S)", command=self.on_save)
        filemenu.add_separator()
        filemenu.add_command(label="終了", command=self.root.quit)
        menubar.add_cascade(label="ファイル", menu=filemenu)
        self.root.config(menu=menubar)

    def on_save(self, event=None):
        print("DEBUG: on_save triggered")
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                data = self.model.save()
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("保存", "保存が完了しました。")
            except Exception as e:
                messagebox.showerror("エラー", f"保存に失敗しました: {e}")

    def on_open(self, event=None):
        print("DEBUG: on_open triggered")
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.model.load(data)
                self.selected_node = self.model.root
                self.render()
                messagebox.showinfo("読み込み", "読み込みが完了しました。")
            except Exception as e:
                messagebox.showerror("エラー", f"読み込みに失敗しました: {e}")

    def navigate(self, direction):
        """左右対称レイアウトに対応したナビゲーション"""
        curr = self.selected_node
        
        if direction == "right":
            if curr == self.model.root:
                # ルートからは右側の子へ
                right_children = [c for c in curr.children if c.direction != 'left']
                if right_children: self.selected_node = right_children[0]
            elif curr.direction != 'left':
                # 右側のノードなら子へ
                if curr.children: self.selected_node = curr.children[0]
            else:
                # 左側のノードなら親（ルート方向）へ
                if curr.parent: self.selected_node = curr.parent
                
        elif direction == "left":
            if curr == self.model.root:
                # ルートからは左側の子へ
                left_children = [c for c in curr.children if c.direction == 'left']
                if left_children: self.selected_node = left_children[0]
            elif curr.direction == 'left':
                # 左側のノードなら子へ
                if curr.children: self.selected_node = curr.children[0]
            else:
                # 右側のノードなら親（ルート方向）へ
                if curr.parent: self.selected_node = curr.parent
                
        elif direction in ("up", "down") and curr.parent:
            # 同じ方向（左右）の兄弟間での移動
            siblings = [c for c in curr.parent.children if c.direction == curr.direction]
            if not siblings: siblings = curr.parent.children
            
            try:
                idx = siblings.index(curr)
                if direction == "up" and idx > 0:
                    self.selected_node = siblings[idx-1]
                elif direction == "down" and idx < len(siblings) - 1:
                    self.selected_node = siblings[idx+1]
            except ValueError:
                pass
                
        self.render()
