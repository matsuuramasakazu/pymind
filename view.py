import tkinter as tk
from tkinter import filedialog, messagebox
import json
from models import MindMapModel, Node
from graphics import GraphicsEngine
from layout import LayoutEngine

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
        self.layout_engine = LayoutEngine()
        self.selected_node: Node = self.model.root
        self.editing_entry = None # インライン編集用のウィジェット
        self.drag_data = {} # ドラッグ＆ドロップ用データ
        
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

        # マウスイベントのバインド
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_drag_drop)

    def on_mouse_wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_mouse_wheel_x(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")

    def _on_canvas_click(self, event):
        if not self.editing_entry:
            self.canvas.focus_set()
            
            # 座標の取得（スクロール位置を考慮）
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            
            # クリックしたノードを選択状態にする
            clicked_node = self.find_node_at(cx, cy)
            
            if clicked_node:
                self.selected_node = clicked_node
                self.render()
                # ドラッグ開始の準備
                self.on_drag_start(event)

    def find_node_at(self, x, y):
        """指定座標にあるノードを返す"""
        # 矩形の当たり判定 (クリック範囲を少し広げる)
        # find_overlapping は (x1, y1, x2, y2) で指定
        padding = 10
        items = self.canvas.find_overlapping(x-padding, y-padding, x+padding, y+padding)
        for item_id in items:
            tags = self.canvas.gettags(item_id)
            if "node" in tags or "text" in tags:
                # タグからnode_idを取得 (e.g., "node <uuid>")
                for tag in tags:
                    if tag not in ("node", "text", "current", "ghost"):
                        node_id = tag
                        return self.model.find_node_by_id(node_id)
        return None

    def on_drag_start(self, event):
        if not self.selected_node: return
        self.drag_data = {"item": self.selected_node, "x": event.x, "y": event.y, "dragging": False}

    def on_drag_motion(self, event):
        if not self.drag_data.get("item"): return
        
        # 一定以上動かしたらドラッグ開始とみなす
        if not self.drag_data["dragging"]:
            dx = abs(event.x - self.drag_data["x"])
            dy = abs(event.y - self.drag_data["y"])
            if dx > 5 or dy > 5:
                self.drag_data["dragging"] = True
                self.drag_data["ghost_id"] = self.canvas.create_rectangle(
                    0, 0, 0, 0, outline="#0078d7", width=2, dash=(4, 4), tags="ghost"
                )

        if self.drag_data["dragging"]:
            # ゴースト（枠線）の移動
            node = self.drag_data["item"]
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            w, h = node.width, node.height
            self.canvas.coords(self.drag_data["ghost_id"], cx - w/2, cy - h/2, cx + w/2, cy + h/2)

            # --- 自動スクロール処理（速度調整版） ---
            cv_w = self.canvas.winfo_width()
            cv_h = self.canvas.winfo_height()
            margin = 50
            
            # スクロール速度を抑えるため、5回に1回の頻度で処理
            self.drag_data["scroll_tick"] = self.drag_data.get("scroll_tick", 0) + 1
            if self.drag_data["scroll_tick"] % 5 == 0:
                if event.x < margin:
                    self.canvas.xview_scroll(-1, "units")
                elif event.x > cv_w - margin:
                    self.canvas.xview_scroll(1, "units")
                    
                if event.y < margin:
                    self.canvas.yview_scroll(-1, "units")
                elif event.y > cv_h - margin:
                    self.canvas.yview_scroll(1, "units")
            # ------------------------

    def on_drag_drop(self, event):
        if not self.drag_data.get("dragging"):
            # ドラッグしていなければクリック処理のみで終了
            self.drag_data = {}
            return

        self.canvas.delete("ghost")
        target_node = self.find_node_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        
        dropped_node = self.drag_data["item"]
        
        if target_node and target_node != dropped_node:
            # ドロップ可能かチェック (自分自身や子孫への移動は不可)
            if not self.is_descendant(target_node, dropped_node):
                 # ルートは移動不可
                if dropped_node != self.model.root:
                    dropped_node.move_to(target_node)
                    
                    # 方向の再計算と適用
                    if target_node == self.model.root:
                        # ルート直下に移動した場合、インデックスに基づいた方向を適用
                        dropped_node.direction = self.model.get_balanced_direction()
                    else:
                        # 親の方向を継承
                        dropped_node.direction = target_node.direction
                    
                    # 子孫ノードにも新しい方向を適用
                    self._update_direction_recursive(dropped_node, dropped_node.direction)
                    
                    self.render()

    def _update_direction_recursive(self, node: Node, direction):
        """ノードとその子孫の方向を再帰的に更新"""
        node.direction = direction
        for child in node.children:
            self._update_direction_recursive(child, direction)
        
        self.drag_data = {}

    def is_descendant(self, node, potential_ancestor):
        """nodeがpotential_ancestorの子孫かどうかをチェック"""
        curr = node
        while curr:
            if curr == potential_ancestor:
                return True
            curr = curr.parent
        return False

    def _wrap_handler(self, func):
        """編集中は入力を無視し、かつイベントが他へ伝播しないようにする"""
        def wrapper(event):
            if self.editing_entry:
                return "break"
            res = func(event)
            return "break" # 基本的にマインドマップの操作はここで完結させる
        return wrapper

        # レイアウト計算 (キャンバスの中央を基準にする)
        self.layout_engine.apply_layout(self.model, self.graphics, w / 2, h / 2)

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
        self.layout_engine.apply_layout(self.model, self.graphics, w / 2, h / 2)
        
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
        
        new_node = self.model.add_node(self.selected_node)
        self.selected_node = new_node
        self.render()
        self.on_edit_node(None)

    def on_add_sibling(self, event):
        if self.editing_entry: return
        if self.selected_node.parent:
            new_node = self.model.add_node(self.selected_node.parent)
            self.selected_node = new_node
            self.render()
            self.on_edit_node(None)

    def on_edit_node(self, event):
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
        self.root.after(100, set_focus)
        
        self.finishing = False # 再入防止フラグ
        
        def finish_edit(event=None):
            if self.finishing or not self.editing_entry:
                return "break"
            self.finishing = True
            
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
            
            # 親がルートの場合、接続点のY座標ランク（見た目の順）でソートする
            if curr.parent == self.model.root:
                def get_y_rank(node):
                    side_siblings = [c for c in curr.parent.children if c.direction == node.direction]
                    try:
                        side_idx = side_siblings.index(node)
                        point_type = side_idx % 3
                        y_rank = 0 if point_type == 0 else (1 if point_type == 2 else 2)
                        return (y_rank, side_idx // 3)
                    except ValueError:
                        return (0, 0)
                siblings.sort(key=get_y_rank)
            
            try:
                idx = siblings.index(curr)
                if direction == "up" and idx > 0:
                    self.selected_node = siblings[idx-1]
                elif direction == "down" and idx < len(siblings) - 1:
                    self.selected_node = siblings[idx+1]
            except ValueError:
                pass
                
        self.render()
