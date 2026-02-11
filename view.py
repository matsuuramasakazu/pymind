import tkinter as tk
from tkinter import filedialog, messagebox
import json
import re
from models import MindMapModel, Node
from graphics import GraphicsEngine
from layout import LayoutEngine

class NodeEditor:
    """ノードのテキスト編集（インライン編集）を管理するクラス"""
    def __init__(self, canvas: tk.Canvas, root: tk.Tk, graphics: GraphicsEngine, on_finish):
        self.canvas = canvas
        self.root = root
        self.graphics = graphics
        self.on_finish = on_finish # 完了時に呼び出すコールバック (renderなど)
        self.editing_entry = None
        self.window_id = None
        self.finishing = False

    def is_editing(self):
        return self.editing_entry is not None

    def start_edit(self, node: Node):
        if self.editing_entry:
            return
            
        # Entryウィジェットの作成
        entry = tk.Entry(self.canvas, justify="center", font=self.graphics.font, 
                         bg="white", fg="black", insertbackground="black",
                         relief="flat", highlightbackground="#0078d7", highlightthickness=2)
        entry.insert(0, node.text)
        entry.select_range(0, tk.END)
        
        self.window_id = self.canvas.create_window(
            node.x, node.y, window=entry, width=max(120, node.width + 20), anchor="center"
        )
        self.editing_entry = entry
        self.finishing = False
        
        def set_focus():
            if self.editing_entry == entry:
                entry.focus_set()
        self.root.after(100, set_focus)
        
        entry.bind("<Return>", lambda e: self.finish_edit(node))
        entry.bind("<Escape>", lambda e: self.cancel_edit())
        entry.bind("<FocusOut>", lambda e: self.finish_edit(node))
        entry.bind("<Tab>", lambda e: "break")

    def finish_edit(self, node: Node):
        if self.finishing or not self.editing_entry:
            return "break"
        self.finishing = True
        
        new_text = self.editing_entry.get()
        if new_text:
            node.text = new_text
            
        self._cleanup()
        self.on_finish()
        return "break"

    def cancel_edit(self):
        if self.finishing or not self.editing_entry:
            return "break"
        self.finishing = True
        
        self._cleanup()
        self.on_finish()
        return "break"

    def _cleanup(self):
        if self.editing_entry:
            self.editing_entry = None
        if self.window_id:
            self.canvas.delete(self.window_id)
            self.window_id = None
        self.canvas.focus_set()

class DragDropHandler:
    """ノードのドラッグ＆ドロップ移動を管理するクラス"""
    def __init__(self, canvas, model, graphics, layout_engine, render_callback, find_node_at):
        self.canvas = canvas
        self.model = model
        self.graphics = graphics
        self.layout_engine = layout_engine
        self.render_callback = render_callback
        self.find_node_at = find_node_at
        self.drag_data = {}

    def start_drag(self, event, node):
        if not node: return
        self.drag_data = {"item": node, "x": event.x, "y": event.y, "dragging": False}

    def handle_motion(self, event):
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
            node = self.drag_data["item"]
            cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            w, h = node.width, node.height
            self.canvas.coords(self.drag_data["ghost_id"], cx - w/2, cy - h/2, cx + w/2, cy + h/2)

            # 移動先の影表示
            target_node = self.find_node_at(cx, cy)
            if target_node and target_node != node and not target_node.is_descendant_of(node) and target_node != node.parent:
                self.show_move_shadow(node, target_node)
            else:
                self.hide_move_shadow()

            self._handle_auto_scroll(event)

    def handle_drop(self, event):
        if not self.drag_data.get("dragging"):
            self.drag_data = {}
            return

        self.canvas.delete("ghost")
        self.hide_move_shadow()
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        target_node = self.find_node_at(cx, cy)
        dropped_node = self.drag_data["item"]
        
        if target_node and target_node != dropped_node and target_node != dropped_node.parent:
            if not target_node.is_descendant_of(dropped_node) and dropped_node != self.model.root:
                dropped_node.move_to(target_node)
                if target_node == self.model.root:
                    dropped_node.direction = self.model.get_balanced_direction(exclude_node=dropped_node)
                else:
                    dropped_node.direction = target_node.direction
                dropped_node.update_direction_recursive(dropped_node.direction)
                self.render_callback()
        
        self.drag_data = {}

    def _handle_auto_scroll(self, event):
        cv_w, cv_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        margin = 50
        self.drag_data["scroll_tick"] = self.drag_data.get("scroll_tick", 0) + 1
        if self.drag_data["scroll_tick"] % 5 == 0:
            if event.x < margin: self.canvas.xview_scroll(-1, "units")
            elif event.x > cv_w - margin: self.canvas.xview_scroll(1, "units")
            if event.y < margin: self.canvas.yview_scroll(-1, "units")
            elif event.y > cv_h - margin: self.canvas.yview_scroll(1, "units")

    def show_move_shadow(self, dragged_node: Node, target_node: Node):
        if self.drag_data.get("shadow_target_id") == target_node.id: return
        self.hide_move_shadow()
        
        base_x, base_y = target_node.x, target_node.y
        old_parent = dragged_node.parent
        old_index = old_parent.children.index(dragged_node) if old_parent else -1
        old_direction = dragged_node.direction
        
        w, h = max(1000, self.canvas.winfo_width()), max(800, self.canvas.winfo_height())
        
        try:
            if old_parent: old_parent.children.remove(dragged_node)
            dragged_node.parent = target_node
            target_node.children.append(dragged_node)
            
            if target_node == self.model.root:
                dragged_node.direction = self.model.get_balanced_direction(exclude_node=dragged_node)
            else:
                dragged_node.direction = target_node.direction
            dragged_node.update_direction_recursive(dragged_node.direction)
            
            self.layout_engine.calculate_subtree_height(self.model.root, self.graphics)
            self.layout_engine.apply_layout(self.model, self.graphics, 5000, 5000)
            
            sx, sy = base_x + (dragged_node.x - target_node.x), base_y + (dragged_node.y - target_node.y)
            sw, sh = dragged_node.width, dragged_node.height
            shadow_id = self.canvas.create_rectangle(
                sx - sw/2, sy - sh/2, sx + sw/2, sy + sh/2,
                fill="#e0e0e0", outline="#cccccc", tags="move_shadow"
            )
            self.canvas.lower(shadow_id)
            
            # 接続線の影
            tmp_x, tmp_y = dragged_node.x, dragged_node.y
            dragged_node.x, dragged_node.y = sx, sy
            target_tmp_x, target_tmp_y = target_node.x, target_node.y
            target_node.x, target_node.y = base_x, base_y
            
            self.graphics.draw_move_shadow_connection(target_node, dragged_node)
            
            dragged_node.x, dragged_node.y = tmp_x, tmp_y
            target_node.x, target_node.y = target_tmp_x, target_tmp_y
            self.drag_data["shadow_target_id"] = target_node.id
        finally:
            if dragged_node in target_node.children: target_node.children.remove(dragged_node)
            dragged_node.parent = old_parent
            if old_parent and dragged_node not in old_parent.children:
                old_parent.children.insert(old_index, dragged_node)
            dragged_node.direction = old_direction
            dragged_node.update_direction_recursive(old_direction)
            self.layout_engine.calculate_subtree_height(self.model.root, self.graphics)
            self.layout_engine.apply_layout(self.model, self.graphics, 5000, 5000)

    def hide_move_shadow(self):
        self.canvas.delete("move_shadow")
        self.drag_data["shadow_target_id"] = None

class KeyboardNavigator:
    """キーボードによるノード間移動を管理するクラス"""
    def __init__(self, model, render_callback):
        self.model = model
        self.render_callback = render_callback

    def navigate(self, current_node, direction):
        """左右対称レイアウトに対応したナビゲーション"""
        curr = current_node
        new_node = curr
        
        if direction == "right":
            if curr == self.model.root:
                right_children = [c for c in curr.children if c.direction != 'left']
                if right_children: new_node = right_children[0]
            elif curr.direction != 'left':
                if curr.children: new_node = curr.children[0]
            else:
                if curr.parent: new_node = curr.parent
        elif direction == "left":
            if curr == self.model.root:
                left_children = [c for c in curr.children if c.direction == 'left']
                if left_children: new_node = left_children[0]
            elif curr.direction == 'left':
                if curr.children: new_node = curr.children[0]
            else:
                if curr.parent: new_node = curr.parent
        elif direction in ("up", "down") and curr.parent:
            siblings = [c for c in curr.parent.children if c.direction == curr.direction]
            if not siblings: siblings = curr.parent.children
            
            if curr.parent == self.model.root:
                def get_y_rank(node):
                    side_siblings = [c for c in curr.parent.children if c.direction == node.direction]
                    try:
                        side_idx = side_siblings.index(node)
                        point_type = side_idx % 3
                        y_rank = 0 if point_type == 0 else (1 if point_type == 2 else 2)
                        return (y_rank, side_idx // 3)
                    except ValueError: return (0, 0)
                siblings.sort(key=get_y_rank)
            
            try:
                idx = siblings.index(curr)
                if direction == "up" and idx > 0: new_node = siblings[idx-1]
                elif direction == "down" and idx < len(siblings) - 1: new_node = siblings[idx+1]
            except ValueError: pass
                
        return new_node

class PersistenceHandler:
    """ファイルの保存・読み込みを管理するクラス"""
    def __init__(self, model, render_callback):
        self.model = model
        self.render_callback = render_callback
        self.current_file_path = None

    def on_save(self, event=None):
        if self.current_file_path:
            self._write_to_file(self.current_file_path, "保存が完了しました。")
        else:
            self.on_save_as(event)

    def on_save_as(self, event=None):
        default_name = self.model.root.text
        default_name = re.sub(r'[\\/:*?"<>|]', '', default_name)
        if len(default_name) > 20:
            default_name = default_name[:20]
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            self._write_to_file(file_path, "別名で保存が完了しました。")

    def _write_to_file(self, file_path, success_msg):
        """共通のファイル書き込み処理"""
        try:
            data = self.model.save()
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.current_file_path = file_path
            messagebox.showinfo("保存", f"{success_msg}\n{file_path}")
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
                self.current_file_path = file_path
                self.render_callback(root_node=self.model.root)
                messagebox.showinfo("読み込み", "読み込みが完了しました。")
            except Exception as e:
                messagebox.showerror("エラー", f"読み込みに失敗しました: {e}")

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
        self.editor = NodeEditor(self.canvas, self.root, self.graphics, self.render)
        self.drag_handler = DragDropHandler(
            self.canvas, self.model, self.graphics, self.layout_engine, self.render, self.find_node_at
        )
        self.navigator = KeyboardNavigator(self.model, self.render)
        self.persistence = PersistenceHandler(self.model, self._on_load_complete)
        
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
        bind_key("<Control-s>", self.persistence.on_save)
        bind_key("<Control-S>", self.persistence.on_save_as) # Ctrl+Shift+S
        bind_key("<Control-o>", self.persistence.on_open)
        bind_key("<Up>", lambda e: self._navigate("up"))
        bind_key("<Down>", lambda e: self._navigate("down"))
        bind_key("<Left>", lambda e: self._navigate("left"))
        bind_key("<Right>", lambda e: self._navigate("right"))
        
        # マウスホイール
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_mouse_wheel_x)
        
        self.first_render = True
        self.render()

        # マウスイベントのバインド
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", lambda e: self.drag_handler.handle_motion(e))
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.drag_handler.handle_drop(e))

    def on_mouse_wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_mouse_wheel_x(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")

    def _on_canvas_click(self, event):
        if not self.editor.is_editing():
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
                self.drag_handler.start_drag(event, self.selected_node)

    def find_node_at(self, x, y):
        """指定座標にあるノードを返す"""
        # 矩形の当たり判定 (クリック範囲を少し広げる)
        # find_overlapping は (x1, y1, x2, y2) で指定
        padding = 10
        items = self.canvas.find_overlapping(x-padding, y-padding, x+padding, y+padding)
        # 描画順（スタッキング順）の逆順でチェックすることで、前面にある（新しい）ノードを優先する
        for item_id in reversed(items):
            tags = self.canvas.gettags(item_id)
            if "node" in tags or "text" in tags:
                # タグからnode_idを取得 (e.g., "node <uuid>")
                for tag in tags:
                    if tag not in ("node", "text", "current", "ghost"):
                        node_id = tag
                        return self.model.find_node_by_id(node_id)
        return None

    def _navigate(self, direction):
        self.selected_node = self.navigator.navigate(self.selected_node, direction)
        self.render(force_center=True)

    def _on_load_complete(self, root_node):
        self.selected_node = root_node
        self.render()

    def _wrap_handler(self, func):
        """編集中は入力を無視し、かつイベントが他へ伝播しないようにする"""
        def wrapper(event):
            if self.editor.is_editing():
                return "break"
            res = func(event)
            return "break" # 基本的にマインドマップの操作はここで完結させる
        return wrapper

    def render(self, force_center=False):
        self.graphics.clear()
        w, h = self._get_canvas_size()
        
        # レイアウト計算: ウィンドウサイズに依存しない固定の基準点を使用
        logical_center_x, logical_center_y = 5000, 5000
        self.layout_engine.apply_layout(self.model, self.graphics, logical_center_x, logical_center_y)
        
        # 全ノード描画
        self._draw_subtree(self.model.root)
        
        # スクロールと自動センタリング
        self._update_scroll_and_focus(w, h, force_center)

    def _get_canvas_size(self):
        self.root.update_idletasks()
        w = max(100, self.canvas.winfo_width())
        h = max(100, self.canvas.winfo_height())
        return w, h

    def _update_scroll_and_focus(self, w, h, force_center=False):
        bbox = self.canvas.bbox("all")
        if not bbox: return
        
        # コンテンツ周囲に余白
        margin = 500
        new_sr = (bbox[0] - margin, bbox[1] - margin, bbox[2] + margin, bbox[3] + margin)
        self.canvas.config(scrollregion=new_sr)
        
        if self.first_render:
            self.canvas.update_idletasks() # 表示状態を確定
            bbox = self.canvas.bbox("all") # 再計算後のbboxを取得
            if bbox:
                new_sr = (bbox[0] - margin, bbox[1] - margin, bbox[2] + margin, bbox[3] + margin)
                self.canvas.config(scrollregion=new_sr)
            self._center_on_root(new_sr, w, h)
            self.first_render = False
        
        self.ensure_node_visible(self.selected_node, force_center=force_center)

    def _center_on_root(self, sr, w, h):
        sr_w, sr_h = sr[2] - sr[0], sr[3] - sr[1]
        fraction_x = (self.model.root.x - sr[0] - w/2) / sr_w
        fraction_y = (self.model.root.y - sr[1] - h/2) / sr_h
        self.canvas.xview_moveto(max(0, fraction_x))
        self.canvas.yview_moveto(max(0, fraction_y))

    def ensure_node_visible(self, node: Node, force_center=False):
        """指定したノードが画面外にある場合、見える位置までスクロールする"""
        if not node or not self.canvas.cget("scrollregion"): return
        
        # scrollregionの変更を反映させる
        self.canvas.update_idletasks()
        
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
        
        # すでに十分見えている場合は何もしない（ジャンプ防止）
        if not force_center:
            if vx1 + margin <= node_rel_x <= vx2 - margin and \
               vy1 + margin <= node_rel_y <= vy2 - margin:
                return

        # 画面外（または端に近い）なら移動
        if force_center or node_rel_x < vx1 + margin or node_rel_x > vx2 - margin:
            self.canvas.xview_moveto(max(0, node_rel_x - view_w_ratio / 2))
            
        if force_center or node_rel_y < vy1 + margin or node_rel_y > vy2 - margin:
            self.canvas.yview_moveto(max(0, node_rel_y - view_h_ratio / 2))

    def _draw_subtree(self, node: Node):
        self.graphics.draw_node(node, is_selected=(node == self.selected_node))
        for child in node.children:
            self._draw_subtree(child)

    def on_add_child(self, event):
        if self.editor.is_editing(): return
        
        new_node = self.model.add_node(self.selected_node)
        self.selected_node = new_node
        self.render()
        self.on_edit_node(None)

    def on_add_sibling(self, event):
        if self.editor.is_editing(): return
        if self.selected_node.parent:
            new_node = self.model.add_node(self.selected_node.parent)
            self.selected_node = new_node
            self.render()
            self.on_edit_node(None)

    def on_edit_node(self, event):
        self.editor.start_edit(self.selected_node)
        return "break"

    def on_delete_node(self, event):
        if self.editor.is_editing(): return
        if self.selected_node.parent:
            parent = self.selected_node.parent
            parent.remove_child(self.selected_node)
            self.selected_node = parent
            self.render()

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="開く (Ctrl+O)", command=self.persistence.on_open)
        filemenu.add_command(label="保存 (Ctrl+S)", command=self.persistence.on_save)
        filemenu.add_command(label="名前を付けて保存 (Ctrl+Shift+S)", command=self.persistence.on_save_as)
        filemenu.add_separator()
        filemenu.add_command(label="終了", command=self.root.quit)
        menubar.add_cascade(label="ファイル", menu=filemenu)
        self.root.config(menu=menubar)
