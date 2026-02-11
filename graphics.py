import tkinter as tk
from typing import Dict, Optional
from models import Node

class GraphicsEngine:
    """tkinter.Canvas上での描画を管理するクラス"""
    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.node_items: Dict[str, list] = {}  # node_id -> list of item ids
        self.text_items: Dict[str, int] = {} 
        self.line_items: Dict[str, list] = {} 
        
        # デザイン設定
        self.text_color = "#333333"
        self.root_outline = "#222222"
        self.font = ("Yu Gothic", 10)
        self.root_font = ("Yu Gothic", 12, "bold")
        
        self.branch_colors = [
            "#FF9D48", # Orange
            "#FF6B6B", # Red
            "#A06EE1", # Purple
            "#4ECDC4", # Teal
            "#5CACE2", # Blue
            "#96CEB4", # Green
        ]

    def _get_node_color(self, node: Node):
        """ノードの系統色を取得（ルートの子ノードに基づき決定）"""
        if node.parent is None:
            return self.root_outline
        
        # ルートの何番目の子孫か
        curr = node
        while curr.parent and curr.parent.parent:
            curr = curr.parent
        
        if curr.parent is None: return self.root_outline
        
        try:
            idx = curr.parent.children.index(curr)
            return self.branch_colors[idx % len(self.branch_colors)]
        except ValueError:
            return self.branch_colors[0]

    def _create_rounded_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        points = [x1+radius, y1, x1+radius, y1, x2-radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y1+radius, x2, y2-radius, x2, y2-radius, x2, y2, x2-radius, y2, x2-radius, y2, x1+radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, x1, y2-radius, x1, y1+radius, x1, y1+radius, x1, y1]
        return self.canvas.create_polygon(points, **kwargs, smooth=True)

    def get_text_size(self, text: str, font, max_width: int = 250):
        temp_id = self.canvas.create_text(0, 0, text=text, font=font, width=max_width)
        bbox = self.canvas.bbox(temp_id)
        self.canvas.delete(temp_id)
        if bbox:
            w = bbox[2] - bbox[0] + 10
            # 下線との重なりを防ぐために高さのパディングを増やす (12px)
            h = bbox[3] - bbox[1] + 12
            return w, h
        return 100, 35

    def draw_node(self, node: Node, is_selected: bool = False):
        x, y = node.x, node.y
        is_root = node.parent is None
        font = self.root_font if is_root else self.font
        
        node.width, node.height = self.get_text_size(node.text, font)
        w, h = node.width, node.height
        
        if node.id in self.node_items:
            for item in self.node_items[node.id]: self.canvas.delete(item)
        if node.id in self.text_items:
            self.canvas.delete(self.text_items[node.id])
        
        items = []
        color = self._get_node_color(node)
        
        # 選択状態の強調表示（背面に配置）
        if is_selected:
            # 淡いブルーのハイライトボックス
            p_h = 4
            highlight_id = self._create_rounded_rect(
                x - w/2 - 10, y - h/2 - p_h, x + w/2 + 10, y + h/2 + p_h,
                radius=6, fill="#E3F2FD", outline="#2196F3", width=1, tags=("node", node.id)
            )
            items.append(highlight_id)

        if is_root:
            # ルートノード：太い枠線の角丸長方形
            outline_w = 4 if is_selected else 3
            # 選択時は背景をハイライト色に変更
            fill_color = "#E3F2FD" if is_selected else "white"
            rect_id = self._create_rounded_rect(
                x - w/2 - 12, y - h/2 - 10, x + w/2 + 12, y + h/2 + 10,
                radius=10, fill=fill_color, outline=color, width=outline_w, tags=("node", node.id)
            )
            items.append(rect_id)
        else:
            # サブトピック：下線のみ
            line_y = y + h/2
            lx1, lx2 = x - w/2 - 5, x + w/2 + 5
            # 選択時は下線を少し太く
            u_width = 3 if is_selected else 2
            underline_id = self.canvas.create_line(
                lx1, line_y, lx2, line_y, fill=color, width=u_width, tags=("node", node.id)
            )
            items.append(underline_id)

        self.node_items[node.id] = items
        
        # テキスト
        text_id = self.canvas.create_text(
            x, y, text=node.text, fill=self.text_color, font=font,
            width=200, justify="center", tags=("text", node.id)
        )
        self.text_items[node.id] = text_id
        
        if node.parent:
            self.draw_connection(node)

    def draw_connection(self, node: Node):
        if not node.parent: return
        if node.id in self.line_items:
            for item in self.line_items[node.id]: self.canvas.delete(item)
        
        p = node.parent
        color = self._get_node_color(node)
        dir = getattr(node, 'direction', 'right')
        
        # ポイント計算
        if p.parent is None:
            # 自分の方向（左右）の兄弟内でのインデックスを取得して接続点を決定
            # これにより、削除などで全体のインデックスがずれても交差しない
            side_siblings = [c for c in p.children if c.direction == node.direction]
            try:
                side_idx = side_siblings.index(node) % 3
            except ValueError:
                side_idx = 0
            
            w_h = p.width / 2 + 12
            h_h = p.height / 2 + 10
            
            if node.direction != 'left':
                # 右側のポイント: 0:右上, 1:右下, 2:右中央
                if side_idx == 0:
                    px, py = p.x + w_h, p.y - h_h
                elif side_idx == 1:
                    px, py = p.x + w_h, p.y + h_h
                else:
                    px, py = p.x + w_h, p.y
            else:
                # 左側のポイント: 0:左上, 1:左下, 2:左中央
                if side_idx == 0:
                    px, py = p.x - w_h, p.y - h_h
                elif side_idx == 1:
                    px, py = p.x - w_h, p.y + h_h
                else:
                    px, py = p.x - w_h, p.y
                
            nx = node.x - node.width/2 if node.x > p.x else node.x + node.width/2
            ny = node.y + node.height/2
            
            items = self._draw_tapered_bezier(px, py, nx, ny, color, 8, 2)
            self.line_items[node.id] = items
        else:
            # 子→孫：親の下線の端から急激な曲線
            parent_dir = 'right' if node.x > p.x else 'left'
            px = p.x + p.width/2 if parent_dir == 'right' else p.x - p.width/2
            py = p.y + p.height/2
            nx = node.x - node.width/2 if parent_dir == 'right' else node.x + node.width/2
            ny = node.y + node.height/2
            
            # S字カーブ（急激な立ち上がり/立ち下がり）
            # 制御点を水平方向に短くすることで垂直移動を急にする
            dx = nx - px
            cp1x = px + dx * 0.4
            cp1y = py
            cp2x = px + dx * 0.6
            cp2y = ny
            
            items = self._draw_bezier(px, py, cp1x, cp1y, cp2x, cp2y, nx, ny, color, 2)
            self.line_items[node.id] = items

    def draw_move_shadow_connection(self, parent_node: Node, shadow_node: Node):
        """移動先の影用の接続線を描画する"""
        p = parent_node
        node = shadow_node
        color = "#cccccc" # 影用カラー
        
        # 基本的な接続ロジックを draw_connection から流用
        if p.parent is None:
            side_siblings = [c for c in p.children if c.direction == node.direction]
            # shadow_node がまだ children に入っていない場合を考慮（仮移動中なら入っているはず）
            try:
                side_idx = side_siblings.index(node) % 3
            except ValueError:
                side_idx = 0
            
            w_h = p.width / 2 + 12
            h_h = p.height / 2 + 10
            
            if node.direction != 'left':
                if side_idx == 0: px, py = p.x + w_h, p.y - h_h
                elif side_idx == 1: px, py = p.x + w_h, p.y + h_h
                else: px, py = p.x + w_h, p.y
            else:
                if side_idx == 0: px, py = p.x - w_h, p.y - h_h
                elif side_idx == 1: px, py = p.x - w_h, p.y + h_h
                else: px, py = p.x - w_h, p.y
                
            nx = node.x - node.width/2 if node.x > p.x else node.x + node.width/2
            ny = node.y + node.height/2
            
            # 影用のタグ "move_shadow" を指定して描画
            steps = 30
            dx = nx - px
            cp1x = px + dx * 0.4
            cp2x = px + dx * 0.6
            if ny < py: cp1y = cp2y = ny
            elif ny > py: cp1y = cp2y = ny
            else: cp1y, cp2y = py, ny
            
            def bz(t, p0, p1, p2, p3):
                return (1-t)**3 * p0 + 3*(1-t)**2 * t * p1 + 3*(1-t) * t**2 * p2 + t**3 * p3

            for i in range(steps):
                t0 = i / steps
                t1 = (i + 1) / steps
                xa, ya = bz(t0, px, cp1x, cp2x, nx), bz(t0, py, cp1y, cp2y, ny)
                xb, yb = bz(t1, px, cp1x, cp2x, nx), bz(t1, py, cp1y, cp2y, ny)
                w = 8 + (2 - 8) * t0
                self.canvas.create_line(xa, ya, xb, yb, fill=color, width=w, capstyle="round", tags="move_shadow")
        else:
            parent_dir = 'right' if node.x > p.x else 'left'
            px = p.x + p.width/2 if parent_dir == 'right' else p.x - p.width/2
            py = p.y + p.height/2
            nx = node.x - node.width/2 if parent_dir == 'right' else node.x + node.width/2
            ny = node.y + node.height/2
            
            dx = nx - px
            cp1x = px + dx * 0.4
            cp1y = py
            cp2x = px + dx * 0.6
            cp2y = ny
            
            steps = 15
            def bz(t, p0, p1, p2, p3):
                return (1-t)**3 * p0 + 3*(1-t)**2 * t * p1 + 3*(1-t) * t**2 * p2 + t**3 * p3
            for i in range(steps):
                t0 = i / steps
                t1 = (i + 1) / steps
                xa, ya = bz(t0, px, cp1x, cp2x, nx), bz(t0, py, cp1y, cp2y, ny)
                xb, yb = bz(t1, px, cp1x, cp2x, nx), bz(t1, py, cp1y, cp2y, ny)
                self.canvas.create_line(xa, ya, xb, yb, fill=color, width=2, capstyle="round", tags="move_shadow")

    def _draw_bezier(self, x1, y1, cp1x, cp1y, cp2x, cp2y, x2, y2, color, width):
        items = []
        steps = 15
        def bz(t, p0, p1, p2, p3):
            return (1-t)**3 * p0 + 3*(1-t)**2 * t * p1 + 3*(1-t) * t**2 * p2 + t**3 * p3
        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps
            xa, ya = bz(t0, x1, cp1x, cp2x, x2), bz(t0, y1, cp1y, cp2y, y2)
            xb, yb = bz(t1, x1, cp1x, cp2x, x2), bz(t1, y1, cp1y, cp2y, y2)
            line_id = self.canvas.create_line(xa, ya, xb, yb, fill=color, width=width, capstyle="round")
            items.append(line_id)
        return items

    def _draw_tapered_bezier(self, x1, y1, x2, y2, color, start_w, end_w):
        items = []
        steps = 30
        
        # XMind風の凸型曲線の計算
        dx = x2 - x1
        cp1x = x1 + dx * 0.4
        cp2x = x1 + dx * 0.6
        
        # 上に凸/下に凸の調整
        if y2 < y1: # 上方向に伸びる
            cp1y = y2 # 最初から上に引っ張ることで「上に凸」
            cp2y = y2
        elif y2 > y1: # 下方向に伸びる
            cp1y = y2 # 最初から下に引っ張ることで「下に凸」
            cp2y = y2
        else: # 水平
            cp1y = y1
            cp2y = y2
            
        def bz(t, p0, p1, p2, p3):
            return (1-t)**3 * p0 + 3*(1-t)**2 * t * p1 + 3*(1-t) * t**2 * p2 + t**3 * p3

        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps
            xa, ya = bz(t0, x1, cp1x, cp2x, x2), bz(t0, y1, cp1y, cp2y, y2)
            xb, yb = bz(t1, x1, cp1x, cp2x, x2), bz(t1, y1, cp1y, cp2y, y2)
            w = start_w + (end_w - start_w) * t0
            line_id = self.canvas.create_line(xa, ya, xb, yb, fill=color, width=w, capstyle="round")
            items.append(line_id)
        return items

    def clear(self):
        self.canvas.delete("all")
        self.node_items.clear()
        self.text_items.clear()
        self.line_items.clear()
